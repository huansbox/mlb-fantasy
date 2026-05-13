"""Stream SP scan — Step 2-6 of /stream-sp pipeline.

Mechanical layer: schedule parse, FA cross-check, v4 Sum, game-log opener filter,
opponent 14d strength. Output JSON for LLM to write report + pending file.
"""

from __future__ import annotations

from dataclasses import dataclass


TEAM_ABBR = {
    108: "LAA", 109: "AZ",  110: "BAL", 111: "BOS", 112: "CHC", 113: "CIN",
    114: "CLE", 115: "COL", 116: "DET", 117: "HOU", 118: "KC",  119: "LAD",
    120: "WSH", 121: "NYM", 133: "ATH", 134: "PIT", 135: "SD",  136: "SEA",
    137: "SF",  138: "STL", 139: "TB",  140: "TEX", 141: "TOR", 142: "MIN",
    143: "PHI", 144: "ATL", 145: "CWS", 146: "MIA", 147: "NYY", 158: "MIL",
}


@dataclass(frozen=True)
class GameLog:
    date: str
    gs: int
    ip: float


@dataclass(frozen=True)
class ProbablePitcher:
    mlb_id: int
    name: str


@dataclass(frozen=True)
class GameRef:
    away_team: str
    home_team: str
    away_sp: "ProbablePitcher | None"
    home_sp: "ProbablePitcher | None"


@dataclass(frozen=True)
class StarterRef:
    mlb_id: int
    name: str
    team: str
    opponent: str
    is_home: bool


@dataclass(frozen=True)
class CrossCheckResult:
    candidates: list
    owned_by_me: list
    owned_by_others: list


@dataclass
class Fetchers:
    schedule_fn: object  # (et_date) -> schedule_json
    fa_pool_fn: object   # () -> iterable[str] (FA names)
    roster_pitchers_fn: object  # () -> iterable[str] (my pitcher names)
    game_log_fn: object  # (mlb_id, season) -> list[GameLog]
    team_14d_ops_fn: object  # (team_abbr) -> float
    v4_data_fn: object   # (mlb_ids, season) -> dict[mlb_id, dict]


def classify_opener(games):
    if len(games) < 3:
        return "small_sample"
    if all(g.gs == 0 and g.ip <= 3 for g in games):
        return "opener_suspect"
    gs_count = sum(1 for g in games if g.gs == 1)
    relief_count = len(games) - gs_count
    avg_ip = sum(g.ip for g in games) / len(games)
    if 2 <= gs_count <= 3 and 2 <= relief_count <= 3 and avg_ip < 4:
        return "opener_suspect"
    return "true_starter"


def parse_schedule(schedule_json):
    games = []
    for date_block in schedule_json.get("dates", []):
        for game in date_block.get("games", []):
            teams = game["teams"]
            away_team = TEAM_ABBR[teams["away"]["team"]["id"]]
            home_team = TEAM_ABBR[teams["home"]["team"]["id"]]
            away_pp = teams["away"].get("probablePitcher")
            home_pp = teams["home"].get("probablePitcher")
            away_sp = ProbablePitcher(mlb_id=away_pp["id"], name=away_pp["fullName"]) if away_pp else None
            home_sp = ProbablePitcher(mlb_id=home_pp["id"], name=home_pp["fullName"]) if home_pp else None
            games.append(GameRef(
                away_team=away_team,
                home_team=home_team,
                away_sp=away_sp,
                home_sp=home_sp,
            ))
    return games


def tier_opponent(ops):
    if ops >= 0.755:
        return "🔴"
    if ops >= 0.720:
        return "🟡"
    return "🟢"


def cross_check_fa(probable, fa_names, my_pitcher_names):
    candidates = []
    owned_by_me = []
    owned_by_others = []
    for sp in probable:
        if sp.name in my_pitcher_names:
            owned_by_me.append(sp)
        elif sp.name in fa_names:
            candidates.append(sp)
        else:
            owned_by_others.append(sp)
    return CrossCheckResult(
        candidates=candidates,
        owned_by_me=owned_by_me,
        owned_by_others=owned_by_others,
    )


