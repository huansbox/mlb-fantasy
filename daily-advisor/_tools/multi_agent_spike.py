#!/usr/bin/env python3
"""multi_agent_spike — Phase 6 simplified spike (D2=C from 2026-04-26 decisions).

Tests Phase 6 multi-agent step 1 only: 3 parallel `claude -p` agents each
independently rank "weakest 4 SP P1-P4" given a fixture. Measures:

  1. P1 consensus rate — do all 3 agents pick the same P1?
  2. Wall-clock latency — how long does parallel spawn take vs sequential?
  3. JSON parse success — does each agent return well-formed structured output?

Does NOT run the full 7-step Phase 6 flow (no master decision, no review,
no FA line). The intent is to derisk the most critical unknowns before
committing to Stage B-F implementation. Step 2/3/etc are exercised in
Stage E parallel verification, per docs/v4-cutover-plan.md.

Usage (from daily-advisor/):
    python3 _tools/multi_agent_spike.py
    python3 _tools/multi_agent_spike.py \\
        --fixture _tools/fixtures/spike_2026_04_22_4sp.json \\
        --prompt _tools/prompts/spike_step1.txt \\
        --agents 3 \\
        --timeout 180

Output: stdout summary + per-agent raw JSON. Pipe to file for results doc.

WARNING: Each run consumes 3x `claude -p` invocations against the user's
Claude subscription. Don't run unsupervised (per docs/phase6-multi-agent-spike.md
§8 "needs user present to supervise").
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

DEFAULT_FIXTURE = "_tools/fixtures/spike_2026_04_22_4sp.json"
DEFAULT_PROMPT = "_tools/prompts/spike_step1.txt"
DEFAULT_TIMEOUT = 180  # 3 min per agent
DEFAULT_AGENTS = 3


def run_claude_p(prompt: str, timeout: int) -> dict:
    """Invoke `claude -p <prompt>` once, capture stdout/stderr/latency.

    Mirrors fa_scan._call_claude pattern (single-call, no retry — spike
    wants clean signal even on first failure).
    """
    t0 = time.time()
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "latency_s": round(time.time() - t0, 2),
            "exit_code": result.returncode,
            "error": None,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "",
            "latency_s": timeout,
            "exit_code": -1,
            "error": "timeout",
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": "",
            "latency_s": round(time.time() - t0, 2),
            "exit_code": -1,
            "error": f"{type(e).__name__}: {e}",
        }


def parallel_agents(prompt_template: str, fixture_data: str, n_agents: int,
                    timeout: int) -> tuple[list[dict], float]:
    """Spawn n_agents `claude -p` subprocesses in parallel via threading.

    Each agent gets the same prompt + fixture, with agent_id substituted in
    the {agent_id} placeholder. Returns (per-agent results, wall-clock total).
    """
    results: list[dict] = [None] * n_agents

    def worker(idx: int):
        agent_prompt = prompt_template.replace("{agent_id}", f"agent_{idx + 1}")
        full_prompt = f"{agent_prompt}\n\n---\n\n{fixture_data}"
        result = run_claude_p(full_prompt, timeout)
        result["agent_id"] = f"agent_{idx + 1}"
        results[idx] = result

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_agents)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall_time = round(time.time() - t0, 2)
    return results, wall_time


def extract_json(stdout: str) -> dict | None:
    """Extract a JSON object from agent stdout (Claude often wraps in fences)."""
    if not stdout:
        return None
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stdout, re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1)
    else:
        first_brace = stdout.find("{")
        last_brace = stdout.rfind("}")
        if first_brace == -1 or last_brace <= first_brace:
            return None
        candidate = stdout[first_brace : last_brace + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def analyze_results(results: list[dict]) -> dict:
    """Compute consensus metrics from per-agent results."""
    parsed = []
    for r in results:
        obj = extract_json(r["stdout"]) if r["error"] is None else None
        parsed.append({
            "agent_id": r["agent_id"],
            "latency_s": r["latency_s"],
            "exit_code": r["exit_code"],
            "error": r["error"],
            "json_parsed": obj is not None,
            "ranking": (obj or {}).get("ranking"),
            "p1": ((obj or {}).get("ranking") or [None])[0],
            "rationale": (obj or {}).get("rationale"),
        })

    p1_set = {p["p1"] for p in parsed if p["p1"]}
    p1_consensus = "all agree" if len(p1_set) == 1 and parsed[0]["p1"] else (
        "no parse" if not p1_set else "split"
    )

    # Pairwise agreement: how many of 3 pairs match exactly on ranking?
    valid_rankings = [p["ranking"] for p in parsed if p["ranking"]]
    pair_matches = 0
    pair_total = 0
    for i in range(len(valid_rankings)):
        for j in range(i + 1, len(valid_rankings)):
            pair_total += 1
            if valid_rankings[i] == valid_rankings[j]:
                pair_matches += 1

    return {
        "per_agent": parsed,
        "p1_consensus": p1_consensus,
        "p1_distribution": {p1: sum(1 for x in parsed if x["p1"] == p1) for p1 in p1_set},
        "ranking_pairwise_match": f"{pair_matches}/{pair_total}" if pair_total else "n/a",
        "json_parse_rate": sum(1 for p in parsed if p["json_parsed"]) / len(parsed),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fixture", default=DEFAULT_FIXTURE,
                        help=f"Fixture JSON path (default {DEFAULT_FIXTURE})")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT,
                        help=f"Prompt template path (default {DEFAULT_PROMPT})")
    parser.add_argument("--agents", type=int, default=DEFAULT_AGENTS,
                        help=f"Number of parallel agents (default {DEFAULT_AGENTS})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Per-agent timeout in seconds (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Load fixture + prompt and print combined input but do NOT call claude -p")
    args = parser.parse_args()

    fixture_path = Path(args.fixture)
    prompt_path = Path(args.prompt)
    if not fixture_path.exists():
        print(f"Fixture not found: {fixture_path}", file=sys.stderr)
        return 1
    if not prompt_path.exists():
        print(f"Prompt not found: {prompt_path}", file=sys.stderr)
        return 1

    fixture_data = fixture_path.read_text(encoding="utf-8")
    prompt_template = prompt_path.read_text(encoding="utf-8")

    if args.dry_run:
        print("=== DRY RUN — no claude -p invocation ===", file=sys.stderr)
        print(f"Prompt template ({prompt_path}):", file=sys.stderr)
        print(prompt_template, file=sys.stderr)
        print(f"\nFixture ({fixture_path}):", file=sys.stderr)
        print(fixture_data, file=sys.stderr)
        print(f"\nWould spawn {args.agents} parallel agents with timeout {args.timeout}s each.",
              file=sys.stderr)
        return 0

    print(f"Spawning {args.agents} parallel claude -p agents (timeout {args.timeout}s each)...",
          file=sys.stderr)
    print(f"  fixture: {fixture_path}", file=sys.stderr)
    print(f"  prompt:  {prompt_path}", file=sys.stderr)
    print(file=sys.stderr)

    results, wall_time = parallel_agents(prompt_template, fixture_data,
                                          args.agents, args.timeout)
    analysis = analyze_results(results)

    # Stdout: structured summary for results doc
    summary = {
        "spike": "phase6-step1-simplified",
        "fixture": str(fixture_path),
        "n_agents": args.agents,
        "wall_time_total_s": wall_time,
        "wall_time_max_per_agent_s": max(r["latency_s"] for r in results),
        "wall_time_avg_per_agent_s": round(sum(r["latency_s"] for r in results) / len(results), 2),
        "parallelism_speedup": round(
            sum(r["latency_s"] for r in results) / wall_time, 2
        ) if wall_time > 0 else None,
        "analysis": analysis,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # Stderr: human-readable digest
    print(file=sys.stderr)
    print("=== Spike Result Summary ===", file=sys.stderr)
    print(f"Wall time (parallel total): {wall_time}s", file=sys.stderr)
    print(f"Per-agent latency (max/avg): {summary['wall_time_max_per_agent_s']}s / "
          f"{summary['wall_time_avg_per_agent_s']}s", file=sys.stderr)
    print(f"Parallelism speedup: {summary['parallelism_speedup']}x", file=sys.stderr)
    print(f"JSON parse rate: {analysis['json_parse_rate']:.0%}", file=sys.stderr)
    print(f"P1 consensus: {analysis['p1_consensus']}", file=sys.stderr)
    if analysis["p1_distribution"]:
        print(f"P1 votes: {analysis['p1_distribution']}", file=sys.stderr)
    print(f"Pairwise full-ranking match: {analysis['ranking_pairwise_match']}", file=sys.stderr)
    print(file=sys.stderr)
    print("Per-agent rankings:", file=sys.stderr)
    for p in analysis["per_agent"]:
        if p["error"]:
            print(f"  {p['agent_id']}: ERROR — {p['error']}", file=sys.stderr)
        elif not p["json_parsed"]:
            print(f"  {p['agent_id']}: ⚠️ JSON parse failed (latency {p['latency_s']}s)",
                  file=sys.stderr)
        else:
            print(f"  {p['agent_id']}: {p['ranking']} (latency {p['latency_s']}s)",
                  file=sys.stderr)

    return 0 if analysis["json_parse_rate"] == 1.0 else 2


if __name__ == "__main__":
    sys.exit(main())
