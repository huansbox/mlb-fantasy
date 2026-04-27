"""Smoke integration test for _phase6_sp orchestrator (Stage D).

Covers the happy path only — no borderline gate, no dissent, no degrade.
The 8-step flow collapses to 5 LLM calls when borderline_pairs is empty:
  step1 × 3 + step2 master + fa_classify × 3 + fa_rank master + final = 5 ?
  Actually: step1×3 (parallel = 3 calls) + step2 (1) + fa_classify×3 (3) +
  fa_rank (1) + final (1) = 9 subprocess invocations total.

Borderline / re-eval / degrade branches are validated by:
- _multi_agent unit tests (control-flow primitives)
- task #6 end-to-end dry-run (real claude -p)
- Stage E parallel period (real Savant + waiver-log behavior)

This test mocks subprocess.run + assemble_data + roster prep helpers so the
orchestrator walks through control flow without touching network or real
fa_compute computations on real data.
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

# Canned responses for each Claude step (happy path: no borderline, no dissent)
_FAKE_STEP1 = lambda agent_id: '```json\n' + json.dumps({
    "ranking": ["Nola", "López", "Holmes", "Cantillo"],
    "rationale": {"P1": "Nola lowest sum", "P2": "...", "P3": "...", "P4": "..."},
    "key_uncertainty": "none",
    "agent_id": agent_id,
}, ensure_ascii=False) + '\n```'

_FAKE_STEP2_MASTER = '```json\n' + json.dumps({
    "final_ranking": ["Nola", "López", "Holmes", "Cantillo"],
    "rationale": {"P1": "...", "P2": "...", "P3": "...", "P4": "..."},
    "agent_consensus": "all 3 agree",
    "borderline_pairs": [],  # empty → skip step 3
    "decision_notes": "none",
}, ensure_ascii=False) + '\n```'

_FAKE_FA_CLASSIFY = lambda agent_id: '```json\n' + json.dumps({
    "classifications": [
        {"name": "Pfaadt", "verdict": "worth", "rationale": "Sum +18, 2 ✅"},
    ],
    "agent_id": agent_id,
}, ensure_ascii=False) + '\n```'

_FAKE_FA_RANK = '```json\n' + json.dumps({
    "ranked_top": [
        {"name": "Pfaadt", "rank": 1, "sum_diff": 18, "classify_verdict": "worth",
         "rationale": "best add"},
    ],
    "agent_consensus": "all worth",
    "borderline_pairs": [],  # empty → skip review
    "decision_notes": "none",
}, ensure_ascii=False) + '\n```'

_FAKE_FINAL = '```json\n' + json.dumps({
    "action": "drop_X_add_Y",
    "drop": "Nola",
    "add": "Pfaadt",
    "watch_target": None,
    "reason": "Pfaadt structurally clear upgrade",
    "watch_triggers": [],
    "waiver_log_updates": [
        {"action": "UPDATE", "name": "Nola", "note": "dropped via Phase 6"},
        {"action": "UPDATE", "name": "Pfaadt", "note": "rostered by us"},
    ],
    "telegram_summary": "[Phase 6] drop Nola add Pfaadt — Sum +18",
}, ensure_ascii=False) + '\n```'


def _make_completed(stdout, returncode=0):
    m = MagicMock()
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


def _route_subprocess(*args, **kwargs):
    """Route claude -p calls based on prompt content to the right canned response."""
    cmd = args[0] if args else kwargs.get("args")
    prompt = cmd[2] if len(cmd) > 2 else ""

    # Detect step from prompt template content (each Phase 6 prompt has unique markers)
    if "Step 1" in prompt and "Rank the team's weakest 4 SPs" in prompt:
        # SP step 1 — extract agent_id and return per-agent response
        for cand in ["agent_1", "agent_2", "agent_3"]:
            if cand in prompt:
                return _make_completed(_FAKE_STEP1(cand))
        return _make_completed(_FAKE_STEP1("agent_1"))
    if "Step 2)" in prompt and "Integrate the 3 agents' rankings" in prompt:
        return _make_completed(_FAKE_STEP2_MASTER)
    if "Step 3)" in prompt and "specific focus on P1" in prompt:
        # Should not reach here since borderline_pairs is empty in master
        pytest.fail("step3_review should be skipped when borderline_pairs is empty")
    if "FA Step 2)" in prompt or ("Rank the surviving FA candidates" in prompt):
        return _make_completed(_FAKE_FA_RANK)
    if "FA Step 3)" in prompt or ("focus on top1 first" in prompt and "FA" in prompt):
        pytest.fail("fa_review should be skipped when borderline_pairs is empty")
    if "FA line, step 1" in prompt or "classify them against the team's anchor" in prompt:
        for cand in ["agent_1", "agent_2", "agent_3"]:
            if cand in prompt:
                return _make_completed(_FAKE_FA_CLASSIFY(cand))
        return _make_completed(_FAKE_FA_CLASSIFY("agent_1"))
    if "Final Decision" in prompt or "compare the anchor one-by-one against the top FAs" in prompt:
        return _make_completed(_FAKE_FINAL)
    # Fallback — unrecognized prompt
    return _make_completed('{"error": "unknown prompt"}')


# Fake my-team SP entries that pass v4 BBE gate + have v4 data attached
def _fake_my_roster():
    sp_template = {
        "team": "X", "selected_pos": "SP", "status": "",
        "savant_2026": {"bbe": 50, "xera": 4.0, "xwoba": 0.310, "hh_pct": 0.40},
        "prior_stats": {},
        "rolling_21d": None,
        "derived": {"ip_per_tg": 0.8},
        "mlb_2026": {"gamesStarted": 5},
    }
    return [
        {**sp_template, "name": "Nola", "mlb_id": 605400},
        {**sp_template, "name": "López", "mlb_id": 663630},
        {**sp_template, "name": "Holmes", "mlb_id": 656529},
        {**sp_template, "name": "Cantillo", "mlb_id": 695253},
    ]


def _fake_v4_data():
    return {
        605400: {"ip_gs": 5.0, "whiff_pct": 22.0, "bb9": 3.5, "gb_pct": 38.0,
                 "xwobacon": 0.400, "xera": 4.0, "era": 4.0, "bbe": 50,
                 "ip": 50, "g": 5, "gs": 5, "k9": 7.0, "whip": 1.4},
        663630: {"ip_gs": 5.5, "whiff_pct": 24.0, "bb9": 3.0, "gb_pct": 42.0,
                 "xwobacon": 0.370, "xera": 3.8, "era": 4.5, "bbe": 50,
                 "ip": 55, "g": 5, "gs": 5, "k9": 8.5, "whip": 1.3},
        656529: {"ip_gs": 5.7, "whiff_pct": 25.0, "bb9": 2.8, "gb_pct": 45.0,
                 "xwobacon": 0.360, "xera": 3.6, "era": 3.5, "bbe": 50,
                 "ip": 57, "g": 5, "gs": 5, "k9": 9.0, "whip": 1.2},
        695253: {"ip_gs": 6.0, "whiff_pct": 27.0, "bb9": 2.3, "gb_pct": 48.0,
                 "xwobacon": 0.345, "xera": 3.0, "era": 3.0, "bbe": 50,
                 "ip": 60, "g": 5, "gs": 5, "k9": 10.0, "whip": 1.1},
        # FA — Pfaadt
        694297: {"ip_gs": 6.2, "whiff_pct": 30.0, "bb9": 2.0, "gb_pct": 50.0,
                 "xwobacon": 0.330, "xera": 2.8, "era": 3.5, "bbe": 60,
                 "ip": 62, "g": 6, "gs": 6, "k9": 11.0, "whip": 1.0},
    }


def _fake_fa_candidates():
    return [{
        "name": "Pfaadt",
        "mlb_id": 694297,
        "team": "AZ",
        "position": "SP",
        "fa_type": "sp",
        "savant_2026": {"bbe": 60, "xera": 2.8, "xwoba": 0.290, "hh_pct": 0.35},
        "savant_2025": {"xera": 4.0, "xwoba": 0.320, "hh_pct": 0.40},
        "mlb_2026": {"gamesStarted": 6, "inningsPitched": "62.0"},
        "mlb_2025": {"inningsPitched": "100.0"},
        "pct": 18, "d1": 2, "d3": 5,
        "waiver_date": "",
        "derived_2026": {"ip_per_tg": 1.0},
    }]


# ── Smoke test ──

class TestPhase6OrchestratorHappyPath:
    @patch("_multi_agent.subprocess.run", new=_route_subprocess)
    @patch("fa_scan_v4.assemble_data")
    def test_happy_path_no_borderline_no_dissent(self, mock_assemble):
        """Verify orchestrator walks 8 steps when no borderline → action=drop_add."""
        # Lazy import after patches set up
        from _phase6_sp import process_sp_v4

        # assemble_data called for my-roster + FA — return same merged dict
        mock_assemble.return_value = _fake_v4_data()

        # Capture publish/update_waiver_log calls
        publish_calls = []
        update_waiver_calls = []
        notify_calls = []

        def fake_publish(today_str, scan_type, advice_tg, advice_issue, raw, env, args):
            publish_calls.append({
                "scan_type": scan_type, "advice_tg": advice_tg, "raw": raw,
            })

        def fake_update_waiver_log(advice, today_str, env=None):
            update_waiver_calls.append({"advice": advice, "today": today_str})

        def fake_notify(env, args, msg):
            notify_calls.append(msg)

        helpers = {
            "notify": fake_notify,
            "handle_error": lambda *a, **kw: pytest.fail(f"handle_error called: {a}"),
            "publish": fake_publish,
            "update_waiver_log": fake_update_waiver_log,
            "prep_my_roster": lambda *a, **kw: _fake_my_roster(),
            "normalize_fa_for_compute": lambda p, gt, fr: {
                **p,
                "savant_v4": _fake_v4_data().get(p["mlb_id"], {}),
                "score": 0,  # will be overwritten by _attach_v4_to_fa
                "breakdown": {},
                "rolling_21d": None,
                "prior_stats": {},
            },
            "fetch_team_games": lambda: {"X": 30, "AZ": 30},
            "load_savant_rolling": lambda player_type=None: {},
            "fetch_fa_rolling": lambda *a, **kw: {},
            "ip_per_gs_from_gamelog": lambda *a, **kw: 5.0,  # all FA pass RP filter
        }

        config = {
            "league": {"cant_cut": [], "faab_remaining": 100},
            "pitchers": [],
            "batters": [],
        }
        args = MagicMock()
        args.no_send = True
        args.no_issue = True
        args.no_waiver_log = False
        args.dry_run = False

        # Run
        process_sp_v4(
            config=config,
            savant_2026={},
            enriched=_fake_fa_candidates(),
            watch_enriched=[],
            changes=[],
            ref_1d=None,
            ref_3d=None,
            today_str="2026-04-27",
            env={},
            args=args,
            rostered_names=set(),
            fa_scan_helpers=helpers,
        )

        # Verify orchestrator emitted final action
        assert len(publish_calls) == 1, f"Expected 1 publish, got {len(publish_calls)}"
        publish = publish_calls[0]
        assert publish["scan_type"] == "SP-v4"
        assert "drop Nola add Pfaadt" in publish["advice_tg"]

        # Verify waiver-log update triggered (2 UPDATE entries from final response)
        assert len(update_waiver_calls) == 1, \
            f"Expected 1 waiver-log update, got {len(update_waiver_calls)}"
        block = update_waiver_calls[0]["advice"]
        assert "```waiver-log" in block
        assert "UPDATE|Nola|" in block
        assert "UPDATE|Pfaadt|" in block

        # No degrade notifications expected on happy path
        assert not notify_calls, f"Unexpected notify calls: {notify_calls}"
