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
    projected: bool = False  # True = user-supplied projected (not MLB-official) starter


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
    projected: bool = False


@dataclass(frozen=True)
class CrossCheckResult:
    candidates: list
    owned_by_me: list
    owned_by_others: list


@dataclass(frozen=True)
class FAEntry:
    name: str
    percent_owned: str  # "9%" / "25%" / "—" — formatted display string


@dataclass
class Fetchers:
    schedule_fn: object  # (et_date) -> schedule_json
    fa_pool_fn: object   # (starter_names: set[str]) -> list[FAEntry]
    roster_pitchers_fn: object  # () -> iterable[str] (my pitcher names)
    game_log_fn: object  # (mlb_id, season) -> list[GameLog]
    team_14d_ops_fn: object  # (team_abbr, end_date: str YYYY-MM-DD) -> float
    v4_data_fn: object   # (mlb_ids, season) -> dict[mlb_id, dict]
    # Optional — old tests / callers not using vs_hand can omit. None ⇒ emit
    # vs_hand_2026=None for every candidate (LLM falls back to 14d/season anchor).
    vs_hand_fn: object = None  # (opp_abbr, sp_id) -> raw dict | None
    # Optional — only needed when scan() is called with projected= injection.
    id_resolver_fn: object = None  # (team_abbr, name) -> mlb_id


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


def parse_projected_arg(s):
    """Parse --projected CLI string → {et_date: [(team_abbr, name), ...]}.

    Format: ``ET_DATE:TEAM:Full Name`` entries joined by commas, e.g.
    ``2026-06-20:WSH:MacKenzie Gore,2026-06-20:CHC:Jameson Taillon``.

    The name segment may contain spaces or colons — only the first two colons
    are split on, so ``WSH:Foo: Bar`` keeps name ``Foo: Bar``. Blank entries
    (trailing/double commas) are skipped. Each segment is whitespace-trimmed.
    Raises ValueError on an entry with fewer than 3 segments.
    """
    if not s:
        return {}
    out: dict = {}
    for entry in s.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":", 2)
        if len(parts) < 3:
            raise ValueError(
                f"projected entry needs ET_DATE:TEAM:Name, got {entry!r}"
            )
        et_date, team, name = (p.strip() for p in parts)
        out.setdefault(et_date, []).append((team, name))
    return out


def apply_projected(games, projected_for_date, id_resolver):
    """Fill TBD sides of ``games`` with user-supplied projected starters.

    ``projected_for_date``: list of ``(team_abbr, name)`` for one ET date.
    ``id_resolver(team_abbr, name) -> mlb_id`` resolves the name to an MLB id
    (team-scoped → avoids homonym collisions; called lazily, only when a slot
    is actually filled).

    Rules:
    - Only an **empty** (``None``) side is filled — official probables are
      never overwritten.
    - The injected ProbablePitcher is flagged ``projected=True``.
    - A team not on this date's schedule (or whose matching side is already
      official) is silently skipped.

    Returns a new games list (frozen GameRefs rebuilt via ``dataclasses.replace``).
    """
    import dataclasses

    games = list(games)
    for team_abbr, name in projected_for_date:
        for i, g in enumerate(games):
            if g.away_team == team_abbr and g.away_sp is None:
                pp = ProbablePitcher(
                    mlb_id=id_resolver(team_abbr, name), name=name, projected=True,
                )
                games[i] = dataclasses.replace(g, away_sp=pp)
                break
            if g.home_team == team_abbr and g.home_sp is None:
                pp = ProbablePitcher(
                    mlb_id=id_resolver(team_abbr, name), name=name, projected=True,
                )
                games[i] = dataclasses.replace(g, home_sp=pp)
                break
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
                projected=g.away_sp.projected,
            ))
        if g.home_sp:
            starters.append(StarterRef(
                mlb_id=g.home_sp.mlb_id, name=g.home_sp.name,
                team=g.home_team, opponent=g.away_team, is_home=True,
                projected=g.home_sp.projected,
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
        "projected": sp.projected,
    }


def _enrich_v4(raw):
    """Wrap raw v4 5-slot dict with sum_score / breakdown_pct / rotation_gate / luck_tag.

    Empty raw (rookie / no Savant data / fetch miss) returns an explicit
    placeholder with ``v4_available=False`` so downstream filter rules can
    branch on a known key instead of catching KeyError on missing fields.

    Lazy-imports fa_compute so test envs that don't need enrichment (e.g. pure-
    function unit tests) don't pay the daily_advisor import cost.
    """
    if not raw:
        return {
            "v4_available": False,
            "sum_score": None,
            "breakdown_pct": {},
            "rotation_gate": None,
            "luck_tag": None,
        }
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
        "v4_available": True,
        "sum_score": sum_score,
        "breakdown_pct": format_sp_breakdown_human(breakdown),
        "rotation_gate": gate_icon,
        "luck_tag": luck,
    }


