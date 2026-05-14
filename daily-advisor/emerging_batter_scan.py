"""Emerging batter scan — Step 2-6 of /emerging-batter pipeline.

Mechanical layer: Yahoo FA pool → role change / hot streak signal filter +
14d trad / savant rolling / %owned trend enrich. Output JSON for LLM to
write report + pending file.

設計依據：docs/emerging-batter-design.md（2026-05-14 定稿）。對齊 batter v4
thin 哲學 — 不算 Sum、不打 ✅/⚠️ tag、不做 verdict，只做 hard filter + enrich。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


# ── Thresholds (decisions §「訊號門檻定義」)──────────────────────────────────

PA_TG_STARTER = 3.5        # 7d PA/TG ≥ 3.5 = 主力門檻（CLAUDE.md P80 季線）
PA_TG_JUMP_MIN = 1.0       # 7d − 14d 跳升至少 +1.0 排除 lineup 漂移
OWNED_DELTA_3D_MIN = 5.0   # +5pp / 3d = 聯盟級發現訊號
OWNED_DELTA_7D_MIN = 10.0  # +10pp / 7d = 累積訊號
PERF_OPS_MIN = 0.650       # 14d OPS 匹配下限
PERF_COUNTING_MIN = 8      # 14d R + HR + RBI 量產下限

# 14d rolling P75 (interpolated P70-P80 from CLAUDE.md 百分位表)
HOT_STREAK_XWOBA_P75 = 0.326
HOT_STREAK_BARREL_P75 = 11.2
HOT_STREAK_BBE_MIN = 25    # 樣本門檻（比 fa_scan v4 batter 40 寬，因 hot streak 信心本就低）

PCT_OWNED_MAX = 40         # %owned > 40 → 已被多隊看到，不算 emerging


# ── Data shapes ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FABatter:
    mlb_id: int
    name: str
    team: str
    positions: list  # ['1B', 'OF'] etc
    percent_owned: int


@dataclass(frozen=True)
class TradStats:
    """從 MLB Stats API gameLog 聚合的 14d 或 7d 區間 trad stats。

    team_games 是球隊 14d / 7d 的比賽場次（不是球員出場數），用來算 PA/TG
    讓「板凳變先發」訊號可呈現（球員 G=14 PA=14 vs G=7 PA=28 區別大）。
    """
    pa: int
    team_games: int
    ops: float
    hr: int
    rbi: int
    r: int
    sb: int
    bb: int
    k: int
    k_pct: float


@dataclass(frozen=True)
class RollingStats:
    """從 savant_rolling.json batter 14d 區間取的。"""
    xwoba: float
    xwobacon: float
    barrel_pct: float
    bbe: int


@dataclass(frozen=True)
class OwnedTrend:
    """從 fa_history.json 算的 %owned 趨勢。delta = None 表示無歷史 snapshot。"""
    current_pct: int
    delta_3d: float | None
    delta_7d: float | None


@dataclass
class Fetchers:
    fa_pool_fn: Callable        # () -> list[FABatter]
    rolling_fn: Callable        # (mlb_id) -> RollingStats | None
    trad_14d_fn: Callable       # (mlb_id) -> TradStats | None
    trad_7d_fn: Callable        # (mlb_id) -> TradStats | None
    owned_trend_fn: Callable    # (player_name) -> OwnedTrend | None
    cant_cut_fn: Callable       # () -> set[int]
    position_saturated_fn: Callable  # (positions: list[str]) -> bool


@dataclass(frozen=True)
class Verdict:
    bucket: str  # role_change / hot_streak / dropped / filtered_*


# ── Pure signal functions ──────────────────────────────────────────────────


def pa_per_team_game(pa: int, team_games: int) -> float:
    if team_games <= 0:
        return 0.0
    return pa / team_games


def has_pa_tg_jump(pa_tg_7d: float, pa_tg_14d: float) -> bool:
    """7d PA/TG ≥ 3.5 且 (7d − 14d) ≥ +1.0。"""
    return pa_tg_7d >= PA_TG_STARTER and (pa_tg_7d - pa_tg_14d) >= PA_TG_JUMP_MIN


def has_owned_burst(delta_3d: float | None, delta_7d: float | None) -> bool:
    """3d ≥ +5pp 或 7d ≥ +10pp。任一 None 視為無訊號該軸。"""
    if delta_3d is not None and delta_3d >= OWNED_DELTA_3D_MIN:
        return True
    if delta_7d is not None and delta_7d >= OWNED_DELTA_7D_MIN:
        return True
    return False


def has_role_change_signal(
    pa_tg_7d: float, pa_tg_14d: float,
    delta_3d: float | None, delta_7d: float | None,
) -> bool:
    return has_pa_tg_jump(pa_tg_7d, pa_tg_14d) or has_owned_burst(delta_3d, delta_7d)


def perf_14d_matches(trad: TradStats) -> bool:
    """14d 表現匹配：OPS ≥ .650 或 R+HR+RBI ≥ 8。"""
    if trad.ops >= PERF_OPS_MIN:
        return True
    if (trad.r + trad.hr + trad.rbi) >= PERF_COUNTING_MIN:
        return True
    return False


def has_hot_streak_signal(rolling: RollingStats) -> bool:
    """14d xwOBA ≥ P75 或 Barrel% ≥ P75，且 BBE ≥ 25。"""
    if rolling.bbe < HOT_STREAK_BBE_MIN:
        return False
    if rolling.xwoba >= HOT_STREAK_XWOBA_P75:
        return True
    if rolling.barrel_pct >= HOT_STREAK_BARREL_P75:
        return True
    return False


# ── Classifier ────────────────────────────────────────────────────────────


def classify_candidate(
    *,
    batter: FABatter,
    trad_14d: TradStats | None,
    trad_7d: TradStats | None,
    rolling: RollingStats | None,
    owned: OwnedTrend | None,
    cant_cut_ids: set,
    position_saturated: bool,
) -> Verdict:
    """單一 candidate 分桶。Hard filters 先跑，再判訊號。

    Filters 順序 (top-down)：
      1. cant_cut_conflict — 名單上的人不該推
      2. high_ownership — %owned > 40 不算 emerging
      3. position_saturated — 同位置 active anchor 飽和

    訊號判定：
      4. role_change_signal + perf_14d_matches → role_change
      5. 否則 hot_streak_signal（含 BBE ≥ 25 gate） → hot_streak
      6. rolling rate 達 P75 但 BBE <25 → filtered_low_bbe
      7. 都不符 → dropped（不出現在 output 任何段）
    """
    if batter.mlb_id in cant_cut_ids:
        return Verdict(bucket="filtered_cant_cut")
    if batter.percent_owned is not None and batter.percent_owned > PCT_OWNED_MAX:
        return Verdict(bucket="filtered_high_ownership")
    if position_saturated:
        return Verdict(bucket="filtered_position_saturated")

    # 計算 PA/TG（trad 缺失 → 0）
    pa_tg_14d = pa_per_team_game(trad_14d.pa, trad_14d.team_games) if trad_14d else 0.0
    pa_tg_7d = pa_per_team_game(trad_7d.pa, trad_7d.team_games) if trad_7d else 0.0
    d3 = owned.delta_3d if owned else None
    d7 = owned.delta_7d if owned else None

    role_change = has_role_change_signal(pa_tg_7d, pa_tg_14d, d3, d7)

    if role_change and trad_14d and perf_14d_matches(trad_14d):
        return Verdict(bucket="role_change")

    # Hot streak 段 — 需要 rolling 才能判
    if rolling is not None:
        # 先看 rate 是否高（即使 BBE 不夠）
        rate_high = (
            rolling.xwoba >= HOT_STREAK_XWOBA_P75
            or rolling.barrel_pct >= HOT_STREAK_BARREL_P75
        )
        if rate_high and rolling.bbe < HOT_STREAK_BBE_MIN:
            return Verdict(bucket="filtered_low_bbe")
        if has_hot_streak_signal(rolling):
            return Verdict(bucket="hot_streak")

    return Verdict(bucket="dropped")


# ── scan() orchestrator ────────────────────────────────────────────────────


def _candidate_payload(
    batter: FABatter,
    *,
    trad_14d: TradStats | None,
    trad_7d: TradStats | None,
    rolling: RollingStats | None,
    owned: OwnedTrend | None,
) -> dict:
    pa_tg_14 = pa_per_team_game(trad_14d.pa, trad_14d.team_games) if trad_14d else 0.0
    pa_tg_7 = pa_per_team_game(trad_7d.pa, trad_7d.team_games) if trad_7d else 0.0
    d3 = owned.delta_3d if owned else None
    d7 = owned.delta_7d if owned else None
    return {
        "name": batter.name,
        "mlb_id": batter.mlb_id,
        "team": batter.team,
        "positions": list(batter.positions),
        "percent_owned": batter.percent_owned,
        "pa_tg_14d": round(pa_tg_14, 2),
        "pa_tg_7d": round(pa_tg_7, 2),
        "pa_tg_jump": round(pa_tg_7 - pa_tg_14, 2),
        "owned_delta_3d": d3,
        "owned_delta_7d": d7,
        "rolling_14d": (
            {
                "xwoba": rolling.xwoba,
                "xwobacon": rolling.xwobacon,
                "barrel_pct": rolling.barrel_pct,
                "bbe": rolling.bbe,
            }
            if rolling
            else None
        ),
        "trad_14d": (
            {
                "pa": trad_14d.pa,
                "team_games": trad_14d.team_games,
                "ops": trad_14d.ops,
                "hr": trad_14d.hr,
                "rbi": trad_14d.rbi,
                "r": trad_14d.r,
                "sb": trad_14d.sb,
                "bb": trad_14d.bb,
                "k": trad_14d.k,
                "k_pct": trad_14d.k_pct,
            }
            if trad_14d
            else None
        ),
    }


def _filtered_summary(batter: FABatter, reason: str) -> dict:
    return {
        "name": batter.name,
        "mlb_id": batter.mlb_id,
        "team": batter.team,
        "positions": list(batter.positions),
        "percent_owned": batter.percent_owned,
        "reason": reason,
    }


def scan(*, fetchers: Fetchers) -> dict:
    """Run mechanical scan over a FA batter pool.

    Production fetchers expose a ``_last_known_team`` slot (``{"_": team_abbr}``)
    that is updated per-batter before per-batter fetcher calls — needed because
    team_games_window lookup keys on team abbr, but trad_*_fn signature only
    sees ``mlb_id`` (to keep fixture fetchers simple). Test fetchers lack the
    slot and the team-threading is skipped.
    """
    fa_pool = fetchers.fa_pool_fn()
    cant_cut_ids = fetchers.cant_cut_fn()
    team_slot = getattr(fetchers, "_last_known_team", None)

    result = {
        "role_change_candidates": [],
        "hot_streak_candidates": [],
        "filtered": {
            "cant_cut_conflict": [],
            "high_ownership": [],
            "position_saturated": [],
            "low_confidence_bbe": [],
        },
    }

    for b in fa_pool:
        if team_slot is not None:
            team_slot["_"] = b.team
        trad_14d = fetchers.trad_14d_fn(b.mlb_id)
        trad_7d = fetchers.trad_7d_fn(b.mlb_id)
        rolling = fetchers.rolling_fn(b.mlb_id)
        owned = fetchers.owned_trend_fn(b.name)
        saturated = fetchers.position_saturated_fn(b.positions)

        verdict = classify_candidate(
            batter=b,
            trad_14d=trad_14d,
            trad_7d=trad_7d,
            rolling=rolling,
            owned=owned,
            cant_cut_ids=cant_cut_ids,
            position_saturated=saturated,
        )

        if verdict.bucket == "role_change":
            result["role_change_candidates"].append(
                _candidate_payload(b, trad_14d=trad_14d, trad_7d=trad_7d,
                                   rolling=rolling, owned=owned),
            )
        elif verdict.bucket == "hot_streak":
            result["hot_streak_candidates"].append(
                _candidate_payload(b, trad_14d=trad_14d, trad_7d=trad_7d,
                                   rolling=rolling, owned=owned),
            )
        elif verdict.bucket == "filtered_cant_cut":
            result["filtered"]["cant_cut_conflict"].append(
                _filtered_summary(b, "cant_cut"),
            )
        elif verdict.bucket == "filtered_high_ownership":
            result["filtered"]["high_ownership"].append(
                _filtered_summary(b, "owned>40"),
            )
        elif verdict.bucket == "filtered_position_saturated":
            result["filtered"]["position_saturated"].append(
                _filtered_summary(b, "saturated"),
            )
        elif verdict.bucket == "filtered_low_bbe":
            result["filtered"]["low_confidence_bbe"].append(
                _filtered_summary(b, "bbe<25"),
            )
        # dropped → 不出現在 output 任何段

    return result


# ── Production fetchers (system boundary; manually verified, not TDD-tested) ──

# Mapping from MLB team abbreviation to teamId for Stats API queries.
# Mirrors stream_sp_scan.TEAM_ABBR inverse — kept duplicated to avoid the
# emerging-batter path depending on stream_sp_scan internals.
_TEAM_ABBR_TO_ID = {
    "LAA": 108, "AZ":  109, "BAL": 110, "BOS": 111, "CHC": 112, "CIN": 113,
    "CLE": 114, "COL": 115, "DET": 116, "HOU": 117, "KC":  118, "LAD": 119,
    "WSH": 120, "NYM": 121, "ATH": 133, "PIT": 134, "SD":  135, "SEA": 136,
    "SF":  137, "STL": 138, "TB":  139, "TEX": 140, "TOR": 141, "MIN": 142,
    "PHI": 143, "ATL": 144, "CWS": 145, "MIA": 146, "NYY": 147, "MIL": 158,
}


def _load_roster_config():
    import json as _json
    from pathlib import Path
    cfg = Path(__file__).parent / "roster_config.json"
    with cfg.open(encoding="utf-8") as f:
        return _json.load(f)


def _load_savant_rolling_batter():
    """Return dict[mlb_id_str -> rolling stat dict] from savant_rolling.json."""
    import json as _json
    from pathlib import Path
    rolling_file = Path(__file__).parent / "savant_rolling.json"
    with rolling_file.open(encoding="utf-8") as f:
        data = _json.load(f)
    return data.get("players", {})


def _load_fa_history():
    import json as _json
    from pathlib import Path
    fh = Path(__file__).parent / "fa_history.json"
    if not fh.exists():
        return {}
    with fh.open(encoding="utf-8") as f:
        return _json.load(f)


def _today_et_str():
    """Today's date in ET (Yahoo lineup tz). Falls back to UTC date if zoneinfo missing."""
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.utcnow().strftime("%Y-%m-%d")


