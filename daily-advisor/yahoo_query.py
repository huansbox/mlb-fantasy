"""Yahoo Fantasy API query tool — FA player search, player lookup, and Savant stats."""

import argparse
import csv
import io
import json
import os
import sys
import unicodedata
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from daily_advisor import pctile_tag  # noqa: E402
from _savant_v4_fetch import fetch_pitcher_v4  # noqa: E402

YAHOO_API = "https://fantasysports.yahooapis.com/fantasy/v2"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_TOKEN_FILE = os.path.join(SCRIPT_DIR, "yahoo_token.json")

# Yahoo stat_id → display name (matches league's 14 scoring categories)
YAHOO_STAT_MAP = {
    "60": ("H/AB", None),
    "7": ("R", False),
    "12": ("HR", False),
    "13": ("RBI", False),
    "16": ("SB", False),
    "18": ("BB", False),
    "3": ("AVG", False),
    "55": ("OPS", False),
    "50": ("IP", False),
    "28": ("W", False),
    "42": ("K", False),
    "26": ("ERA", True),
    "27": ("WHIP", True),
    "83": ("QS", False),
    "89": ("SV+H", False),
}


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


def refresh_token(env):
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


def api_get(path, access_token):
    url = f"{YAHOO_API}{path}"
    sep = "&" if "?" in path else "?"
    url += f"{sep}format=json"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def load_config():
    with open(os.path.join(SCRIPT_DIR, "roster_config.json"), encoding="utf-8") as f:
        return json.load(f)


# ── Roster helpers ──

ALL_BATTER_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]


def is_pitcher(player):
    """Check if player is pitcher based on positions array."""
    return any(p in ("SP", "RP") for p in player.get("positions", []))


def pitcher_type(player):
    """Derive SP/RP from positions array. Returns 'SP', 'RP', or None."""
    positions = player.get("positions", [])
    if "SP" in positions:
        return "SP"
    if "RP" in positions:
        return "RP"
    return None


# Yahoo slot codes that mean "not in active lineup pool"
INACTIVE_SLOTS = ("IL", "IL+", "NA")


def is_active(player):
    """Return True if player is active (not on IL/IL+/NA).

    Checks both 'role' (set during roster parsing) and 'selected_pos'
    (Yahoo raw position) to handle all data sources consistently.
    """
    if player.get("role") == "IL":
        return False
    if player.get("selected_pos", "") in INACTIVE_SLOTS:
        return False
    return True


def calc_position_depth(config):
    """Calculate position coverage from config.

    Returns dict of positions with <= 1 player covering them.
    Example: {"C": 1, "SS": 1} means C and SS have only 1 player each.
    """
    coverage = {pos: 0 for pos in ALL_BATTER_POSITIONS}
    for b in config.get("batters", []):
        for pos in b.get("positions", []):
            if pos in coverage:
                coverage[pos] += 1
    return {pos: count for pos, count in coverage.items() if count <= 1}


def extract_player_info(player_data):
    """Extract player fields from Yahoo's nested player structure."""
    info = player_data[0]
    name = team = position = status = percent_owned = None
    player_key = None
    for item in info:
        if isinstance(item, dict):
            if "name" in item:
                name = item["name"].get("full")
            if "editorial_team_abbr" in item:
                team = item["editorial_team_abbr"].upper()
            if "display_position" in item:
                position = item["display_position"]
            if "status" in item:
                status = item["status"]
            if "player_key" in item:
                player_key = item["player_key"]
    # percent_owned and ownership may be at any index after 0
    ownership_type = waiver_date = None
    for idx in range(1, len(player_data)):
        po_data = player_data[idx]
        if isinstance(po_data, dict):
            if "percent_owned" in po_data:
                po_list = po_data["percent_owned"]
                if isinstance(po_list, list):
                    for po in po_list:
                        if isinstance(po, dict) and "value" in po:
                            percent_owned = po["value"]
                elif isinstance(po_list, dict):
                    percent_owned = po_list.get("value")
            if "ownership" in po_data:
                own = po_data["ownership"]
                ownership_type = own.get("ownership_type", "")
                waiver_date = own.get("waiver_date", "")
    return {
        "name": name or "?",
        "team": team or "?",
        "position": position or "?",
        "status": status or "",
        "percent_owned": percent_owned,
        "player_key": player_key,
        "ownership_type": ownership_type or "",
        "waiver_date": waiver_date or "",
    }


