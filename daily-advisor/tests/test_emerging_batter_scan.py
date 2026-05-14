"""TDD tests for emerging_batter_scan.py — Step 2-6 of /emerging-batter pipeline.

設計依據：docs/emerging-batter-design.md（2026-05-14 定稿）
"""

import pytest

from emerging_batter_scan import (
    FABatter,
    Fetchers,
    OwnedTrend,
    RollingStats,
    TradStats,
    classify_candidate,
    has_hot_streak_signal,
    has_owned_burst,
    has_pa_tg_jump,
    has_role_change_signal,
    pa_per_team_game,
    perf_14d_matches,
    scan,
)


# ── Decision 1: role change signal — PA/TG jump ───────────────────────────


class TestPaPerTeamGame:
    def test_basic_division(self):
        assert pa_per_team_game(pa=28, team_games=7) == 4.0

    def test_zero_games_returns_zero(self):
        # 球員剛 call up 隔天就掃 → team 14d 內 0 場（或計算 bug）→ 不爆 div by zero
        assert pa_per_team_game(pa=0, team_games=0) == 0.0

    def test_partial_decimal_rounded_reasonable(self):
        # 球員 25 PA / 14 場 = 1.785... → 不四捨五入，由呼叫端決定顯示
        assert pa_per_team_game(pa=25, team_games=14) == pytest.approx(1.7857, abs=1e-3)


class TestHasPaTgJump:
    def test_jump_from_bench_to_starter_passes(self):
        # 14d 1.8 (bench) → 7d 4.0 (everyday starter): +2.2 > +1.0 ✅, 7d ≥ 3.5 ✅
        assert has_pa_tg_jump(pa_tg_7d=4.0, pa_tg_14d=1.8) is True

    def test_steady_starter_fails_no_jump(self):
        # 14d 4.0 / 7d 4.0 = 維持 everyday，沒「跳升」訊號（角色未變）
        assert has_pa_tg_jump(pa_tg_7d=4.0, pa_tg_14d=4.0) is False

    def test_jump_but_still_below_starter_threshold_fails(self):
        # 14d 1.0 → 7d 2.5：跳了 +1.5 但 7d <3.5（還沒到主力門檻）
        assert has_pa_tg_jump(pa_tg_7d=2.5, pa_tg_14d=1.0) is False

    def test_high_7d_but_small_delta_fails(self):
        # 7d 4.0 ≥ 3.5 但 14d 3.8（delta 只 +0.2）— 排除 lineup 漂移
        assert has_pa_tg_jump(pa_tg_7d=4.0, pa_tg_14d=3.8) is False

    def test_boundary_7d_eq_3p5_delta_eq_1p0_passes(self):
        # 7d 3.5, 14d 2.5: 邊界含 — 兩條件剛好達標
        assert has_pa_tg_jump(pa_tg_7d=3.5, pa_tg_14d=2.5) is True


# ── Decision 1: role change signal — %owned burst ─────────────────────────


class TestHasOwnedBurst:
    def test_3d_explosive_passes(self):
        # delta_3d +6pp ≥ +5pp → 聯盟層發現訊號
        assert has_owned_burst(delta_3d=6.0, delta_7d=8.0) is True

    def test_7d_long_run_passes(self):
        # delta_3d +2pp (rising 不算 burst), delta_7d +12pp 累積 → 7d 達標
        assert has_owned_burst(delta_3d=2.0, delta_7d=12.0) is True

    def test_plateau_fails(self):
        assert has_owned_burst(delta_3d=1.0, delta_7d=3.0) is False

    def test_dropping_fails(self):
        assert has_owned_burst(delta_3d=-2.0, delta_7d=-5.0) is False

    def test_none_deltas_treated_as_no_signal(self):
        # 新進 FA 沒 7d ago snapshot → delta None → 不算訊號達標
        assert has_owned_burst(delta_3d=None, delta_7d=None) is False

    def test_one_delta_none_other_passes(self):
        # 剛進市場 3 天，沒 7d ago → delta_7d=None 但 delta_3d 達標仍 True
        assert has_owned_burst(delta_3d=8.0, delta_7d=None) is True


