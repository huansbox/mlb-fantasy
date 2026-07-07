"""318b B6 — sp_data_fetchers parse (mocked fetch_url) + _phase6_sp attach
orchestration (all fetchers injected/monkeypatched)."""

import json
from datetime import date

import pytest

import _phase6_sp
import micro_fields_sp
import sp_data_fetchers as sdf


# ── fetch_gamelog_starts / fetch_week_schedule / fetch_standings_winpct ──

def _gamelog_payload():
    def split(d, gs, ip, er):
        return {"date": d, "team": {"id": 158},
                "stat": {"gamesStarted": gs, "inningsPitched": ip,
                         "earnedRuns": er}}
    return json.dumps({"stats": [{"splits": [
        split("2026-06-20", 1, "6.0", 2),    # QS
        split("2026-06-25", 0, "1.0", 0),    # relief — ignored
        split("2026-06-26", 1, "5.2", 4),    # not QS
        split("2026-07-02", 1, "7.1", 1),    # QS
    ]}]})


def test_fetch_gamelog_starts_parse(monkeypatch):
    monkeypatch.setattr(sdf, "fetch_url", lambda url, timeout=30: _gamelog_payload())
    out = sdf.fetch_gamelog_starts(123, 2026)
    assert out["start_dates"] == ["2026-06-20", "2026-06-26", "2026-07-02"]
    assert out["team_id"] == 158
    assert out["qs_rate"] == pytest.approx(2 / 3)


def test_fetch_gamelog_starts_no_starts_none(monkeypatch):
    monkeypatch.setattr(sdf, "fetch_url", lambda url, timeout=30: json.dumps(
        {"stats": [{"splits": []}]}))
    assert sdf.fetch_gamelog_starts(123, 2026) is None


def test_fetch_gamelog_starts_error_none(monkeypatch):
    def boom(url, timeout=30):
        raise TimeoutError("nope")
    monkeypatch.setattr(sdf, "fetch_url", boom)
    assert sdf.fetch_gamelog_starts(123, 2026) is None


def _schedule_payload():
    def game(home_id, away_id, probable_side=None, pid=None):
        g = {"teams": {
            "home": {"team": {"id": home_id}},
            "away": {"team": {"id": away_id}},
        }}
        if probable_side:
            g["teams"][probable_side]["probablePitcher"] = {"id": pid}
        return g
    return json.dumps({"dates": [
        {"date": "2026-07-13", "games": [game(158, 112, "home", 777)]},
        {"date": "2026-07-15", "games": [game(112, 158, "away", 777)]},
        {"date": "2026-07-18", "games": [game(158, 112)]},
    ]})


def test_fetch_week_schedule_parse(monkeypatch):
    monkeypatch.setattr(sdf, "fetch_url", lambda url, timeout=30: _schedule_payload())
    out = sdf.fetch_week_schedule("2026-07-13", "2026-07-19")
    assert out["team_days"][158] == ["2026-07-13", "2026-07-15", "2026-07-18"]
    assert out["probables"][777] == ["2026-07-13", "2026-07-15"]
    assert out["horizon_end"] == "2026-07-15"   # last date with ANY probable


def test_fetch_standings_winpct_parse(monkeypatch):
    payload = json.dumps({"records": [{"teamRecords": [
        {"team": {"id": 158}, "winningPercentage": ".588"},
        {"team": {"id": 112}, "winningPercentage": ".451"},
    ]}]})
    monkeypatch.setattr(sdf, "fetch_url", lambda url, timeout=30: payload)
    out = sdf.fetch_standings_winpct(2026)
    assert out == {158: 0.588, 112: 0.451}


# ── _attach_318b orchestration (everything injected) ──

STRONG_V4 = {
    "ip_gs": 6.0, "whiff_pct": 27.0, "bb9": 2.2, "gb_pct": 47.0,
    "xwobacon": 0.355, "bbe": 120, "ip": 96.0, "g": 16, "gs": 16,
    "k9": 9.0, "whip": 1.1, "era": 3.5, "xera": 3.6,
    "k": 96, "bb": 24, "bf": 400,
}
SMALL_V4 = {
    "ip_gs": 5.0, "whiff_pct": 24.0, "bb9": 3.2, "gb_pct": 42.0,
    "xwobacon": 0.370, "bbe": 20, "ip": 18.0, "g": 4, "gs": 4,
    "k9": 8.0, "whip": 1.3, "era": 4.2, "xera": 4.1,
    "k": 20, "bb": 6, "bf": 80,
}


@pytest.fixture()
def wired(monkeypatch):
    """Monkeypatch every network seam _attach_318b touches."""
    week = (date(2026, 7, 13), date(2026, 7, 19))
    monkeypatch.setattr(_phase6_sp, "_week_window_et", lambda today=None: week)

    gamelogs = {
        1: {"start_dates": ["2026-06-28", "2026-07-03", "2026-07-08"],
            "team_id": 158, "qs_rate": 0.6},       # incumbent
        2: {"start_dates": ["2026-06-29", "2026-07-04", "2026-07-09"],
            "team_id": 112, "qs_rate": 0.7},       # strong FA
        3: {"start_dates": ["2026-07-01", "2026-07-06"],
            "team_id": 112, "qs_rate": 0.5},       # small-sample FA
    }
    monkeypatch.setattr(sdf, "fetch_gamelog_starts",
                        lambda pid, year: gamelogs.get(pid))
    monkeypatch.setattr(sdf, "fetch_week_schedule", lambda s, e: {
        "team_days": {158: [f"2026-07-{d}" for d in range(13, 20)],
                      112: [f"2026-07-{d}" for d in range(13, 20)]},
        "probables": {2: ["2026-07-14"]},
        "horizon_end": "2026-07-17",
    })
    monkeypatch.setattr(sdf, "fetch_standings_winpct",
                        lambda season: {158: 0.55, 112: 0.60})
    monkeypatch.setattr(micro_fields_sp, "fetch_season_velo_bulk",
                        lambda year: ({2: {"FF": 95.5}} if year == 2026
                                      else {2: {"FF": 96.0}}))
    return week