def parse_player_stats(player_data):
    """Extract stats from player data that includes /stats sub-resource."""
    stats = {}
    for idx in range(1, len(player_data)):
        ps = player_data[idx]
        if isinstance(ps, dict) and "player_stats" in ps:
            for s in ps["player_stats"].get("stats", []):
                sid = s["stat"]["stat_id"]
                val = s["stat"]["value"]
                if sid in YAHOO_STAT_MAP:
                    name, _ = YAHOO_STAT_MAP[sid]
                    stats[name] = val
            break
    return stats


def _fetch_fa_page(start, *, page_size, position, status, sort, sort_type,
                   league_key, access_token):
    """Fetch a single page of Yahoo FA pool. Returns list[dict] of player
    info + stats (extract_player_info shape with a ``stats`` key).

    Empty list when Yahoo returns no players (end of pool or filter miss).
    """
    filters = [f"status={status}"]
    if position:
        filters.append(f"position={position}")
    filters.append(f"sort={sort}")
    if sort_type:
        filters.append(f"sort_type={sort_type}")
    filters.append(f"count={page_size}")
    if start:
        filters.append(f"start={start}")

    filter_str = ";".join(filters)
    path = f"/league/{league_key}/players;{filter_str};out=stats,percent_owned,ownership"

    data = api_get(path, access_token)
    league_data = data["fantasy_content"]["league"]
    if len(league_data) < 2 or "players" not in league_data[1]:
        return []
    players_data = league_data[1]["players"]
    players = []
    for k, v in players_data.items():
        if k == "count":
            continue
        p = extract_player_info(v["player"])
        p["stats"] = parse_player_stats(v["player"])
        players.append(p)
    return players


def query_fa(access_token, league_key, *, position=None, status="A",
             sort="AR", sort_type=None, page_size=25, start=0,
             names=None, auto_page=False, max_pages=12):
    """Query Yahoo FA pool. Returns list[dict] of player info + stats.

    - ``names=None, auto_page=False`` (default): one page from ``start``.
    - ``auto_page=True``: loop pages until empty page, partial page (<
      page_size), or ``max_pages`` cap.
    - ``names={...}``: implies ``auto_page``; only matching players returned;
      stops early once all wanted names located.

    Single importable entry point shared by ``cmd_fa`` and external callers
    (e.g. ``stream_sp_scan.fetch_yahoo_fa_sp_pool``).
    """
    target_names = set(names) if names else None
    do_auto_page = bool(auto_page or target_names)

    collected = []
    cur_start = start
    pages_fetched = 0

    while pages_fetched < max_pages:
        page = _fetch_fa_page(
            cur_start,
            page_size=page_size, position=position, status=status,
            sort=sort, sort_type=sort_type,
            league_key=league_key, access_token=access_token,
        )
        pages_fetched += 1
        if not page:
            break

        if target_names:
            collected.extend(p for p in page if p["name"] in target_names)
            found = {p["name"] for p in collected}
            if target_names.issubset(found):
                break
        else:
            collected.extend(page)

        if not do_auto_page:
            break
        if len(page) < page_size:
            break
        cur_start += page_size

    return collected


