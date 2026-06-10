"""_judge_demo_runner — real-claude judge panel audit harness (issue 030).

Builds demo accounts from REAL MLB byDateRange production (names resolved
via MLB API search — never hardcoded ids), runs the actual judge panel
(2 claude -p calls from neutral cwd), and prints payload + per-judge
output + consensus + mapped outcome next to the mechanical scorecard for
manual audit (PRD risk note: 第一批裁判輸出必須人工對照機械比數底稿;
系統性唱反調 → 回頭修裁判 prompt → 重跑本 harness 驗證).

Usage (any already-elapsed window start works):
    python3 _tools/_judge_demo_runner.py --start 2026-05-15 \
        --pairs "Joc Pederson:Luis Arraez:replace,Kody Clemens:Luis Arraez:watch"

Costs 2 claude -p calls (+retries on contract violation). Not a cron
script; never touches Yahoo.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows cp950 console

from _backtest_lib import build_judge_payload, compare_batter_categories
from backtest_batter import run_judge_panel
from backtest_track import search_mlb_id


def build_demo_rows(pairs: list[tuple[str, str, str]], start: date) -> list[dict]:
    from backtest_batter import fetch_batter_window_stats

    rows = []
    for player, vs, kind in pairs:
        player_id = search_mlb_id(player)
        vs_id = search_mlb_id(vs)
        if not player_id or not vs_id:
            raise SystemExit(f"id resolution failed: {player}={player_id} "
                             f"{vs}={vs_id}")
        card = compare_batter_categories(
            fetch_batter_window_stats(player_id, start),
            fetch_batter_window_stats(vs_id, start))
        rows.append({"kind": kind, "player": player, "vs": vs,
                     "outcome": "pending-judge", "scorecard": card})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", required=True,
                        help="Observation window start (YYYY-MM-DD); pick a "
                             "date ≥21 days ago so the window has elapsed")
    parser.add_argument("--pairs", required=True,
                        help="Comma-separated player:vs:kind triples "
                             "(kind ∈ replace/watch)")
    args = parser.parse_args(argv)

    pairs = []
    for chunk in args.pairs.split(","):
        player, vs, kind = (p.strip() for p in chunk.split(":"))
        assert kind in ("replace", "watch"), kind
        pairs.append((player, vs, kind))

    rows = build_demo_rows(pairs, date.fromisoformat(args.start))
    payload, _ = build_judge_payload(rows, window_days=21)
    print("=== payload sent to both judges ===")
    print(payload)

    status = run_judge_panel(rows)  # real _claude_judge_runner
    print(f"\n=== panel status: {json.dumps(status)} ===")
    for row in rows:
        print(f"\n--- {row['kind']}: {row['player']} (A) vs {row['vs']} (B) ---")
        card = row["scorecard"]
        if card:
            print(f"機械比數 A {card['wins']}W-{card['losses']}L-{card['ties']}T")
            for cat, c in card["categories"].items():
                print(f"  {cat}: A={c['player']} B={c['vs']} ({c['result']})")
        print(f"judge: {json.dumps(row.get('judge'), ensure_ascii=False)}")
        print(f"outcome: {row['outcome']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
