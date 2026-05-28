"""_phase6_sp — SP B2 2-step single-LLM orchestrator (v4 framework, B2 thin).

Entry point: process_sp_v4(...). Called from fa_scan._process_group_sp_v4.

Pipeline:
  Layer 1.5: filter pure-RP from FA pool (game-log GS=1 IP/GS gate)
  Layer 4:   v4 mechanical (pick_weakest_v4_sp with anchor_filter +
             compute_fa_tags_v4_sp) — no urgency, no slump hold, no Sum exposure
  Layer 5:   2-step single-LLM
    - Step A:  rank top-3 eligible + classify FAs (1 LLM call → JSON)
    - Step B:  reads Step A JSON + full pools → final verdict (1 LLM call → JSON)

Step A JSON validation + retry + Telegram alert + fall-through to `pass`. Pipeline
never crashes cron silently.

Refs:
- docs/sp-b2-cutover-design.md (B2 design source of truth)
- docs/sp-framework-v4-balanced.md (v4 5-slot mechanics)
- issues/prd-sp-b2-thin.md (PRD)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import fa_compute
import payload_slimmer
from _multi_agent import run_single_agent

_MODULE_DIR = Path(__file__).resolve().parent

_PROMPTS = {
    "step_a": "prompt_sp_b2_step_a.txt",
    "step_b": "prompt_sp_b2_step_b.txt",
}

_LLM_TIMEOUT = 600

_STEP_A_REQUIRED_KEYS = {"my_team_rank", "fa_classify"}
_STEP_A_FA_VERDICTS = {"worth", "borderline", "not_worth"}
_STEP_B_REQUIRED_KEYS = {"action", "reason"}
_STEP_B_ACTIONS = {"drop_X_add_Y", "watch", "pass"}


def _load_prompt(name: str) -> str:
    return (_MODULE_DIR / _PROMPTS[name]).read_text(encoding="utf-8")


def _dump_fixture(args, today_str: str, suffix: str, payload_str: str) -> None:
    """Capture LLM payload as spike fixture (issue 008 baseline collection)."""
    capture_dir = getattr(args, "capture_payload", None)
    if not isinstance(capture_dir, str) or not capture_dir:
        return
    try:
        out_dir = Path(capture_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{today_str}_{suffix}.json"
        out_path.write_text(payload_str, encoding="utf-8")
        print(f"  capture: wrote {out_path}", file=sys.stderr)
    except Exception as e:
        print(f"  capture: failed to dump {suffix}: {e}", file=sys.stderr)


# ── v4 data attachment ──

def _attach_v4_to_my_roster(my_roster: list[dict]) -> None:
    """Add `savant_v4` dict to each my-team SP entry (mutates in-place)."""
    from sp_data_fetchers import assemble_data

    pids = {p["mlb_id"] for p in my_roster if p.get("mlb_id")}
    if not pids:
        return
    print(f"  Layer 4 (SP-v4): fetching v4 data for {len(pids)} my-team SP...",
          file=sys.stderr)
    v4 = assemble_data(pids, 2026)
    for p in my_roster:
        pid = p.get("mlb_id")
        if pid in v4:
            p["savant_v4"] = v4[pid]


def _attach_v4_to_fa(fa_entries: list[dict]) -> None:
    """Same as _attach_v4_to_my_roster but for FA candidates."""
    from sp_data_fetchers import assemble_data

    pids = {p["mlb_id"] for p in fa_entries if p.get("mlb_id")}
    if not pids:
        return
    print(f"  Layer 4 (SP-v4): fetching v4 data for {len(pids)} FA SP...",
          file=sys.stderr)
    v4 = assemble_data(pids, 2026)
    for p in fa_entries:
        pid = p.get("mlb_id")
        if pid in v4:
            p["savant_v4"] = v4[pid]
            score, breakdown = fa_compute.compute_sum_score_v4_sp(v4[pid])
            p["score"] = score
            p["breakdown"] = breakdown


# ── Payload builders ──

def _slim_my_team_entry(entry: dict) -> dict:
    return payload_slimmer.slim_entry(entry, "my_team")


def _slim_fa_entry(entry: dict) -> dict:
    return payload_slimmer.slim_entry(entry, "fa")


def _build_step_a_payload(weakest: list[dict], fa_pool: list[dict],
                          low_conf: list[dict]) -> str:
    """JSON for Step A.

    Reads ONLY the anchor-filtered ``weakest`` (output of pick_weakest_v4_sp).
    NEVER reads raw ``my_roster`` — that still contains anchor data and would
    leak anchors into LLM context.
    """
    payload = {
        "candidates": [_slim_my_team_entry(e) for e in weakest],
        "fa_candidates": [_slim_fa_entry(f) for f in fa_pool],
        "low_confidence_excluded": low_conf,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _build_step_b_payload(step_a_result: dict, weakest: list[dict],
                          fa_pool: list[dict], non_data_context: dict) -> str:
    """JSON for Step B.

    Step B sees Step A's output PLUS the same full slimmed pools Step A saw —
    not just JSON summary, so Step B can reason over original metrics.
    """
    payload = {
        "step_a": step_a_result,
        "candidates": [_slim_my_team_entry(e) for e in weakest],
        "fa_candidates": [_slim_fa_entry(f) for f in fa_pool],
        "non_data_context": non_data_context,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


# ── Step A validation ──

def _validate_step_a(parsed: dict, expected_eligible: list[str],
                     expected_fa: list[str]) -> str | None:
    """Return None if valid, else a short error string for logging."""
    if not isinstance(parsed, dict):
        return "Step A output is not a JSON object"
    missing = _STEP_A_REQUIRED_KEYS - set(parsed)
    if missing:
        return f"Step A missing required keys: {sorted(missing)}"
    mtr = parsed.get("my_team_rank")
    if not isinstance(mtr, list):
        return "Step A.my_team_rank is not a list"
    fac = parsed.get("fa_classify")
    if not isinstance(fac, list):
        return "Step A.fa_classify is not a list"
    for i, entry in enumerate(mtr):
        if not isinstance(entry, dict) or "name" not in entry:
            return f"Step A.my_team_rank[{i}] missing name"
    for i, entry in enumerate(fac):
        if not isinstance(entry, dict) or "name" not in entry:
            return f"Step A.fa_classify[{i}] missing name"
        if entry.get("verdict") not in _STEP_A_FA_VERDICTS:
            return f"Step A.fa_classify[{i}] verdict invalid: {entry.get('verdict')!r}"
    # Cross-check names against expected pool — Step A must not invent ghost names
    mtr_names = {e["name"] for e in mtr}
    fac_names = {e["name"] for e in fac}
    expected_eligible_set = set(expected_eligible)
    expected_fa_set = set(expected_fa)
    if not mtr_names.issubset(expected_eligible_set):
        ghosts = mtr_names - expected_eligible_set
        return f"Step A.my_team_rank contains unknown names: {sorted(ghosts)}"
    if not fac_names.issubset(expected_fa_set):
        ghosts = fac_names - expected_fa_set
        return f"Step A.fa_classify contains unknown names: {sorted(ghosts)}"
    return None


def _validate_step_b(parsed: dict, eligible_names: list[str],
                     fa_names: list[str]) -> str | None:
    if not isinstance(parsed, dict):
        return "Step B output is not a JSON object"
    missing = _STEP_B_REQUIRED_KEYS - set(parsed)
    if missing:
        return f"Step B missing required keys: {sorted(missing)}"
    action = parsed.get("action")
    if action not in _STEP_B_ACTIONS:
        return f"Step B action invalid: {action!r}"
    drop = parsed.get("drop")
    add = parsed.get("add")
    watch_target = parsed.get("watch_target")
    if action == "drop_X_add_Y":
        if not drop or drop not in eligible_names:
            return f"Step B drop name invalid for drop_X_add_Y: {drop!r}"
        if not add or add not in fa_names:
            return f"Step B add name invalid for drop_X_add_Y: {add!r}"
        if watch_target is not None:
            return "Step B drop_X_add_Y must have null watch_target"
    elif action == "watch":
        if drop is not None or add is not None:
            return "Step B watch must have null drop/add"
        if not watch_target or watch_target not in fa_names:
            return f"Step B watch_target invalid: {watch_target!r}"
    elif action == "pass":
        if drop is not None or add is not None or watch_target is not None:
            return "Step B pass must have null drop/add/watch_target"
    return None


# ── Main orchestrator ──

def process_sp_v4(config, savant_2026, enriched, watch_enriched,
                  changes, ref_1d, ref_3d, today_str, env, args,
                  rostered_names=None,
                  fa_scan_helpers=None):
    """SP B2 2-step single-LLM pipeline. Drop-in for B1 phase6 entrypoint.

    fa_scan_helpers: dict of helper callables from fa_scan.py. Required keys:
    notify, handle_error, publish, update_waiver_log, prep_my_roster,
    normalize_fa_for_compute, fetch_team_games, load_savant_rolling,
    fetch_fa_rolling, ip_per_gs_from_gamelog.
    """
    h = fa_scan_helpers or {}
    label = "SP-v4"

    try:
        fa_candidates = [p for p in enriched if p["fa_type"] == "sp"]
        watch_candidates = [p for p in watch_enriched if p["fa_type"] == "sp"]

        # Layer 1.5: pure-RP filter
        ip_per_gs_helper = h.get("ip_per_gs_from_gamelog")
        if ip_per_gs_helper:
            def _is_real_sp(p):
                mlb = p.get("mlb_2026") or {}
                gs = int(mlb.get("gamesStarted", 0) or 0)
                if gs == 0:
                    return False
                pid = p.get("mlb_id")
                if not pid:
                    return False
                ip_per_gs = ip_per_gs_helper(pid, 2026)
                if ip_per_gs is None:
                    return False
                return ip_per_gs >= 3.0
            before = len(fa_candidates) + len(watch_candidates)
            fa_candidates = [p for p in fa_candidates if _is_real_sp(p)]
            watch_candidates = [p for p in watch_candidates if _is_real_sp(p)]
            removed = before - len(fa_candidates) - len(watch_candidates)
            if removed:
                print(f"  Layer 1.5 ({label}): {removed} pure RP removed", file=sys.stderr)

        # ── Layer 4: B2 thin mechanical ──
        print(f"  Layer 4 ({label}): pick_weakest (anchor_filter + sum asc top-3)...",
              file=sys.stderr)
        standings = h["fetch_team_games"]()
        rolling = h["load_savant_rolling"](player_type="sp")
        my_roster = h["prep_my_roster"]("sp", config, savant_2026, standings, rolling)
        _attach_v4_to_my_roster(my_roster)

        league_cfg = config.get("league", {})
        cant_cut = league_cfg.get("cant_cut", [])
        weekly_anchor = league_cfg.get("weekly_anchor_sp", [])
        weakest, low_conf = fa_compute.pick_weakest_v4_sp(
            my_roster, n=3, cant_cut=cant_cut, weekly_anchor=weekly_anchor,
        )

        if not weakest:
            h["notify"](env, args,
                        f"[FA Scan {label}] 無有效 anchor (eligible pool empty after filter)")
            return

        if not fa_candidates and not watch_candidates:
            h["notify"](env, args, f"[FA Scan {label}] 無 FA 候選通過品質門檻")
            return

        fa_rolling = h["fetch_fa_rolling"](
            fa_candidates, watch_candidates, today_str, player_type="pitcher",
        )
        fa_entries = []
        for p in fa_candidates + watch_candidates:
            entry = h["normalize_fa_for_compute"](p, "sp", fa_rolling)
            fa_entries.append(entry)
        _attach_v4_to_fa(fa_entries)

        # FA tags computed for all (B2: no win_gate short-circuit)
        anchor = weakest[0]
        fa_tagged = []
        for f in fa_entries:
            tags = fa_compute.compute_fa_tags_v4_sp(f, anchor)
            fa_tagged.append({**f, **tags})

        # ── Layer 5: 2-step single-LLM ──
        print(f"  Layer 5 ({label}): Step A — rank + classify...", file=sys.stderr)
        step_a_payload = _build_step_a_payload(weakest, fa_tagged, low_conf)
        _dump_fixture(args, today_str, "sp_b2_step_a", step_a_payload)

        eligible_names = [w["name"] for w in weakest]
        fa_names = [f["name"] for f in fa_tagged]

        step_a_result = _run_step_a(
            step_a_payload, eligible_names, fa_names, env, args, h, label,
        )
        if step_a_result is None:
            # Final fall-through: pass verdict with alert (already sent inside _run_step_a)
            _emit_b2_pass(label, anchor, fa_tagged, today_str, env, args, h,
                          reason="Step A failed; defaulting to pass")
            return

        print(f"  Layer 5 ({label}): Step B — final verdict...", file=sys.stderr)
        non_data_context = {
            "faab_remaining": league_cfg.get("faab_remaining"),
            "rostered_names": list(rostered_names) if rostered_names else [],
        }
        step_b_payload = _build_step_b_payload(
            step_a_result, weakest, fa_tagged, non_data_context,
        )
        _dump_fixture(args, today_str, "sp_b2_step_b", step_b_payload)

        step_b_result = _run_step_b(
            step_b_payload, eligible_names, fa_names, env, args, h, label,
        )
        if step_b_result is None:
            _emit_b2_pass(label, anchor, fa_tagged, today_str, env, args, h,
                          reason="Step B failed; defaulting to pass")
            return

        _emit_b2_final(
            label, step_a_result, step_b_result, today_str, env, args, h,
            weakest=weakest, fa_tagged=fa_tagged,
        )

    except Exception as e:
        if h.get("handle_error"):
            h["handle_error"](f"{label} scan", e, env, args)
        else:
            raise


# ── Step runners with validation + 1 retry + Telegram alert ──

def _run_step_a(payload: str, eligible_names: list[str], fa_names: list[str],
                env, args, h: dict, label: str) -> dict | None:
    """Call Step A with parse + schema validation; 1 retry on failure. Return
    parsed dict or None (caller routes to _emit_b2_pass which sends the
    single Telegram alert for the whole step failure)."""
    prompt = _load_prompt("step_a")
    full = f"{prompt}\n\n---\n\n{payload}"
    for attempt in (1, 2):
        result = run_single_agent(full, f"step_a_v{attempt}", timeout=_LLM_TIMEOUT)
        parsed = result.parsed
        if parsed is not None:
            err = _validate_step_a(parsed, eligible_names, fa_names)
            if err is None:
                return parsed
            # Log to stderr only; single Telegram alert from caller after exhaustion
            print(f"[{label}] Step A schema invalid (attempt {attempt}): {err}",
                  file=sys.stderr)
        else:
            print(f"[{label}] Step A JSON parse failed (attempt {attempt}): "
                  f"{result.error or 'no parse'}", file=sys.stderr)
    return None


def _run_step_b(payload: str, eligible_names: list[str], fa_names: list[str],
                env, args, h: dict, label: str) -> dict | None:
    prompt = _load_prompt("step_b")
    full = f"{prompt}\n\n---\n\n{payload}"
    for attempt in (1, 2):
        result = run_single_agent(full, f"step_b_v{attempt}", timeout=_LLM_TIMEOUT)
        parsed = result.parsed
        if parsed is not None:
            err = _validate_step_b(parsed, eligible_names, fa_names)
            if err is None:
                return parsed
            print(f"[{label}] Step B schema invalid (attempt {attempt}): {err}",
                  file=sys.stderr)
        else:
            print(f"[{label}] Step B JSON parse failed (attempt {attempt}): "
                  f"{result.error or 'no parse'}", file=sys.stderr)
    return None


# ── Output emission ──

def _emit_b2_pass(label, anchor, fa_tagged, today_str, env, args, h, reason: str) -> None:
    """Pipeline-degrade pass — used when Step A or B fail validation."""
    anchor_name = anchor["name"] if isinstance(anchor, dict) else str(anchor)
    msg = (f"[FA Scan {label}] {reason}\n\n"
           f"Anchor (eligible-pool P1): {anchor_name}\n"
           f"FA pool size: {len(fa_tagged)}")
    h["publish"](today_str, label, msg, msg, msg, env, args)


def _emit_b2_final(label, step_a: dict, step_b: dict, today_str, env, args, h,
                   weakest: list[dict], fa_tagged: list[dict]) -> None:
    """Publish Step B verdict to Telegram + Issue + waiver-log."""
    action = step_b.get("action")
    reason = step_b.get("reason") or ""

    telegram_lines = [f"[{label}] B2 verdict: {action}"]
    if action == "drop_X_add_Y":
        telegram_lines.append(f"  drop: {step_b.get('drop')}")
        telegram_lines.append(f"  add:  {step_b.get('add')}")
    elif action == "watch":
        telegram_lines.append(f"  watch: {step_b.get('watch_target')}")
    telegram_lines.append("")
    telegram_lines.append(reason)
    advice_telegram = "\n".join(telegram_lines)

    # waiver-log block — only for watch or drop_X_add_Y
    waiver_block_lines = []
    watch_target = step_b.get("watch_target")
    if action == "watch" and watch_target:
        team, position = _lookup_team_position(watch_target, fa_tagged, weakest)
        note = (reason or "").replace("|", "/").replace("\n", " ")[:200]
        waiver_block_lines.append(f"NEW|{watch_target}|{team}|{position}|B2 2-step watch|{note}")
    elif action == "drop_X_add_Y":
        add_name = step_b.get("add")
        if add_name:
            team, position = _lookup_team_position(add_name, fa_tagged, weakest)
            note = (reason or "").replace("|", "/").replace("\n", " ")[:200]
            waiver_block_lines.append(f"NEW|{add_name}|{team}|{position}|B2 2-step add|{note}")

    waiver_block = ""
    if waiver_block_lines:
        waiver_block = "\n\n```waiver-log\n" + "\n".join(waiver_block_lines) + "\n```\n"

    advice_full = advice_telegram + waiver_block
    advice_issue = advice_telegram

    full_raw_parts = [
        f"=== {label} B2 Step A ===",
        json.dumps(step_a, ensure_ascii=False, indent=2, default=str),
        f"=== {label} B2 Step B (final verdict) ===",
        json.dumps(step_b, ensure_ascii=False, indent=2, default=str),
    ]
    full_raw = "\n\n".join(full_raw_parts)

    h["publish"](today_str, label, advice_telegram, advice_issue, full_raw, env, args)

    if waiver_block_lines and not getattr(args, "no_waiver_log", False):
        h["update_waiver_log"](advice_full, today_str, env)


def _lookup_team_position(name: str, fa_pool: list[dict],
                          weakest: list[dict]) -> tuple[str, str]:
    for collection in (fa_pool, weakest):
        for entry in collection:
            if entry.get("name") == name:
                return entry.get("team") or "", entry.get("position") or "SP"
    return "", "SP"