def _fetch_team_games_in_window(team_abbr, end_date, days):
    """Fetch team's gamesPlayed count in the last `days` ending at `end_date`.

    Returns int. Defaults to `days` when API fails — conservative fallback
    (球隊通常每天 1 場，最多差 1-2 場與真實值偏離；對 P80=3.5 門檻影響有限）。
    """
    from datetime import date, timedelta
    team_id = _TEAM_ABBR_TO_ID.get(team_abbr)
    if team_id is None:
        return days
    end = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
    start = end - timedelta(days=days - 1)  # inclusive 7d window = 7 calendar days
    url = (
        f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats"
        f"?stats=byDateRange&group=hitting&season={end.year}"
        f"&startDate={start.isoformat()}&endDate={end.isoformat()}&sportId=1"
    )
    try:
        import urllib.request
        import json as _json
        with urllib.request.urlopen(url, timeout=30) as r:
            data = _json.loads(r.read().decode("utf-8"))
        return int(data["stats"][0]["splits"][0]["stat"]["gamesPlayed"])
    except Exception:
        return days


def _build_team_games_cache(teams, end_date, days):
    """Pre-fetch gamesPlayed for a set of team abbreviations. Returns dict."""
    return {t: _fetch_team_games_in_window(t, end_date, days) for t in teams}


