#!/usr/bin/env python3
"""spike_b1_baseline — Issue 008 baseline spike runner (B1 prompts, full mini-pipeline).

Re-runs Phase 6 SP + FA path against captured fixtures using the current B1-thin
prompts to measure baseline consensus rates. Unlike the older `multi_agent_spike.py`
(step 1 only), this runs both step 1 (3 agents) AND step 2 master per path so we
can capture both M1 (P1 match rate) and M4 (master borderline trigger rate).

Per-case pipeline:
  SP path:
    1. SP step1 — 3 parallel agents on `<date>_sp_step1.json`        → M1 SP
    2. SP step2 master — 1 master call (3 agents output + material)  → M4 SP
  FA path:
    3. FA classify — 3 parallel agents on `<date>_fa_classify.json`
    4. FA rank master — 1 master call (3 verdicts + survivors)
       M1 FA = did all 3 step1 agents classify master's top1 as 'worth'
       M4 FA = master.borderline_pairs non-empty

Output: per-case JSON to stdout + aggregate stats (mean/std) to stderr.

Usage (from daily-advisor/):
  python3 _tools/spike_b1_baseline.py --fixture-dir _tools/fixtures/b1_baseline
  python3 _tools/spike_b1_baseline.py --fixture-dir DIR --cases 2026-05-04 2026-05-08
  python3 _tools/spike_b1_baseline.py --fixture-dir DIR --skip-fa  # SP only

WARNING: 4 claude -p calls per case for SP path + 4 for FA = 8/case. 7 cases ≈ 56
calls against subscription. Don't run unsupervised.

Refs: issues/008-spike-fixture-baseline.md, docs/sp-b1-baseline.md
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

# Re-use production helpers — import paths assume cwd=daily-advisor/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _multi_agent import (  # noqa: E402
    aggregate_classifications,
    all_parsed,
    consensus_check_key,
    run_parallel_agents,
    run_single_agent,
)

_MODULE_DIR = Path(__file__).resolve().parent.parent
_TIMEOUT = 600


def _load_prompt(fname: str) -> str:
    return (_MODULE_DIR / fname).read_text(encoding="utf-8")


def _list_cases(fixture_dir: Path) -> list[str]:
    """Return sorted list of dates that have BOTH sp_step1 + fa_classify fixtures."""
    sp_dates = {f.stem.removesuffix("_sp_step1")
                for f in fixture_dir.glob("*_sp_step1.json")}
    fa_dates = {f.stem.removesuffix("_fa_classify")
                for f in fixture_dir.glob("*_fa_classify.json")}
    return sorted(sp_dates & fa_dates)


def _run_sp_path(case: str, sp_step1_payload: str) -> dict:
    """Run SP step1 (3 agents) + step2 master. Return per-case metrics."""
    t0 = time.time()
    print(f"  [{case}] SP step1: 3 agents...", file=sys.stderr)
    step1_results = run_parallel_agents(
        _load_prompt("prompt_phase6_sp_step1_rank.txt"),
        sp_step1_payload, n_agents=3, timeout=_TIMEOUT,
    )

    parsed_count = sum(1 for r in step1_results if r.parsed is not None)
    sp_p1_match = None
    sp_p1_distribution = None
    if all_parsed(step1_results):
        match, info = consensus_check_key(step1_results, ["ranking", 0])
        sp_p1_match = match
        sp_p1_distribution = info["distribution"]

    sp_master_borderline = None
    sp_master_p1 = None
    sp_borderline_pairs = None
    master_parsed = False
    if parsed_count > 0:
        # Build step2 payload (mirrors _phase6_sp._build_step2_payload)
        material = json.loads(sp_step1_payload)
        step2_obj = {
            "agents_step1": [
                {"agent_id": r.agent_id, **(r.parsed or {"error": r.error})}
                for r in step1_results
            ],
            "material": material,
        }
        step2_payload = json.dumps(step2_obj, ensure_ascii=False, indent=2,
                                   default=str)
        print(f"  [{case}] SP step2 master...", file=sys.stderr)
        master = run_single_agent(
            _load_prompt("prompt_phase6_sp_step2_master.txt") + "\n\n---\n\n" + step2_payload,
            "master", timeout=_TIMEOUT,
        )
        if master.parsed is not None:
            master_parsed = True
            sp_borderline_pairs = master.parsed.get("borderline_pairs") or []
            sp_master_borderline = bool(sp_borderline_pairs)
            sp_master_p1 = (master.parsed.get("final_ranking") or [None])[0]

    return {
        "case": case,
        "sp_step1_parsed": parsed_count,
        "sp_p1_match": sp_p1_match,
        "sp_p1_distribution": sp_p1_distribution,
        "sp_master_parsed": master_parsed,
        "sp_master_p1": sp_master_p1,
        "sp_master_borderline": sp_master_borderline,
        "sp_borderline_pairs": sp_borderline_pairs,
        "sp_path_seconds": round(time.time() - t0, 1),
    }


def _run_fa_path(case: str, fa_classify_payload: str) -> dict:
    """Run FA classify (3 agents) + rank master. Return per-case metrics."""
    t0 = time.time()
    print(f"  [{case}] FA classify: 3 agents...", file=sys.stderr)
    classify_results = run_parallel_agents(
        _load_prompt("prompt_phase6_fa_step1_classify.txt"),
        fa_classify_payload, n_agents=3, timeout=_TIMEOUT,
    )
    parsed_count = sum(1 for r in classify_results if r.parsed is not None)

    # Aggregate classify into worth/borderline survivors
    payload_obj = json.loads(fa_classify_payload)
    fa_names = [f["name"] for f in payload_obj.get("fa_candidates", [])]
    aggregated = aggregate_classifications(classify_results, fa_names)
    survivors_lookup = {
        f["name"]: f for f in payload_obj.get("fa_candidates", [])
        if aggregated.get(f["name"]) in ("worth", "borderline")
    }

    fa_master_top1 = None
    fa_master_borderline = None
    fa_borderline_pairs = None
    fa_master_parsed = False
    fa_top1_unanimous_worth = None

    if not survivors_lookup:
        print(f"  [{case}] FA: 0 survivors after classify aggregation, skipping master",
              file=sys.stderr)
    elif parsed_count == 0:
        print(f"  [{case}] FA: classify all parse-failed, skipping master",
              file=sys.stderr)
    else:
        # Build rank master payload (mirrors _phase6_sp._build_fa_rank_payload)
        rank_obj = {
            "agents_step1": [
                {"agent_id": r.agent_id, **(r.parsed or {"error": r.error})}
                for r in classify_results
            ],
            "aggregated_verdicts": aggregated,
            "anchor": payload_obj.get("anchor"),
            "fa_survivors": list(survivors_lookup.values()),
        }
        rank_payload = json.dumps(rank_obj, ensure_ascii=False, indent=2,
                                  default=str)
        print(f"  [{case}] FA rank master ({len(survivors_lookup)} survivors)...",
              file=sys.stderr)
        master = run_single_agent(
            _load_prompt("prompt_phase6_fa_step2_rank.txt") + "\n\n---\n\n" + rank_payload,
            "fa_master", timeout=_TIMEOUT,
        )
        if master.parsed is not None:
            fa_master_parsed = True
            ranked_top = master.parsed.get("ranked_top") or []
            if ranked_top:
                fa_master_top1 = ranked_top[0].get("name")
            fa_borderline_pairs = master.parsed.get("borderline_pairs") or []
            fa_master_borderline = bool(fa_borderline_pairs)

            # M1 FA = did all 3 classify agents classify master.top1 as 'worth'?
            if fa_master_top1:
                top1_verdicts = []
                for r in classify_results:
                    if r.parsed is None:
                        continue
                    for c in r.parsed.get("classifications", []) or []:
                        if c.get("name") == fa_master_top1:
                            top1_verdicts.append(c.get("verdict"))
                            break
                fa_top1_unanimous_worth = (
                    len(top1_verdicts) == 3
                    and all(v == "worth" for v in top1_verdicts)
                )

    return {
        "case": case,
        "fa_classify_parsed": parsed_count,
        "fa_aggregated": aggregated,
        "fa_survivors_count": len(survivors_lookup),
        "fa_master_parsed": fa_master_parsed,
        "fa_master_top1": fa_master_top1,
        "fa_master_borderline": fa_master_borderline,
        "fa_borderline_pairs": fa_borderline_pairs,
        "fa_top1_unanimous_worth": fa_top1_unanimous_worth,
        "fa_path_seconds": round(time.time() - t0, 1),
    }


def _aggregate_stats(per_case: list[dict], skip_fa: bool, skip_sp: bool) -> dict:
    """Compute baseline mean/std for M1 + M4 across cases."""
    def _rate(values: list[bool | None]) -> tuple[float | None, float | None, int]:
        vals = [1.0 if v is True else 0.0 for v in values if v is not None]
        if not vals:
            return None, None, 0
        mean = statistics.mean(vals)
        # population std (single sample interpreted as one observation, so use stdev with n-1)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        return round(mean, 3), round(sd, 3), len(vals)

    summary: dict = {"n_cases": len(per_case)}
    if not skip_sp:
        m1_sp_mean, m1_sp_sd, n = _rate([c.get("sp_p1_match") for c in per_case])
        m4_sp_mean, m4_sp_sd, _ = _rate([c.get("sp_master_borderline") for c in per_case])
        summary["sp"] = {
            "M1_p1_match_rate": {"mean": m1_sp_mean, "std": m1_sp_sd, "n": n},
            "M4_master_borderline_rate": {"mean": m4_sp_mean, "std": m4_sp_sd, "n": n},
            "M1_minus_1sd_threshold": (
                round(m1_sp_mean - m1_sp_sd, 3)
                if m1_sp_mean is not None and m1_sp_sd is not None else None
            ),
        }
    if not skip_fa:
        m1_fa_mean, m1_fa_sd, n = _rate([c.get("fa_top1_unanimous_worth") for c in per_case])
        m4_fa_mean, m4_fa_sd, _ = _rate([c.get("fa_master_borderline") for c in per_case])
        summary["fa"] = {
            "M1_top1_unanimous_worth_rate": {"mean": m1_fa_mean, "std": m1_fa_sd, "n": n},
            "M4_master_borderline_rate": {"mean": m4_fa_mean, "std": m4_fa_sd, "n": n},
            "M1_minus_1sd_threshold": (
                round(m1_fa_mean - m1_fa_sd, 3)
                if m1_fa_mean is not None and m1_fa_sd is not None else None
            ),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fixture-dir", required=True,
                        help="Directory containing <date>_sp_step1.json + <date>_fa_classify.json pairs")
    parser.add_argument("--cases", nargs="*",
                        help="Specific case dates to run (default: all in dir)")
    parser.add_argument("--skip-sp", action="store_true",
                        help="Skip SP path (FA only)")
    parser.add_argument("--skip-fa", action="store_true",
                        help="Skip FA path (SP only)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List cases + estimated calls, don't invoke claude -p")
    args = parser.parse_args()

    fixture_dir = Path(args.fixture_dir)
    if not fixture_dir.is_dir():
        print(f"fixture-dir not found: {fixture_dir}", file=sys.stderr)
        return 1

    available = _list_cases(fixture_dir)
    if args.cases:
        cases = [c for c in args.cases if c in available]
        missing = set(args.cases) - set(available)
        if missing:
            print(f"⚠️ skipping cases without complete fixture pairs: {sorted(missing)}",
                  file=sys.stderr)
    else:
        cases = available

    if not cases:
        print("No complete fixture pairs found.", file=sys.stderr)
        return 1

    calls_per_case = (4 if not args.skip_sp else 0) + (4 if not args.skip_fa else 0)
    total_calls = calls_per_case * len(cases)
    print(f"Cases: {len(cases)} | calls/case: {calls_per_case} | total claude -p calls: {total_calls}",
          file=sys.stderr)

    if args.dry_run:
        print("=== DRY RUN ===", file=sys.stderr)
        for c in cases:
            print(f"  {c}", file=sys.stderr)
        return 0

    per_case: list[dict] = []
    for case in cases:
        case_data: dict = {"case": case}
        if not args.skip_sp:
            sp_payload = (fixture_dir / f"{case}_sp_step1.json").read_text(encoding="utf-8")
            case_data.update(_run_sp_path(case, sp_payload))
        if not args.skip_fa:
            fa_payload = (fixture_dir / f"{case}_fa_classify.json").read_text(encoding="utf-8")
            case_data.update(_run_fa_path(case, fa_payload))
        per_case.append(case_data)

    summary = _aggregate_stats(per_case, args.skip_fa, args.skip_sp)

    output = {"per_case": per_case, "baseline": summary}
    print(json.dumps(output, indent=2, ensure_ascii=False))

    print(file=sys.stderr)
    print("=== Baseline Summary ===", file=sys.stderr)
    print(json.dumps(summary, indent=2, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