def cmd_fa(args, access_token, config):
    """Query FA players. Supports --names filter + --auto-page (multi-page sweep)."""
    league_key = config["league"]["league_key"]

    target_names = (
        {n.strip() for n in args.names.split(",") if n.strip()}
        if args.names else None
    )
    auto_page = bool(args.auto_page or target_names)

    players = query_fa(
        access_token, league_key,
        position=args.position, status=args.status,
        sort=args.sort, sort_type=args.sort_type,
        page_size=args.count, start=args.start,
        names=target_names, auto_page=auto_page,
    )

    pos_filter = args.position or "ALL"
    extras = []
    if target_names:
        extras.append(f"names={','.join(sorted(target_names))}")
    if auto_page:
        extras.append("auto-page")
    extra_str = f", {', '.join(extras)}" if extras else ""
    print(f"=== FA 查詢 (position={pos_filter}, sort={args.sort}, count={args.count}{extra_str}) ===\n")

    if not players:
        print("查無結果")
        if target_names:
            print(f"(--names filter: {', '.join(sorted(target_names))} 未在 {pos_filter} 池中找到)")
        return

    if target_names:
        found = {p["name"] for p in players}
        missing = target_names - found
        if missing:
            print(f"(--names filter: 未找到 {', '.join(sorted(missing))})\n")

    for i, p in enumerate(players, 1):
        po = f"{p['percent_owned']}%" if p["percent_owned"] else "—"
        st = p["status"] if p["status"] else ""
        waiver_tag = f"W {p['waiver_date']}" if p.get("waiver_date") else ""
        status_tag = f"{st} {waiver_tag}".strip()
        stats = p.get("stats", {})
        if "ERA" in stats:
            stat_str = f"ERA {stats.get('ERA', '—')} | WHIP {stats.get('WHIP', '—')} | K {stats.get('K', '—')} | IP {stats.get('IP', '—')}"
        elif "AVG" in stats:
            stat_str = f"AVG {stats.get('AVG', '—')} | OPS {stats.get('OPS', '—')} | HR {stats.get('HR', '—')} | BB {stats.get('BB', '—')}"
        else:
            stat_str = ""
        print(f"{i:3}  {p['name']:20}  {p['team']:5}  {p['position']:12}  {po:>7}  {stat_str}  {status_tag}")


def _search_players(search_name, league_key, access_token):
    """Search for players, with apostrophe fallback."""
    queries = [search_name]
    if "'" in search_name:
        queries.append(search_name.replace("'", ""))
        parts = search_name.replace("'", " ").split()
        if parts:
            queries.append(parts[-1])

    for q in queries:
        encoded = urllib.parse.quote(q)
        path = f"/league/{league_key}/players;search={encoded}"
        try:
            data = api_get(path, access_token)
        except Exception:
            continue
        league_data = data["fantasy_content"]["league"]
        if len(league_data) < 2 or "players" not in league_data[1]:
            continue
        players_data = league_data[1]["players"]
        if isinstance(players_data, list) or players_data.get("count", 0) == 0:
            continue
        return players_data
    return None


def cmd_player(args, access_token, config):
    """Look up a specific player with stats and percent_owned via two-step query."""
    league_key = config["league"]["league_key"]
    search_name = args.player
    players_data = _search_players(search_name, league_key, access_token)
    if players_data is None:
        print(f"找不到球員: {search_name}")
        return

    for k, v in players_data.items():
        if k == "count":
            continue
        p = extract_player_info(v["player"])
        player_key = p.get("player_key")

        # Two-step: use player_key to get stats + percent_owned
        stats = {}
        percent_owned = None
        if player_key:
            try:
                sd = api_get(
                    f"/league/{league_key}/players;player_keys={player_key}/stats",
                    access_token,
                )
                sp = sd["fantasy_content"]["league"][1]["players"]["0"]["player"]
                stats = parse_player_stats(sp)
            except Exception:
                pass
            try:
                pd = api_get(
                    f"/league/{league_key}/players;player_keys={player_key}/percent_owned",
                    access_token,
                )
                pp = pd["fantasy_content"]["league"][1]["players"]["0"]["player"]
                for item in pp[1].get("percent_owned", []):
                    if isinstance(item, dict) and "value" in item:
                        percent_owned = item["value"]
            except Exception:
                pass

        # MLB API cross-check for roster status
        mlb_status = None
        mlb_team = None
        try:
            search_url = (
                "https://statsapi.mlb.com/api/v1/people/search"
                f"?names={urllib.parse.quote(p['name'])}&sportIds=1&active=true"
            )
            with urllib.request.urlopen(search_url, timeout=10) as resp:
                mlb_data = json.loads(resp.read())
            rows = mlb_data.get("people", [])
            if rows:
                pid = rows[0]["id"]
                p_url = f"https://statsapi.mlb.com/api/v1/people/{pid}?hydrate=currentTeam"
                with urllib.request.urlopen(p_url, timeout=10) as resp:
                    pd2 = json.loads(resp.read())
                person = pd2.get("people", [{}])[0]
                ct = person.get("currentTeam", {})
                mlb_team = ct.get("name")
                mlb_status = person.get("status", {}).get("description", "Active")
        except Exception:
            pass

        po_str = f"{percent_owned}%" if percent_owned is not None else "—"
        yahoo_status = p['status'] or '健康'
        mlb_str = f"{mlb_status} - {mlb_team}" if mlb_status else "—"
        print(f"=== {p['name']} ===")
        print(f"隊伍: {p['team']}")
        print(f"位置: {p['position']}")
        print(f"持有率: {po_str}")
        print(f"狀態: {yahoo_status} (Yahoo) | {mlb_str} (MLB)")
        if stats:
            print("--- 本季數據 ---")
            for name, val in stats.items():
                print(f"  {name}: {val}")
        print()