class TestHasRoleChangeSignal:
    def test_pa_jump_alone_passes(self):
        # 只 PA/TG 跳，沒 %owned burst → 仍算 role change
        assert (
            has_role_change_signal(
                pa_tg_7d=4.0,
                pa_tg_14d=1.8,
                delta_3d=1.0,
                delta_7d=2.0,
            )
            is True
        )

    def test_owned_burst_alone_passes(self):
        # 只 %owned 衝刺，PA/TG 還沒升（聯盟先發現）→ 仍算 role change
        assert (
            has_role_change_signal(
                pa_tg_7d=3.0,
                pa_tg_14d=2.9,
                delta_3d=6.0,
                delta_7d=8.0,
            )
            is True
        )

    def test_neither_signal_fails(self):
        assert (
            has_role_change_signal(
                pa_tg_7d=3.0,
                pa_tg_14d=2.9,
                delta_3d=1.0,
                delta_7d=2.0,
            )
            is False
        )


# ── Decision 1: 14d perf gate ─────────────────────────────────────────────


class TestPerf14dMatches:
    def test_ops_above_650_passes(self):
        trad = _trad(ops=0.720, r=2, hr=0, rbi=3)
        assert perf_14d_matches(trad) is True

    def test_counting_above_8_passes(self):
        # OPS .580 偏弱但 R+HR+RBI=10 — 算量產
        trad = _trad(ops=0.580, r=4, hr=2, rbi=4)
        assert perf_14d_matches(trad) is True

    def test_both_below_fails(self):
        trad = _trad(ops=0.540, r=1, hr=0, rbi=2)
        assert perf_14d_matches(trad) is False

    def test_boundary_ops_eq_650_passes(self):
        trad = _trad(ops=0.650, r=0, hr=0, rbi=0)
        assert perf_14d_matches(trad) is True

    def test_boundary_counting_eq_8_passes(self):
        trad = _trad(ops=0.500, r=3, hr=1, rbi=4)
        assert perf_14d_matches(trad) is True


# ── Decision 2: hot streak signal ─────────────────────────────────────────


class TestHasHotStreakSignal:
    def test_high_xwoba_with_enough_bbe_passes(self):
        # xwOBA .340 ≥ P75 .326, BBE 30 ≥ 25
        rolling = RollingStats(xwoba=0.340, xwobacon=0.380, barrel_pct=9.0, bbe=30)
        assert has_hot_streak_signal(rolling) is True

    def test_high_barrel_with_enough_bbe_passes(self):
        # xwOBA 普通但 Barrel% 14% ≥ P75 11.2%
        rolling = RollingStats(xwoba=0.310, xwobacon=0.350, barrel_pct=14.0, bbe=28)
        assert has_hot_streak_signal(rolling) is True

    def test_low_bbe_excluded(self):
        # xwOBA .380 強但 BBE 20 < 25 — 樣本太小不採信
        rolling = RollingStats(xwoba=0.380, xwobacon=0.420, barrel_pct=15.0, bbe=20)
        assert has_hot_streak_signal(rolling) is False

    def test_neither_rate_high_fails(self):
        # xwOBA .310 < P75, Barrel% 8% < P75，雖 BBE 達標但兩者都不夠
        rolling = RollingStats(xwoba=0.310, xwobacon=0.340, barrel_pct=8.0, bbe=40)
        assert has_hot_streak_signal(rolling) is False


# ── classify_candidate（dispatcher）────────────────────────────────────────


def _trad(
    pa=20, team_games=14, ops=0.700, hr=1, rbi=4, r=3, sb=0, bb=2, k=5, k_pct=20.0,
):
    return TradStats(
        pa=pa, team_games=team_games, ops=ops, hr=hr, rbi=rbi, r=r, sb=sb,
        bb=bb, k=k, k_pct=k_pct,
    )


def _rolling(xwoba=0.310, xwobacon=0.350, barrel_pct=9.0, bbe=30):
    return RollingStats(xwoba=xwoba, xwobacon=xwobacon, barrel_pct=barrel_pct, bbe=bbe)


