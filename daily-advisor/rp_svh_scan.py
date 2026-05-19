"""RP-SV+H scan — mechanical layer of the /rp-svh skill.

Production-first SOP (docs/rp-svh-metrics.md):

  Step 1  all-league 14d SV+H≥floor producers   (MLB byDateRange)
  Step 2  cross-check Yahoo FA                   (query_fa --names)
  Step 3  3-axis fetch — BB/9 · whiff% · 30d SV+H
  Step 4  rank-sum → top-N (ties at cutoff included)
  Step 5  incumbent (rostered SV+H RP) — same axes, as benchmark
  Step 6  role signals for top-N + incumbent — recent-10g SV/H · blownSaves+SVO · week schedule

Output JSON; the LLM layer does news check + verdict. Pure-function core is
TDD-tested; production fetchers are a system boundary, manually verified.

Axis 3 = 30d SV+H (a window wider than the 14d entry floor) was chosen over
team win% / this-week games: it is player-level, orthogonal to the two
quality axes (no double-voting), and reuses the Step 1 byDateRange call.
See issues/rp-svh-sop.md open decision 2.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

from stream_sp_scan import TEAM_ABBR

FLOOR_DEFAULT = 3
TOP_N_DEFAULT = 4
WINDOW_14D = 14
WINDOW_30D = 30
WEEK_AHEAD_DAYS = 6
# Savant pitch-arsenal percentile baseline is ≥500 pitches; an in-season RP
# sits around ~300, so whiff% rank is usable (relative) but the absolute
# value carries a low-sample caveat for the LLM layer.
WHIFF_LOW_SAMPLE_PITCHES = 500


def _normalize(name: str) -> str:
    """Strip accents + apostrophes + lowercase — fuzzy name match across the
    MLB Stats API (Step 1) and Yahoo (Step 2) name spellings."""
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    )
    return stripped.replace("'", "").replace("’", "").lower()


# ── Dataclasses ──

@dataclass(frozen=True)
class SvhProducer:
    mlb_id: int
    name: str
    team_id: int
    team: str
    saves: int
    holds: int

    @property
    def svh(self) -> int:
        return self.saves + self.holds


@dataclass(frozen=True)
class FAEntry:
    name: str
    percent_owned: str  # "9%" / "—" — formatted display string


@dataclass(frozen=True)
class RosterPitcher:
    mlb_id: int
    name: str
    positions: tuple  # ("SP",) / ("RP",) / ("SP", "RP") ...


@dataclass
class Fetchers:
    svh_leaderboard_fn: object   # (start_date, end_date) -> bydate_json
    fa_pool_fn: object           # (names: set[str]) -> list[FAEntry]
    roster_pitchers_fn: object   # () -> list[RosterPitcher]
    season_stats_fn: object      # (mlb_ids, season) -> {pid: {...}}
    whiff_fn: object             # (season) -> {pid: {whiff_pct, arsenal_pitches}}
    game_log_fn: object          # (mlb_id, season) -> list[dict] (per-game saves/holds)
    week_schedule_fn: object     # (start_date, end_date) -> schedule_json


# ── Step 1: parse all-league SV+H leaderboard ──

def parse_svh_leaderboard(bydate_json) -> list[SvhProducer]:
    """Parse a byDateRange pitching leaderboard into SvhProducer list (unfiltered).

    The caller applies the SV+H floor; this returns every split so the same
    parse serves both the 14d window (floor + sv/h split) and the 30d window
    (axis-3 lookup).
    """
    producers = []
    for stat_group in bydate_json.get("stats", []):
        for split in stat_group.get("splits", []):
            player = split.get("player") or {}
            team = split.get("team") or {}
            stat = split.get("stat") or {}
            pid = player.get("id")
            if pid is None:
                continue
            team_id = team.get("id", 0)
            producers.append(SvhProducer(
                mlb_id=pid,
                name=player.get("fullName", ""),
                team_id=team_id,
                team=TEAM_ABBR.get(team_id, team.get("name", "")[:3].upper()),
                saves=int(stat.get("saves", 0) or 0),
                holds=int(stat.get("holds", 0) or 0),
            ))
    return producers


# ── Step 2: cross-check Yahoo FA ──

def filter_fa_candidates(producers, fa_entries):
    """Keep producers that are Yahoo FA. Returns list of (SvhProducer, FAEntry).

    Match on accent/apostrophe-normalized name — Step 1 (MLB) and Step 2
    (Yahoo) disagree on spellings. mlb_id is retained from the producer so
    downstream fetches need no name→id resolution.
    """
    fa_by_norm = {_normalize(e.name): e for e in fa_entries}
    out = []
    for pr in producers:
        entry = fa_by_norm.get(_normalize(pr.name))
        if entry is not None:
            out.append((pr, entry))
    return out


# ── Step 4: rank-sum ──

def rank_avg(values, *, ascending):
    """Average-rank a list of values (ties share the mean of their ranks).

    ascending=True  → smaller value gets rank 1 (BB/9: lower is better).
    ascending=False → larger value gets rank 1 (whiff% / 30d SV+H).
    None values always rank worst (placed after every real value).
    """
    ranks = [0.0] * len(values)
    reals = [(i, v) for i, v in enumerate(values) if v is not None]
    nones = [i for i, v in enumerate(values) if v is None]
    reals.sort(key=lambda iv: iv[1], reverse=not ascending)

    pos = 0
    j = 0
    while j < len(reals):
        k = j
        while k < len(reals) and reals[k][1] == reals[j][1]:
            k += 1
        avg = (pos + 1 + pos + (k - j)) / 2  # ranks pos+1 .. pos+(k-j)
        for m in range(j, k):
            ranks[reals[m][0]] = avg
        pos += k - j
        j = k

    if nones:
        avg = (pos + 1 + pos + len(nones)) / 2
        for i in nones:
            ranks[i] = avg
    return ranks


def rank_sum_select(candidates, *, n):
    """Compute 3-axis ranks + rank-sum, return (ranked_all, top).

    candidates: list of dicts each with axes value keys bb9 / whiff_pct /
    svh_30d. Mutates each dict in place adding ``axes`` (per-axis value+rank)
    and ``rank_sum``. ``top`` is the best ``n`` by rank-sum, with every
    candidate tied at the Nth rank-sum value included.
    """
    bb9_ranks = rank_avg([c["bb9"] for c in candidates], ascending=True)
    whiff_ranks = rank_avg([c["whiff_pct"] for c in candidates], ascending=False)
    svh_ranks = rank_avg([c["svh_30d"] for c in candidates], ascending=False)

    for c, rb, rw, rs in zip(candidates, bb9_ranks, whiff_ranks, svh_ranks):
        c["axes"] = {
            "bb9": {"value": c["bb9"], "rank": rb},
            "whiff_pct": {"value": c["whiff_pct"], "rank": rw},
            "svh_30d": {"value": c["svh_30d"], "rank": rs},
        }
        c["rank_sum"] = rb + rw + rs

    ranked = sorted(candidates, key=lambda c: c["rank_sum"])
    for place, c in enumerate(ranked, 1):
        c["rank_sum_place"] = place

    if len(ranked) <= n:
        return ranked, list(ranked)
    cutoff = ranked[n - 1]["rank_sum"]
    top = [c for c in ranked if c["rank_sum"] <= cutoff]
    return ranked, top


# ── Step 5: incumbent ──

def pick_incumbent(roster_pitchers, season_stats):
    """The rostered SV+H reliever to benchmark FA candidates against.

    RP-eligible roster pitcher with the highest season SV+H. Returns None
    when there is no RP-eligible pitcher or none has any SV+H (case B — no
    incumbent, see docs/rp-svh-metrics.md "要 LLM 輸出").
    """
    rp = [p for p in roster_pitchers if "RP" in p.positions]
    if not rp:
        return None
    best = None
    best_svh = 0
    for p in rp:
        st = season_stats.get(p.mlb_id, {})
        svh = int(st.get("saves", 0) or 0) + int(st.get("holds", 0) or 0)
        if svh > best_svh:
            best_svh, best = svh, p
    return best


# ── Step 6: role signals ──

def recent_svh(game_logs, *, limit=10):
    """Sum SV / H over the most recent ``limit`` game-log entries."""
    recent = list(game_logs)[-limit:]
    sv = sum(int(g.get("saves", 0) or 0) for g in recent)
    h = sum(int(g.get("holds", 0) or 0) for g in recent)
    return {"games": len(recent), "sv": sv, "h": h, "svh": sv + h}


def count_team_games(schedule_json):
    """Per-team game count + opponent list over a schedule date range."""
    out = {}
    for date_block in schedule_json.get("dates", []):
        for game in date_block.get("games", []):
            teams = game.get("teams", {})
            away = teams.get("away", {}).get("team", {}).get("id")
            home = teams.get("home", {}).get("team", {}).get("id")
            if away is None or home is None:
                continue
            for tid, opp in ((away, home), (home, away)):
                slot = out.setdefault(tid, {"games": 0, "opponents": []})
                slot["games"] += 1
                slot["opponents"].append(TEAM_ABBR.get(opp, str(opp)))
    return out


# ── Enrichment helper ──

def _whiff_profile(whiff_entry):
    if not whiff_entry:
        return None, None, False
    pct = whiff_entry.get("whiff_pct")
    pitches = whiff_entry.get("arsenal_pitches", 0)
    return pct, pitches, bool(pitches and pitches < WHIFF_LOW_SAMPLE_PITCHES)


def _build_signals(pid, *, season_stats, game_log_fn, season, team_games):
    st = season_stats.get(pid, {})
    logs = game_log_fn(pid, season)
    return {
        "recent_10g": recent_svh(logs, limit=10),
        "blown_saves": int(st.get("blown_saves", 0) or 0),
        "save_opportunities": int(st.get("save_opportunities", 0) or 0),
        "week_schedule": team_games,
    }


# ── Orchestrator ──

def scan(*, today, fetchers, floor=FLOOR_DEFAULT, top_n=TOP_N_DEFAULT,
         window_30d=WINDOW_30D, week_ahead_days=WEEK_AHEAD_DAYS):
    """Run the full RP-SV+H mechanical pipeline. ``today`` is a date object."""
    season = today.year
    end = today.isoformat()
    start_14 = (today - timedelta(days=WINDOW_14D)).isoformat()
    start_30 = (today - timedelta(days=window_30d)).isoformat()

    # Step 1 — all-league SV+H producers (14d window)
    producers_14 = parse_svh_leaderboard(
        fetchers.svh_leaderboard_fn(start_14, end))
    producer_by_pid = {p.mlb_id: p for p in producers_14}
    producers = [p for p in producers_14 if p.svh >= floor]

    # Step 2 — cross-check Yahoo FA
    fa_entries = fetchers.fa_pool_fn({p.name for p in producers}) if producers else []
    fa_pairs = filter_fa_candidates(producers, fa_entries)

    # Step 5 prep — incumbent (needs RP-eligible roster season stats)
    roster = list(fetchers.roster_pitchers_fn())
    rp_ids = [p.mlb_id for p in roster if "RP" in p.positions]

    # Step 3 — 3-axis data (one season-stats + one whiff call cover all)
    cand_ids = [pr.mlb_id for pr, _ in fa_pairs]
    season_stats = fetchers.season_stats_fn(cand_ids + rp_ids, season)
    whiff = fetchers.whiff_fn(season)
    svh_30_by_pid = {
        p.mlb_id: p.svh
        for p in parse_svh_leaderboard(
            fetchers.svh_leaderboard_fn(start_30, end))
    }

    candidates = []
    for pr, entry in fa_pairs:
        st = season_stats.get(pr.mlb_id, {})
        w_pct, w_pitches, w_low = _whiff_profile(whiff.get(pr.mlb_id))
        candidates.append({
            "name": pr.name,
            "mlb_id": pr.mlb_id,
            "team": pr.team,
            "team_id": pr.team_id,
            "percent_owned": entry.percent_owned,
            "bb9": st.get("bb9"),
            "whiff_pct": w_pct,
            "whiff_pitches": w_pitches,
            "whiff_low_sample": w_low,
            "svh_30d": svh_30_by_pid.get(pr.mlb_id, pr.svh),
            "profile": {
                "svh_14d": pr.svh,
                "sv_14d": pr.saves,
                "h_14d": pr.holds,
                "era": st.get("era"),
                "ip": st.get("ip"),
            },
        })

    # Step 4 — rank-sum → top-N
    ranked, top = rank_sum_select(candidates, n=top_n) if candidates else ([], [])

    # Step 6 — role signals for top-N + incumbent
    week_start = today.isoformat()
    week_end = (today + timedelta(days=week_ahead_days)).isoformat()
    sched = fetchers.week_schedule_fn(week_start, week_end)
    team_games = count_team_games(sched)

    for c in top:
        c["role_signals"] = _build_signals(
            c["mlb_id"], season_stats=season_stats,
            game_log_fn=fetchers.game_log_fn, season=season,
            team_games=team_games.get(c["team_id"], {"games": 0, "opponents": []}),
        )

    incumbent_player = pick_incumbent(roster, season_stats)
    incumbent_out = None
    if incumbent_player is not None:
        pid = incumbent_player.mlb_id
        st = season_stats.get(pid, {})
        pr = producer_by_pid.get(pid)
        w_pct, w_pitches, w_low = _whiff_profile(whiff.get(pid))
        incumbent_out = {
            "name": incumbent_player.name,
            "mlb_id": pid,
            "in_pool": False,
            "bb9": st.get("bb9"),
            "whiff_pct": w_pct,
            "whiff_pitches": w_pitches,
            "whiff_low_sample": w_low,
            "svh_30d": svh_30_by_pid.get(pid, 0),
            "profile": {
                "svh_14d": pr.svh if pr else 0,
                "sv_14d": pr.saves if pr else 0,
                "h_14d": pr.holds if pr else 0,
                "era": st.get("era"),
                "ip": st.get("ip"),
            },
            "role_signals": _build_signals(
                pid, season_stats=season_stats,
                game_log_fn=fetchers.game_log_fn, season=season,
                team_games=team_games.get(
                    _roster_team_id(incumbent_player, producer_by_pid),
                    {"games": 0, "opponents": []}),
            ),
        }

    return {
        "scan_date": end,
        "floor": floor,
        "window_14d": {"start": start_14, "end": end},
        "window_30d": {"start": start_30, "end": end},
        "week_window": {"start": week_start, "end": week_end},
        "candidate_pool_size": len(candidates),
        "top_candidates": top,
        "incumbent": incumbent_out,
        "all_candidates": [
            {
                "name": c["name"], "team": c["team"], "mlb_id": c["mlb_id"],
                "svh_14d": c["profile"]["svh_14d"],
                "rank_sum": c["rank_sum"], "rank_sum_place": c["rank_sum_place"],
                "axes": c["axes"],
            }
            for c in ranked
        ],
    }


def _roster_team_id(incumbent_player, producer_by_pid):
    """Best-effort team id for the incumbent's week-schedule lookup."""
    pr = producer_by_pid.get(incumbent_player.mlb_id)
    return pr.team_id if pr else None