def _player_to_id_seed(roster_config, savant_rolling):
    """Build name->mlb_id seed from roster + savant_rolling — avoids paying
    search_mlb_id per FA when the player already has Savant rolling data
    (which covers ~all 14d-active batters)."""
    seed = {}
    for b in roster_config.get("batters", []):
        if b.get("mlb_id"):
            seed[b["name"]] = b["mlb_id"]
    for mid_str, p in savant_rolling.items():
        if "name" in p:
            try:
                seed[p["name"]] = int(mid_str)
            except (TypeError, ValueError):
                pass
    return seed


def _resolve_cant_cut_ids(roster_config):
    """league.cant_cut 是名字 list — 解析為 mlb_id set 透過 roster batters/pitchers
    （cant_cut 球員必在我 roster 上）。"""
    names = set(roster_config.get("league", {}).get("cant_cut", []))
    ids = set()
    for b in roster_config.get("batters", []):
        if b["name"] in names and b.get("mlb_id"):
            ids.add(b["mlb_id"])
    for p in roster_config.get("pitchers", []):
        if p["name"] in names and p.get("mlb_id"):
            ids.add(p["mlb_id"])
    return ids


def _parse_positions(yahoo_position_str):
    """Yahoo 'position' field eg '1B,OF' → ['1B', 'OF']."""
    if not yahoo_position_str:
        return []
    return [p.strip() for p in yahoo_position_str.split(",") if p.strip()]


