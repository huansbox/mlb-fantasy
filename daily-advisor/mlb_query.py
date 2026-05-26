"""MLB Stats API helpers for /stream-sp-deep skill.

Helpers:
  - gamelog_with_qs(mlb_id, season) — pitching game log enriched with ip_decimal + qs
  - opponent_context(team_id, end_date, sp_id) — opponent 3-window trend + vs-handedness split
  - deep_batch(players) — batch orchestrator: loop both helpers for N SPs in one call,
                          emit by_player payload + 7-column comparison_table

Pure functions exported for unit testing:
  - parse_ip(ip_str): MLB "I.frac" format ("5.2" = 5⅔) → decimal float
  - is_quality_start(ip_decimal, er): IP ≥ 6 AND ER ≤ 3

CLI:
  python3 mlb_query.py deep --players ID1,ID2 --et-dates D1,D2 \
                            [--opp-teams T1,T2] [--sp-names "N1|N2"] \
                            [--opp-abbrs A1,A2] [--sum26 S1,S2] [--sum25 S1,S2] [--pretty]
"""

import json
import urllib.request
from datetime import date, timedelta

_BASE = "https://statsapi.mlb.com/api/v1"
_TEAM_ABBR_CACHE: dict[int, str] = {}

_COMPARISON_HEADERS = [
    "7d OPS", "30d→7d Δ", "vs hand OPS", "近 6 場 ERA",
    "Floor risk hint", "Sum26", "雙年 prior",
]


class MlbIdNotFoundError(Exception):
    """Raised when an MLB Player ID lookup returns no player.

    Re-raised by deep_batch (instead of swallowed as partial failure) so a typo'd
    ID fails loud rather than silently producing missing rows.
    """


def parse_ip(ip_str: str) -> float:
    """Parse MLB innings string ('5.2' = 5⅔) to decimal float."""
    int_part, frac = ip_str.split(".")
    return int(int_part) + int(frac) / 3


def is_quality_start(ip_decimal: float, er: int) -> bool:
    """Quality Start = ≥6 IP and ≤3 ER."""
    return ip_decimal >= 6.0 and er <= 3


def _team_abbr(team_id: int) -> str:
    if not _TEAM_ABBR_CACHE:
        data = json.loads(urllib.request.urlopen(f"{_BASE}/teams?sportId=1").read())
        for t in data["teams"]:
            _TEAM_ABBR_CACHE[t["id"]] = t.get("abbreviation", t["name"][:3])
    return _TEAM_ABBR_CACHE.get(team_id, str(team_id))


def _stat_pct(stat: dict, count_key: str) -> float:
    pa = stat.get("plateAppearances") or 1
    return stat.get(count_key, 0) / pa * 100


def _default_gamelog_fetch(mlb_id: int, season: int) -> list[dict]:
    url = f"{_BASE}/people/{mlb_id}/stats?stats=gameLog&season={season}&group=pitching"
    data = json.loads(urllib.request.urlopen(url).read())
    splits = data["stats"][0]["splits"]
    out = []
    for s in splits:
        st = s["stat"]
        out.append({
            "date": s["date"],
            "opp": _team_abbr(s["opponent"]["id"]),
            "h_a": "H" if s.get("isHome") else "A",
            "ip": str(st["inningsPitched"]),
            "h": st["hits"],
            "r": st["runs"],
            "er": st["earnedRuns"],
            "bb": st["baseOnBalls"],
            "k": st["strikeOuts"],
            "hr": st["homeRuns"],
            "pc": st.get("numberOfPitches"),
            "era": st.get("era"),
        })
    return out


def _default_meta_fetch(sp_id: int) -> dict:
    url = f"{_BASE}/people/{sp_id}"
    data = json.loads(urllib.request.urlopen(url).read())
    person = data["people"][0]
    hand = person.get("pitchHand", {}).get("code", "R")
    return {"throws": hand}


def _default_range_fetch(team_id: int, end_date: str, days: int) -> dict:
    end = date.fromisoformat(end_date)
    start = end - timedelta(days=days)
    url = (
        f"{_BASE}/teams/{team_id}/stats?stats=byDateRange&group=hitting"
        f"&season={end.year}&startDate={start.isoformat()}&endDate={end.isoformat()}&sportId=1"
    )
    data = json.loads(urllib.request.urlopen(url).read())
    stat = data["stats"][0]["splits"][0]["stat"]
    g = max(stat.get("gamesPlayed", 1), 1)
    return {
        "g": stat["gamesPlayed"],
        "avg": stat["avg"],
        "obp": stat["obp"],
        "ops": stat["ops"],
        "rg": stat["runs"] / g,
        "k_pct": _stat_pct(stat, "strikeOuts"),
        "bb_pct": _stat_pct(stat, "baseOnBalls"),
    }