def _flatten_to_starters(games):
    starters = []
    for g in games:
        if g.away_sp:
            starters.append(StarterRef(
                mlb_id=g.away_sp.mlb_id, name=g.away_sp.name,
                team=g.away_team, opponent=g.home_team, is_home=False,
            ))
        if g.home_sp:
            starters.append(StarterRef(
                mlb_id=g.home_sp.mlb_id, name=g.home_sp.name,
                team=g.home_team, opponent=g.away_team, is_home=True,
            ))
    return starters


def _extract_tbd_games(games):
    tbd = []
    for g in games:
        if g.away_sp and g.home_sp:
            continue
        if g.away_sp is None and g.home_sp is None:
            side = "both"
        elif g.away_sp is None:
            side = "away"
        else:
            side = "home"
        tbd.append({"away": g.away_team, "home": g.home_team, "side": side})
    return tbd


def _starter_to_summary(sp):
    return {
        "name": sp.name,
        "mlb_id": sp.mlb_id,
        "team": sp.team,
        "opponent": sp.opponent,
        "is_home": sp.is_home,
    }


def _enrich_v4(raw):
    """Wrap raw v4 5-slot dict with sum_score / breakdown_pct / rotation_gate / luck_tag.

    Lazy-imports fa_compute so test envs that don't need enrichment (e.g. pure-
    function unit tests) don't pay the daily_advisor import cost.
    """
    if not raw:
        return {}
    from fa_compute import (  # type: ignore[import-not-found]
        compute_sum_score_v4_sp,
        format_sp_breakdown_human,
        luck_tag_v4,
        rotation_gate_v4,
    )
    sum_score, breakdown = compute_sum_score_v4_sp(raw)
    gate_icon, _ = rotation_gate_v4(raw.get("g", 0), raw.get("gs", 0))
    luck = luck_tag_v4(raw.get("xera"), raw.get("era"), raw.get("bbe"))
    return {
        **raw,
        "sum_score": sum_score,
        "breakdown_pct": format_sp_breakdown_human(breakdown),
        "rotation_gate": gate_icon,
        "luck_tag": luck,
    }


def scan(et_dates, *, fetchers):
    result = {}
    for et_date in et_dates:
        sched_json = fetchers.schedule_fn(et_date)
        games = parse_schedule(sched_json)
        probable = _flatten_to_starters(games)

        fa_names = set(fetchers.fa_pool_fn())
        my_names = set(fetchers.roster_pitchers_fn())
        cross = cross_check_fa(probable, fa_names, my_names)

        # Batch v4 fetches: one call per season covers all candidates.
        ids = [sp.mlb_id for sp in cross.candidates]
        v4_26_all = fetchers.v4_data_fn(ids, 2026) if ids else {}
        v4_25_all = fetchers.v4_data_fn(ids, 2025) if ids else {}

        candidates_out = []
        for sp in cross.candidates:
            log = fetchers.game_log_fn(sp.mlb_id, 2026)
            ops = fetchers.team_14d_ops_fn(sp.opponent)
            candidates_out.append({
                **_starter_to_summary(sp),
                "opener_verdict": classify_opener(log),
                "opponent_14d": {"ops": ops, "tier": tier_opponent(ops)},
                "v4_2026": _enrich_v4(v4_26_all.get(sp.mlb_id, {})),
                "v4_2025": _enrich_v4(v4_25_all.get(sp.mlb_id, {})),
            })

        result[et_date] = {
            "tbd_games": _extract_tbd_games(games),
            "candidates": candidates_out,
            "owned_by_me": [_starter_to_summary(s) for s in cross.owned_by_me],
            "owned_by_others": [_starter_to_summary(s) for s in cross.owned_by_others],
        }
    return result


# ── Production fetchers (system boundary; not TDD-tested, manually verified) ──

ABBR_TO_ID = {v: k for k, v in TEAM_ABBR.items()}


def _http_get_json(url):
    import urllib.request
    import json as _json
    with urllib.request.urlopen(url, timeout=30) as r:
        return _json.loads(r.read().decode("utf-8"))


def fetch_mlb_schedule(et_date):
    url = (
        f"https://statsapi.mlb.com/api/v1/schedule"
        f"?date={et_date}&sportId=1&hydrate=probablePitcher"
    )
    return _http_get_json(url)