VS_HAND_PA_THRESHOLD = 400  # Below this, opponent vs SP-hand sample too thin → fallback to full season OPS.


def compute_sample_warning(*, bbe, gs):
    """2026 sample-confidence warning (issue 013).

    Two axes — BBE drives contact-quality slots (GB%/xwOBACON), GS drives
    role/usage slots (IP/GS, BB/9, Whiff%). AND-for-low semantics:

    - "low": BBE<30 AND GS<6 — both critically thin, every structural axis
      suspect → LLM should downgrade confidence by 2 notches
    - "medium": BBE≤80 OR GS≤12 — at least one axis sample concerning →
      downgrade confidence by 1 notch
    - "none": BBE>80 AND GS>12 — both reliable, trust structural signals

    None on either input → return None (caller should pass through when
    v4 data unavailable; "low" would over-warn rookies missing Savant).
    """
    if bbe is None or gs is None:
        return None
    if bbe < 30 and gs < 6:
        return "low"
    if bbe <= 80 or gs <= 12:
        return "medium"
    return "none"


def _apply_vs_hand_gate(raw, pa_threshold=VS_HAND_PA_THRESHOLD):
    """Transform raw vs-hand fetcher output → final emit dict (with PA gate).

    raw expected keys: pa, split_ops, k_pct, bb_pct, hand, season_ops.
    None raw (API failure) passes through as None.
    Hand=None (switch / unknown) or PA<threshold → fallback to season_ops + low_pa_fallback=True.
    """
    if raw is None:
        return None
    pa = raw.get("pa", 0) or 0
    hand = raw.get("hand")
    low_pa = pa < pa_threshold or hand is None
    final_ops = raw.get("season_ops") if low_pa else raw.get("split_ops")
    return {
        "pa": pa,
        "ops": final_ops,
        "k_pct": raw.get("k_pct"),
        "bb_pct": raw.get("bb_pct"),
        "hand": hand,
        "low_pa_fallback": low_pa,
    }


def compute_pending_diff(pending_evaluations, scan_result_for_date):
    """Diff pending evaluations vs today's scan for one ET date.

    Slot-based matching: each pending eval has (name, team, is_home). We look
    up the (team, is_home) slot in today's scan and bucket by outcome:

    - **still_starting**: same SP at the slot, in candidates or owned_by_me
      (FA-or-mine + still starting)
    - **lost_to_others**: same SP at the slot, in owned_by_others
      (聯盟認領)
    - **replaced**: different SP at the slot (incl. new=None when slot is TBD)
    - **no_longer_scheduled**: that team has no slot today (球隊雨延 / 沒打)

    Slot keying disambiguates homonyms (Clay Holmes NYM vs Grant Holmes ATL).
    """
    starters_by_slot: dict = {}  # (team, is_home) → {"name", "bucket"}
    for bucket in ("candidates", "owned_by_me", "owned_by_others"):
        for sp in scan_result_for_date.get(bucket, []):
            starters_by_slot[(sp["team"], sp["is_home"])] = {
                "name": sp["name"], "bucket": bucket,
            }

    tbd_slots: set = set()
    for t in scan_result_for_date.get("tbd_games", []):
        side = t.get("side")
        if side in ("away", "both"):
            tbd_slots.add((t["away"], False))
        if side in ("home", "both"):
            tbd_slots.add((t["home"], True))

    teams_playing = (
        {team for (team, _) in starters_by_slot}
        | {team for (team, _) in tbd_slots}
    )

    still: list = []
    lost: list = []
    replaced: list = []
    gone: list = []
    for ev in pending_evaluations:
        slot = (ev["team"], ev["is_home"])
        starter = starters_by_slot.get(slot)
        if starter and starter["name"] == ev["name"]:
            if starter["bucket"] == "owned_by_others":
                lost.append(ev["name"])
            else:
                still.append(ev["name"])
        elif starter:
            replaced.append({
                "old": ev["name"], "new": starter["name"], "team": ev["team"],
            })
        elif slot in tbd_slots:
            replaced.append({
                "old": ev["name"], "new": None, "team": ev["team"],
            })
        elif ev["team"] not in teams_playing:
            gone.append(ev["name"])
        else:
            # Team plays today but pending side has no slot — defensive fallback
            gone.append(ev["name"])
    return {
        "still_starting": still,
        "lost_to_others": lost,
        "replaced": replaced,
        "no_longer_scheduled": gone,
    }