# ── Production fetchers (system boundary; not TDD-tested, manually verified) ──

def _http_get_json(url, timeout=30):
    import json as _json
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return _json.loads(r.read().decode("utf-8"))


def fetch_svh_leaderboard(start_date, end_date):
    """All-league pitching byDateRange leaderboard (no token needed)."""
    url = (
        "https://statsapi.mlb.com/api/v1/stats?stats=byDateRange&group=pitching"
        f"&startDate={start_date}&endDate={end_date}"
        "&sportId=1&playerPool=All&limit=900"
    )
    return _http_get_json(url)


def fetch_yahoo_fa_pool(names=None):
    """Yahoo FA pitcher pool filtered by name. Requires VPS env (Yahoo token)."""
    import yahoo_query  # type: ignore[import-not-found]
    env = yahoo_query.load_env()
    access_token = yahoo_query.refresh_token(env)
    config = yahoo_query.load_config()
    league_key = config["league"]["league_key"]
    players = yahoo_query.query_fa(
        access_token, league_key,
        position="P", status="A",
        names=set(names) if names else None,
        auto_page=True,
    )
    return [
        FAEntry(
            name=p["name"],
            percent_owned=(f"{p['percent_owned']}%" if p.get("percent_owned")
                           not in (None, "") else "—"),
        )
        for p in players
    ]