def _mk(name, pid, v4, rolling=None, prior=None):
    return {"name": name, "mlb_id": pid, "team": "X", "source": "scan-query",
            "savant_v4": dict(v4), "rolling_21d": rolling or {},
            "prior_stats": prior or {}}


def test_attach_318b_end_to_end(wired):
    incumbent = _mk("Inc SP", 1, {**STRONG_V4, "ip_gs": 5.4})
    strong_fa = _mk(
        "Strong FA", 2, STRONG_V4,
        rolling={"xwobacon": 0.340, "bbe": 60, "csw_pct": 29.0, "pitches": 400,
                 "velo_fb": 94.2, "velo_fb_type": "FF",
                 "velo_fb_last_game": 93.8},
        prior={"whiff_pct": 27.9, "bb9": 2.18, "xwobacon": 0.345, "ip": 120})
    small_fa = _mk("Small FA", 3, SMALL_V4)

    histories = {"Inc SP": [], "Strong FA": [], "Small FA": []}
    h = {"ledger_histories": lambda names: histories}

    enrich_map = _phase6_sp._attach_318b(
        [incumbent], [strong_fa, small_fa], h, "2026-07-07")

    # 046 — probable-anchored projection for the strong FA:
    # probable 07-14 + cadence 5 → 07-19 also in window → 2 starts
    nws = strong_fa["next_week_starts"]
    assert nws["starts"] == 2
    assert nws["dates"] == ["2026-07-14", "2026-07-19"]
    assert nws["source"] == "probable"
    assert nws["window"] == ["2026-07-13", "2026-07-19"]
    # incumbent: last start 07-08, cadence 5 → 07-13 + 07-18, no probable but
    # candidates beyond horizon-slack are kept... 07-13+2 <= 07-17 → suppressed;
    # 07-18+2 > 07-17 → kept → 1 start
    assert incumbent["next_week_starts"]["starts"] == 1

    # 050 — velo deltas + tag on the strong FA (94.2 vs 95.5 → -1.3)
    assert strong_fa["micro_velo"]["d21_vs_season"] == -1.3
    assert strong_fa["micro_velo"]["yoy"] == -0.5
    assert any(t.startswith("⚠️ 球速下滑") for t in strong_fa["warn_tags"])
    # kbb only for the BBE<30 entry
    assert "kbb_small_sample" not in strong_fa
    assert small_fa["kbb_small_sample"]["tier"] == "stable"   # BF 80 ≥ 70

    # ledger memory — day-0 everywhere: no notes, but enrich map carries
    # channel/stars/add_reason for the waiver-log write
    assert "ledger_note" not in strong_fa
    assert enrich_map["Strong FA"].stars == 4
    assert enrich_map["Strong FA"].channel == "structure"
    assert enrich_map["Strong FA"].add_reason.startswith("IP/GS")

    # 048 — swap only for the 4★ FA, vs the incumbent by name
    assert strong_fa["swap_vs_incumbent"].startswith(
        "swap Inc SP→Strong FA/week:")
    assert "swap_vs_incumbent" not in small_fa


def test_attach_318b_history_renders_note(wired):
    class _E:
        verdict = "watch"
        ts = "2026-07-04"
        add_reason = "原本理由"
        channel = "heat"

    fa = _mk("FA X", 2, STRONG_V4)
    h = {"ledger_histories": lambda names: {"FA X": [_E()]}}
    _phase6_sp._attach_318b([_mk("Inc", 1, STRONG_V4)], [fa], h, "2026-07-07")
    assert fa["ledger_note"] == ["[記事] 上次 watch（3 天前）", "[原撿因] 原本理由"]
    # first-contact heat channel honored → hard cap 3★ → no swap line
    assert fa["_stars"] <= 3
    assert "swap_vs_incumbent" not in fa


def test_attach_318b_survives_fetch_failures(monkeypatch):
    monkeypatch.setattr(_phase6_sp, "_week_window_et",
                        lambda today=None: (date(2026, 7, 13), date(2026, 7, 19)))

    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(sdf, "fetch_week_schedule", boom)
    monkeypatch.setattr(sdf, "fetch_gamelog_starts", lambda pid, year: None)
    monkeypatch.setattr(sdf, "fetch_standings_winpct", boom)
    monkeypatch.setattr(micro_fields_sp, "fetch_season_velo_bulk", boom)

    fa = _mk("FA X", 2, STRONG_V4)
    enrich_map = _phase6_sp._attach_318b(
        [_mk("Inc", 1, STRONG_V4)], [fa], {}, "2026-07-07")
    assert "next_week_starts" not in fa      # degraded, not crashed
    assert "micro_velo" not in fa
    assert enrich_map["FA X"].stars is not None