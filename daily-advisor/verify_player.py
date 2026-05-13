#!/usr/bin/env python3
"""
Verify player identity before using their ID/data in analysis.

Priority:
1. roster_config.json (source of truth for owned players — has both mlb_id + yahoo_player_key)
2. MLB Stats API search (fallback for FA / opponents)

Usage:
    python verify_player.py "Grant Holmes"
    python verify_player.py "Holmes" --fuzzy
    python verify_player.py "Jake Miller"          # warns if ambiguous

Exit codes:
    0 = exactly one match
    1 = no match or ambiguous (multiple matches without --fuzzy disambiguation)
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROSTER_CONFIG = Path(__file__).parent / "roster_config.json"
MLB_SEARCH_URL = "https://statsapi.mlb.com/api/v1/people/search"


def search_roster_config(name: str, fuzzy: bool = False) -> list[dict]:
    """Search roster_config.json batters + pitchers by name."""
    if not ROSTER_CONFIG.exists():
        return []
    with ROSTER_CONFIG.open(encoding="utf-8") as f:
        cfg = json.load(f)
    matches = []
    target = name.lower().strip()
    for kind in ("batters", "pitchers"):
        for p in cfg.get(kind, []):
            pname = p.get("name", "").lower()
            hit = (target in pname) if fuzzy else (target == pname)
            if hit:
                matches.append({
                    "source": "roster_config",
                    "name": p.get("name"),
                    "mlb_id": p.get("mlb_id"),
                    "yahoo_player_key": p.get("yahoo_player_key"),
                    "team": p.get("team"),
                    "positions": p.get("positions"),
                    "selected_pos": p.get("selected_pos"),
                    "kind": kind[:-1],  # batter / pitcher
                })
    return matches


def search_mlb_api(name: str) -> list[dict]:
    """Fallback: MLB Stats API people search."""
    qs = urllib.parse.urlencode({"names": name, "sportId": 1})
    url = f"{MLB_SEARCH_URL}?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  MLB API error: {e}", file=sys.stderr)
        return []
    matches = []
    for p in data.get("people", []):
        matches.append({
            "source": "mlb_api",
            "name": p.get("fullName"),
            "mlb_id": p.get("id"),
            "yahoo_player_key": None,
            "team": p.get("currentTeam", {}).get("name"),
            "positions": [p.get("primaryPosition", {}).get("abbreviation")],
            "selected_pos": None,
            "kind": "mlb_player",
        })
    return matches


def format_match(m: dict) -> str:
    positions = "/".join(m.get("positions") or []) or "?"
    team = m.get("team") or "?"
    yk = m.get("yahoo_player_key")
    yk_str = f" yahoo={yk}" if yk else ""
    sel = m.get("selected_pos")
    sel_str = f" sel={sel}" if sel else ""
    return (
        f"  [{m['source']}] {m['name']} | mlb_id={m['mlb_id']} | "
        f"{team} {positions}{sel_str}{yk_str}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="Player full name (e.g. 'Grant Holmes')")
    ap.add_argument("--fuzzy", action="store_true", help="Substring match in roster_config")
    args = ap.parse_args()

    matches = search_roster_config(args.name, fuzzy=args.fuzzy)
    if not matches:
        print(f"Not in roster_config — falling back to MLB Stats API search for '{args.name}'...")
        matches = search_mlb_api(args.name)

    if not matches:
        print(f"  No match found for '{args.name}'.")
        return 1

    if len(matches) == 1:
        print(f"Verified ({matches[0]['source']}):")
        print(format_match(matches[0]))
        return 0

    print(f"AMBIGUOUS — {len(matches)} candidates for '{args.name}'. Confirm before using:")
    for m in matches:
        print(format_match(m))
    return 1


if __name__ == "__main__":
    sys.exit(main())
