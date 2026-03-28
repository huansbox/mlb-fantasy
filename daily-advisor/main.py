"""Daily Advisor Phase 1 — Fantasy Baseball 每日陣容建議產生器"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MLB_API = "https://statsapi.mlb.com/api/v1"


def load_config():
    with open(os.path.join(SCRIPT_DIR, "roster_config.json"), encoding="utf-8") as f:
        return json.load(f)


def load_env():
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if not os.path.exists(env_path):
        return {}
    env = {}
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def load_prompt_template():
    with open(os.path.join(SCRIPT_DIR, "prompt_template.txt"), encoding="utf-8") as f:
        return f.read()


def api_get(path):
    url = f"{MLB_API}{path}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"API error: {url} — {e}", file=sys.stderr)
        raise


def parse_ip(val):
    """Convert baseball IP notation (6.1 = 6⅓, 6.2 = 6⅔) to decimal."""
    s = str(val)
    if "." in s:
        whole, frac = s.split(".", 1)
        return int(whole) + int(frac) / 3
    return float(s)


# ── MLB team full name → abbreviation mapping ──

_team_abbr_cache = {}


def build_team_abbr_map(season):
    if _team_abbr_cache:
        return _team_abbr_cache
    data = api_get(f"/teams?sportId=1&season={season}")
    for t in data["teams"]:
        _team_abbr_cache[t["name"]] = t["abbreviation"]
        _team_abbr_cache[t["abbreviation"]] = t["abbreviation"]
        _team_abbr_cache[str(t["id"])] = t["abbreviation"]
    return _team_abbr_cache


def team_abbr(name_or_id, season=2026):
    m = build_team_abbr_map(season)
    return m.get(str(name_or_id), str(name_or_id))


# ── Data fetching ──


def fetch_schedule(date_str):
    """Fetch games + probable pitchers for a date (YYYY-MM-DD)."""
    data = api_get(f"/schedule?sportId=1&date={date_str}&hydrate=probablePitcher")
    games = []
    for d in data.get("dates", []):
        for g in d["games"]:
            away = g["teams"]["away"]
            home = g["teams"]["home"]
            games.append({
                "away_team": away["team"]["name"],
                "home_team": home["team"]["name"],
                "away_pitcher": away.get("probablePitcher", {}).get("fullName"),
                "home_pitcher": home.get("probablePitcher", {}).get("fullName"),
                "away_pitcher_id": away.get("probablePitcher", {}).get("id"),
                "home_pitcher_id": home.get("probablePitcher", {}).get("id"),
                "game_time": g.get("gameDate", ""),
            })
    return games


def fetch_pitcher_gamelog(player_id, season):
    """Fetch pitching game log for the season."""
    data = api_get(
        f"/people/{player_id}/stats?stats=gameLog&season={season}&group=pitching"
    )
    splits = data.get("stats", [{}])[0].get("splits", [])
    return [
        {
            "date": s["date"],
            "opponent": s.get("opponent", {}).get("name", "?"),
            "ip": parse_ip(s["stat"].get("inningsPitched", 0)),
            "er": int(s["stat"].get("earnedRuns", 0)),
            "k": int(s["stat"].get("strikeOuts", 0)),
        }
        for s in splits
    ]


def fetch_team_hitting(team_id, season):
    """Fetch team season hitting stats."""
    data = api_get(
        f"/teams/{team_id}/stats?stats=season&season={season}&group=hitting"
    )
    splits = data.get("stats", [{}])[0].get("splits", [])
    if not splits:
        return None
    s = splits[0]["stat"]
    return {
        "avg": s.get("avg", "—"),
        "obp": s.get("obp", "—"),
        "ops": s.get("ops", "—"),
        "hr": s.get("homeRuns", "—"),
    }


# ── Analysis logic ──


def get_week_monday(today):
    """Return the Monday of the current fantasy week (Mon-Sun)."""
    days_since_monday = today.weekday()  # 0=Mon
    return today - timedelta(days=days_since_monday)


def calc_weekly_ip(config, target_date):
    """Calculate total IP for the fantasy week containing target_date."""
    monday = get_week_monday(target_date)
    sunday = monday + timedelta(days=6)
    season = config["league"]["season"]
    active_pitchers = [p for p in config["pitchers"] if p["role"] != "IL"]

    entries = []
    total_ip = 0.0
    for p in active_pitchers:
        try:
            logs = fetch_pitcher_gamelog(p["mlb_id"], season)
        except Exception:
            continue
        for log in logs:
            log_date = datetime.strptime(log["date"], "%Y-%m-%d").date()
            if monday <= log_date <= sunday:
                total_ip += log["ip"]
                entries.append(
                    f"  {p['name']}: {log['ip']:.1f} IP ({log['date']} vs {team_abbr(log['opponent'])})"
                )
    return total_ip, entries


def analyze(config, target_date):
    """Build the full data summary for claude -p."""
    season = config["league"]["season"]
    date_str = target_date.strftime("%Y-%m-%d")
    weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
    weekday = weekday_names[target_date.weekday()]

    games = fetch_schedule(date_str)

    # Build set of teams playing tomorrow
    teams_playing = set()
    # Map: team_abbr → opponent_team_abbr
    matchup_map = {}
    for g in games:
        a = team_abbr(g["away_team"], season)
        h = team_abbr(g["home_team"], season)
        teams_playing.add(a)
        teams_playing.add(h)
        matchup_map[a] = h
        matchup_map[h] = a

    # Identify my SP starts tomorrow
    my_sp_names = {p["name"]: p for p in config["pitchers"] if p["type"] == "SP"}
    sp_starts = []
    for g in games:
        for pitcher_key, side, opp_side in [
            ("away_pitcher", "away_team", "home_team"),
            ("home_pitcher", "home_team", "away_team"),
        ]:
            name = g.get(pitcher_key)
            if name and name in my_sp_names:
                opp = team_abbr(g[opp_side], season)
                sp_starts.append({"name": name, "opponent": opp, "info": my_sp_names[name]})

    # ── Section 1: Batters ──
    lines = [f"=== 明日賽程 ({date_str} 週{weekday}) ===\n"]
    lines.append("我的打者：")
    for b in config["batters"]:
        pos = "/".join(b["positions"])
        tag = "正選" if b["role"] == "starter" else "板凳"
        if b["team"] in teams_playing:
            opp = matchup_map.get(b["team"], "?")
            lines.append(f"  [{tag}] {b['name']} ({pos}, {b['team']}) → vs {opp}")
        else:
            lines.append(f"  [{tag}] {b['name']} ({pos}, {b['team']}) → 休兵")

    # ── Section 2: SP starts ──
    lines.append("\n我的 SP 明日先發：")
    if sp_starts:
        for sp in sp_starts:
            opp_team_id = config["teams"].get(sp["opponent"])
            hitting = fetch_team_hitting(opp_team_id, season) if opp_team_id else None
            if hitting:
                lines.append(
                    f"  {sp['name']} ({sp['info']['team']}) vs {sp['opponent']}"
                    f" — 對手打線 AVG {hitting['avg']} / OPS {hitting['ops']}"
                )
            else:
                lines.append(f"  {sp['name']} ({sp['info']['team']}) vs {sp['opponent']}")
    else:
        lines.append("  (無)")

    # ── Section 3: Pitcher-batter conflicts ──
    lines.append("\n投打衝突：")
    conflicts = []
    for sp in sp_starts:
        for b in config["batters"]:
            if b["team"] == sp["opponent"]:
                conflicts.append(
                    f"  {sp['name']} 先發 vs {sp['opponent']}"
                    f" → 你的 {b['name']} ({'/'.join(b['positions'])}) 是對手打者"
                )
    if conflicts:
        lines.extend(conflicts)
    else:
        lines.append("  (無)")

    # ── Section 4: Weekly IP ──
    lines.append("\n本週 IP 進度：")
    total_ip, ip_entries = calc_weekly_ip(config, target_date)
    min_ip = config["league"]["min_ip"]
    if ip_entries:
        lines.extend(ip_entries)
    lines.append(f"  合計: {total_ip:.1f} / {min_ip} IP")
    remaining = min_ip - total_ip
    if remaining > 0:
        lines.append(f"  還需: {remaining:.1f} IP")
    else:
        lines.append("  已達標")

    # ── Section 5: Upcoming SP schedule (next 3 days) ──
    schedule_cache = {date_str: games}
    lines.append("\n未來 3 天 SP 排程：")
    for offset in range(0, 3):
        future = target_date + timedelta(days=offset)
        future_str = future.strftime("%Y-%m-%d")
        future_weekday = weekday_names[future.weekday()]
        try:
            future_games = schedule_cache.get(future_str) or fetch_schedule(future_str)
        except Exception:
            continue
        day_starts = []
        for g in future_games:
            for pk in ["away_pitcher", "home_pitcher"]:
                if g.get(pk) in my_sp_names:
                    day_starts.append(g[pk])
        if day_starts:
            lines.append(f"  {future_str} (週{future_weekday}): {', '.join(day_starts)}")
        else:
            lines.append(f"  {future_str} (週{future_weekday}): (無)")

    return "\n".join(lines)


def call_claude(data_summary):
    """Call claude -p with the data summary and prompt template."""
    prompt = load_prompt_template()
    full_prompt = f"{prompt}\n\n---\n以下是今日數據：\n\n{data_summary}"

    result = subprocess.run(
        ["claude", "-p", full_prompt],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if result.returncode != 0:
        print(f"claude -p error: {result.stderr}", file=sys.stderr)
        return None
    return result.stdout.strip()


def send_telegram(message, env):
    """Send message via Telegram Bot API."""
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials missing in .env", file=sys.stderr)
        return False

    MAX_LEN = 4096
    if len(message) > MAX_LEN:
        message = message[:MAX_LEN - 20] + "\n\n(訊息截斷)"

    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        print(f"Telegram send error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Fantasy Baseball Daily Advisor")
    parser.add_argument("--dry-run", action="store_true", help="Only fetch data and print summary, skip claude and telegram")
    parser.add_argument("--no-send", action="store_true", help="Run claude but don't send to Telegram")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: tomorrow)")
    args = parser.parse_args()

    config = load_config()
    env = load_env()

    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now().date() + timedelta(days=1)

    print(f"Fetching data for {target_date}...", file=sys.stderr)
    data_summary = analyze(config, target_date)

    if args.dry_run:
        print(data_summary)
        return

    print("Calling claude -p...", file=sys.stderr)
    advice = call_claude(data_summary)
    if not advice:
        print("Claude returned no output.", file=sys.stderr)
        print("\n--- Raw data summary ---")
        print(data_summary)
        return

    print(advice)

    if args.no_send:
        return

    print("\nSending to Telegram...", file=sys.stderr)
    ok = send_telegram(advice, env)
    if ok:
        print("Sent.", file=sys.stderr)
    else:
        print("Failed to send.", file=sys.stderr)


if __name__ == "__main__":
    main()
