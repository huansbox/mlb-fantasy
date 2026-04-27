"""_phase6_sp — Phase 6 multi-agent SP orchestrator (v4 framework).

Entry point: process_sp_v4(...). Called from fa_scan._process_group_sp_v4
when SP_FRAMEWORK_VERSION=v4. Mirrors v2 _process_group("sp") top-level
structure but Layer 5 is an 8-step multi-agent flow.

Pipeline:
  Layer 1.5: filter pure-RP from FA pool (game-log GS=1 IP/GS gate, reuse v2)
  Layer 4:   v4 mechanical (pick_weakest_v4_sp + compute_urgency_v4_sp +
             compute_fa_tags_v4_sp) — no Python decision
  Layer 5:   8-step multi-agent
    - my-team:  step1×3 → step2 master → step3×3 review (gated) → re-eval (gated)
    - FA:       classify×3 → master rank → review×3 (gated) → re-eval (gated)
    - final:    1 master call → action / drop_X_add_Y / watch / pass

Per-step failure: graceful degrade with Telegram flag (see
docs/v4-cutover-plan.md §D.5).

Refs:
- docs/fa_scan-claude-decision-layer-design.md (§4 flow, §7 decisions)
- docs/sp-framework-v4-balanced.md (v4 framework mechanics)
- docs/phase6-multi-agent-spike-results.md (§7.2 P1 match converges)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import fa_compute
from _multi_agent import (
    aggregate_classifications,
    all_parsed,
    consensus_check_key,
    count_dissent,
    run_parallel_agents,
    run_single_agent,
)

# Module dir (where prompt files live alongside this module + fa_scan.py)
_MODULE_DIR = Path(__file__).resolve().parent

_PHASE6_PROMPTS = {
    "sp_step1": "prompt_phase6_sp_step1_rank.txt",
    "sp_step2": "prompt_phase6_sp_step2_master.txt",
    "sp_step3_review": "prompt_phase6_sp_step3_review.txt",
    "fa_classify": "prompt_phase6_fa_step1_classify.txt",
    "fa_rank": "prompt_phase6_fa_step2_rank.txt",
    "fa_review": "prompt_phase6_fa_step3_review.txt",
    "final": "prompt_phase6_final_decision.txt",
}

# Per-step claude -p timeout (seconds). Spike measured ~40s per agent,
# but FA candidate count varies; 600s gives generous headroom.
_PHASE6_TIMEOUT = 600


def _load_prompt(name: str) -> str:
    fname = _PHASE6_PROMPTS[name]
    return (_MODULE_DIR / fname).read_text(encoding="utf-8")


# ── v4 data attachment ──

def _attach_v4_to_my_roster(my_roster: list[dict]) -> None:
    """Add `savant_v4` dict to each my-team SP entry (mutates in-place).

    Uses fa_scan_v4.assemble_data — one batch fetch for all SP. The savant_v4
    dict has the 5 v4 Sum inputs (ip_gs/whiff_pct/bb9/gb_pct/xwobacon) plus
    gate / luck / context fields (g/gs/ip/bbe/xera/era/...).
    """
    # Lazy import to avoid circular deps at module load (fa_scan_v4 has heavy
    # network imports we only need when v4 is active)
    from fa_scan_v4 import assemble_data

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
    from fa_scan_v4 import assemble_data

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
            # Also recompute v4 Sum + breakdown (needed for compute_fa_tags_v4_sp diff)
            score, breakdown = fa_compute.compute_sum_score_v4_sp(v4[pid])
            p["score"] = score
            p["breakdown"] = breakdown


# ── Payload builders (Python → prompt input JSON) ──

def _slim_my_team_entry(entry: dict) -> dict:
    """Reduce my-team weakest entry to fields Claude needs (drops MLB API blobs)."""
    sv4 = entry.get("savant_v4") or {}
    return {
        "name": entry["name"],
        "team": entry.get("team"),
        "score": entry.get("score"),  # v4 Sum 0-50
        "breakdown": entry.get("breakdown"),
        "savant_v4": {
            "ip_gs": sv4.get("ip_gs"),
            "whiff_pct": sv4.get("whiff_pct"),
            "bb9": sv4.get("bb9"),
            "gb_pct": sv4.get("gb_pct"),
            "xwobacon": sv4.get("xwobacon"),
            "xera": sv4.get("xera"),
            "era": sv4.get("era"),
            "bbe": sv4.get("bbe"),
            "ip": sv4.get("ip"),
            "g": sv4.get("g"),
            "gs": sv4.get("gs"),
            "k9": sv4.get("k9"),
            "whip": sv4.get("whip"),
        },
        "prior_stats": entry.get("prior_stats") or {},
        "prior_sum": entry.get("prior_sum"),
        "prior_ip": entry.get("prior_ip"),
        "prior_breakdown": entry.get("prior_breakdown"),
        "rolling_delta_xwobacon": entry.get("rolling_delta_xwobacon"),
        "rolling_bbe": entry.get("rolling_bbe"),
        "rolling_21d_xwobacon": (entry.get("rolling_21d") or {}).get("xwobacon"),
        "urgency": entry.get("urgency"),
        "factors": entry.get("factors"),
        "selected_pos": entry.get("selected_pos"),
        "status": entry.get("status"),
        "notes": entry.get("notes") or [],
    }


def _slim_fa_entry(entry: dict) -> dict:
    """Reduce FA entry to fields Claude needs."""
    sv4 = entry.get("savant_v4") or {}
    return {
        "name": entry["name"],
        "team": entry.get("team"),
        "position": entry.get("position"),
        "pct": entry.get("pct"),
        "score": entry.get("score"),
        "breakdown": entry.get("breakdown"),
        "savant_v4": {
            "ip_gs": sv4.get("ip_gs"),
            "whiff_pct": sv4.get("whiff_pct"),
            "bb9": sv4.get("bb9"),
            "gb_pct": sv4.get("gb_pct"),
            "xwobacon": sv4.get("xwobacon"),
            "xera": sv4.get("xera"),
            "era": sv4.get("era"),
            "bbe": sv4.get("bbe"),
            "ip": sv4.get("ip"),
            "g": sv4.get("g"),
            "gs": sv4.get("gs"),
            "k9": sv4.get("k9"),
            "whip": sv4.get("whip"),
        },
        "rolling_21d_xwobacon": (entry.get("rolling_21d") or {}).get("xwobacon"),
        "rolling_21d_bbe": (entry.get("rolling_21d") or {}).get("bbe"),
        "d1": entry.get("d1"),  # %owned 1d delta
        "d3": entry.get("d3"),
        "waiver_date": entry.get("waiver_date"),
    }


def _build_step1_payload(urgency_result: dict, low_conf: list[dict]) -> str:
    """JSON for SP step 1 prompt (3 agents see this)."""
    candidates = [_slim_my_team_entry(e) for e in urgency_result["weakest_ranked"]]
    payload = {
        "candidates": candidates,
        "slump_hold_excluded": [
            {"name": s["name"], "prior_sum": s["prior_sum"], "prior_ip": s["prior_ip"],
             "sum_2026": s["sum_2026"], "note": s["note"]}
            for s in urgency_result.get("slump_hold", [])
        ],
        "low_confidence_excluded": low_conf,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _build_step2_payload(step1_results: list, urgency_result: dict,
                         low_conf: list[dict]) -> str:
    """JSON for SP step 2 master prompt."""
    payload = {
        "agents_step1": [
            {"agent_id": r.agent_id, **(r.parsed or {"error": r.error})}
            for r in step1_results
        ],
        "material": {
            "candidates": [_slim_my_team_entry(e) for e in urgency_result["weakest_ranked"]],
            "slump_hold_excluded": urgency_result.get("slump_hold", []),
            "low_confidence_excluded": low_conf,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _build_step3_review_payload(master: dict, step1_results: list,
                                urgency_result: dict, my_agent_step1: dict) -> str:
    """JSON for SP step 3 review prompt — each reviewer sees master + own step1."""
    payload = {
        "master_decision": master,
        "your_step1": my_agent_step1,
        "material": {
            "candidates": [_slim_my_team_entry(e) for e in urgency_result["weakest_ranked"]],
            "slump_hold_excluded": urgency_result.get("slump_hold", []),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _build_fa_classify_payload(anchor: dict, fa_tagged: list[dict]) -> str:
    payload = {
        "anchor": _slim_my_team_entry(anchor),
        "fa_candidates": [
            {**_slim_fa_entry(f),
             "sum_diff": f.get("sum_diff"),
             "breakdown_diff": f.get("breakdown_diff"),
             "win_gate_passed": f.get("win_gate_passed"),
             "add_tags": f.get("add_tags") or [],
             "warn_tags": f.get("warn_tags") or [],
             "anchor_name": f.get("anchor_name")}
            for f in fa_tagged
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _build_fa_rank_payload(anchor: dict, fa_survivors: list[dict],
                           classify_results: list, aggregated: dict[str, str]) -> str:
    payload = {
        "agents_step1": [
            {"agent_id": r.agent_id, **(r.parsed or {"error": r.error})}
            for r in classify_results
        ],
        "aggregated_verdicts": aggregated,
        "anchor": _slim_my_team_entry(anchor),
        "fa_survivors": [
            {**_slim_fa_entry(f),
             "sum_diff": f.get("sum_diff"),
             "win_gate_passed": f.get("win_gate_passed"),
             "add_tags": f.get("add_tags") or [],
             "warn_tags": f.get("warn_tags") or []}
            for f in fa_survivors
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _build_fa_review_payload(fa_master: dict, classify_results: list,
                             my_classify_step1: dict, anchor: dict,
                             fa_survivors: list[dict]) -> str:
    payload = {
        "master_decision": fa_master,
        "your_step1": my_classify_step1,
        "anchor": _slim_my_team_entry(anchor),
        "material": {
            "fa_survivors": [_slim_fa_entry(f) for f in fa_survivors],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _build_final_payload(anchor: dict, fa_master_final: dict,
                         anchor_flag: str | None, fa_top_flag: str | None,
                         fa_survivors_lookup: dict[str, dict],
                         non_data_context: dict) -> str:
    """JSON for final decision prompt.

    fa_master_final.parsed["ranked_top"] is a list of {name, rank, sum_diff,
    classify_verdict, rationale}. We hydrate each with full v4 material.
    """
    ranked_top_full = []
    for entry in fa_master_final.get("ranked_top") or []:
        name = entry.get("name")
        full = fa_survivors_lookup.get(name)
        if full:
            ranked_top_full.append({
                **_slim_fa_entry(full),
                "rank": entry.get("rank"),
                "sum_diff": entry.get("sum_diff"),
                "classify_verdict": entry.get("classify_verdict"),
                "master_rationale": entry.get("rationale"),
                "add_tags": full.get("add_tags") or [],
                "warn_tags": full.get("warn_tags") or [],
            })

    payload = {
        "anchor": _slim_my_team_entry(anchor),
        "fa_top": ranked_top_full,
        "borderline_pairs": fa_master_final.get("borderline_pairs") or [],
        "convergence_flags": [f for f in [anchor_flag, fa_top_flag] if f],
        "non_data_context": non_data_context,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


# ── Main orchestrator ──

def process_sp_v4(config, savant_2026, enriched, watch_enriched,
                  changes, ref_1d, ref_3d, today_str, env, args,
                  rostered_names=None,
                  fa_scan_helpers=None):
    """Phase 6 multi-agent v4 SP path. Drop-in for v2 _process_group("sp").

    fa_scan_helpers: dict of helper callables from fa_scan.py (passed in to
    avoid circular import). Required keys: notify, handle_error, publish,
    update_waiver_log, prep_my_roster, normalize_fa_for_compute, fetch_team_games,
    load_savant_rolling, fetch_fa_rolling, ip_per_gs_from_gamelog, classify_fa_type.
    """
    h = fa_scan_helpers or {}
    label = "SP-v4"

    try:
        fa_candidates = [p for p in enriched if p["fa_type"] == "sp"]
        watch_candidates = [p for p in watch_enriched if p["fa_type"] == "sp"]

        # Layer 1.5: pure-RP filter (same as v2; ip_per_gs_from_gamelog passed in)
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

        # ── Layer 4: v4 mechanical ──
        print(f"  Layer 4 ({label}): pick_weakest + urgency...", file=sys.stderr)
        standings = h["fetch_team_games"]()
        rolling = h["load_savant_rolling"](player_type="sp")
        my_roster = h["prep_my_roster"]("sp", config, savant_2026, standings, rolling)
        _attach_v4_to_my_roster(my_roster)

        cant_cut = set(config.get("league", {}).get("cant_cut", []))
        weakest, low_conf = fa_compute.pick_weakest_v4_sp(my_roster, n=4, cant_cut=cant_cut)
        urgency_result = fa_compute.compute_urgency_v4_sp(weakest)

        if not urgency_result["weakest_ranked"]:
            h["notify"](env, args, f"[FA Scan {label}] 無有效 anchor (all slump-hold/excluded)")
            return

        # FA tagging (v4)
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

        # anchor for FA tag diff = first ranked weakest (urgency-sorted, ties
        # already left for Claude to break in step 2)
        anchor = urgency_result["weakest_ranked"][0]

        fa_tagged = []
        for f in fa_entries:
            tags = fa_compute.compute_fa_tags_v4_sp(f, anchor)
            fa_tagged.append({**f, **tags})

        # ── Layer 5: 8-step multi-agent ──
        print(f"  Layer 5 ({label}): step 1 — 3 agents rank P1-P4 in parallel...",
              file=sys.stderr)
        step1_payload = _build_step1_payload(urgency_result, low_conf)
        step1_results = run_parallel_agents(
            _load_prompt("sp_step1"), step1_payload, n_agents=3, timeout=_PHASE6_TIMEOUT,
        )
        if not all_parsed(step1_results):
            return _degrade(label, "step 1 parse failed", step1_results, env, args, h)

        # log P1 distribution for debug
        p1_match, p1_info = consensus_check_key(step1_results, ["ranking", 0])
        print(f"    step 1 P1 distribution: {p1_info['distribution']}", file=sys.stderr)

        print(f"  Layer 5 ({label}): step 2 — master integrates...", file=sys.stderr)
        step2_payload = _build_step2_payload(step1_results, urgency_result, low_conf)
        master_v1 = run_single_agent(
            _load_prompt("sp_step2") + "\n\n---\n\n" + step2_payload,
            "master_v1", timeout=_PHASE6_TIMEOUT,
        )
        if master_v1.parsed is None:
            return _degrade(label, "step 2 master parse failed", [master_v1], env, args, h)

        anchor_flag = None
        final_master_p = master_v1.parsed
        if final_master_p.get("borderline_pairs"):
            print(f"  Layer 5 ({label}): step 3 — 3 reviewers (borderline gate triggered)...",
                  file=sys.stderr)
            review_payloads = [
                _build_step3_review_payload(
                    final_master_p, step1_results, urgency_result,
                    step1_results[i].parsed or {},
                )
                for i in range(len(step1_results))
            ]
            # Reviewers see different "your_step1" each — run sequentially
            # in 3 threads via separate run_single_agent calls inside threads.
            review_results = _run_personalized_reviewers(
                _load_prompt("sp_step3_review"), review_payloads, _PHASE6_TIMEOUT,
            )
            dissent = count_dissent(review_results, "agree_on_p1")
            if dissent >= 2:
                print(f"  Layer 5 ({label}): re-eval (dissent={dissent})...", file=sys.stderr)
                # Re-eval: master sees review feedback + reruns step 2
                reeval_payload = _build_reeval_payload(step2_payload, review_results)
                master_v2 = run_single_agent(
                    _load_prompt("sp_step2") + "\n\n---\n\n" + reeval_payload,
                    "master_v2", timeout=_PHASE6_TIMEOUT,
                )
                if master_v2.parsed:
                    final_master_p = master_v2.parsed
                    # 1 round cap: check dissent again on new master
                    if final_master_p.get("borderline_pairs"):
                        review2_payloads = [
                            _build_step3_review_payload(
                                final_master_p, step1_results, urgency_result,
                                step1_results[i].parsed or {},
                            )
                            for i in range(len(step1_results))
                        ]
                        review2_results = _run_personalized_reviewers(
                            _load_prompt("sp_step3_review"), review2_payloads, _PHASE6_TIMEOUT,
                        )
                        if count_dissent(review2_results, "agree_on_p1") >= 2:
                            anchor_flag = "⚠️ P1 分歧未收斂"

        anchor_name = (final_master_p.get("final_ranking") or [None])[0]
        if not anchor_name:
            return _degrade(label, "no P1 in master decision", [master_v1], env, args, h)
        # Re-resolve anchor to the ranked entry by name
        anchor_entry = next(
            (e for e in urgency_result["weakest_ranked"] if e["name"] == anchor_name),
            anchor,
        )

        # === FA line ===
        print(f"  Layer 5 ({label}): step 4 — FA classify (3 agents)...", file=sys.stderr)
        fa_classify_payload = _build_fa_classify_payload(anchor_entry, fa_tagged)
        fa_classify_results = run_parallel_agents(
            _load_prompt("fa_classify"), fa_classify_payload,
            n_agents=3, timeout=_PHASE6_TIMEOUT,
        )
        if not all_parsed(fa_classify_results):
            print(f"    {label}: FA classify partial parse — proceeding with parsed only",
                  file=sys.stderr)

        all_fa_names = [f["name"] for f in fa_tagged]
        aggregated = aggregate_classifications(fa_classify_results, all_fa_names)
        survivors = [f for f in fa_tagged if aggregated[f["name"]] in ("worth", "borderline")]
        if not survivors:
            return _emit_pass(label, anchor_entry, anchor_flag, fa_tagged, aggregated,
                              "FA classify 全 not_worth", today_str, env, args, h)

        print(f"  Layer 5 ({label}): step 5 — FA master rank (1 call, "
              f"{len(survivors)} survivors)...", file=sys.stderr)
        fa_rank_payload = _build_fa_rank_payload(anchor_entry, survivors, fa_classify_results, aggregated)
        fa_master_v1 = run_single_agent(
            _load_prompt("fa_rank") + "\n\n---\n\n" + fa_rank_payload,
            "fa_master_v1", timeout=_PHASE6_TIMEOUT,
        )
        if fa_master_v1.parsed is None:
            return _degrade(label, "FA master rank parse failed", [fa_master_v1], env, args, h)

        fa_top_flag = None
        fa_master_p = fa_master_v1.parsed
        if fa_master_p.get("borderline_pairs"):
            print(f"  Layer 5 ({label}): step 6 — FA review (borderline gate)...",
                  file=sys.stderr)
            fa_review_payloads = [
                _build_fa_review_payload(
                    fa_master_p, fa_classify_results,
                    fa_classify_results[i].parsed or {},
                    anchor_entry, survivors,
                )
                for i in range(len(fa_classify_results))
            ]
            fa_review_results = _run_personalized_reviewers(
                _load_prompt("fa_review"), fa_review_payloads, _PHASE6_TIMEOUT,
            )
            dissent = count_dissent(fa_review_results, "agree_on_top1")
            if dissent >= 2:
                print(f"  Layer 5 ({label}): step 7 — FA re-eval (dissent={dissent})...",
                      file=sys.stderr)
                reeval_fa = _build_reeval_payload(fa_rank_payload, fa_review_results)
                fa_master_v2 = run_single_agent(
                    _load_prompt("fa_rank") + "\n\n---\n\n" + reeval_fa,
                    "fa_master_v2", timeout=_PHASE6_TIMEOUT,
                )
                if fa_master_v2.parsed:
                    fa_master_p = fa_master_v2.parsed
                    if fa_master_p.get("borderline_pairs"):
                        review2_payloads = [
                            _build_fa_review_payload(
                                fa_master_p, fa_classify_results,
                                fa_classify_results[i].parsed or {},
                                anchor_entry, survivors,
                            )
                            for i in range(len(fa_classify_results))
                        ]
                        review2 = _run_personalized_reviewers(
                            _load_prompt("fa_review"), review2_payloads, _PHASE6_TIMEOUT,
                        )
                        if count_dissent(review2, "agree_on_top1") >= 2:
                            fa_top_flag = "⚠️ FA top 排序分歧未收斂"

        # ── Step 8: final decision ──
        print(f"  Layer 5 ({label}): step 8 — final decision...", file=sys.stderr)
        survivors_by_name = {f["name"]: f for f in survivors}
        non_data_context = {
            "faab_remaining": config.get("league", {}).get("faab_remaining"),
            "current_acquisitions_this_week": None,  # could compute from changes
            "rostered_names": list(rostered_names) if rostered_names else [],
        }
        final_payload = _build_final_payload(
            anchor_entry, fa_master_p, anchor_flag, fa_top_flag,
            survivors_by_name, non_data_context,
        )
        final_result = run_single_agent(
            _load_prompt("final") + "\n\n---\n\n" + final_payload,
            "final", timeout=_PHASE6_TIMEOUT,
        )
        if final_result.parsed is None:
            return _degrade(label, "final decision parse failed", [final_result], env, args, h)

        # Publish
        _emit_final(label, final_result.parsed, anchor_flag, fa_top_flag,
                    today_str, env, args, h,
                    anchor_entry=anchor_entry,
                    survivors_by_name=survivors_by_name,
                    debug_dump={
                        "step1": [r.parsed for r in step1_results],
                        "step2": master_v1.parsed,
                        "fa_classify_aggregated": aggregated,
                        "fa_rank": fa_master_p,
                    })
    except Exception as e:
        if h.get("handle_error"):
            h["handle_error"](f"{label} scan", e, env, args)
        else:
            raise


# ── Helpers (private) ──

def _run_personalized_reviewers(prompt_template: str, payloads: list[str],
                                timeout: int) -> list:
    """Like run_parallel_agents but each agent gets a different payload (its own
    `your_step1` view). Threads spawn 3 run_single_agent calls in parallel."""
    import threading
    from _multi_agent import AgentResult

    results: list = [None] * len(payloads)

    def worker(idx: int):
        agent_id = f"agent_{idx + 1}"
        agent_prompt = prompt_template.replace("{agent_id}", agent_id)
        full_prompt = f"{agent_prompt}\n\n---\n\n{payloads[idx]}"
        results[idx] = run_single_agent(full_prompt, agent_id, timeout=timeout)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(payloads))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return [r for r in results if r is not None]


def _build_reeval_payload(original_payload: str, review_results: list) -> str:
    """Augment the original master payload with reviewer dissent feedback for re-eval."""
    feedback = [
        {"agent_id": r.agent_id, **(r.parsed or {"error": r.error})}
        for r in review_results
    ]
    payload_obj = json.loads(original_payload)
    payload_obj["reviewer_feedback"] = feedback
    payload_obj["reeval_note"] = (
        "REVIEWERS DISSENTED on the previous master decision. Reconsider the "
        "P1/top1 pick using their dissent_reason fields. If you still believe "
        "your original was correct, you may keep it but address each dissent "
        "explicitly in the rationale."
    )
    return json.dumps(payload_obj, ensure_ascii=False, indent=2, default=str)


def _emit_pass(label, anchor, anchor_flag, fa_tagged, aggregated,
               reason, today_str, env, args, h):
    """No FA worth pursuing → emit pass action."""
    msg = f"[FA Scan {label}] {reason}\n\nAnchor (隊上最該觀察 SP): {anchor['name']}"
    if anchor_flag:
        msg = f"{anchor_flag}\n\n" + msg
    h["publish"](today_str, label, msg, msg, msg, env, args)


def _emit_final(label, final_parsed, anchor_flag, fa_top_flag,
                today_str, env, args, h, anchor_entry=None, survivors_by_name=None,
                debug_dump=None):
    """Publish final action (drop_X_add_Y / watch / pass) to Telegram + Issue + waiver-log.

    Translates Phase 6 structured `waiver_log_updates` into v2 text-block format
    (NEW|name|team|position|trigger|summary / UPDATE|name|summary) so existing
    _update_waiver_log mechanism handles git lock/sync/push.
    """
    flags = [f for f in [anchor_flag, fa_top_flag] if f]
    flag_prefix = ("\n".join(flags) + "\n\n") if flags else ""

    telegram_summary = final_parsed.get("telegram_summary") or "[Phase 6] (no summary)"
    reason = final_parsed.get("reason") or ""

    advice_telegram = f"{flag_prefix}{telegram_summary}\n\n{reason}"

    # Translate waiver_log_updates → v2 text block embedded in advice
    waiver_block_lines = []
    for u in final_parsed.get("waiver_log_updates") or []:
        action = u.get("action")
        name = u.get("name")
        note = (u.get("note") or "").replace("|", "/").replace("\n", " ")
        if not action or not name:
            continue
        if action == "NEW":
            # Team/position lookup: prefer survivors (FA), fall back to anchor (drop case)
            team, position = "", "SP"
            lookup = (survivors_by_name or {}).get(name)
            if lookup is None and anchor_entry and anchor_entry.get("name") == name:
                lookup = anchor_entry
            if lookup:
                team = lookup.get("team") or ""
                position = lookup.get("position") or "SP"
            trigger = "Phase 6 multi-agent watch"
            waiver_block_lines.append(f"NEW|{name}|{team}|{position}|{trigger}|{note}")
        elif action == "UPDATE":
            waiver_block_lines.append(f"UPDATE|{name}|{note}")

    waiver_block = ""
    if waiver_block_lines:
        waiver_block = "\n\n```waiver-log\n" + "\n".join(waiver_block_lines) + "\n```\n"

    advice_full = advice_telegram + waiver_block
    advice_issue = advice_telegram  # Issue body skips waiver-log block

    full_raw_parts = [
        f"=== Phase 6 Final Decision ({label}) ===",
        json.dumps(final_parsed, ensure_ascii=False, indent=2, default=str),
    ]
    if debug_dump:
        full_raw_parts.append("=== Phase 6 Debug Dump ===")
        full_raw_parts.append(json.dumps(debug_dump, ensure_ascii=False, indent=2, default=str))
    full_raw = "\n\n".join(full_raw_parts)

    h["publish"](today_str, label, advice_telegram, advice_issue, full_raw, env, args)

    # waiver-log: reuse v2 mechanism (git lock + pull/commit/push) by embedding block
    if waiver_block_lines and not getattr(args, "no_waiver_log", False):
        h["update_waiver_log"](advice_full, today_str, env)


def _degrade(label, reason, results, env, args, h):
    """Step failed catastrophically (all agents parse-fail / crash) — notify + bail."""
    detail_lines = []
    for r in results:
        if r.error:
            detail_lines.append(f"  {r.agent_id}: ERROR {r.error}")
        elif r.parsed is None:
            detail_lines.append(f"  {r.agent_id}: parse-fail (stdout {len(r.stdout)} chars)")
        else:
            detail_lines.append(f"  {r.agent_id}: parsed OK")
    msg = f"[FA Scan {label}] DEGRADE: {reason}\n" + "\n".join(detail_lines)
    print(msg, file=sys.stderr)
    h["notify"](env, args, msg)