def load_roster_pitchers():
    import json as _json
    from pathlib import Path
    cfg = Path(__file__).parent / "roster_config.json"
    with cfg.open(encoding="utf-8") as f:
        data = _json.load(f)
    return [
        RosterPitcher(
            mlb_id=p["mlb_id"], name=p["name"],
            positions=tuple(p.get("positions", [])),
        )
        for p in data.get("pitchers", [])
    ]


def fetch_season_stats(mlb_ids, season):
    import contextlib
    import sys

    from sp_data_fetchers import fetch_mlb_season_stats  # type: ignore[import-not-found]
    with contextlib.redirect_stdout(sys.stderr):
        return fetch_mlb_season_stats(list(mlb_ids), season)


def fetch_whiff(season):
    import contextlib
    import sys

    from sp_data_fetchers import fetch_savant_arsenal_whiff  # type: ignore[import-not-found]
    with contextlib.redirect_stdout(sys.stderr):
        return fetch_savant_arsenal_whiff(season)


def fetch_game_log(mlb_id, season):
    """Per-game pitching log with saves/holds for the recent-10g signal."""
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
        f"?stats=gameLog&season={season}&group=pitching"
    )
    data = _http_get_json(url)
    splits = (data.get("stats") or [{}])[0].get("splits", []) or []
    return [
        {
            "date": s.get("date", ""),
            "saves": int(s.get("stat", {}).get("saves", 0) or 0),
            "holds": int(s.get("stat", {}).get("holds", 0) or 0),
        }
        for s in splits
    ]