def _default_split_fetch(team_id: int, hand: str) -> dict:
    sit = "vr" if hand == "R" else "vl"
    season = date.today().year
    url = (
        f"{_BASE}/teams/{team_id}/stats?stats=statSplits&sitCodes={sit}"
        f"&group=hitting&season={season}&sportId=1"
    )
    data = json.loads(urllib.request.urlopen(url).read())
    splits = data["stats"][0]["splits"]
    if not splits:
        return {"ops": None, "pa": 0, "avg": None, "obp": None, "k_pct": None, "bb_pct": None, "hand": hand}
    stat = splits[0]["stat"]
    return {
        "pa": stat["plateAppearances"],
        "avg": stat["avg"],
        "obp": stat["obp"],
        "ops": stat["ops"],
        "k_pct": _stat_pct(stat, "strikeOuts"),
        "bb_pct": _stat_pct(stat, "baseOnBalls"),
        "hand": hand,
    }


def gamelog_with_qs(mlb_id: int, season: int, fetch_fn=None) -> list[dict]:
    """Fetch pitching game log + enrich each entry with ip_decimal (float) + qs (bool).

    fetch_fn: callable(mlb_id, season) -> list[dict] with at least 'ip' and 'er' keys.
              Defaults to live MLB Stats API.
    """
    if fetch_fn is None:
        fetch_fn = _default_gamelog_fetch
    raw = fetch_fn(mlb_id, season)
    enriched = []
    for entry in raw:
        ip_decimal = parse_ip(entry["ip"])
        enriched.append({**entry, "ip_decimal": ip_decimal, "qs": is_quality_start(ip_decimal, entry["er"])})
    return enriched


def opponent_context(
    team_id: int,
    end_date: str,
    sp_id: int,
    fetch_meta_fn=None,
    fetch_range_fn=None,
    fetch_split_fn=None,
) -> dict:
    """Fetch opponent 7d/14d/30d trend windows + vs SP-handedness season split.

    Internally resolves SP handedness from sp_id (no caller burden).

    fetch_meta_fn: callable(sp_id) -> {"throws": "R" | "L", ...}
    fetch_range_fn: callable(team_id, end_date, days) -> {ops, g, k_pct, bb_pct, ...}
    fetch_split_fn: callable(team_id, hand) -> {ops, pa, k_pct, bb_pct, ...}

    All three default to live MLB Stats API fetchers.
    """
    if fetch_meta_fn is None:
        fetch_meta_fn = _default_meta_fetch
    if fetch_range_fn is None:
        fetch_range_fn = _default_range_fetch
    if fetch_split_fn is None:
        fetch_split_fn = _default_split_fetch

    throws = fetch_meta_fn(sp_id)["throws"]
    return {
        "7d": fetch_range_fn(team_id, end_date, 7),
        "14d": fetch_range_fn(team_id, end_date, 14),
        "30d": fetch_range_fn(team_id, end_date, 30),
        "vs_hand": fetch_split_fn(team_id, throws),
    }


# ---------- deep_batch orchestrator + formatters ----------


def _ops_to_float(ops) -> float:
    """Parse OPS string ('.769' or '0.769' or '1.025') or numeric → float."""
    if ops is None:
        raise ValueError("OPS is None")
    if isinstance(ops, (int, float)):
        return float(ops)
    s = str(ops).strip()
    if s.startswith("."):
        s = "0" + s
    return float(s)


def _format_ops(ops) -> str:
    """Format OPS for display: strip leading 0 from '0.XXX' → '.XXX'. Pass through values >= 1."""
    if ops is None or ops == "":
        return "-"
    try:
        v = _ops_to_float(ops)
    except (TypeError, ValueError):
        return "-"
    if v < 1:
        return f"{v:.3f}"[1:]
    return f"{v:.3f}"


def _format_delta(delta: float) -> str:
    """Format OPS delta as '+.XXX' / '-.XXX' (strip leading 0)."""
    sign = "+" if delta >= 0 else "-"
    abs_str = f"{abs(delta):.3f}"
    if abs_str.startswith("0."):
        abs_str = abs_str[1:]
    return f"{sign}{abs_str}"


def _recent_era(game_log: list[dict], n: int = 6) -> tuple[str, float | None]:
    """Compute ERA from last n starts. Returns (display_str, numeric_or_None)."""
    recent = game_log[-n:] if len(game_log) >= n else game_log
    if not recent:
        return "-", None
    total_er = sum(g.get("er", 0) for g in recent)
    total_ip = sum(g.get("ip_decimal", 0) for g in recent)
    if total_ip == 0:
        return "-", None
    era = total_er * 9 / total_ip
    return f"{era:.2f}", era


