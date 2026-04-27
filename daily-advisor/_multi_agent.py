"""_multi_agent — Phase 6 multi-agent orchestration helpers for fa_scan.py.

Provides:
- AgentResult dataclass: per-agent invocation outcome
- run_single_agent: one `claude -p` subprocess call
- run_parallel_agents: spawn N threads, each runs run_single_agent in parallel
- extract_json: fence-aware JSON extraction from stdout
- consensus_check_key: generic P1/top1 distribution check (debug + early-fail)
- aggregate_classifications: FA classify three-way vote tally
- count_dissent: review-step dissent counting (agree_on_p1 / agree_on_top1)
- all_parsed / any_parsed: gate helpers

Used by fa_scan._process_group_sp_v4 (v4 SP path). Mirrors
_tools/multi_agent_spike.py threading + JSON-parse pattern but as a production
module imported by fa_scan, not a CLI.

Threading model: one thread per agent, joins all before returning. `claude -p`
is I/O bound (subprocess + network), so GIL doesn't matter.

Failure modes:
- subprocess timeout → AgentResult.error == "timeout", parsed=None
- subprocess exception → AgentResult.error == "exception: <msg>", parsed=None
- non-zero exit → AgentResult.exit_code != 0, error captured from stderr,
  parsed still attempted (Claude sometimes returns valid JSON despite warning logs)
- JSON parse fail → AgentResult.parsed is None
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentResult:
    agent_id: str
    stdout: str
    stderr: str
    latency_s: float
    exit_code: int
    error: Optional[str]
    parsed: Optional[dict] = None


def run_single_agent(prompt: str, agent_id: str, timeout: int = 600) -> AgentResult:
    """Invoke `claude -p <prompt>` once, capture stdout/stderr/latency.

    Mirrors fa_scan._call_claude pattern (single-call, no retry — multi-agent
    orchestrator prefers clean signal on first failure; retries belong at the
    orchestrator level if needed).
    """
    t0 = time.time()
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout,
        )
        latency = round(time.time() - t0, 2)
        err: Optional[str] = None if result.returncode == 0 else f"exit_code {result.returncode}"
        ar = AgentResult(
            agent_id=agent_id,
            stdout=result.stdout,
            stderr=result.stderr,
            latency_s=latency,
            exit_code=result.returncode,
            error=err,
        )
    except subprocess.TimeoutExpired:
        ar = AgentResult(
            agent_id=agent_id, stdout="", stderr="",
            latency_s=timeout, exit_code=-1, error="timeout",
        )
    except Exception as e:
        ar = AgentResult(
            agent_id=agent_id, stdout="", stderr="",
            latency_s=round(time.time() - t0, 2),
            exit_code=-1, error=f"exception: {type(e).__name__}: {e}",
        )

    ar.parsed = extract_json(ar.stdout)
    return ar


def run_parallel_agents(prompt_template: str, fixture_data: str,
                        n_agents: int = 3, timeout: int = 600) -> list[AgentResult]:
    """Spawn n_agents `claude -p` subprocesses in parallel via threading.

    Each agent gets the same prompt + fixture, with agent_id substituted in
    the {agent_id} placeholder. Returns results in agent_1..N order.

    fixture_data is appended after the prompt with a `\n\n---\n\n` separator,
    matching the spike runner pattern (multi_agent_spike.py).
    """
    results: list[Optional[AgentResult]] = [None] * n_agents

    def worker(idx: int) -> None:
        agent_id = f"agent_{idx + 1}"
        agent_prompt = prompt_template.replace("{agent_id}", agent_id)
        full_prompt = f"{agent_prompt}\n\n---\n\n{fixture_data}"
        results[idx] = run_single_agent(full_prompt, agent_id, timeout=timeout)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_agents)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return [r for r in results if r is not None]


def extract_json(stdout: str) -> Optional[dict]:
    """Extract a JSON object from agent stdout (Claude often wraps in ``` fences)."""
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


def consensus_check_key(results: list[AgentResult],
                        key_path: list) -> tuple[bool, dict]:
    """Check whether all parsed agents agree on the value at key_path.

    key_path is a list of dict-keys / list-indices applied left-to-right, e.g.
    - ["ranking", 0]: SP step 1 each agent's ranking[0] = P1
    - ["final_ranking", 0]: master's P1 (single-agent, but useful for debug log)
    - ["ranked_top", 0, "name"]: FA step 2 master top1 name

    Returns (all_match, info) where info contains:
    - parsed_count: number of agents whose JSON parsed and contains key_path
    - distribution: {value: count} of values found
    - parse_failures: count of agents missing key_path or unparsed
    """
    parsed_values = []
    parse_failures = 0
    for r in results:
        if r.parsed is None:
            parse_failures += 1
            continue
        try:
            v = r.parsed
            for k in key_path:
                v = v[k]
            parsed_values.append(v)
        except (KeyError, IndexError, TypeError):
            parse_failures += 1

    if not parsed_values:
        return False, {"parsed_count": 0, "distribution": {}, "parse_failures": parse_failures}

    distribution: dict = {}
    for v in parsed_values:
        # Coerce non-hashable values (dict/list) to JSON string for tallying
        key = v if isinstance(v, (str, int, float, bool, type(None))) else \
            json.dumps(v, sort_keys=True, ensure_ascii=False)
        distribution[key] = distribution.get(key, 0) + 1

    all_match = len(distribution) == 1
    return all_match, {
        "parsed_count": len(parsed_values),
        "distribution": distribution,
        "parse_failures": parse_failures,
    }


def aggregate_classifications(results: list[AgentResult],
                              all_fa_names: list[str]) -> dict[str, str]:
    """Aggregate FA classify votes into majority verdicts.

    Each agent emits classifications: [{name, verdict ∈ {worth, not_worth, borderline}}, ...]
    Aggregation rule (per design doc §7.5=B):
    - ≥ 2 not_worth → "not_worth"
    - ≥ 2 worth → "worth"
    - else → "borderline" (mix incl. 1+1+1, 2 borderline, etc.)

    Parse failures count as 0 votes for that agent (conservative — missing
    votes don't push toward any classification).
    """
    tally: dict[str, dict[str, int]] = {
        n: {"worth": 0, "not_worth": 0, "borderline": 0} for n in all_fa_names
    }
    for r in results:
        if r.parsed is None:
            continue
        for c in r.parsed.get("classifications", []) or []:
            name = c.get("name")
            verdict = c.get("verdict")
            if name in tally and verdict in tally[name]:
                tally[name][verdict] += 1

    aggregated: dict[str, str] = {}
    for name, votes in tally.items():
        if votes["not_worth"] >= 2:
            aggregated[name] = "not_worth"
        elif votes["worth"] >= 2:
            aggregated[name] = "worth"
        else:
            aggregated[name] = "borderline"
    return aggregated


def count_dissent(results: list[AgentResult], key: str = "agree_on_p1") -> int:
    """Count how many review agents dissented on the given key.

    key options:
    - "agree_on_p1" — SP step 3 review
    - "agree_on_top1" — FA step 3 review

    A dissent = agree_on_X is exactly False. Parse failures and missing keys
    count as 0 dissent (conservative — failed reviewers don't trigger re-eval).
    """
    n = 0
    for r in results:
        if r.parsed is None:
            continue
        if r.parsed.get(key) is False:
            n += 1
    return n


def all_parsed(results: list[AgentResult]) -> bool:
    """Check if all agents returned parseable JSON. Used for early-fail gates."""
    return bool(results) and all(r.parsed is not None for r in results)


def any_parsed(results: list[AgentResult]) -> bool:
    """Check if at least one agent returned parseable JSON."""
    return any(r.parsed is not None for r in results)
