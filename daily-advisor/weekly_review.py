"""Weekly Review — 週覆盤資料準備腳本

Usage:
    python weekly_review.py --prepare [--dry-run] [--date YYYY-MM-DD]

Cron: 每週一 TW 18:00 (UTC 10:00)，在 Weekly Scan 之前執行。
輸出: daily-advisor/weekly-data/week-{N}.json
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
MLB_API = "https://statsapi.mlb.com/api/v1"
YAHOO_API = "https://fantasysports.yahooapis.com/fantasy/v2"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_TOKEN_FILE = os.path.join(SCRIPT_DIR, "yahoo_token.json")
WEEKLY_DATA_DIR = os.path.join(SCRIPT_DIR, "weekly-data")

# Yahoo stat_id → (display_name, lower_is_better)
YAHOO_STAT_MAP = {
    "7": ("R", False), "12": ("HR", False), "13": ("RBI", False),
    "16": ("SB", False), "18": ("BB", False), "3": ("AVG", False),
    "55": ("OPS", False), "50": ("IP", False), "28": ("W", False),
    "42": ("K", False), "26": ("ERA", True), "27": ("WHIP", True),
    "83": ("QS", False), "89": ("SV+H", False),
}

LOWER_IS_BETTER = {"ERA", "WHIP"}

CATEGORY_ORDER = ["R", "HR", "RBI", "SB", "BB", "AVG", "OPS",
                   "IP", "W", "K", "ERA", "WHIP", "QS", "SV+H"]

# Single-point risk positions (only 1 eligible player on roster)
RISK_POSITIONS = ["C", "1B", "SS"]


# ── Config & Env ──


def load_config():
    with open(os.path.join(SCRIPT_DIR, "roster_config.json"), encoding="utf-8") as f:
        config = json.load(f)
    config["mlb_id_map"] = {}
    for p in config.get("batters", []) + config.get("pitchers", []):
        if p.get("mlb_id"):
            config["mlb_id_map"][p["name"]] = p["mlb_id"]
    return config


def load_env():
    env = {}
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "YAHOO_CLIENT_ID", "YAHOO_CLIENT_SECRET"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


# ── API Helpers (match main.py patterns) ──


def yahoo_refresh_token(env):
    """Refresh Yahoo OAuth token. Returns access_token."""
    with open(YAHOO_TOKEN_FILE, encoding="utf-8") as f:
        tokens = json.load(f)
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": env["YAHOO_CLIENT_ID"],
        "client_secret": env["YAHOO_CLIENT_SECRET"],
    }).encode()
    req = urllib.request.Request(
        YAHOO_TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    tokens["access_token"] = result["access_token"]
    if "refresh_token" in result:
        tokens["refresh_token"] = result["refresh_token"]
    with open(YAHOO_TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)
    return result["access_token"]


def yahoo_api_get(path, access_token):
    """Yahoo Fantasy API GET request."""
    url = f"{YAHOO_API}{path}"
    sep = "&" if "?" in path else "?"
    url += f"{sep}format=json"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def mlb_api_get(path):
    """MLB Stats API GET request."""
    url = f"{MLB_API}{path}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def get_fantasy_week(target_date, config):
    """Return (week_start, week_end, week_number) for the given date."""
    opening = date.fromisoformat(config["league"]["opening_day"])
    first_sunday = opening
    while first_sunday.weekday() != 6:
        first_sunday += timedelta(days=1)
    if target_date <= first_sunday:
        return opening, first_sunday, 1
    week_start = first_sunday + timedelta(days=1)
    week_num = 2
    while True:
        week_end = week_start + timedelta(days=6)
        if week_start <= target_date <= week_end:
            return week_start, week_end, week_num
        week_start = week_end + timedelta(days=1)
        week_num += 1


# ── Review Data Fetching ──
# TODO: Task 2


# ── Preview Data Fetching ──
# TODO: Task 3


# ── JSON Assembly ──
# TODO: Task 4


# ── Main ──


def main():
    parser = argparse.ArgumentParser(description="Weekly Review Data Preparation")
    parser.add_argument("--prepare", action="store_true", help="Prepare weekly data JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON to stdout, skip file write and git push")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today in ET)")
    args = parser.parse_args()

    if not args.prepare:
        print("Usage: weekly_review.py --prepare [--dry-run] [--date YYYY-MM-DD]", file=sys.stderr)
        return

    config = load_config()
    env = load_env()

    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now(ET).date()

    week_start, week_end, week_number = get_fantasy_week(target_date, config)
    league_key = config["league"]["league_key"]
    team_name = config["league"]["team_name"]

    print(f"[Weekly Review] Week {week_number} ({week_start} ~ {week_end})", file=sys.stderr)

    access_token = yahoo_refresh_token(env)

    # TODO: Task 2 — review data
    review_data = {}

    # TODO: Task 3 — preview data
    preview_data = {}

    # TODO: Task 4 — assemble + output
    output = {
        "week": week_number,
        "dates": [week_start.isoformat(), week_end.isoformat()],
        "generated": datetime.now(ET).isoformat(),
        "review": review_data,
        "preview": preview_data,
    }

    if args.dry_run:
        print(json.dumps(output, indent=2, ensure_ascii=False, default=str))

    print("[Weekly Review] Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