def _floor_risk_hint(game_log: list[dict]) -> str:
    """Heuristic from CLAUDE.md SOP: count last-6 ER>=4 collapses + recent ERA threshold.

    0 collapses → 低 ; 1 collapse + recent ERA <4.50 → 中 ;
    1 collapse + recent ERA >=4.50 → 中-高 ; 2+ collapses → 高.
    """
    recent = game_log[-6:] if len(game_log) >= 6 else game_log
    if not recent:
        return "-"
    collapses = sum(1 for g in recent if g.get("er", 0) >= 4)
    _, era = _recent_era(game_log, n=6)
    if collapses >= 2:
        return "高"
    if collapses == 1 and era is not None and era >= 4.50:
        return "中-高"
    if collapses == 1:
        return "中"
    return "低"


def _build_comparison_row(
    sp_name: str,
    opp_abbr: str,
    game_log: list[dict],
    opp_ctx: dict | None,
    sp_meta: dict,
    sum26,
    sum25,
) -> dict:
    """Assemble one comparison_table row from per-SP payload."""
    if opp_ctx:
        ops_7d_raw = opp_ctx.get("7d", {}).get("ops")
        ops_30d_raw = opp_ctx.get("30d", {}).get("ops")
        vs_hand_raw = opp_ctx.get("vs_hand", {}).get("ops")
        hand = opp_ctx.get("vs_hand", {}).get("hand") or sp_meta.get("hand", "?")
        try:
            delta_str = _format_delta(_ops_to_float(ops_7d_raw) - _ops_to_float(ops_30d_raw))
        except (TypeError, ValueError):
            delta_str = "-"
        vs_hand_disp = f"{_format_ops(vs_hand_raw)} ({hand})"
        ops_7d_disp = _format_ops(ops_7d_raw)
    else:
        ops_7d_disp = "-"
        delta_str = "-"
        vs_hand_disp = "-"

    era_disp, _ = _recent_era(game_log, n=6)
    floor_disp = _floor_risk_hint(game_log)
    sum26_disp = str(sum26) if sum26 is not None else "-"
    if sum26 is not None and sum25 is not None:
        prior_disp = f"{sum26}/{sum25}"
    elif sum26 is not None:
        prior_disp = f"{sum26}/-"
    elif sum25 is not None:
        prior_disp = f"-/{sum25}"
    else:
        prior_disp = "-"

    return {
        "sp": f"{sp_name} vs {opp_abbr}",
        "values": [
            ops_7d_disp, delta_str, vs_hand_disp, era_disp,
            floor_disp, sum26_disp, prior_disp,
        ],
    }


def deep_batch(players: list[dict], fetchers: dict | None = None) -> dict:
    """Batch deep-eval orchestrator: loop existing helpers for N SPs in one call.

    Args:
        players: list of dicts. Each entry requires `mlb_id` + `et_date`.
                 Optional: `opp_team_id` (for opponent_context), `sp_name`,
                 `opp_abbr`, `sp_team`, `sum26`, `sum25`.
        fetchers: dict of injectable fetchers (for tests). Keys:
                  `gamelog`, `meta`, `range`, `split`. Each falls back to
                  the live MLB Stats API fetcher when missing.

    Returns:
        {
          "by_player": {
            "{mlb_id}": {"game_log": [...], "opponent_context": {...},
                         "sp_meta": {"name": ..., "team": ..., "hand": ...}}
                        | {"error": "..."}
          },
          "comparison_table": {"headers": [...7 fixed...], "rows": [...]}
        }

    Failure handling:
        - MlbIdNotFoundError → re-raised (entire batch aborts; loud failure on typo'd ID)
        - TimeoutError / other Exception → that SP's by_player entry holds `{"error": ...}`,
          other SPs continue. comparison_table preserves row position with "-" placeholders.

    Internal: loops gamelog_with_qs + opponent_context per SP (no fetch logic rewrite).
    """
    fetchers = fetchers or {}
    by_player: dict[str, dict] = {}
    rows: list[dict] = []

    meta_fn = fetchers.get("meta") or _default_meta_fetch

    for p in players:
        mlb_id = p["mlb_id"]
        et_date = p["et_date"]
        opp_team_id = p.get("opp_team_id")
        sp_name = p.get("sp_name", str(mlb_id))
        opp_abbr = p.get("opp_abbr") or (str(opp_team_id) if opp_team_id else "?")
        sum26 = p.get("sum26")
        sum25 = p.get("sum25")
        season = int(str(et_date)[:4])

        try:
            game_log = gamelog_with_qs(mlb_id, season, fetch_fn=fetchers.get("gamelog"))
            opp_ctx = None
            if opp_team_id is not None:
                opp_ctx = opponent_context(
                    team_id=opp_team_id,
                    end_date=et_date,
                    sp_id=mlb_id,
                    fetch_meta_fn=fetchers.get("meta"),
                    fetch_range_fn=fetchers.get("range"),
                    fetch_split_fn=fetchers.get("split"),
                )
            meta = meta_fn(mlb_id)
            sp_meta = {
                "name": sp_name,
                "team": p.get("sp_team", "?"),
                "hand": meta.get("throws", "?"),
            }
            by_player[str(mlb_id)] = {
                "game_log": game_log,
                "opponent_context": opp_ctx,
                "sp_meta": sp_meta,
            }
            rows.append(_build_comparison_row(
                sp_name, opp_abbr, game_log, opp_ctx, sp_meta, sum26, sum25,
            ))
        except MlbIdNotFoundError:
            raise
        except TimeoutError as e:
            by_player[str(mlb_id)] = {"error": f"timeout: {e}"}
            rows.append({"sp": f"{sp_name} vs {opp_abbr}", "values": ["-"] * 7})
        except Exception as e:
            by_player[str(mlb_id)] = {"error": str(e)}
            rows.append({"sp": f"{sp_name} vs {opp_abbr}", "values": ["-"] * 7})

    return {
        "by_player": by_player,
        "comparison_table": {"headers": list(_COMPARISON_HEADERS), "rows": rows},
    }