def _owned(current=10, d3=2.0, d7=4.0):
    return OwnedTrend(current_pct=current, delta_3d=d3, delta_7d=d7)


def _batter(mlb_id=100, name="Test Batter", team="ATL", positions=("OF",), pct_owned=10):
    return FABatter(
        mlb_id=mlb_id, name=name, team=team, positions=list(positions),
        percent_owned=pct_owned,
    )


class TestClassifyCandidate:
    def test_role_change_with_perf_match_goes_to_role_change(self):
        # PA/TG 14d 1.71 → 7d 4.0 跳 +2.29 + 14d OPS .720 達標
        verdict = classify_candidate(
            batter=_batter(),
            trad_14d=_trad(pa=24, team_games=14, ops=0.720),  # PA/TG = 1.71
            trad_7d=_trad(pa=24, team_games=6),               # PA/TG = 4.0
            rolling=_rolling(),
            owned=_owned(d3=2.0, d7=4.0),
            cant_cut_ids=set(),
            position_saturated=False,
        )
        assert verdict.bucket == "role_change"

    def test_role_change_signal_but_perf_low_drops(self):
        # PA/TG 跳但 14d OPS .540 + 量產 5 → 不進 role_change，也不進 hot_streak（無 rate 訊號）
        verdict = classify_candidate(
            batter=_batter(),
            trad_14d=_trad(pa=42, team_games=12, ops=0.540, r=1, hr=0, rbi=4),
            trad_7d=_trad(pa=24, team_games=6),
            rolling=_rolling(xwoba=0.290, barrel_pct=7.0),
            owned=_owned(d3=1.0, d7=2.0),
            cant_cut_ids=set(),
            position_saturated=False,
        )
        assert verdict.bucket == "dropped"  # 無分桶（不出現在 output）

    def test_hot_streak_without_role_change(self):
        # 無 PA/TG 跳 + 無 %owned burst，但 14d xwOBA .340 + BBE 30
        verdict = classify_candidate(
            batter=_batter(),
            trad_14d=_trad(pa=30, team_games=14, ops=0.720),  # PA/TG = 2.14
            trad_7d=_trad(pa=15, team_games=7),               # PA/TG = 2.14 (穩定)
            rolling=_rolling(xwoba=0.340, bbe=30),
            owned=_owned(d3=1.0, d7=2.0),
            cant_cut_ids=set(),
            position_saturated=False,
        )
        assert verdict.bucket == "hot_streak"

    def test_role_change_takes_priority_over_hot_streak(self):
        # PA/TG jump + owned burst + hot streak rate 三訊號都達標 → 進 role_change
        verdict = classify_candidate(
            batter=_batter(),
            trad_14d=_trad(pa=24, team_games=14, ops=0.800),  # PA/TG 14d = 1.71
            trad_7d=_trad(pa=24, team_games=6),               # PA/TG 7d = 4.0
            rolling=_rolling(xwoba=0.360, barrel_pct=15.0, bbe=35),
            owned=_owned(d3=6.0, d7=10.0),
            cant_cut_ids=set(),
            position_saturated=False,
        )
        assert verdict.bucket == "role_change"

    def test_cant_cut_filtered_first(self):
        # 即使有訊號，cant_cut 上的人從 FA 池應該已被排除（不該出現）
        verdict = classify_candidate(
            batter=_batter(mlb_id=669373),  # Skubal 假裝 batter
            trad_14d=_trad(pa=42, team_games=12, ops=0.800),
            trad_7d=_trad(pa=24, team_games=6),
            rolling=_rolling(),
            owned=_owned(),
            cant_cut_ids={669373},
            position_saturated=False,
        )
        assert verdict.bucket == "filtered_cant_cut"

    def test_high_ownership_filtered(self):
        # %owned > 40 → 不算 emerging（已多隊看到）
        verdict = classify_candidate(
            batter=_batter(pct_owned=55),
            trad_14d=_trad(pa=42, team_games=12, ops=0.800),
            trad_7d=_trad(pa=24, team_games=6),
            rolling=_rolling(),
            owned=_owned(current=55),
            cant_cut_ids=set(),
            position_saturated=False,
        )
        assert verdict.bucket == "filtered_high_ownership"

    def test_position_saturated_filtered(self):
        # 隊上同位置已有 active anchor 飽和
        verdict = classify_candidate(
            batter=_batter(positions=["1B"]),
            trad_14d=_trad(pa=42, team_games=12, ops=0.800),
            trad_7d=_trad(pa=24, team_games=6),
            rolling=_rolling(),
            owned=_owned(),
            cant_cut_ids=set(),
            position_saturated=True,
        )
        assert verdict.bucket == "filtered_position_saturated"

    def test_low_bbe_with_hot_streak_only_filtered(self):
        # 14d rate 達 P75 但 BBE 20 < 25 → low_confidence
        verdict = classify_candidate(
            batter=_batter(),
            trad_14d=_trad(pa=20, team_games=14, ops=0.720),  # PA/TG 1.43 (no role change)
            trad_7d=_trad(pa=10, team_games=7),
            rolling=_rolling(xwoba=0.380, barrel_pct=15.0, bbe=20),
            owned=_owned(d3=1.0, d7=2.0),
            cant_cut_ids=set(),
            position_saturated=False,
        )
        assert verdict.bucket == "filtered_low_bbe"

    def test_low_bbe_does_not_filter_role_change(self):
        # role change 有結構錨，BBE 低仍進 role_change（不卡 BBE gate）
        verdict = classify_candidate(
            batter=_batter(),
            trad_14d=_trad(pa=24, team_games=14, ops=0.720),  # PA/TG 14d = 1.71
            trad_7d=_trad(pa=24, team_games=6),               # PA/TG 7d = 4.0 → jump 2.29
            rolling=_rolling(bbe=15),  # 樣本小
            owned=_owned(),
            cant_cut_ids=set(),
            position_saturated=False,
        )
        assert verdict.bucket == "role_change"