def send_telegram(message, env):
    """Send message via Telegram Bot API.

    Tries Markdown parse_mode first; on HTTP 400 (parse error from unbalanced
    `*` / `_` / `[` etc. in Claude-generated content), falls back to plain
    text so the message still arrives, just without formatting.
    """
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials missing", file=sys.stderr)
        return False
    MAX_LEN = 4096
    if len(message) > MAX_LEN:
        message = message[:MAX_LEN - 20] + "\n\n(訊息截斷)"

    def _send(parse_mode):
        body = {"chat_id": chat_id, "text": message}
        if parse_mode:
            body["parse_mode"] = parse_mode
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get("ok", False)

    try:
        return _send("Markdown")
    except urllib.error.HTTPError as e:
        if e.code == 400:
            print("Telegram Markdown 400, fallback plain text", file=sys.stderr)
            try:
                return _send(None)
            except Exception as e2:
                print(f"Telegram plain send error: {e2}", file=sys.stderr)
                return False
        print(f"Telegram send error: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Telegram send error: {e}", file=sys.stderr)
        return False


def _normalize(name):
    """Strip accents for fuzzy matching (Jesús → Jesus)."""
    return "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    ).lower()


MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


def _fetch_savant_csv(url):
    """Fetch a Baseball Savant CSV leaderboard."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode("utf-8-sig")


def _safe_float(v, default=None):
    if v in (None, "", "null", "None", "-", "--", "-.--"):
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _ip_str_to_real(ip_str) -> float:
    """Convert MLB IP notation (5.1 = 5⅓, 5.2 = 5⅔) to real innings."""
    v = _safe_float(ip_str, 0.0) or 0.0
    return int(v) + (v - int(v)) * 10 / 3


def _match_player(rows, query):
    """Find a player in Savant CSV rows by fuzzy name match."""
    q = _normalize(query)
    q_parts = q.split()
    matches = []
    for row in rows:
        raw_name = row.get("\ufefflast_name, first_name") or row.get("last_name, first_name", "")
        if not raw_name:
            continue
        # CSV format: "LastName, FirstName"
        parts = [p.strip().strip('"') for p in raw_name.split(",")]
        if len(parts) < 2:
            continue
        last = _normalize(parts[0])
        first = _normalize(parts[1])
        full = f"{first} {last}"
        # Match: exact full name, or last name + first initial
        if q == full or q == f"{last} {first}":
            matches.append((row, 0))
        elif last in q_parts and first.startswith(q_parts[0][:3]):
            matches.append((row, 1))
        elif last in q_parts:
            matches.append((row, 2))
    matches.sort(key=lambda x: x[1])
    return matches[0][0] if matches else None


def _savant_lookup(query, year, player_type):
    """Fetch Savant data for a single player from CSV.

    Returns dict with found data (incl. player_id), or None if player not found.
    """
    sc_url = (
        f"https://baseballsavant.mlb.com/leaderboard/statcast"
        f"?type={player_type}&year={year}&position=&team=&min=1&csv=true"
    )
    ex_url = (
        f"https://baseballsavant.mlb.com/leaderboard/expected_statistics"
        f"?type={player_type}&year={year}&position=&team=&min=1&csv=true"
    )

    hh_pct = barrel_pct = bbe = xwoba = xera = None
    player_id = None

    try:
        sc_text = _fetch_savant_csv(sc_url)
        sc_rows = list(csv.DictReader(io.StringIO(sc_text)))
        sc_match = _match_player(sc_rows, query)
        if sc_match:
            hh_pct = float(sc_match.get("ev95percent", 0) or 0)
            barrel_pct = float(sc_match.get("brl_percent", 0) or 0)
            bbe = int(sc_match.get("attempts", 0) or 0)
            player_id = int(sc_match.get("player_id", 0) or 0) or None
    except Exception as e:
        print(f"  Statcast CSV error ({year}): {e}", file=sys.stderr)

    try:
        ex_text = _fetch_savant_csv(ex_url)
        ex_rows = list(csv.DictReader(io.StringIO(ex_text)))
        ex_match = _match_player(ex_rows, query)
        if ex_match:
            xwoba = float(ex_match.get("est_woba", 0) or 0)
            if bbe is None:
                bbe = int(ex_match.get("bip", 0) or 0)
            if player_id is None:
                player_id = int(ex_match.get("player_id", 0) or 0) or None
            if player_type == "pitcher":
                raw = ex_match.get("xera")
                xera = float(raw) if raw and raw.strip() else None
    except Exception as e:
        print(f"  Expected CSV error ({year}): {e}", file=sys.stderr)

    if hh_pct is None and xwoba is None:
        return None
    return {
        "hh_pct": hh_pct, "barrel_pct": barrel_pct,
        "bbe": bbe, "xwoba": xwoba, "xera": xera,
        "player_id": player_id,
    }


def _fetch_batter_bb_pct(pid: int, year: int):
    """Fetch BB% (walks / PA) for a single batter via MLB Stats API.

    Savant statcast/expected leaderboards do not expose BB%, but BB% is one of
    the v4 thin core 3 batter signals. Returns float (e.g. 13.7) or None on
    failure / missing data.
    """
    try:
        url = (
            f"{MLB_API_BASE}/people/{pid}/stats"
            f"?stats=season&season={year}&group=hitting"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
        splits = (data.get("stats") or [{}])[0].get("splits", []) or []
        if not splits:
            return None
        stat = splits[0].get("stat", {})
        bb = _safe_float(stat.get("baseOnBalls"))
        pa = _safe_float(stat.get("plateAppearances"))
        if bb is None or not pa:
            return None
        return 100.0 * bb / pa
    except Exception as e:
        print(f"  Batter BB% fetch error ({year}): {e}", file=sys.stderr)
        return None


def _savant_custom_batter(query: str, year: int):
    """Deep Savant signals for a batter via the custom leaderboard endpoint.

    Returns dict with launch_angle / exit_velocity / whiff_pct / chase_pct /
    xslg / xba (None on missing fields) or None if the player is not found.

    Surfaces age-related decline and swing-mechanic breaks that the v4 thin
    core (xwOBA / BB% / Barrel%) cannot — e.g. launch_angle dropping ≥10°
    year-over-year is a structural-decay signature.
    """
    url = (
        "https://baseballsavant.mlb.com/leaderboard/custom"
        f"?year={year}&type=batter&filter=&min=q"
        "&selections=launch_angle_avg,exit_velocity_avg,whiff_percent,"
        "oz_swing_percent,xslg,xba&csv=true"
    )
    try:
        text = _fetch_savant_csv(url)
        rows = list(csv.DictReader(io.StringIO(text)))
        match = _match_player(rows, query)
        if not match:
            print(f"  Savant custom: player not found for '{query}' ({year})",
                  file=sys.stderr)
            return None
        return {
            "launch_angle": _safe_float(match.get("launch_angle_avg")),
            "exit_velocity": _safe_float(match.get("exit_velocity_avg")),
            "whiff_pct": _safe_float(match.get("whiff_percent")),
            "chase_pct": _safe_float(match.get("oz_swing_percent")),
            "xslg": _safe_float(match.get("xslg")),
            "xba": _safe_float(match.get("xba")),
        }
    except Exception as e:
        print(f"  Savant custom CSV error ({year}): {e}", file=sys.stderr)
        return None


def _fmt_pct(value, fmt: str) -> str:
    """Format a numeric metric with given fmt string, dash if None."""
    if value is None:
        return "—"
    return fmt.format(value)


def _print_pitcher_v4_line(label: str, d: dict) -> None:
    """Print one year's SP v4 5-slot output with luck signal + context."""
    if d is None or not any(d.get(k) is not None
                            for k in ("ip_gs", "whiff_pct", "bb9", "gb_pct", "xwobacon")):
        print(f"  {label}: no data found")
        return

    ip_gs = d.get("ip_gs")
    whiff = d.get("whiff_pct")
    bb9 = d.get("bb9")
    gb = d.get("gb_pct")
    xwc = d.get("xwobacon")

    line1 = (
        f"IP/GS {_fmt_pct(ip_gs, '{:.2f}')} {pctile_tag(ip_gs, 'ip_gs', 'sp_v4')} | "
        f"Whiff% {_fmt_pct(whiff, '{:.1f}%')} {pctile_tag(whiff, 'whiff_pct', 'sp_v4')} | "
        f"BB/9 {_fmt_pct(bb9, '{:.2f}')} {pctile_tag(bb9, 'bb9', 'sp_v4')}"
    )
    line2 = (
        f"GB% {_fmt_pct(gb, '{:.1f}')} {pctile_tag(gb, 'gb_pct', 'sp_v4')} | "
        f"xwOBACON {_fmt_pct(xwc, '{:.3f}')} {pctile_tag(xwc, 'xwobacon', 'sp_v4')}"
    )
    print(f"  {label}:")
    print(f"    {line1}")
    print(f"    {line2}")

    # Luck signal: |xERA - ERA| ≥ 0.81 (P70 threshold) is significant
    xera = d.get("xera")
    era = d.get("era")
    if xera is not None and era is not None:
        diff = xera - era
        if abs(diff) >= 0.81:
            direction = "賣高" if diff > 0 else "buy-low"
            sign = "+" if diff > 0 else ""
            print(f"    [運氣] xERA {xera:.2f} / ERA {era:.2f} (Δ {sign}{diff:.2f}, {direction})")
        else:
            print(f"    [運氣] xERA {_fmt_pct(xera, '{:.2f}')} / ERA {_fmt_pct(era, '{:.2f}')} (Δ {diff:+.2f}, 中性)")

    bbe = d.get("bbe")
    bbe_str = str(bbe) if bbe is not None else "—"
    print(f"    GS/G: {d.get('gs', 0)}/{d.get('g', 0)} | IP: {d.get('ip', 0):.1f} | BBE: {bbe_str}")


