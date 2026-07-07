"""Unit tests for issue 040 — star_rating mechanical 1-5★.

Covers:
    score — data-driven weight table over a named factor dict (adding a
        factor is a data change, not a signature change); standard-day
        4-factor sum and day-0 3-factor scaled variant capped at 4★.
    bucketers — raw → level for dual_year / playing_time / trigger.
    Calibration fixture (machine-checkable AC): the retrospective cases must
        bucket correctly — Vargas/Horwitz/O'Hearn ≥4★ (structure-led, real
        credentials), Sheets/Pederson ≤3★ (heat-led with a real gap). The
        discovery-channel structure/heat split is the load-bearing
        discriminator (docs/fa-scan-decision-retrospective-2026h1.md §4).
    format_stars — payload display string (injection itself is 039-gated).
"""

import pytest

from star_rating import (
    StarResult,
    bucket_dual_year,
    bucket_playing_time,
    bucket_trigger,
    format_stars,
    score,
)


# ── score: per-factor levels ──

def test_all_full_is_five_stars():
    r = score({"channel": "structure", "dual_year": "full",
               "playing_time": "high", "trigger": "full"})
    assert isinstance(r, StarResult)
    assert r.total == 4.0
    assert r.stars == 5


def test_all_zero_is_one_star():
    r = score({"channel": "heat", "dual_year": "none",
               "playing_time": "low", "trigger": "none"})
    assert r.total == 0.0
    assert r.stars == 1


def test_channel_levels():
    base = {"dual_year": "none", "playing_time": "low", "trigger": "none"}
    assert score({**base, "channel": "structure"}).breakdown["channel"] == 1.0
    assert score({**base, "channel": "market"}).breakdown["channel"] == 0.5
    assert score({**base, "channel": "news"}).breakdown["channel"] == 0.5
    assert score({**base, "channel": "unknown"}).breakdown["channel"] == 0.5
    assert score({**base, "channel": "heat"}).breakdown["channel"] == 0.0


def test_partial_credits_round_half_up():
    # structure(1) + partial(0.5) + mid(0.5) + partial(0.5) = 2.5 → 1+3 = 4
    r = score({"channel": "structure", "dual_year": "partial",
               "playing_time": "mid", "trigger": "partial"})
    assert r.total == 2.5
    assert r.stars == 4  # half-up rounding


def test_heat_capped_at_three_despite_strong_credentials():
    # heat(0)+full(1)+high(1)+partial(0.5)=2.5 → would be 4★, capped to 3★.
    r = score({"channel": "heat", "dual_year": "full",
               "playing_time": "high", "trigger": "partial"})
    assert r.total == 2.5
    assert r.stars == 3  # heat hard-cap: a 14d spike never reaches notify


def test_heat_cap_does_not_inflate_weak():
    r = score({"channel": "heat", "dual_year": "none",
               "playing_time": "low", "trigger": "none"})
    assert r.stars == 1  # cap is a ceiling, not a floor


def test_unknown_level_scores_zero():
    r = score({"channel": "bogus", "dual_year": "full",
               "playing_time": "high", "trigger": "full"})
    assert r.breakdown["channel"] == 0.0
    assert r.total == 3.0


def test_unknown_factor_name_ignored():
    r = score({"channel": "structure", "dual_year": "full",
               "playing_time": "high", "trigger": "full",
               "made_up_factor": "whatever"})
    assert "made_up_factor" not in r.breakdown
    assert r.total == 4.0


def test_missing_factor_treated_absent():
    # only channel present → total 1.0 → 2 stars
    r = score({"channel": "structure"})
    assert r.total == 1.0
    assert r.stars == 2


# ── day-0 variant: 3 factors, scaled, capped at 4★ ──

def test_day0_ignores_trigger():
    full = {"channel": "structure", "dual_year": "full",
            "playing_time": "high", "trigger": "full"}
    r = score(full, day0=True)
    # 3 factors maxed = 3.0 scaled to 4.0 → 1+4 = 5, capped to 4★
    assert r.stars == 4


def test_day0_caps_at_four():
    r = score({"channel": "structure", "dual_year": "full",
               "playing_time": "high"}, day0=True)
    assert r.stars == 4


def test_day0_mid_credentials():
    # structure(1)+partial(0.5)+mid(0.5)=2.0 scaled ×4/3 = 2.667 → 1+3 = 4
    r = score({"channel": "structure", "dual_year": "partial",
               "playing_time": "mid"}, day0=True)
    assert r.stars == 4


def test_day0_weak_is_low():
    r = score({"channel": "heat", "dual_year": "none",
               "playing_time": "low"}, day0=True)
    assert r.stars == 1


def test_day0_cap_at_threshold_not_just_max():
    # structure(1)+full(1)+mid(0.5)=2.5 → scaled ×4/3 = 3.333 → 1+3 = 4★;
    # uncapped this would still be 4 (cap is a no-op here) — but the next step
    # up (raw 3.0 → scaled 4.0 → would be 5) is where the cap bites:
    assert score({"channel": "structure", "dual_year": "full",
                  "playing_time": "mid"}, day0=True).stars == 4
    # raw 3.0 → 5 pre-cap → capped to 4 (the boundary that matters)
    assert score({"channel": "structure", "dual_year": "full",
                  "playing_time": "high"}, day0=True).stars == 4