def scan(et_dates, *, fetchers, pending_data=None, projected=None):
    """Scan ET dates for streamable FA starters.

    ``projected`` (optional): ``{et_date: [(team_abbr, name), ...]}`` — manual
    projected starters injected into TBD slots before FA cross-check, so the
    user can evaluate not-yet-official probables (e.g. read off the Yahoo app)
    through the full v4 pipeline. Injected candidates carry ``projected=True``.
    """
    result = {}
    for et_date in et_dates:
        sched_json = fetchers.schedule_fn(et_date)
        games = parse_schedule(sched_json)
        if projected and projected.get(et_date):
            games = apply_projected(
                games, projected[et_date], fetchers.id_resolver_fn,
            )
        probable = _flatten_to_starters(games)

        # Pass starter names to fa_pool_fn so it can filter the pool early —
        # production fetcher can stop paging once all hits are found.
        starter_names = {sp.name for sp in probable}
        fa_entries = fetchers.fa_pool_fn(starter_names) if starter_names else []
        fa_names = {e.name for e in fa_entries}
        pct_by_name = {e.name: e.percent_owned for e in fa_entries}

        my_names = set(fetchers.roster_pitchers_fn())
        cross = cross_check_fa(probable, fa_names, my_names)

        # Batch v4 fetches: one call per season covers all candidates.
        ids = [sp.mlb_id for sp in cross.candidates]
        v4_26_all = fetchers.v4_data_fn(ids, 2026) if ids else {}
        v4_25_all = fetchers.v4_data_fn(ids, 2025) if ids else {}

        candidates_out = []
        for sp in cross.candidates:
            log = fetchers.game_log_fn(sp.mlb_id, 2026)
            ops = fetchers.team_14d_ops_fn(sp.opponent, et_date)
            vs_hand_raw = (
                fetchers.vs_hand_fn(sp.opponent, sp.mlb_id)
                if fetchers.vs_hand_fn else None
            )
            v4_26 = _enrich_v4(v4_26_all.get(sp.mlb_id, {}))
            sample_warning = (
                compute_sample_warning(bbe=v4_26.get("bbe"), gs=v4_26.get("gs"))
                if v4_26.get("v4_available") else None
            )
            candidates_out.append({
                **_starter_to_summary(sp),
                "percent_owned": pct_by_name.get(sp.name, "—"),
                "opener_verdict": classify_opener(log),
                "opponent_14d": {"ops": ops, "tier": tier_opponent(ops)},
                "sample_warning": sample_warning,
                "v4_2026": v4_26,
                "v4_2025": _enrich_v4(v4_25_all.get(sp.mlb_id, {})),
                "vs_hand_2026": _apply_vs_hand_gate(vs_hand_raw),
            })

        result[et_date] = {
            "tbd_games": _extract_tbd_games(games),
            "candidates": candidates_out,
            "owned_by_me": [_starter_to_summary(s) for s in cross.owned_by_me],
            "owned_by_others": [_starter_to_summary(s) for s in cross.owned_by_others],
        }

    if pending_data is not None:
        diff: dict = {}
        for et_date in et_dates:
            day_pending = pending_data.get(et_date)
            day_scan = result.get(et_date)
            if day_pending and day_scan:
                diff[et_date] = compute_pending_diff(
                    day_pending.get("evaluations", []), day_scan,
                )
        result["pending_diff"] = diff
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
    stats_list = data.get("stats") or []
    if not stats_list:
        return []
    splits = stats_list[0].get("splits", [])
    logs = []
    for s in splits[-limit:]:
        st = s.get("stat", {})
        logs.append(GameLog(
            date=s.get("date", ""),
            gs=int(st.get("gamesStarted", 0)),
            ip=_ip_str_to_float(st.get("inningsPitched", "0")),
        ))
    return logs