def _print_savant_line(label, data, player_type):
    """Print one year's Savant data line with percentile tags."""
    parts = [f"{label}:"]
    if player_type == "pitcher" and data.get("xera") is not None:
        parts.append(f"xERA {data['xera']:.2f} {pctile_tag(data['xera'], 'xera', 'pitcher')}")
    if data.get("xwoba") is not None:
        tag = "xwOBA allowed" if player_type == "pitcher" else "xwOBA"
        parts.append(f"{tag} {data['xwoba']:.3f} {pctile_tag(data['xwoba'], 'xwoba', player_type)}")
    if player_type == "batter" and "bb_pct" in data:
        bb = data.get("bb_pct")
        if bb is None:
            parts.append("BB% —")
        else:
            parts.append(f"BB% {bb:.1f}% {pctile_tag(bb, 'bb_pct', 'batter')}")
    if data.get("hh_pct") is not None:
        tag = "HH% allowed" if player_type == "pitcher" else "HH%"
        parts.append(f"{tag} {data['hh_pct']:.1f}% {pctile_tag(data['hh_pct'], 'hh_pct', player_type)}")
    if data.get("barrel_pct") is not None:
        tag = "Barrel% allowed" if player_type == "pitcher" else "Barrel%"
        parts.append(f"{tag} {data['barrel_pct']:.1f}% {pctile_tag(data['barrel_pct'], 'barrel_pct', player_type)}")
    if data.get("bbe"):
        parts.append(f"BBE {data['bbe']}")
    print("  " + " | ".join(parts))

    # Batter deep-signal line: raw values without percentile tags — agent
    # reasons from cross-year comparison (e.g. launch angle 17.7° → 5.5° as
    # a swing-mechanic collapse signature).
    if player_type == "batter":
        deep_parts = []
        if data.get("xslg") is not None:
            deep_parts.append(f"xSLG {data['xslg']:.3f}")
        if data.get("xba") is not None:
            deep_parts.append(f"xBA {data['xba']:.3f}")
        if data.get("launch_angle") is not None:
            deep_parts.append(f"LA {data['launch_angle']:.1f}°")
        if data.get("exit_velocity") is not None:
            deep_parts.append(f"EV {data['exit_velocity']:.1f} mph")
        if data.get("whiff_pct") is not None:
            deep_parts.append(f"Whiff% {data['whiff_pct']:.1f}%")
        if data.get("chase_pct") is not None:
            deep_parts.append(f"Chase% {data['chase_pct']:.1f}%")
        if deep_parts:
            print("    " + " | ".join(deep_parts))