def test_day0_heat_capped_at_three():
    # day-0 heat with otherwise-max credentials: 4★ day-0 cap, then 3★ heat cap
    r = score({"channel": "heat", "dual_year": "full",
               "playing_time": "high"}, day0=True)
    assert r.stars == 3


# ── bucketers: raw → level ──

def test_bucket_playing_time():
    assert bucket_playing_time(3.9) == "high"
    assert bucket_playing_time(3.5) == "high"
    assert bucket_playing_time(3.0) == "mid"
    assert bucket_playing_time(2.5) == "mid"
    assert bucket_playing_time(2.4) == "low"
    assert bucket_playing_time(None) == "low"


def test_bucket_playing_time_sp():
    from star_rating import bucket_playing_time_sp
    # anchors = 2025 SP IP/GS P80 (5.89) / P40 (5.35), the same population
    # positions as the batter 3.5 / 2.5 PA-TG thresholds
    assert bucket_playing_time_sp(6.1) == "high"
    assert bucket_playing_time_sp(5.89) == "high"
    assert bucket_playing_time_sp(5.88) == "mid"
    assert bucket_playing_time_sp(5.35) == "mid"
    assert bucket_playing_time_sp(5.34) == "low"
    assert bucket_playing_time_sp(None) == "low"
    # Rotation Gate: no start volume to credit however long the outings
    assert bucket_playing_time_sp(6.5, rotation_ok=False) == "low"


def test_bucket_dual_year():
    # ≥2 core metrics P70+ with adequate sample = full
    assert bucket_dual_year([72, 80, 65], sample_ok=True) == "full"
    assert bucket_dual_year([72, 60, 50], sample_ok=True) == "partial"
    assert bucket_dual_year([50, 40, 30], sample_ok=True) == "none"
    # dual-elite percentiles but thin prior sample → not full
    assert bucket_dual_year([90, 90, 90], sample_ok=False) == "partial"
    assert bucket_dual_year([], sample_ok=True) == "none"
    # exactly P70 counts as strong (>= boundary)
    assert bucket_dual_year([70, 70], sample_ok=True) == "full"
    assert bucket_dual_year([70, 69], sample_ok=True) == "partial"


def test_bucket_trigger():
    assert bucket_trigger(met=3, total=3) == "full"
    assert bucket_trigger(met=2, total=3) == "partial"
    assert bucket_trigger(met=0, total=3) == "none"
    assert bucket_trigger(met=0, total=0) == "none"


# ── Calibration fixture (machine-checkable AC) ──
# Factor levels encoded from the retrospective waiver-log data
# (docs/fa-scan-decision-retrospective-2026h1.md). The structure/heat channel
# split is what separates the winners from the losers.

# Factor levels are read off the retrospective data, NOT reverse-engineered to
# pass: Sheets is dual_year "full" (doc §3/§4: "prior P80" — a real prior
# credential); Pederson is playing_time "low" (doc §3: platoon weak-side,
# measured -28% weekly PA). They still land ≤3★ because the heat-channel cap —
# the doc's actual discriminator — carries the split, not hand-tuned gaps.
CALIBRATION = {
    # ≥4★ — structure-led with real dual-year + playing time + trigger
    "Vargas": (
        {"channel": "structure", "dual_year": "full",
         "playing_time": "high", "trigger": "full"}, 4, 5),
    "Horwitz": (
        {"channel": "structure", "dual_year": "full",
         "playing_time": "mid", "trigger": "full"}, 4, 5),
    "O'Hearn": (
        {"channel": "structure", "dual_year": "full",
         "playing_time": "high", "trigger": "partial"}, 4, 5),
    # ≤3★ — heat-led surfaced (14d spike); faithful credentials, capped anyway
    "Sheets": (
        {"channel": "heat", "dual_year": "full",
         "playing_time": "high", "trigger": "partial"}, 1, 3),
    "Pederson": (
        {"channel": "heat", "dual_year": "partial",
         "playing_time": "low", "trigger": "full"}, 1, 3),
}


@pytest.mark.parametrize("name", list(CALIBRATION))
def test_calibration_buckets(name):
    factors, lo, hi = CALIBRATION[name]
    stars = score(factors).stars
    assert lo <= stars <= hi, f"{name}: {stars}★ outside [{lo},{hi}]"


def test_calibration_winners_strictly_above_losers():
    def s(n):
        return score(CALIBRATION[n][0]).stars
    winners = min(s("Vargas"), s("Horwitz"), s("O'Hearn"))
    losers = max(s("Sheets"), s("Pederson"))
    assert winners >= 4 and losers <= 3 and winners > losers


def test_channel_alone_flips_the_verdict():
    # Identical credentials, ONLY channel differs → isolates the discriminator
    # (would catch a flipped/removed heat weight or cap).
    creds = {"dual_year": "full", "playing_time": "high", "trigger": "partial"}
    structured = score({**creds, "channel": "structure"}).stars
    heated = score({**creds, "channel": "heat"}).stars
    assert structured >= 4 and heated <= 3


# ── format_stars: payload display ──

def test_format_stars_shape():
    r = score({"channel": "structure", "dual_year": "full",
               "playing_time": "high", "trigger": "full"})
    s = format_stars(r)
    assert "★" in s
    assert s.count("★") == 5


def test_format_stars_shows_breakdown():
    r = score({"channel": "structure", "dual_year": "partial",
               "playing_time": "mid", "trigger": "partial"})
    s = format_stars(r)
    assert "路徑" in s or "channel" in s  # breakdown surfaced
