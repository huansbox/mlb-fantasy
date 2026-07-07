"""318b B6 injection behavior of payload_slimmer.slim_entry."""

import payload_slimmer


def _entry(**extra):
    base = {
        "name": "Test SP",
        "team": "MIL",
        "savant_v4": {
            "ip_gs": 5.5, "whiff_pct": 24.0, "bb9": 3.0, "gb_pct": 44.0,
            "xwobacon": 0.360, "bbe": 120, "ip": 90.0, "g": 16, "gs": 16,
            "k9": 8.5, "whip": 1.2, "era": 3.8, "xera": 3.9,
        },
    }
    base.update(extra)
    return base


NWS = {"starts": 2, "window": ["2026-07-13", "2026-07-19"],
       "dates": ["2026-07-14", "2026-07-19"], "source": "probable"}
VELO = {"fb_type": "FF", "velo_21d": 94.0, "velo_season": 95.2,
        "d21_vs_season": -1.2, "yoy": None, "last_game": 93.6}
KBB = {"kbb_pct": 15.0, "bf": 55, "tier": "early"}


def test_no_injection_keys_no_injection_fields():
    slim = payload_slimmer.slim_entry(_entry(), "fa")
    for key in ("ledger_note", "next_week_starts", "velo",
                "kbb_small_sample", "swap_vs_incumbent"):
        assert key not in slim


def test_all_without_ledger_fit_base_pool():
    slim = payload_slimmer.slim_entry(
        _entry(next_week_starts=NWS, micro_velo=VELO, kbb_small_sample=KBB),
        "fa")
    assert slim["next_week_starts"] == NWS
    assert slim["velo"] == VELO
    assert slim["kbb_small_sample"] == KBB


def test_ledger_plus_starts_evicts_velo_and_kbb():
    slim = payload_slimmer.slim_entry(
        _entry(ledger_note=["[記事] 上次 watch（3 天前）", "[原撿因] X"],
               next_week_starts=NWS, micro_velo=VELO, kbb_small_sample=KBB),
        "fa")
    assert slim["ledger_note"] == ["[記事] 上次 watch（3 天前）", "[原撿因] X"]
    assert slim["next_week_starts"] == NWS   # 2 + 1 = base ceiling
    assert "velo" not in slim                # lower priority yields
    assert "kbb_small_sample" not in slim


def test_ledger_plus_velo_fits_without_starts():
    slim = payload_slimmer.slim_entry(
        _entry(ledger_note=["[記事] 上次 watch（1 天前）"], micro_velo=VELO),
        "fa")
    assert slim["velo"] == VELO              # 1 + 1 ≤ 3


def test_oversized_ledger_note_truncated_to_ceiling():
    # a future format_ledger_note emitting >3 lines must not smuggle lines
    # past the budget — inject exactly what is registered
    slim = payload_slimmer.slim_entry(
        _entry(ledger_note=["a", "b", "c", "d"], next_week_starts=NWS), "fa")
    assert slim["ledger_note"] == ["a", "b", "c"]
    assert "next_week_starts" not in slim    # ledger filled the base pool


def test_swap_rides_its_own_pool_even_when_base_full():
    slim = payload_slimmer.slim_entry(
        _entry(ledger_note=["a", "b"], next_week_starts=NWS,
               swap_vs_incumbent="swap A→B/week: IP +1.2, K +3.1"),
        "fa")
    assert slim["swap_vs_incumbent"].startswith("swap A→B/week:")


def test_velo_tag_prefix_whitelisted():
    slim = payload_slimmer.slim_entry(
        _entry(warn_tags=["⚠️ 球速下滑 (FF -1.3 vs season)", "⚠️ 不在名單的怪tag"],
               add_tags=["✅ 球速上升 (SI +1.1 vs season)"]),
        "fa")
    assert slim["warn_tags"] == ["⚠️ 球速下滑 (FF -1.3 vs season)"]
    assert slim["add_tags"] == ["✅ 球速上升 (SI +1.1 vs season)"]


def test_csw_rides_rolling_dict():
    slim = payload_slimmer.slim_entry(
        _entry(rolling_21d={"xwobacon": 0.340, "bbe": 60,
                            "csw_pct": 28.3, "pitches": 410}),
        "my_team")
    assert slim["rolling_21d"]["csw_pct"] == 28.3
    assert slim["rolling_21d"]["pitches"] == 410


def test_csw_absent_keeps_rolling_shape():
    slim = payload_slimmer.slim_entry(
        _entry(rolling_21d={"xwobacon": 0.340, "bbe": 60}), "my_team")
    assert "csw_pct" not in slim["rolling_21d"]


def test_private_stars_never_slimmed():
    slim = payload_slimmer.slim_entry(_entry(_stars=4), "fa")
    assert "_stars" not in slim