def cmd_savant(args):
    """Look up a player's Statcast data from Baseball Savant CSV.

    Checks both batter and pitcher CSVs, picks the type with higher BBE.
    For pitchers, branches on GS: ≥3 → SP v4 5-slot; else → RP v2 indicators.

    SP v4 = first-order signal per CLAUDE.md framework. RP still on v2 because
    the RP framework hasn't been upgraded yet — TODO: align when it is.
    """
    query = args.player
    years = [int(args.year)] if args.year else [2026, 2025]

    print(f"=== {query} — Statcast ===\n")

    # Detect player type: check both CSVs, pick the one with more BBE
    # (pitchers have hundreds of BBE as pitcher but few as batter)
    detected_type = None
    best_bbe = -1
    primary_pid = None
    for pt in ["batter", "pitcher"]:
        test = _savant_lookup(query, years[0], pt)
        if test and (test.get("bbe") or 0) > best_bbe:
            best_bbe = test.get("bbe") or 0
            detected_type = pt
            primary_pid = test.get("player_id")

    if not detected_type:
        print(f"  Player not found in batter or pitcher CSV for {years[0]}")
        print()
        return

    if detected_type == "batter":
        for year in years:
            label = "本季" if year == 2026 else str(year)
            data = _savant_lookup(query, year, "batter")
            if data:
                pid = data.get("player_id")
                # BB% comes from MLB Stats API, not Savant CSV. Always populate
                # the key so the print line shows '—' rather than omitting on
                # fetch failure.
                data["bb_pct"] = _fetch_batter_bb_pct(pid, year) if pid else None
                # Deep signals (LA / EV / Whiff% / Chase% / xSLG / xBA) from
                # the custom endpoint surface age/mechanic decay invisible to
                # the v4 thin core. Filter out None so partial schema drift
                # surfaces as missing line items rather than silently zeroing
                # the whole deep line.
                deep = _savant_custom_batter(query, year)
                if deep:
                    data.update({k: v for k, v in deep.items() if v is not None})
                _print_savant_line(label, data, "batter")
            else:
                print(f"  {label}: no data found")
        print()
        return

    # Pitcher path: decide SP v4 vs RP v2 from primary-year GS
    is_sp = False
    primary_v4 = None
    if primary_pid:
        primary_v4 = fetch_pitcher_v4(primary_pid, years[0])
        is_sp = primary_v4.get("gs", 0) >= 3

    if is_sp:
        print(f"  (detected as SP — v4 5-slot)\n")
        for year in years:
            label = "本季" if year == 2026 else str(year)
            data = primary_v4 if year == years[0] else fetch_pitcher_v4(primary_pid, year)
            _print_pitcher_v4_line(label, data)
    else:
        print(f"  (detected as RP — v2 indicators; RP framework v4 upgrade pending)\n")
        for year in years:
            label = "本季" if year == 2026 else str(year)
            data = _savant_lookup(query, year, "pitcher")
            if data:
                _print_savant_line(label, data, "pitcher")
            else:
                print(f"  {label}: no data found")

    print()


