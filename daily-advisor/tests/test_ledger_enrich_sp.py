"""Unit tests for the 318b B6 SP section of ledger_enrich."""

from ledger_enrich import (
    CHANNEL_HEAT,
    CHANNEL_STRUCTURE,
    CHANNEL_UNKNOWN,
    SPSignals,
    build_star_factors_sp,
    compute_candidate_stars_sp,
    enrich_candidate_sp,
    is_hot_21d_sp,
    is_season_strong_sp,
    snapshot_add_reason_sp,
    sp_percentile_of,
)


class _E:
    def __init__(self, verdict="watch", ts="2026-07-01",
                 add_reason=None, channel=None):
        self.verdict = verdict
        self.ts = ts
        self.add_reason = add_reason
        self.channel = channel


# ── sp_percentile_of (elite-direction, reverse-aware) ──

def test_percentile_normal_metric():
    assert sp_percentile_of(6.11, "ip_gs") == 90
    assert sp_percentile_of(5.5, "ip_gs") == 50
    assert sp_percentile_of(5.0, "ip_gs") == 0


def test_percentile_reverse_metric():
    assert sp_percentile_of(1.96, "bb9") == 90
    assert sp_percentile_of(2.0, "bb9") == 80
    assert sp_percentile_of(4.0, "bb9") == 0
    assert sp_percentile_of(0.341, "xwobacon") == 90


def test_percentile_none_and_unknown_metric():
    assert sp_percentile_of(None, "ip_gs") == 0
    assert sp_percentile_of(5.0, "nope") == 0


# ── season strong / hot ──

def test_season_strong_three_of_five():
    sig = SPSignals(source="scan-query", ip_gs=5.61, whiff_pct=25.1, bb9=2.73)
    assert is_season_strong_sp(sig)          # exactly 3 slots at P60


def test_season_not_strong_two_of_five():
    sig = SPSignals(source="scan-query", ip_gs=5.61, whiff_pct=25.1, bb9=3.5)
    assert not is_season_strong_sp(sig)


def test_hot_21d_surge():
    assert is_hot_21d_sp(0.330, 0.375)       # .045 below season
    assert not is_hot_21d_sp(0.360, 0.375)   # .015 — noise
    assert not is_hot_21d_sp(None, 0.375)
    assert not is_hot_21d_sp(0.330, None)


# ── star factors ──

def test_factors_dual_year_full():
    sig = SPSignals(source="scan-query", ip_gs=5.9,
                    prior_whiff_pct=26.5, prior_bb9=2.38, prior_ip=120)
    f = build_star_factors_sp(sig, CHANNEL_STRUCTURE)
    assert f["dual_year"] == "full"          # 2 slots P70+, sample ok
    assert f["playing_time"] == "high"       # 5.9 ≥ P80 anchor 5.89


def test_factors_dual_year_thin_sample_partial():
    sig = SPSignals(source="scan-query", ip_gs=5.5,
                    prior_whiff_pct=26.5, prior_bb9=2.38, prior_ip=30)
    f = build_star_factors_sp(sig, CHANNEL_STRUCTURE)
    assert f["dual_year"] == "partial"
    assert f["playing_time"] == "mid"        # 5.35 ≤ 5.5 < 5.89


def test_factors_rotation_gate_low():
    sig = SPSignals(source="scan-query", ip_gs=6.5, rotation_ok=False)
    f = build_star_factors_sp(sig, CHANNEL_UNKNOWN)
    assert f["playing_time"] == "low"


# ── stars ──

STRONG = dict(ip_gs=6.0, whiff_pct=27.0, bb9=2.2,
              prior_whiff_pct=27.9, prior_bb9=2.18, prior_ip=100)


def test_day0_strong_capped_at_four():
    sig = SPSignals(source="scan-query", **STRONG)
    stars, channel, _ = compute_candidate_stars_sp(sig, history=[])
    assert channel == CHANNEL_STRUCTURE
    assert stars == 4                        # day-0 cap — 5★ needs a trigger


def test_established_strong_four_stars():
    sig = SPSignals(source="scan-query", **STRONG)
    stars, _, result = compute_candidate_stars_sp(sig, history=[_E()])
    assert stars == 4                        # 3.0 factors + trigger none
    assert result.breakdown["trigger"] == 0.0


def test_first_contact_channel_honored():
    sig = SPSignals(source="scan-query", **STRONG)
    stars, channel, _ = compute_candidate_stars_sp(
        sig, history=[_E(channel="heat")])
    assert channel == CHANNEL_HEAT           # never re-judged
    assert stars <= 3                        # heat hard cap


def test_weak_unknown_channel():
    sig = SPSignals(source="scan-query", ip_gs=5.0, whiff_pct=20.0, bb9=4.0)
    _, channel, _ = compute_candidate_stars_sp(sig, history=[])
    assert channel == CHANNEL_UNKNOWN


# ── snapshot + enrich bundle ──

def test_snapshot_add_reason_sp():
    sig = SPSignals(source="scan-query", ip_gs=5.85, whiff_pct=24.05,
                    bb9=3.08, gb_pct=55.3, xwobacon=0.348)
    assert snapshot_add_reason_sp(sig) == (
        "IP/GS 5.85 / Whiff% 24.1 / BB/9 3.08 / GB% 55.3 / xwOBACON .348")


def test_snapshot_empty_is_question_mark():
    assert snapshot_add_reason_sp(SPSignals(source="scan-query")) == "?"


def test_enrich_candidate_sp_no_history_no_note():
    enr = enrich_candidate_sp(SPSignals(source="scan-query", **STRONG),
                              [], "2026-07-07")
    assert enr.note_lines == []              # day-0: no memory yet
    assert enr.add_reason.startswith("IP/GS")
    assert enr.stars == 4


def test_enrich_candidate_sp_with_history_renders_note():
    hist = [_E(verdict="watch", ts="2026-07-04", add_reason="原因A")]
    enr = enrich_candidate_sp(SPSignals(source="scan-query", **STRONG),
                              hist, "2026-07-07")
    assert enr.note_lines == ["[記事] 上次 watch（3 天前）", "[原撿因] 原因A"]
    assert enr.add_reason == "原因A"         # never re-judged