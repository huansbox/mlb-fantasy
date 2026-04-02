"""Roster sync — auto-update roster_config.json from Yahoo Fantasy API."""

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "roster_config.json")
LAST_SYNC_PATH = os.path.join(SCRIPT_DIR, ".last_sync")
MLB_API = "https://statsapi.mlb.com/api/v1"

sys.path.insert(0, SCRIPT_DIR)
from yahoo_query import load_env, refresh_token, api_get as yahoo_api_get, is_pitcher, pitcher_type  # noqa: E402


def load_config():
    """Load roster_config.json as dict."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    """Write config back to JSON with consistent formatting."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


def mlb_api_get(path):
    """GET request to MLB Stats API (no auth needed)."""
    url = f"{MLB_API}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def read_last_sync():
    """Read last sync timestamp from state file. Returns 0 if not exists."""
    if os.path.exists(LAST_SYNC_PATH):
        with open(LAST_SYNC_PATH) as f:
            return int(f.read().strip())
    return 0


def write_last_sync(ts):
    """Write timestamp to state file."""
    with open(LAST_SYNC_PATH, "w") as f:
        f.write(str(ts))


def main():
    parser = argparse.ArgumentParser(description="Sync Yahoo roster to roster_config.json")
    parser.add_argument("--init", action="store_true", help="Full bootstrap: pull entire roster and build config")
    parser.add_argument("--dry-run", action="store_true", help="Print diff without writing config or pushing")
    args = parser.parse_args()

    env = load_env()
    token = refresh_token(env)
    config = load_config()
    league_key = config["league"]["league_key"]

    my_key = find_my_team_key(league_key, token)
    print(f"Team key: {my_key}", file=sys.stderr)

    if args.init:
        run_init(my_key, token, config, args.dry_run)
    else:
        run_daily(league_key, my_key, token, config, env, args.dry_run)


if __name__ == "__main__":
    main()