def fetch_week_schedule(start_date, end_date):
    url = (
        "https://statsapi.mlb.com/api/v1/schedule"
        f"?startDate={start_date}&endDate={end_date}&sportId=1"
    )
    return _http_get_json(url)


def build_real_fetchers():
    return Fetchers(
        svh_leaderboard_fn=fetch_svh_leaderboard,
        fa_pool_fn=fetch_yahoo_fa_pool,
        roster_pitchers_fn=load_roster_pitchers,
        season_stats_fn=fetch_season_stats,
        whiff_fn=fetch_whiff,
        game_log_fn=fetch_game_log,
        week_schedule_fn=fetch_week_schedule,
    )


def main():
    import argparse
    import json as _json
    from datetime import datetime
    from zoneinfo import ZoneInfo

    parser = argparse.ArgumentParser(
        description="RP-SV+H scan — mechanical layer (Step 1-6) of the /rp-svh skill",
    )
    parser.add_argument("--floor", type=int, default=FLOOR_DEFAULT,
                        help=f"14d SV+H entry floor (default {FLOOR_DEFAULT})")
    parser.add_argument("--top", type=int, default=TOP_N_DEFAULT,
                        help=f"rank-sum top-N (default {TOP_N_DEFAULT}; ties at cutoff included)")
    parser.add_argument("--date", default=None,
                        help="ET scan date YYYY-MM-DD (default: ET today)")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = parser.parse_args()

    today = (date.fromisoformat(args.date) if args.date
             else datetime.now(ZoneInfo("America/New_York")).date())
    result = scan(today=today, fetchers=build_real_fetchers(),
                  floor=args.floor, top_n=args.top)
    indent = 2 if args.pretty else None
    print(_json.dumps(result, indent=indent, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