def fetch_team_14d_ops(team_abbr, end_date):
    """14d team OPS ending at ``end_date`` (YYYY-MM-DD).

    Anchored on the scanned ET date rather than wall-clock today() so
    backtests / cross-day scans get the correct window.
    """
    from datetime import date, timedelta
    team_id = ABBR_TO_ID.get(team_abbr)
    if team_id is None:
        return 0.720  # fallback to league avg
    end = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
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


def _format_pct_owned(value):
    """Yahoo percent_owned is int (0-100) or None/empty. Display as '9%' / '—'."""
    if value is None or value == "":
        return "—"
    return f"{value}%"


def fetch_yahoo_fa_sp_pool(starter_names=None):
    """Page through Yahoo FA SP pool, optionally short-circuit on starter name hits.

    Delegates paging + filter + early-stop to ``yahoo_query.query_fa`` so the
    logic is shared with the CLI ``yahoo_query.py fa --names`` flag.

    Requires VPS env (Yahoo token).
    """
    import yahoo_query  # type: ignore[import-not-found]
    env = yahoo_query.load_env()
    access_token = yahoo_query.refresh_token(env)
    config = yahoo_query.load_config()
    league_key = config["league"]["league_key"]

    players = yahoo_query.query_fa(
        access_token, league_key,
        position="SP", status="A",
        names=set(starter_names) if starter_names else None,
        auto_page=True,
    )
    return [
        FAEntry(name=p["name"], percent_owned=_format_pct_owned(p.get("percent_owned")))
        for p in players
    ]


def fetch_v4_data(mlb_ids, season):
    # sp_data_fetchers prints progress to stdout — redirect to stderr so our
    # JSON output stays clean for downstream LLM consumption.
    import contextlib
    import sys

    from sp_data_fetchers import assemble_data  # type: ignore[import-not-found]
    with contextlib.redirect_stdout(sys.stderr):
        return assemble_data(mlb_ids, season)


_VS_HAND_SEASON_OPS_CACHE: dict[tuple[int, int], float] = {}


def _fetch_team_season_ops(team_id, season):
    key = (team_id, season)
    if key in _VS_HAND_SEASON_OPS_CACHE:
        return _VS_HAND_SEASON_OPS_CACHE[key]
    url = (
        f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats"
        f"?stats=season&group=hitting&season={season}&sportId=1"
    )
    try:
        data = _http_get_json(url)
        stat = data["stats"][0]["splits"][0]["stat"]
        ops = float(stat.get("ops", 0.720))
    except (KeyError, IndexError, ValueError, OSError):
        ops = 0.720  # league avg fallback (also covers HTTP failure)
    _VS_HAND_SEASON_OPS_CACHE[key] = ops
    return ops


def fetch_vs_hand_split(opp_abbr, sp_id, season=2026):
    """Fetch opponent vs SP-handedness split + season OPS fallback.

    Returns raw dict for ``_apply_vs_hand_gate`` to transform:
      {pa, split_ops, k_pct, bb_pct, hand, season_ops}
    Or ``None`` on statSplits API failure (scan emits vs_hand_2026=null).

    Internally:
      - SP meta fetch fail / non-R/L hand → hand=None (gate triggers fallback)
      - statSplits fail (when hand known) → return None (upstream null)
      - Season OPS fetch fail → 0.720 league avg
    """
    import sys

    from mlb_query import _default_meta_fetch, _default_split_fetch  # type: ignore[import-not-found]

    team_id = ABBR_TO_ID.get(opp_abbr)
    if team_id is None:
        print(f"vs_hand: unknown opponent abbr {opp_abbr}", file=sys.stderr)
        return None

    # 1) Resolve SP handedness
    try:
        meta = _default_meta_fetch(sp_id)
        hand = meta.get("throws")
        if hand not in ("R", "L"):
            hand = None  # switch-pitcher / unknown → fallback path
    except (KeyError, IndexError, OSError) as e:
        print(f"vs_hand meta fail (sp_id={sp_id}): {e}", file=sys.stderr)
        hand = None

    # 2) Opponent vs-hand split (only if hand known)
    if hand is not None:
        try:
            split = _default_split_fetch(team_id, hand)
        except (KeyError, IndexError, OSError) as e:
            print(f"vs_hand split fail ({opp_abbr} vs {hand}): {e}", file=sys.stderr)
            return None  # statSplits API failure → vs_hand_2026=null
    else:
        split = {"pa": 0, "ops": None, "k_pct": None, "bb_pct": None}

    # 3) Season full OPS for PA<400 fallback
    season_ops = _fetch_team_season_ops(team_id, season)

    split_ops_raw = split.get("ops")
    return {
        "pa": split.get("pa", 0),
        "split_ops": float(split_ops_raw) if split_ops_raw else None,
        "k_pct": split.get("k_pct"),
        "bb_pct": split.get("bb_pct"),
        "hand": hand,
        "season_ops": season_ops,
    }