# ---------- CLI ----------


def _split_csv(value: str | None, length: int, sep: str = ",") -> list:
    if not value:
        return [None] * length
    parts = [p.strip() for p in value.split(sep)]
    if len(parts) != length:
        raise SystemExit(
            f"flag value '{value}' has {len(parts)} items, expected {length} to match --players length"
        )
    return parts


def _cli_deep(args) -> None:
    ids = [s.strip() for s in args.players.split(",") if s.strip()]
    et_dates = [s.strip() for s in args.et_dates.split(",") if s.strip()]
    if len(ids) != len(et_dates):
        raise SystemExit(
            f"--players ({len(ids)}) / --et-dates ({len(et_dates)}) length mismatch"
        )
    n = len(ids)
    opp_teams = _split_csv(args.opp_teams, n)
    sp_names = _split_csv(args.sp_names, n, sep="|")
    opp_abbrs = _split_csv(args.opp_abbrs, n)
    sum26_list = _split_csv(args.sum26, n)
    sum25_list = _split_csv(args.sum25, n)

    players = []
    for i, pid in enumerate(ids):
        p = {
            "mlb_id": int(pid),
            "et_date": et_dates[i],
        }
        if opp_teams[i]:
            p["opp_team_id"] = int(opp_teams[i])
        if sp_names[i]:
            p["sp_name"] = sp_names[i]
        if opp_abbrs[i]:
            p["opp_abbr"] = opp_abbrs[i]
        if sum26_list[i]:
            p["sum26"] = int(sum26_list[i])
        if sum25_list[i]:
            p["sum25"] = int(sum25_list[i])
        players.append(p)

    result = deep_batch(players=players)
    indent = 2 if args.pretty else None
    print(json.dumps(result, indent=indent, ensure_ascii=False, default=str))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="MLB Stats API helpers — deep_batch CLI for /stream-sp-deep skill",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    deep = sub.add_parser(
        "deep",
        help="Batch deep-eval (game_log + opponent_context) for N SPs in one call",
    )
    deep.add_argument("--players", required=True,
                      help="comma-separated MLB Player IDs (e.g. 686790,605488)")
    deep.add_argument("--et-dates", required=True,
                      help="comma-separated ET dates ISO (e.g. 2026-05-27,2026-05-27)")
    deep.add_argument("--opp-teams",
                      help="comma-separated opponent team IDs (required for opponent_context)")
    deep.add_argument("--sp-names",
                      help='pipe-separated SP display names (e.g. "Trevor McDonald|Jeffrey Springs")')
    deep.add_argument("--opp-abbrs",
                      help="comma-separated opponent abbreviations (e.g. AZ,SEA)")
    deep.add_argument("--sum26",
                      help="comma-separated 2026 Sum values (from scan candidates)")
    deep.add_argument("--sum25",
                      help="comma-separated 2025 Sum values (from scan candidates)")
    deep.add_argument("--pretty", action="store_true", help="pretty-print JSON")

    args = parser.parse_args()
    if args.cmd == "deep":
        _cli_deep(args)


if __name__ == "__main__":
    main()