# ── scan() 端到端 ──────────────────────────────────────────────────────────


def _build_fetchers(
    *,
    fa_pool=None,
    rolling=None,
    trad_14d=None,
    trad_7d=None,
    owned=None,
    cant_cut=None,
    saturated_positions=None,
):
    rolling = rolling or {}
    trad_14d = trad_14d or {}
    trad_7d = trad_7d or {}
    owned = owned or {}
    cant_cut = cant_cut or set()
    saturated_positions = saturated_positions or set()
    return Fetchers(
        fa_pool_fn=lambda: list(fa_pool or []),
        rolling_fn=lambda mid: rolling.get(mid),
        trad_14d_fn=lambda mid: trad_14d.get(mid),
        trad_7d_fn=lambda mid: trad_7d.get(mid),
        owned_trend_fn=lambda name: owned.get(name),
        cant_cut_fn=lambda: set(cant_cut),
        position_saturated_fn=lambda positions: any(
            p in saturated_positions for p in positions
        ),
    )


class TestScan:
    def test_single_role_change_candidate_end_to_end(self):
        b = _batter(mlb_id=701, name="Hot Rookie", team="STL", positions=["OF"], pct_owned=8)
        fetchers = _build_fetchers(
            fa_pool=[b],
            rolling={701: _rolling(xwoba=0.330, bbe=28)},
            trad_14d={701: _trad(pa=42, team_games=12, ops=0.812, hr=3, rbi=9, r=8)},
            trad_7d={701: _trad(pa=24, team_games=6)},
            owned={"Hot Rookie": _owned(current=8, d3=6.0, d7=12.0)},
        )
        result = scan(fetchers=fetchers)

        assert len(result["role_change_candidates"]) == 1
        c = result["role_change_candidates"][0]
        assert c["name"] == "Hot Rookie"
        assert c["mlb_id"] == 701
        assert c["team"] == "STL"
        assert c["positions"] == ["OF"]
        assert c["percent_owned"] == 8
        # role change 訊號細節
        assert c["pa_tg_14d"] == pytest.approx(3.5, abs=0.01)
        assert c["pa_tg_7d"] == pytest.approx(4.0, abs=0.01)
        assert c["pa_tg_jump"] == pytest.approx(0.5, abs=0.01)
        assert c["owned_delta_3d"] == 6.0
        assert c["owned_delta_7d"] == 12.0
        # rolling 14d
        assert c["rolling_14d"]["xwoba"] == 0.330
        assert c["rolling_14d"]["bbe"] == 28
        # trad 14d
        assert c["trad_14d"]["ops"] == 0.812
        assert c["trad_14d"]["hr"] == 3

    def test_hot_streak_candidate_separate_bucket(self):
        b = _batter(mlb_id=702, name="Streaky Vet", positions=["2B"])
        fetchers = _build_fetchers(
            fa_pool=[b],
            rolling={702: _rolling(xwoba=0.340, barrel_pct=12.0, bbe=30)},
            trad_14d={702: _trad(pa=28, team_games=14, ops=0.760)},  # PA/TG 2.0
            trad_7d={702: _trad(pa=14, team_games=7)},               # PA/TG 2.0 穩定
            owned={"Streaky Vet": _owned(d3=1.0, d7=2.0)},           # 無 burst
        )
        result = scan(fetchers=fetchers)
        assert len(result["role_change_candidates"]) == 0
        assert len(result["hot_streak_candidates"]) == 1
        assert result["hot_streak_candidates"][0]["name"] == "Streaky Vet"

    def test_filtered_buckets_populated(self):
        # 三人各 hit 一種 filter
        skubal = _batter(mlb_id=669373, name="Skubal Batter", pct_owned=5)
        owned_too_much = _batter(mlb_id=802, name="Already Owned", pct_owned=55)
        sat = _batter(mlb_id=803, name="Pos Saturated", positions=["1B"])
        fetchers = _build_fetchers(
            fa_pool=[skubal, owned_too_much, sat],
            rolling={
                669373: _rolling(), 802: _rolling(), 803: _rolling(),
            },
            trad_14d={
                669373: _trad(), 802: _trad(), 803: _trad(),
            },
            trad_7d={
                669373: _trad(), 802: _trad(), 803: _trad(),
            },
            owned={
                "Skubal Batter": _owned(), "Already Owned": _owned(current=55),
                "Pos Saturated": _owned(),
            },
            cant_cut={669373},
            saturated_positions={"1B"},
        )
        result = scan(fetchers=fetchers)
        names = lambda k: [x["name"] for x in result["filtered"][k]]
        assert names("cant_cut_conflict") == ["Skubal Batter"]
        assert names("high_ownership") == ["Already Owned"]
        assert names("position_saturated") == ["Pos Saturated"]

    def test_missing_rolling_skips_candidate(self):
        # 某 batter 沒在 savant rolling.json（剛 call up < 14 天）— 不爆，列為 low_confidence
        b = _batter(mlb_id=704, name="Just Called Up", pct_owned=2)
        fetchers = _build_fetchers(
            fa_pool=[b],
            rolling={},  # rolling miss
            trad_14d={704: _trad(pa=20, team_games=10, ops=0.680)},
            trad_7d={704: _trad(pa=20, team_games=7)},  # PA/TG 7d=2.86
            owned={"Just Called Up": _owned(d3=3.0, d7=5.0)},
        )
        result = scan(fetchers=fetchers)
        # 沒 rolling → hot streak 訊號算不出 → 若無 role change 仍可進 low_bbe filter
        # 這人 PA/TG 7d 2.86 < 3.5 → 無 role change，無 rolling → 丟
        assert len(result["role_change_candidates"]) == 0
        assert len(result["hot_streak_candidates"]) == 0

    def test_empty_pool_returns_empty_segments(self):
        fetchers = _build_fetchers(fa_pool=[])
        result = scan(fetchers=fetchers)
        assert result == {
            "role_change_candidates": [],
            "hot_streak_candidates": [],
            "filtered": {
                "cant_cut_conflict": [],
                "high_ownership": [],
                "position_saturated": [],
                "low_confidence_bbe": [],
            },
        }