PITCHING_CATS = {"IP", "W", "K", "ERA", "WHIP", "QS", "SV+H"}
BATTING_CATS = {"R", "HR", "RBI", "SB", "BB", "AVG", "OPS"}


def cmd_scoreboard(args, access_token, config):
    """Show league-wide category standings for current week."""
    league_key = config["league"]["league_key"]
    team_name = config["league"].get("team_name", "")

    sb = api_get(f"/league/{league_key}/scoreboard", access_token)
    matchups = sb["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    teams = []
    for k, v in matchups.items():
        if k == "count":
            continue
        for tidx in ["0", "1"]:
            tinfo = v["matchup"]["0"]["teams"][tidx]["team"][0]
            tstats = v["matchup"]["0"]["teams"][tidx]["team"][1]["team_stats"]["stats"]
            name = "?"
            is_mine = False
            for item in tinfo:
                if isinstance(item, dict):
                    if "name" in item:
                        name = item["name"]
                    if "is_owned_by_current_login" in item:
                        is_mine = True
            if not is_mine and name == team_name:
                is_mine = True
            row = {"name": name, "is_mine": is_mine}
            for s in tstats:
                sid = s["stat"]["stat_id"]
                val = s["stat"]["value"]
                if sid in YAHOO_STAT_MAP:
                    cat, _ = YAHOO_STAT_MAP[sid]
                    row[cat] = val
            teams.append(row)

    # Determine which categories to show
    if args.pitching:
        cats = [c for c in ["IP", "W", "K", "ERA", "WHIP", "QS", "SV+H"] if c in PITCHING_CATS]
        sort_key, sort_reverse = "ERA", False  # lower ERA = better → ascending
    elif args.batting:
        cats = [c for c in ["R", "HR", "RBI", "SB", "BB", "AVG", "OPS"] if c in BATTING_CATS]
        sort_key, sort_reverse = "OPS", True  # higher OPS = better → descending
    else:
        cats = ["R", "HR", "RBI", "SB", "BB", "AVG", "OPS", "IP", "W", "K", "ERA", "WHIP", "QS", "SV+H"]
        sort_key, sort_reverse = "ERA", False

    # Sort
    def sort_val(t):
        try:
            return float(t.get(sort_key, ""))
        except (ValueError, TypeError):
            return float("-inf") if sort_reverse else float("inf")
    teams.sort(key=sort_val, reverse=sort_reverse)

    # Print
    header = "| # | Team | " + " | ".join(cats) + " |"
    sep = "|---|------|" + "|".join(["------"] * len(cats)) + "|"
    print(header)
    print(sep)
    for i, t in enumerate(teams, 1):
        mark = " *" if t["is_mine"] else ""
        cols = [t.get(c, "-") for c in cats]
        print(f"| {i} | {t['name'][:20]}{mark} | " + " | ".join(str(c) for c in cols) + " |")


def main():
    parser = argparse.ArgumentParser(description="Yahoo Fantasy API Query Tool")
    sub = parser.add_subparsers(dest="command")

    # FA query
    fa_parser = sub.add_parser("fa", help="Search free agents")
    fa_parser.add_argument("--position", "-p", help="Position filter (C, 1B, 2B, SS, LF, CF, RF, SP, RP, B, P)")
    fa_parser.add_argument("--sort", "-s", default="AR", help="Sort by: AR (actual rank), OR (overall rank) (default: AR)")
    fa_parser.add_argument("--sort-type", default="season", help="Sort period: season, lastweek, lastmonth (default: season)")
    fa_parser.add_argument("--count", "-n", type=int, default=25, help="Number of results (default: 25)")
    fa_parser.add_argument("--start", type=int, default=0, help="Pagination offset (default: 0)")
    fa_parser.add_argument("--status", default="A", help="Player status: A (all available, default), FA (free agents only), W (waivers only)")
    fa_parser.add_argument("--names", help="Comma-separated player names to filter (implies --auto-page; pages until all hits found)")
    fa_parser.add_argument("--auto-page", action="store_true", help="Loop pages until empty/partial/cap (default: single page from --start)")

    # Player lookup
    player_parser = sub.add_parser("player", help="Look up a specific player")
    player_parser.add_argument("player", help="Player name to search")

    # Savant Statcast lookup
    savant_parser = sub.add_parser("savant", help="Look up Statcast data from Baseball Savant")
    savant_parser.add_argument("player", help="Player name to search")
    savant_parser.add_argument("--year", "-y", help="Specific year (default: 2026 + 2025)")

    # Scoreboard
    sb_parser = sub.add_parser("scoreboard", help="League scoreboard for current week")
    sb_parser.add_argument("--pitching", action="store_true", help="Show pitching categories only")
    sb_parser.add_argument("--batting", action="store_true", help="Show batting categories only")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    # Savant command doesn't need Yahoo auth
    if args.command == "savant":
        cmd_savant(args)
        return

    env = load_env()
    if not os.path.exists(YAHOO_TOKEN_FILE):
        print("Yahoo token not found. Run yahoo_auth.py first.", file=sys.stderr)
        sys.exit(1)

    access_token = refresh_token(env)
    config = load_config()

    if args.command == "fa":
        cmd_fa(args, access_token, config)
    elif args.command == "player":
        cmd_player(args, access_token, config)
    elif args.command == "scoreboard":
        cmd_scoreboard(args, access_token, config)


if __name__ == "__main__":
    main()