def _norm_name(s):
    """Accent-strip + casefold for roster name matching (no hardcoded ids)."""
    import unicodedata
    decomposed = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def fetch_team_roster_id(team_abbr, name, season=2026):
    """Resolve (team_abbr, player name) → mlb_id via statsapi team roster.

    Team-scoped lookup avoids homonym collisions; never hardcodes ids
    (see feedback_no_hardcode_facts). Tries active roster then 40-man.
    Raises ValueError if not found — no silent wrong-id injection.
    """
    team_id = ABBR_TO_ID.get(team_abbr)
    if team_id is None:
        raise ValueError(f"unknown team abbr {team_abbr!r}")
    target = _norm_name(name)
    for roster_type in ("active", "40Man"):
        url = (
            f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
            f"?rosterType={roster_type}&season={season}"
        )
        try:
            data = _http_get_json(url)
        except OSError:
            continue
        for entry in data.get("roster", []):
            person = entry.get("person", {})
            if _norm_name(person.get("fullName", "")) == target:
                return person["id"]
    raise ValueError(
        f"projected SP {name!r} not found on {team_abbr} roster "
        f"(check spelling / team abbr)"
    )


def build_real_fetchers():
    return Fetchers(
        schedule_fn=fetch_mlb_schedule,
        fa_pool_fn=fetch_yahoo_fa_sp_pool,
        roster_pitchers_fn=load_roster_pitchers,
        game_log_fn=fetch_game_log,
        team_14d_ops_fn=fetch_team_14d_ops,
        v4_data_fn=fetch_v4_data,
        vs_hand_fn=fetch_vs_hand_split,
        id_resolver_fn=fetch_team_roster_id,
    )


def main():
    import argparse
    import json as _json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Stream SP scan — pipeline Step 2-6 (schedule + FA cross-check + v4 + opener filter + opponent strength + optional pending diff)",
    )
    parser.add_argument(
        "--et-dates", required=True,
        help="comma-separated ET dates, e.g. 2026-05-14,2026-05-15",
    )
    parser.add_argument(
        "--pending-file",
        help="path to stream-sp-pending.md — when given, emit top-level pending_diff key",
    )
    parser.add_argument(
        "--projected",
        help=(
            "manual projected starters injected into TBD slots: "
            "'ET_DATE:TEAM:Full Name,ET_DATE:TEAM:Full Name'. "
            "Each runs the full v4 pipeline and is flagged projected=true."
        ),
    )
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = parser.parse_args()

    et_dates = [d.strip() for d in args.et_dates.split(",") if d.strip()]
    projected = parse_projected_arg(args.projected) if args.projected else None
    fetchers = build_real_fetchers()

    pending_data = None
    if args.pending_file:
        pf = Path(args.pending_file)
        if pf.exists():
            from pending_parser import parse_pending  # type: ignore[import-not-found]
            pending_data = parse_pending(pf.read_text(encoding="utf-8"))
        else:
            print(
                f"Warning: --pending-file {args.pending_file} not found, "
                "skipping pending_diff", file=sys.stderr,
            )

    result = scan(
        et_dates, fetchers=fetchers, pending_data=pending_data, projected=projected,
    )
    indent = 2 if args.pretty else None
    print(_json.dumps(result, indent=indent, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
