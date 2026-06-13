"""One-off paired A/B runner for issue 037 trigger-schema-constraint prompt change.

Methodology per PRD Testing Decisions (lever 2 lesson): same payload, same
model, neutral cwd; judge by output_tokens + trigger machine-parseability,
never by visible text alone.

A = pre-037 prompt (git master), B = working-tree prompt (037 trigger grammar).
Payload = verbatim Layer 4 mechanical report from production issue #306 (reused
from the 028 A/B — same real batter payload).

Usage: uv run python _tools/_ab_037_runner.py
Writes ab_037_A.json / ab_037_B.json (full claude CLI JSON) + a summary to
stdout. Throwaway tool — delete after 037 ships.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # daily-advisor/
REPO = HERE.parent
OUT_DIR = HERE / "_tools"

PAYLOAD_START = "=== Layer 4 Mechanical Report (打者) ===\n"
PAYLOAD_END = "\n\n=== Layer 5 Claude Output"


def extract_payload() -> str:
    body = json.loads(
        (HERE / "tests/fixtures/issue_306_batter.json").read_text(encoding="utf-8")
    )["body"]
    start = body.index(PAYLOAD_START) + len(PAYLOAD_START)
    end = body.index(PAYLOAD_END, start)
    return body[start:end]


def prompt_a() -> str:
    return subprocess.run(
        ["git", "show", "master:daily-advisor/prompt_fa_scan_pass2_batter.txt"],
        cwd=REPO, capture_output=True, text=True, check=True, encoding="utf-8",
    ).stdout


def prompt_b() -> str:
    return (HERE / "prompt_fa_scan_pass2_batter.txt").read_text(encoding="utf-8")


def run_one(tag: str, prompt: str, payload: str, neutral_cwd: str) -> dict:
    full = prompt.replace("{data}", payload)
    print(f"[{tag}] calling claude -p ({len(full)} chars)...", file=sys.stderr)
    # Prompt goes via stdin — Windows argv is capped at ~32K chars.
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI not found in PATH")
    result = subprocess.run(
        [exe, "-p", "--output-format", "json"],
        input=full, capture_output=True, text=True, encoding="utf-8",
        cwd=neutral_cwd, timeout=900,
    )
    if result.returncode != 0:
        raise RuntimeError(f"[{tag}] claude -p failed: {result.stderr[:500]}")
    data = json.loads(result.stdout)
    (OUT_DIR / f"ab_037_{tag}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def main() -> int:
    payload = extract_payload()
    print(f"payload: {len(payload)} chars", file=sys.stderr)
    # Windows: claude -p leaves an open handle in cwd → TemporaryDirectory
    # cleanup races and masks the real error. Use a non-auto-deleted dir.
    neutral = tempfile.mkdtemp(prefix="ab037_")
    a = run_one("A", prompt_a(), payload, neutral)
    b = run_one("B", prompt_b(), payload, neutral)

    for tag, d in (("A", a), ("B", b)):
        u = d.get("usage") or {}
        print(f"--- {tag} ---")
        print(f"output_tokens: {u.get('output_tokens')}")
        print(f"input_tokens: {u.get('input_tokens')} "
              f"(cache_read {u.get('cache_read_input_tokens')})")
        print(f"cost_usd: {d.get('total_cost_usd')}")
        print(f"duration_ms: {d.get('duration_ms')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
