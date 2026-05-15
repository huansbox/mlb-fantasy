"""MLB Stats API helpers for /stream-sp-deep skill.

Two helpers:
  - gamelog_with_qs(mlb_id, season) — pitching game log enriched with ip_decimal + qs
  - opponent_context(team_id, end_date, sp_id) — opponent 3-window trend + vs-handedness split

Pure functions exported for unit testing:
  - parse_ip(ip_str): MLB "I.frac" format ("5.2" = 5⅔) → decimal float
  - is_quality_start(ip_decimal, er): IP ≥ 6 AND ER ≤ 3
"""

import json
import urllib.request
from datetime import date, timedelta

_BASE = "https://statsapi.mlb.com/api/v1"
_TEAM_ABBR_CACHE: dict[int, str] = {}


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