def _ip_str_to_float(ip_str):
    s = str(ip_str)
    if "." in s:
        whole, frac = s.split(".")
        return int(whole) + int(frac) / 3.0
    return float(s)


def fetch_game_log(mlb_id, season, *, limit=6):
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
        f"?stats=gameLog&season={season}&group=pitching"
    )
    data = _http_get_json(url)
    splits = data.get("stats", [{}])[0].get("splits", [])
    logs = []
    for s in splits[-limit:]:
        st = s.get("stat", {})
        logs.append(GameLog(
            date=s.get("date", ""),
            gs=int(st.get("gamesStarted", 0)),
            ip=_ip_str_to_float(st.get("inningsPitched", "0")),
        ))
    return logs


def fetch_team_14d_ops(team_abbr):
    from datetime import date, timedelta
    team_id = ABBR_TO_ID.get(team_abbr)
    if team_id is None:
        return 0.720  # fallback to league avg
    end = date.today()
    start = end - timedelta(days=14)
    url = (
        f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats"
        f"?stats=byDateRange&group=hitting&season={end.year}"
        f"&startDate={start.isoformat()}&endDate={end.isoformat()}&sportId=1"
    )
    data = _http_get_json(url)
    try:
        s = data["stats"][0]["splits"][0]["stat"]
        return float(s.get("ops", 0.720))
    except (KeyError, IndexError, ValueError):
        return 0.720


def load_roster_pitchers():
    import json as _json
    from pathlib import Path
    cfg = Path(__file__).parent / "roster_config.json"
    with cfg.open(encoding="utf-8") as f:
        data = _json.load(f)
    return [p["name"] for p in data.get("pitchers", [])]


def fetch_yahoo_fa_sp_names():
    """Page through Yahoo FA SP pool, return all names. Requires VPS env (token)."""
    import yahoo_query  # type: ignore[import-not-found]
    env = yahoo_query.load_env()
    access_token = yahoo_query.refresh_token(env)
    config = yahoo_query.load_config()
    league_key = config["league"]["league_key"]

    names = []
    page_size = 25
    for start in range(0, 300, page_size):
        path = (
            f"/league/{league_key}/players"
            f";status=A;position=SP;sort=AR;count={page_size};start={start}"
            f";out=stats,percent_owned,ownership"
        )
        data = yahoo_query.api_get(path, access_token)
        league_data = data["fantasy_content"]["league"]
        if len(league_data) < 2 or "players" not in league_data[1]:
            break
        players_data = league_data[1]["players"]
        page_names = []
        for k, v in players_data.items():
            if k == "count":
                continue
            p = yahoo_query.extract_player_info(v["player"])
            page_names.append(p["name"])
        if not page_names:
            break
        names.extend(page_names)
        if len(page_names) < page_size:
            break
    return names


def fetch_v4_data(mlb_ids, season):
    # sp_data_fetchers prints progress to stdout — redirect to stderr so our
    # JSON output stays clean for downstream LLM consumption.
    import contextlib
    import sys

    from sp_data_fetchers import assemble_data  # type: ignore[import-not-found]
    with contextlib.redirect_stdout(sys.stderr):
        return assemble_data(mlb_ids, season)


def build_real_fetchers():
    return Fetchers(
        schedule_fn=fetch_mlb_schedule,
        fa_pool_fn=fetch_yahoo_fa_sp_names,
        roster_pitchers_fn=load_roster_pitchers,
        game_log_fn=fetch_game_log,
        team_14d_ops_fn=fetch_team_14d_ops,
        v4_data_fn=fetch_v4_data,
    )


def main():
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(
        description="Stream SP scan — pipeline Step 2-6 (schedule + FA cross-check + v4 + opener filter + opponent strength)",
    )
    parser.add_argument(
        "--et-dates", required=True,
        help="comma-separated ET dates, e.g. 2026-05-14,2026-05-15",
    )
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = parser.parse_args()

    et_dates = [d.strip() for d in args.et_dates.split(",") if d.strip()]
    fetchers = build_real_fetchers()
    result = scan(et_dates, fetchers=fetchers)
    indent = 2 if args.pretty else None
    print(_json.dumps(result, indent=indent, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