def build_real_fetchers():
    """Wire production fetchers (Yahoo FA + MLB Stats API + savant_rolling).

    Requires VPS env (Yahoo token + savant_rolling.json freshly generated by
    daily cron). Caches team-game counts and mlb_id lookups in-process to
    keep API call count bounded.
    """
    from datetime import datetime  # noqa: F401 — imported for closures

    config = _load_roster_config()
    rolling = _load_savant_rolling_batter()
    fa_history = _load_fa_history()
    today_str = _today_et_str()

    cant_cut_ids = _resolve_cant_cut_ids(config)
    name_to_id = _player_to_id_seed(config, rolling)

    def _resolve_mlb_id(name):
        if name in name_to_id:
            return name_to_id[name]
        # Late-bind: avoid forcing roster_sync import unless we miss seed.
        from roster_sync import search_mlb_id  # type: ignore[import-not-found]
        mid = search_mlb_id(name)
        if mid:
            name_to_id[name] = mid
        return mid

    # Team-games cache — fill lazily once FA pool is known.
    team_games_14d = {}
    team_games_7d = {}

    def _get_team_games(team_abbr, days, cache):
        if team_abbr not in cache:
            cache[team_abbr] = _fetch_team_games_in_window(team_abbr, today_str, days)
        return cache[team_abbr]

    def fa_pool_fn():
        import yahoo_query  # type: ignore[import-not-found]
        env = yahoo_query.load_env()
        access_token = yahoo_query.refresh_token(env)
        league_key = config["league"]["league_key"]
        players = yahoo_query.query_fa(
            access_token, league_key,
            position="B", status="A", sort="AR", page_size=50,
        )
        out = []
        for p in players:
            # Inactive filter (mirrors fa_scan.is_inactive_fa: IL60 / NA hard-excluded).
            status = (p.get("status") or "").strip().upper()
            if status in {"IL60", "NA"}:
                continue
            mid = _resolve_mlb_id(p["name"])
            if mid is None:
                continue
            out.append(FABatter(
                mlb_id=mid,
                name=p["name"],
                team=p.get("team") or "?",
                positions=_parse_positions(p.get("position")),
                percent_owned=int(p.get("percent_owned") or 0),
            ))
        return out

    def rolling_fn(mlb_id):
        entry = rolling.get(str(mlb_id))
        if not entry:
            return None
        try:
            return RollingStats(
                xwoba=float(entry.get("xwoba", 0)),
                xwobacon=float(entry.get("xwobacon", 0)),
                barrel_pct=float(entry.get("barrel_pct", 0)),
                bbe=int(entry.get("bbe", 0)),
            )
        except (TypeError, ValueError):
            return None

    def _trad_via_gamelog(mlb_id, window_days, team_abbr_hint, team_games_cache):
        from fa_scan import enrich_14d_trad  # type: ignore[import-not-found]
        trad = enrich_14d_trad(mlb_id, season=2026, window_days=window_days)
        if not trad:
            return None
        tg = _get_team_games(team_abbr_hint, window_days, team_games_cache) if team_abbr_hint else window_days
        return TradStats(
            pa=trad["pa"], team_games=tg,
            ops=trad["ops"], hr=trad["hr"], rbi=trad["rbi"],
            r=trad["r"], sb=trad["sb"], bb=trad["bb"], k=trad["k"],
            k_pct=trad["k_pct"],
        )

    # Production fetchers need batter.team to look up team_games. Wrap so the
    # caller can pass either mlb_id alone (when team unknown — falls back to
    # window_days) or via closure binding.
    _last_known_team = {"_": None}

    def trad_14d_fn(mlb_id):
        return _trad_via_gamelog(mlb_id, 14, _last_known_team["_"], team_games_14d)

    def trad_7d_fn(mlb_id):
        return _trad_via_gamelog(mlb_id, 7, _last_known_team["_"], team_games_7d)

    def owned_trend_fn(name):
        from fa_scan import enrich_owned_trend  # type: ignore[import-not-found]
        ot = enrich_owned_trend(name, fa_history, today_str)
        if not ot:
            return None
        return OwnedTrend(
            current_pct=ot.get("current_pct") or 0,
            delta_3d=ot.get("delta_3d"),
            delta_7d=ot.get("delta_7d"),
        )

    def cant_cut_fn():
        return set(cant_cut_ids)

    def position_saturated_fn(positions):
        # Placeholder: 不做 saturation 判斷（落地後觀察 1-2 週再實作）
        # 設計文件 §「尚待決定」決策 2：簡單 cap — 同位置 active ≥2 且 ≥ season Sum 25 → 飽和
        return False

    fetchers = Fetchers(
        fa_pool_fn=fa_pool_fn,
        rolling_fn=rolling_fn,
        trad_14d_fn=trad_14d_fn,
        trad_7d_fn=trad_7d_fn,
        owned_trend_fn=owned_trend_fn,
        cant_cut_fn=cant_cut_fn,
        position_saturated_fn=position_saturated_fn,
    )
    fetchers._last_known_team = _last_known_team  # type: ignore[attr-defined]
    return fetchers


def main():
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(
        description="Emerging batter scan — pipeline Step 2-6 (Yahoo FA + role change / hot streak signal filter + 14d enrich)",
    )
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = parser.parse_args()

    fetchers = build_real_fetchers()
    result = scan(fetchers=fetchers)
    indent = 2 if args.pretty else None
    print(_json.dumps(result, indent=indent, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
