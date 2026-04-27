#!/usr/bin/env python3
"""diff_v2_v4_outputs.py — Stage E parallel cutover comparison.

Fetches v2 SP advice (from GitHub Issue archive) and v4 SP advice (from
VPS fa_scan_v4.log), parses key signals (drop P1, top FA recommendation,
action), and prints a markdown-ready side-by-side report for pasting
into docs/v4-cutover-parallel-log.md.

Usage:
  python3 _tools/diff_v2_v4_outputs.py                       # today, ssh
  python3 _tools/diff_v2_v4_outputs.py --date 2026-04-28
  python3 _tools/diff_v2_v4_outputs.py --v4-log /tmp/v4.log  # local file
  python3 _tools/diff_v2_v4_outputs.py --v4-log ssh          # default
  python3 _tools/diff_v2_v4_outputs.py --no-v2               # skip v2 fetch
  python3 _tools/diff_v2_v4_outputs.py --no-v4               # skip v4 fetch
  python3 _tools/diff_v2_v4_outputs.py --raw                 # dump full advice text

Notes:
- v2 source = GitHub Issue titled "[FA Scan SP] {date}" — body's `## Analysis`
  block is the advice text.
- v4 source = log file accumulating cron stdout+stderr from
  `SP_FRAMEWORK_VERSION=v4 fa_scan.py --no-send --no-issue --no-waiver-log`.
  Each day starts with `[FA Scan] Daily scan {date}...` (stderr); v4 final
  emits `[Phase 6] {action} — {reason}` on stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta

TPE = timezone(timedelta(hours=8))

VPS_HOST = "root@107.175.30.172"
VPS_LOG_PATH = "/var/log/fa-scan-v4.log"
GH_REPO = "huansbox/mlb-fantasy"


# ── v2 fetch (GitHub Issue) ──────────────────────────────────────────────


def fetch_v2_issue_body(date: str) -> str | None:
    """Fetch GitHub Issue body for `[FA Scan SP] {date}`. Returns None if absent."""
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", GH_REPO,
             "--search", f"[FA Scan SP] {date} in:title",
             "--state", "all", "--limit", "5",
             "--json", "number,title"],
            capture_output=True, text=True, encoding="utf-8", timeout=30, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"[v2] gh issue list failed: {e.stderr.strip()}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("[v2] gh CLI not installed; install or use --no-v2", file=sys.stderr)
        return None

    issues = json.loads(result.stdout or "[]")
    target_title = f"[FA Scan SP] {date}"
    matched = [iss for iss in issues if iss["title"] == target_title]
    if not matched:
        print(f"[v2] no Issue found titled {target_title!r}", file=sys.stderr)
        return None

    issue_num = matched[0]["number"]
    try:
        body_result = subprocess.run(
            ["gh", "issue", "view", str(issue_num), "--repo", GH_REPO,
             "--json", "body"],
            capture_output=True, text=True, encoding="utf-8", timeout=30, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"[v2] gh issue view failed: {e.stderr.strip()}", file=sys.stderr)
        return None

    return json.loads(body_result.stdout)["body"]


def extract_v2_advice(issue_body: str) -> str:
    """Pull the `## Analysis` section out of an Issue body.

    Body shape: `## Analysis\n\n{advice}\n\n---\n\n<details>...</details>`.
    Advice itself can contain `---` separator lines, so anchor on `<details>`
    (the Raw Data block) as the true terminator.
    """
    m = re.search(r"## Analysis\s*\n(.*?)(?:\n---\s*\n<details>|\Z)",
                  issue_body, re.DOTALL)
    return m.group(1).strip() if m else issue_body.strip()


# ── v4 fetch (log file) ──────────────────────────────────────────────────


def fetch_v4_log_text(log_arg: str) -> str | None:
    """Read v4 log. `log_arg='ssh'` → ssh into VPS; otherwise local path."""
    if log_arg == "ssh":
        try:
            result = subprocess.run(
                ["ssh", VPS_HOST, f"cat {VPS_LOG_PATH}"],
                capture_output=True, text=True, encoding="utf-8", timeout=30, check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"[v4] ssh fetch failed: {e.stderr.strip()}", file=sys.stderr)
            return None
        except FileNotFoundError:
            print("[v4] ssh not available; pass --v4-log <local-path>", file=sys.stderr)
            return None

    try:
        with open(log_arg, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"[v4] log file not found: {log_arg}", file=sys.stderr)
        return None


def extract_v4_advice(log_text: str, date: str) -> str | None:
    """Slice the log block for `date` and pull the [Phase 6] advice.

    A daily run begins with `[FA Scan] Daily scan {date}...`. The advice
    is `[Phase 6] ...` printed on stdout near the end of that block.
    """
    start_marker = f"[FA Scan] Daily scan {date}"
    start = log_text.find(start_marker)
    if start < 0:
        return None
    next_run = re.search(r"\n\[FA Scan\] Daily scan \d{4}-\d{2}-\d{2}", log_text[start + 1:])
    end = (start + 1 + next_run.start()) if next_run else len(log_text)
    block = log_text[start:end]

    phase6 = re.search(r"\[Phase 6\][^\n]*\n(?:.*?)(?=\n\[FA Scan\]|\n\s*Layer |\Z)",
                       block, re.DOTALL)
    if not phase6:
        return None
    return phase6.group(0).strip()


# ── parsers ──────────────────────────────────────────────────────────────


def parse_v2_signals(advice: str) -> dict:
    """Extract drop P1, top FA, action verdict from v2 SP advice text."""
    p1 = None
    m = re.search(r"\*\*P1\s+([^*]+?)\*\*\s+urgency", advice)
    if m:
        p1 = m.group(1).strip()

    top_fa = None
    fa_judgment = None
    # ACTION/END_ACTION markers are stripped by fa_scan._publish; find the
    # first numbered FA list item directly. Pass-section uses bullet ("- **")
    # not numbered, so this won't false-match.
    first_fa = re.search(r"^\s*1\.\s*\*\*([^*]+?)\*\*[^—\n]*—\s*([^\n]+)",
                         advice, re.MULTILINE)
    if first_fa:
        top_fa = first_fa.group(1).strip()
        fa_judgment = first_fa.group(2).strip()

    action = None
    waiver_block = re.search(r"```waiver-log\s*\n(.*?)```", advice, re.DOTALL)
    if waiver_block:
        for line in waiver_block.group(1).splitlines():
            parts = line.strip().split("|")
            if len(parts) >= 5 and parts[0] == "NEW" and "立即行動" in parts[4]:
                action = f"add {parts[1]}"
                break
        if action is None and waiver_block.group(1).strip():
            action = "watch (NEW/UPDATE entries)"
        elif action is None:
            action = "pass / no-op"
    if action is None and fa_judgment:
        if "立即取代" in fa_judgment or "取代" in fa_judgment:
            action = f"add {top_fa}" if top_fa else "add (FA)"
        elif "觀察" in fa_judgment:
            action = "watch"

    return {"p1": p1, "top_fa": top_fa, "fa_judgment": fa_judgment, "action": action}


def parse_v4_signals(advice: str) -> dict:
    """Extract action / drop / add from v4 [Phase 6] telegram_summary line."""
    first_line = advice.splitlines()[0] if advice else ""
    summary = re.sub(r"^\[Phase 6\]\s*", "", first_line).strip()

    action_kw = None
    drop = None
    add = None
    if summary.startswith("drop ") and " add " in summary:
        m = re.match(r"drop\s+(.+?)\s+add\s+([^—\-]+)", summary)
        if m:
            drop = m.group(1).strip()
            add = m.group(2).strip()
            action_kw = "drop_X_add_Y"
    elif summary.startswith("watch"):
        action_kw = "watch"
    elif summary.startswith("pass"):
        action_kw = "pass"
    return {"action": action_kw, "drop": drop, "add": add, "summary": summary}


# ── render ───────────────────────────────────────────────────────────────


def render_report(date: str, v2_advice: str | None, v4_advice: str | None,
                  raw: bool) -> str:
    out = [f"# v2/v4 SP diff — {date}\n"]

    v2_sig = parse_v2_signals(v2_advice) if v2_advice else None
    v4_sig = parse_v4_signals(v4_advice) if v4_advice else None

    out.append("## Summary\n")
    out.append("| field | v2 (live) | v4 (parallel) |")
    out.append("|---|---|---|")
    fields = [
        ("drop P1",    "p1",        "drop"),
        ("top FA",     "top_fa",    "add"),
        ("action",     "action",    "action"),
    ]
    for label, v2_key, v4_key in fields:
        v2_val = (v2_sig or {}).get(v2_key) or "—"
        v4_val = (v4_sig or {}).get(v4_key) or "—"
        out.append(f"| {label} | {v2_val} | {v4_val} |")

    if v4_sig and v4_sig.get("summary"):
        out.append(f"\n**v4 telegram**: `[Phase 6] {v4_sig['summary']}`")

    diverged = []
    if v2_sig and v4_sig:
        v2_target = v2_sig.get("p1")
        v4_target = v4_sig.get("drop")
        if v2_target and v4_target and v2_target != v4_target:
            diverged.append(f"- drop target: v2={v2_target} / v4={v4_target}")
        if v2_sig.get("top_fa") and v4_sig.get("add") and v2_sig["top_fa"] != v4_sig["add"]:
            diverged.append(f"- add target: v2={v2_sig['top_fa']} / v4={v4_sig['add']}")
        if v2_sig.get("action") and v4_sig.get("action"):
            v2_kind = "swap" if v2_sig["action"].startswith("add ") else v2_sig["action"]
            v4_kind = "swap" if v4_sig["action"] == "drop_X_add_Y" else v4_sig["action"]
            if v2_kind != v4_kind:
                diverged.append(f"- action kind: v2={v2_kind} / v4={v4_kind}")
    if diverged:
        out.append("\n**Diverged**:")
        out.extend(diverged)
    elif v2_sig and v4_sig:
        out.append("\n**Aligned** ✅ (P1 / top FA / action kind all match)")

    if raw:
        out.append("\n## v2 advice (raw)\n")
        out.append("```")
        out.append(v2_advice or "(missing)")
        out.append("```")
        out.append("\n## v4 advice (raw)\n")
        out.append("```")
        out.append(v4_advice or "(missing)")
        out.append("```")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Stage E v2/v4 SP advice diff")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today TPE)")
    parser.add_argument("--v4-log", default="ssh",
                        help="'ssh' (default — fetch from VPS) or local log path")
    parser.add_argument("--no-v2", action="store_true",
                        help="Skip v2 GitHub Issue fetch")
    parser.add_argument("--no-v4", action="store_true",
                        help="Skip v4 log fetch")
    parser.add_argument("--raw", action="store_true",
                        help="Include raw advice text in report")
    args = parser.parse_args()

    date = args.date or datetime.now(TPE).strftime("%Y-%m-%d")

    v2_advice = None
    if not args.no_v2:
        body = fetch_v2_issue_body(date)
        if body:
            v2_advice = extract_v2_advice(body)

    v4_advice = None
    if not args.no_v4:
        log_text = fetch_v4_log_text(args.v4_log)
        if log_text:
            v4_advice = extract_v4_advice(log_text, date)
            if v4_advice is None:
                print(f"[v4] no block found for {date} in log", file=sys.stderr)

    print(render_report(date, v2_advice, v4_advice, raw=args.raw))


if __name__ == "__main__":
    main()
