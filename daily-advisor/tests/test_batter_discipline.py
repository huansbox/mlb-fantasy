"""Unit tests for batter_discipline.py pure layer (issue 049 M-bat).

Network fetch (fetch_batter_discipline_bulk) is not exercised — only the pure
percentile / delta / tag logic, which carries the correctness risk.
"""

from batter_discipline import (
    CHASE_DELTA_SIG,
    CUR_PA_FLOOR,
    PRIOR_PA_FLOOR,
    ZCON_DELTA_SIG,
    _CHASE_PCTILES,
    _ZCON_PCTILES,
    compute_discipline,
    discipline_tag,
    pctile_rank,
)


class TestPctileRank:
    def test_below_lowest_band(self):
        assert pctile_rank(15.0, _CHASE_PCTILES) == 5

    def test_mid_band(self):
        # chase 27.9 == P50 threshold
        assert pctile_rank(27.9, _CHASE_PCTILES) == 50

    def test_top_band(self):
        assert pctile_rank(40.0, _CHASE_PCTILES) == 90

    def test_zone_contact_band(self):
        assert pctile_rank(83.1, _ZCON_PCTILES) == 50

    def test_none_value(self):
        assert pctile_rank(None, _CHASE_PCTILES) is None


class TestComputeDiscipline:
    def _cur(self, **kw):
        base = {"chase": 28.0, "zone_contact": 83.0, "pa": 300}
        base.update(kw)
        return base

    def test_no_current_returns_none(self):
        assert compute_discipline(None, self._cur()) is None

    def test_thin_current_pa_returns_none(self):
        assert compute_discipline(self._cur(pa=CUR_PA_FLOOR - 1), self._cur()) is None

    def test_levels_without_prior(self):
        r = compute_discipline(self._cur(), None)
        assert r["chase"] == 28.0
        assert r["chase_pctile"] is not None
        assert r["chase_delta"] is None
        assert r["has_prior"] is False

    def test_thin_prior_gives_levels_no_delta(self):
        r = compute_discipline(self._cur(), self._cur(pa=PRIOR_PA_FLOOR - 1))
        assert r["has_prior"] is False
        assert r["chase_delta"] is None

    def test_significant_chase_improvement(self):
        # chase 24 now vs 30 prior → delta -6.0, |6|>=3.6 significant
        r = compute_discipline(self._cur(chase=24.0), self._cur(chase=30.0, pa=400))
        assert r["chase_delta"] == -6.0
        assert r["chase_delta_sig"] is True

    def test_insignificant_chase_move(self):
        r = compute_discipline(self._cur(chase=28.0), self._cur(chase=30.0, pa=400))
        assert r["chase_delta"] == -2.0  # |2| < 3.6
        assert r["chase_delta_sig"] is False

    def test_zone_contact_delta(self):
        r = compute_discipline(
            self._cur(zone_contact=88.0), self._cur(zone_contact=83.0, pa=400)
        )
        assert r["zone_contact_delta"] == 5.0
        assert r["zone_contact_delta_sig"] is True

    def test_missing_metric_does_not_crash(self):
        r = compute_discipline(
            {"chase": None, "zone_contact": 83.0, "pa": 300},
            {"chase": 30.0, "zone_contact": 80.0, "pa": 400},
        )
        assert r["chase_delta"] is None  # no current chase
        assert r["zone_contact_delta"] == 3.0


class TestDisciplineTag:
    def _cur(self, **kw):
        base = {"chase": 28.0, "zone_contact": 83.0, "pa": 300}
        base.update(kw)
        return base

    def test_none_result(self):
        assert discipline_tag(None) is None

    def test_chase_improvement_tag(self):
        r = compute_discipline(self._cur(chase=24.0), self._cur(chase=30.0, pa=400))
        assert discipline_tag(r) == "✅ 選球進化 (chase -6.0)"

    def test_chase_decay_tag(self):
        r = compute_discipline(self._cur(chase=34.0), self._cur(chase=28.0, pa=400))
        assert discipline_tag(r) == "⚠️ 選球崩壞 (chase +6.0)"

    def test_combined_chase_and_zone(self):
        r = compute_discipline(
            self._cur(chase=24.0, zone_contact=88.0),
            self._cur(chase=30.0, zone_contact=83.0, pa=400),
        )
        assert discipline_tag(r) == "✅ 選球進化 (chase -6.0, zone-contact +5.0)"

    def test_zone_only_when_chase_quiet(self):
        r = compute_discipline(
            self._cur(chase=28.0, zone_contact=88.0),
            self._cur(chase=30.0, zone_contact=83.0, pa=400),
        )
        # chase -2.0 not significant; zone +5.0 significant
        assert discipline_tag(r) == "✅ 擊球接觸升 (zone-contact +5.0)"

    def test_no_significant_move_no_tag(self):
        r = compute_discipline(self._cur(), self._cur(pa=400))
        assert discipline_tag(r) is None

    def test_no_prior_no_tag(self):
        r = compute_discipline(self._cur(chase=20.0), None)
        assert discipline_tag(r) is None
