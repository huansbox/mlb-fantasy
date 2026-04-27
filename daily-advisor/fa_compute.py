"""fa_compute — Python compute layer for fa_scan.

Mechanical rules (Sum / urgency / ✅⚠️ tags / upgrade) extracted from Claude
prompts into deterministic, unit-testable Python. See
`docs/fa_scan-python-compute-design.md` §3 for architecture.

Single source of truth for rule definitions remains CLAUDE.md. This module
implements those rules 1:1.
"""

from __future__ import annotations

from typing import Literal

from daily_advisor import BATTER_PCTILES, PITCHER_PCTILES

PlayerType = Literal["batter", "sp"]

# Metric → prior_stats key mapping (SP prior uses _allowed suffix)
_PRIOR_KEY_MAP = {
    "batter": {
        "xwoba": "xwoba",
        "bb_pct": "bb_pct",
        "barrel_pct": "barrel_pct",
    },
    "sp": {
        "xera": "xera",
        "xwoba": "xwoba_allowed",
        "hh_pct": "hh_pct_allowed",
    },
}

# Human-readable breakdown labels (preserve prompt casing: "xwOBA", "BB%", ...)
_BREAKDOWN_LABELS = {
    "batter": {"xwoba": "xwOBA", "bb_pct": "BB%", "barrel_pct": "Barrel%"},
    "sp": {"xera": "xERA", "xwoba": "xwOBA", "hh_pct": "HH%"},
}

# Metric order for Sum (xwOBA / BB% / Barrel% for batter; xERA / xwOBA / HH% for SP)
_METRIC_ORDER = {
    "batter": ("xwoba", "bb_pct", "barrel_pct"),
    "sp": ("xera", "xwoba", "hh_pct"),
}


def _pctile_table(player_type: PlayerType):
    if player_type == "batter":
        return BATTER_PCTILES
    if player_type == "sp":
        return PITCHER_PCTILES
    raise ValueError(f"unknown player_type: {player_type}")


def metric_to_score(value, metric: str, player_type: PlayerType) -> int:
    """Convert metric value to 1-10 score per CLAUDE.md Sum 打分表.

    >P90=10, P80-90=9, P70-80=8, P60-70=7, P50-60=6, P40-50=5, P25-40=3, <P25=1.
    Auto-detects higher_better from percentile table direction.
    Returns 0 if value is None.
    """
    if value is None:
        return 0
    bp = _pctile_table(player_type).get(metric)
    if not bp:
        return 0
    higher_better = bp[-1][1] > bp[0][1]
    matched_pct = 0
    for pct, thresh in bp:
        if (higher_better and value >= thresh) or (not higher_better and value <= thresh):
            matched_pct = pct
    if matched_pct >= 90:
        return 10
    if matched_pct >= 80:
        return 9
    if matched_pct >= 70:
        return 8
    if matched_pct >= 60:
        return 7
    if matched_pct >= 50:
        return 6
    if matched_pct >= 40:
        return 5
    if matched_pct >= 25:
        return 3
    return 1


def compute_sum_score(metrics: dict, player_type: PlayerType) -> tuple[int, dict]:
    """3-metric Sum per CLAUDE.md Step 1 規則.

    Args:
        metrics: batter {"xwoba", "bb_pct", "barrel_pct"}
                 sp     {"xera",  "xwoba",  "hh_pct"}
        player_type: "batter" or "sp"

    Returns:
        (sum_score, breakdown) where breakdown is {"xwOBA": n, "BB%": n, ...}.
        sum_score range 3-30 (or 0-30 if values are None).
    """
    labels = _BREAKDOWN_LABELS[player_type]
    breakdown = {}
    total = 0
    for metric in _METRIC_ORDER[player_type]:
        score = metric_to_score(metrics.get(metric), metric, player_type)
        breakdown[labels[metric]] = score
        total += score
    return total, breakdown


def _confidence_label(bbe: int, player_type: PlayerType) -> str:
    """Confidence band per CLAUDE.md 樣本量加權.

    Batter: BBE <40 低 / 40-50 中 / >50 高.
    SP:     BBE <30 is excluded from rank; remaining 30-50 中 / >50 高.
    """
    if player_type == "batter":
        if bbe < 40:
            return "低"
        if bbe <= 50:
            return "中"
        return "高"
    # sp
    if bbe <= 50:
        return "中"
    return "高"


def _sp_bbe_excluded(bbe: int) -> bool:
    """SP: BBE <30 moved to low_confidence_excluded (per CLAUDE.md SP Step 1)."""
    return bbe < 30


def pick_weakest(
    players: list[dict],
    player_type: PlayerType,
    n: int = 4,
    cant_cut: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Pick weakest N players by Sum asc + low_confidence_excluded.

    Expects each player dict to have `savant_2026` pre-attached:
        batter: {xwoba, bb_pct, barrel_pct, bbe}
        sp:     {xera, xwoba, hh_pct, bbe}

    Filters applied in order:
        1. Exclude cant_cut by case-insensitive name.
        2. SP only: BBE <30 → low_confidence_excluded (not in weakest).
        3. Sort remaining by Sum asc, take first n.

    Returns:
        (weakest, excluded)
        weakest: [{name, mlb_id, score, breakdown, confidence, savant_2026, ...原 player 欄位}]
        excluded (SP only): [{name, bbe, note}]
    """
    cant_cut_lower = {c.lower() for c in (cant_cut or set())}

    weakest_pool = []
    excluded = []

    for p in players:
        if p.get("name", "").lower() in cant_cut_lower:
            continue

        savant = p.get("savant_2026") or {}
        bbe = int(savant.get("bbe") or 0)

        if player_type == "sp" and _sp_bbe_excluded(bbe):
            excluded.append(
                {
                    "name": p["name"],
                    "mlb_id": p.get("mlb_id"),
                    "bbe": bbe,
                    "note": "BBE 小樣本，驗證期暫不排序",
                }
            )
            continue

        score, breakdown = compute_sum_score(savant, player_type)
        confidence = _confidence_label(bbe, player_type)

        weakest_pool.append(
            {
                **p,
                "score": score,
                "breakdown": breakdown,
                "confidence": confidence,
                "bbe": bbe,
            }
        )

    weakest_pool.sort(key=lambda e: e["score"])
    weakest = weakest_pool[:n]
    return weakest, excluded


# ── Phase 5.3: urgency four-factor computation ──
# Prior IP <20 → too small a sample to count as prior data (per #2 bug fix).
# CLAUDE.md rule: "2025 Sum 雙年檢核（需 2025 IP ≥50）" for Slump hold gate,
# but the base Sum scoring also skips on <20 IP to avoid 5-IP noise
# (López 5 IP, 22 BBE → xera 10.73 was giving +2 结构性確認 erroneously).
_PRIOR_IP_MIN = 20
_PRIOR_IP_SLUMP_HOLD_MIN = 50

# Luck tag (xERA-ERA diff) needs enough BBE for xERA to be stable.
# BBE <40 → suppress luck tag to avoid mislabeling崩盤中 cases as 賣高運氣
# (e.g. Kelly 2026-04-24: xERA 13.4 / ERA 9.31 / BBE 27 → diff +4.09 was
# actually crash-in-progress, not a sell-high luck signal).
_LUCK_TAG_BBE_MIN = 40


def _factor_2026_sum(sum_2026: int) -> int:
    """Per CLAUDE.md urgency factor (1): 2026 Sum bucket.

    <9=+5, 9-11=+4, 12-14=+3, 15-17=+2, 18-21=+1, ≥22=+0.
    """
    if sum_2026 < 9:
        return 5
    if sum_2026 <= 11:
        return 4
    if sum_2026 <= 14:
        return 3
    if sum_2026 <= 17:
        return 2
    if sum_2026 <= 21:
        return 1
    return 0


def _factor_2025_sum(sum_2025: int, prior_ip: float | None, player_type: PlayerType) -> int:
    """Per CLAUDE.md urgency factor (2): 2025 Sum (with optional IP gate for SP).

    SP rules:
        Sum ≥24 + IP ≥50 → Slump hold (handled separately, this returns +0)
        Sum ≥24 + IP <50 → +0 (菁英但低樣本)
        Sum 22-23 → +0 (灰色帶)
        Sum 18-21 → +1
        Sum <18   → +2 (結構性確認)

    Batter rules: same except no IP gate (Slump hold handled separately).
    """
    if sum_2025 == 0:
        return 0  # no prior (or prior IP <20 for SP, already zeroed in caller)
    if sum_2025 >= 24:
        return 0  # Slump hold handled by caller; low-IP also +0
    if sum_2025 >= 22:
        return 0  # 灰色帶
    if sum_2025 >= 18:
        return 1
    return 2  # 結構性確認


def _factor_rolling(rolling: dict | None, season_xwoba_allowed: float | None,
                    player_type: PlayerType) -> int:
    """Per CLAUDE.md urgency factor (3): 21d Δ xwOBA (SP) / 14d Δ xwOBA (batter).

    SP direction (allowed): Δ ≤ -.050 = 🔥強回升 = -2; Δ ≥ +.050 = ❄️強劣化 = +2.
    Batter direction: Δ ≥ +.050 = 🔥強回升 = -2; Δ ≤ -.050 = ❄️強下滑 = +2.

    BBE gate: batter ≥25, SP ≥20 (per CLAUDE.md).
    """
    if not rolling:
        return 0
    bbe_gate = 25 if player_type == "batter" else 20
    if (rolling.get("bbe") or 0) < bbe_gate:
        return 0
    r_xwoba = rolling.get("xwoba")
    if r_xwoba is None or season_xwoba_allowed is None:
        return 0
    delta = r_xwoba - season_xwoba_allowed

    if player_type == "sp":
        # Allowed direction: lower = better, so Δ negative = improving (-urgency)
        if delta <= -0.050:
            return -2
        if delta <= -0.035:
            return -1
        if delta >= 0.050:
            return 2
        if delta >= 0.035:
            return 1
        return 0
    # batter: higher xwOBA = better → Δ positive = rising (-urgency)
    if delta >= 0.050:
        return -2
    if delta >= 0.035:
        return -1
    if delta <= -0.050:
        return 2
    if delta <= -0.035:
        return 1
    return 0


def _factor_sp_ip_per_tg(ip_per_tg: float | None) -> int:
    """SP factor (4): 2026 IP/Team_G — active 輪值越多越拖比率."""
    if ip_per_tg is None:
        return 0
    if ip_per_tg >= 1.0:
        return 2
    if ip_per_tg >= 0.5:
        return 1
    return 0


def _factor_batter_pa_per_tg(pa_per_tg: float | None) -> int:
    """Batter factor (4): 2026 PA/Team_G — 越主力越拖 stats."""
    if pa_per_tg is None:
        return 0
    if pa_per_tg >= 3.5:
        return 2
    if pa_per_tg >= 3.0:
        return 1
    return 0


def compute_urgency(
    weakest_n: list[dict],
    player_type: PlayerType,
) -> dict:
    """Compute urgency four-factor score for weakest-N players.

    Each weakest entry should include:
        score         — 2026 Sum (from pick_weakest)
        prior_stats   — 2025 prior dict (may be empty/None)
        rolling_21d   — SP 21d rolling {xwoba, bbe} (or None)
        rolling_14d   — batter 14d rolling (or None)
        savant_2026   — current-season Savant (for rolling Δ base xwoba)
        derived       — {ip_per_tg (SP) / pa_per_tg (batter)}

    Returns:
        {
            "weakest_ranked": [  # sorted by urgency desc
                {name, urgency, factors: {...}, prior_sum, prior_ip, notes: [...],
                 ...original weakest entry}
            ],
            "slump_hold": [{name, prior_sum, prior_ip}]  # excluded from rank
        }
    """
    season_xwoba_key = "xwoba" if player_type == "batter" else "xwoba"
    # For SP, Savant xwoba in 2026 data represents xwOBA allowed (same key).

    ranked = []
    slump_hold = []

    for w in weakest_n:
        name = w["name"]
        sum_2026 = w.get("score", 0)
        prior = w.get("prior_stats") or {}
        prior_ip = prior.get("ip") if player_type == "sp" else None

        # Prior Sum — with #2 bug fix: SP prior IP <20 ⇒ treat as no prior
        notes = []
        effective_prior = prior
        if player_type == "sp" and prior and prior_ip is not None and prior_ip < _PRIOR_IP_MIN:
            effective_prior = {}
            notes.append(
                f"2025 prior IP {prior_ip:.1f} <{_PRIOR_IP_MIN} 無效（樣本過小），視為無 prior"
            )

        sum_2025, prior_breakdown = compute_2025_sum(effective_prior, player_type)

        # Slump hold detection (BEFORE adding 2025 factor)
        is_slump_hold = False
        if sum_2025 >= 24:
            if player_type == "sp":
                if prior_ip is not None and prior_ip >= _PRIOR_IP_SLUMP_HOLD_MIN:
                    is_slump_hold = True
            else:
                is_slump_hold = True  # batter: no IP gate

        if is_slump_hold:
            slump_hold.append(
                {
                    "name": name,
                    "mlb_id": w.get("mlb_id"),
                    "prior_sum": sum_2025,
                    "prior_ip": prior_ip,
                    "prior_breakdown": prior_breakdown,
                    "sum_2026": sum_2026,
                    "note": "菁英底，slump 候選",
                }
            )
            continue

        # Four factors
        f_2026 = _factor_2026_sum(sum_2026)
        f_2025 = _factor_2025_sum(sum_2025, prior_ip, player_type)

        # Rolling Δ base: season xwOBA (allowed for SP; batting for batter)
        season_savant = w.get("savant_2026") or {}
        season_xwoba = season_savant.get(season_xwoba_key)

        if player_type == "sp":
            rolling = w.get("rolling_21d")
            f_rolling = _factor_rolling(rolling, season_xwoba, "sp")
            ip_per_tg = (w.get("derived") or {}).get("ip_per_tg")
            f_production = _factor_sp_ip_per_tg(ip_per_tg)
        else:
            rolling = w.get("rolling_14d")
            f_rolling = _factor_rolling(rolling, season_xwoba, "batter")
            pa_per_tg = (w.get("derived") or {}).get("pa_per_tg")
            f_production = _factor_batter_pa_per_tg(pa_per_tg)

        urgency = f_2026 + f_2025 + f_rolling + f_production

        entry = {
            **w,
            "urgency": urgency,
            "factors": {
                "sum_2026": f_2026,
                "sum_2025": f_2025,
                "rolling": f_rolling,
                "ip_per_tg" if player_type == "sp" else "pa_per_tg": f_production,
            },
            "prior_sum": sum_2025,
            "prior_ip": prior_ip,
            "prior_breakdown": prior_breakdown,
            "notes": notes,
        }
        ranked.append(entry)

    ranked.sort(key=lambda e: e["urgency"], reverse=True)

    return {
        "weakest_ranked": ranked,
        "slump_hold": slump_hold,
    }


# ── Phase 5.4: FA tags + upgrade decision ──
# Strong warnings that force "觀察" regardless of ✅ count:
#   - 短局 / 上場有限 (CLAUDE.md 明示 "強警示")
#   - 樣本小 (confidence blocker; CLAUDE.md 未標但 fixture 要求 — BBE <30 意義等同
#             pick_weakest 的排除門檻，不應單純視為一般警示)
_STRONG_WARN_TAGS = {"⚠️ 短局", "⚠️ 上場有限", "⚠️ 樣本小"}


def _compute_sp_add_tags(fa: dict) -> list[str]:
    tags = []
    prior = fa.get("prior_stats") or {}
    prior_ip = prior.get("ip")
    derived = fa.get("derived") or {}
    savant = fa.get("savant_2026") or {}
    rolling = fa.get("rolling_21d")

    # ✅ 雙年菁英 — 2025 Sum ≥24 且 IP ≥50
    # (Use effective prior — IP <20 zeroes out.)
    if prior_ip is not None and prior_ip >= _PRIOR_IP_MIN:
        prior_sum, _ = compute_2025_sum(prior, "sp")
        if prior_sum >= 24 and prior_ip >= _PRIOR_IP_SLUMP_HOLD_MIN:
            tags.append("✅ 雙年菁英")

    # ✅ 深投型 — IP/GS >5.7
    ip_per_gs = derived.get("ip_per_gs")
    if ip_per_gs is not None and ip_per_gs > 5.7:
        tags.append("✅ 深投型")

    # ✅ 球隊主力 — 2026 IP/Team_G ≥1.0
    ip_per_tg = derived.get("ip_per_tg")
    if ip_per_tg is not None and ip_per_tg >= 1.0:
        tags.append("✅ 球隊主力")

    # ✅ 近況確認 — 21d Δ xwOBA ≤ -0.035
    if rolling and (rolling.get("bbe") or 0) >= 20:
        r_x = rolling.get("xwoba")
        s_x = savant.get("xwoba")
        if r_x is not None and s_x is not None:
            if (r_x - s_x) <= -0.035:
                tags.append("✅ 近況確認")

    # ✅ 撿便宜運氣 — xERA-ERA ≤ -0.81 (BBE ≥ 40，避免崩盤中誤判為運氣加持)
    era_diff = derived.get("era_diff")
    bbe_2026 = int(savant.get("bbe") or 0)
    if era_diff is not None and era_diff <= -0.81 and bbe_2026 >= _LUCK_TAG_BBE_MIN:
        tags.append("✅ 撿便宜運氣")

    return tags


def _compute_sp_warn_tags(fa: dict) -> list[str]:
    tags = []
    prior = fa.get("prior_stats") or {}
    prior_ip = prior.get("ip")
    derived = fa.get("derived") or {}
    savant = fa.get("savant_2026") or {}
    rolling = fa.get("rolling_21d")
    bbe = int(savant.get("bbe") or 0)

    ip_per_gs = derived.get("ip_per_gs")
    ip_per_tg = derived.get("ip_per_tg")
    era_diff = derived.get("era_diff")

    # ⚠️ 短局 (強) — IP/GS <5.0
    if ip_per_gs is not None and ip_per_gs < 5.0:
        tags.append("⚠️ 短局")

    # ⚠️ 上場有限 (強) — IP/TG <0.5
    if ip_per_tg is not None and ip_per_tg < 0.5:
        tags.append("⚠️ 上場有限")

    # ⚠️ 樣本小 — BBE <30 或 IP <20 (prior IP 缺值不觸發此警示)
    prior_low_ip = prior_ip is not None and prior_ip < _PRIOR_IP_MIN
    if bbe < 30 or prior_low_ip:
        tags.append("⚠️ 樣本小")

    # ⚠️ Breakout 待驗 — 2025 Sum <18 或無 prior
    if not prior or (prior_ip is not None and prior_ip < _PRIOR_IP_MIN):
        tags.append("⚠️ Breakout 待驗")
    else:
        prior_sum, _ = compute_2025_sum(prior, "sp")
        if prior_sum < 18:
            tags.append("⚠️ Breakout 待驗")

    # ⚠️ 賣高運氣 — xERA-ERA ≥ +0.81 (BBE ≥ 40，避免崩盤中誤判為運氣加持)
    if era_diff is not None and era_diff >= 0.81 and bbe >= _LUCK_TAG_BBE_MIN:
        tags.append("⚠️ 賣高運氣")

    # ⚠️ 近況下滑 — 21d Δ xwOBA ≥ +0.035
    if rolling and (rolling.get("bbe") or 0) >= 20:
        r_x = rolling.get("xwoba")
        s_x = savant.get("xwoba")
        if r_x is not None and s_x is not None:
            if (r_x - s_x) >= 0.035:
                tags.append("⚠️ 近況下滑")

    return tags


def _compute_batter_add_tags(fa: dict) -> list[str]:
    tags = []
    prior = fa.get("prior_stats") or {}
    derived = fa.get("derived") or {}
    savant = fa.get("savant_2026") or {}
    rolling = fa.get("rolling_14d")

    # ✅ 雙年菁英 — 2025 Sum ≥24 (no IP gate for batter)
    if prior:
        prior_sum, _ = compute_2025_sum(prior, "batter")
        if prior_sum >= 24:
            tags.append("✅ 雙年菁英")

    # ✅ 球隊主力 — 2026 PA/Team_G ≥3.5
    pa_per_tg = derived.get("pa_per_tg")
    if pa_per_tg is None:
        pa_per_tg = prior.get("pa_per_team_g")  # fallback
    if pa_per_tg is not None and pa_per_tg >= 3.5:
        tags.append("✅ 球隊主力")

    # ✅ 近況確認 — 14d xwOBA Δ ≥ +0.035 (batter direction: rising)
    if rolling and (rolling.get("bbe") or 0) >= 25:
        r_x = rolling.get("xwoba")
        s_x = savant.get("xwoba")
        if r_x is not None and s_x is not None:
            if (r_x - s_x) >= 0.035:
                tags.append("✅ 近況確認")

    return tags


def _compute_batter_warn_tags(fa: dict) -> list[str]:
    tags = []
    prior = fa.get("prior_stats") or {}
    derived = fa.get("derived") or {}
    savant = fa.get("savant_2026") or {}
    rolling = fa.get("rolling_14d")
    bbe = int(savant.get("bbe") or 0)

    # ⚠️ 上場有限 (強) — PA/Team_G <2.5
    pa_per_tg = derived.get("pa_per_tg")
    if pa_per_tg is None:
        pa_per_tg = prior.get("pa_per_team_g")
    if pa_per_tg is not None and pa_per_tg < 2.5:
        tags.append("⚠️ 上場有限")

    # ⚠️ 樣本小 — BBE <30
    if bbe < 30:
        tags.append("⚠️ 樣本小")

    # ⚠️ Breakout 待驗 — 2025 Sum <18 或無 prior
    if not prior:
        tags.append("⚠️ Breakout 待驗")
    else:
        prior_sum, _ = compute_2025_sum(prior, "batter")
        if prior_sum < 18:
            tags.append("⚠️ Breakout 待驗")

    # ⚠️ 近況下滑 — 14d Δ ≤ -0.035
    if rolling and (rolling.get("bbe") or 0) >= 25:
        r_x = rolling.get("xwoba")
        s_x = savant.get("xwoba")
        if r_x is not None and s_x is not None:
            if (r_x - s_x) <= -0.035:
                tags.append("⚠️ 近況下滑")

    return tags


def _decision_from_tags(add_tags: list[str], warn_tags: list[str]) -> str:
    """Upgrade decision per CLAUDE.md + fixture behavior.

    立即取代 — ≥2 ✅ AND 0 ⚠️
    取代    — ≥1 ✅ AND no strong ⚠️
    觀察    — has strong ⚠️, or 0 ✅
    """
    has_strong_warn = any(w in _STRONG_WARN_TAGS for w in warn_tags)
    if has_strong_warn:
        return "觀察"
    if not add_tags:
        return "觀察"
    if len(add_tags) >= 2 and not warn_tags:
        return "立即取代"
    return "取代"


def compute_fa_tags(fa_player: dict, anchor_player: dict, player_type: PlayerType) -> dict:
    """Compute Sum diff + ✅⚠️ tags + upgrade decision for one FA candidate.

    Args:
        fa_player: FA candidate with {name, score, breakdown, savant_2026,
                   prior_stats, rolling_21d/14d, derived}
        anchor_player: weakest player to compare (with {name, score, breakdown})
        player_type: "batter" or "sp"

    Returns:
        {
            sum_diff: int,
            breakdown_diff: dict,
            win_gate_passed: bool,
            add_tags: list[str],
            warn_tags: list[str],
            decision: "立即取代" | "取代" | "觀察" | "pass",
            anchor_name: str,
        }
    """
    sum_diff = fa_player["score"] - anchor_player["score"]
    anchor_bd = anchor_player.get("breakdown") or {}
    fa_bd = fa_player.get("breakdown") or {}
    breakdown_diff = {k: fa_bd.get(k, 0) - anchor_bd.get(k, 0) for k in fa_bd}

    # Win gate: Sum diff ≥3 且 at least 2 metrics ≥0
    positive_count = sum(1 for d in breakdown_diff.values() if d >= 0)
    win_gate_passed = sum_diff >= 3 and positive_count >= 2

    if not win_gate_passed:
        return {
            "sum_diff": sum_diff,
            "breakdown_diff": breakdown_diff,
            "win_gate_passed": False,
            "add_tags": [],
            "warn_tags": [],
            "decision": "pass",
            "anchor_name": anchor_player["name"],
        }

    if player_type == "sp":
        add_tags = _compute_sp_add_tags(fa_player)
        warn_tags = _compute_sp_warn_tags(fa_player)
    else:
        add_tags = _compute_batter_add_tags(fa_player)
        warn_tags = _compute_batter_warn_tags(fa_player)

    decision = _decision_from_tags(add_tags, warn_tags)

    return {
        "sum_diff": sum_diff,
        "breakdown_diff": breakdown_diff,
        "win_gate_passed": True,
        "add_tags": add_tags,
        "warn_tags": warn_tags,
        "decision": decision,
        "anchor_name": anchor_player["name"],
    }


def compute_2025_sum(prior_stats: dict | None, player_type: PlayerType) -> tuple[int, dict]:
    """Same as compute_sum_score but tolerates two prior schemas.

    Accepts:
      - Config schema (roster_config prior_stats): SP uses ``xwoba_allowed`` /
        ``hh_pct_allowed`` keys.
      - Raw Savant schema (from Savant CSV extraction): SP uses plain ``xwoba``
        / ``hh_pct`` keys (same field names as batter, disambiguated by role).

    Args:
        prior_stats: prior dict in either schema, or None for no prior.

    Returns:
        (sum_score, breakdown). Returns (0, zero-filled breakdown) if prior is
        empty/None — caller handles "no prior" semantics.
    """
    if not prior_stats:
        labels = _BREAKDOWN_LABELS[player_type]
        return 0, {label: 0 for label in labels.values()}

    if player_type == "sp":
        metrics = {
            "xera": prior_stats.get("xera"),
            "xwoba": prior_stats.get("xwoba_allowed") or prior_stats.get("xwoba"),
            "hh_pct": prior_stats.get("hh_pct_allowed") or prior_stats.get("hh_pct"),
        }
    else:
        key_map = _PRIOR_KEY_MAP["batter"]
        metrics = {metric: prior_stats.get(prior_key) for metric, prior_key in key_map.items()}
    return compute_sum_score(metrics, player_type)


# ═════════════════════════════════════════════════════════════════════════
# v4 SP framework (2026-04-24 defined in docs/sp-framework-v4-balanced.md)
# Parallel to v2 above — v2 stays live for batter + existing cron safety.
# v4 applies to SP only. Batters still use v2 (no user request to change).
# ═════════════════════════════════════════════════════════════════════════

# 2025 MLB SP percentile bands, computed by calc_v4_percentiles.py (n=178/115).
# Format: [(pctile, threshold)] sorted ascending so higher-index = elite direction.
# For "reverse" indicators (lower = better), thresholds listed low-to-high too
# but semantically P90 = lowest = elite; use v4_metric_to_score with reverse=True.
PITCHER_V4_PCTILES = {
    "ip_gs": [(25, 5.21), (40, 5.35), (45, 5.41), (50, 5.46),
              (55, 5.55), (60, 5.61), (70, 5.73), (80, 5.89), (90, 6.11)],
    "whiff_pct": [(25, 21.3), (40, 23.1), (45, 23.5), (50, 24.0),
                  (55, 24.6), (60, 25.1), (70, 26.5), (80, 27.9), (90, 30.0)],
    # reverse: threshold at P25 is the "worst" value; P90 the "best" (lowest)
    # Here we list the actual values at each elite-percentile label.
    "bb9": [(25, 3.47), (40, 3.17), (45, 3.06), (50, 2.95),
            (55, 2.83), (60, 2.73), (70, 2.38), (80, 2.18), (90, 1.96)],
    "gb_pct": [(25, 38.3), (40, 40.5), (45, 41.4), (50, 43.2),
               (55, 44.1), (60, 44.7), (70, 46.7), (80, 51.4), (90, 54.6)],
    "xwobacon": [(25, 0.386), (40, 0.375), (45, 0.374), (50, 0.370),
                 (55, 0.367), (60, 0.364), (70, 0.356), (80, 0.350), (90, 0.341)],
}

# Which v4 indicators are reverse-direction (lower raw value = elite).
_V4_REVERSE_METRICS = {"bb9", "xwobacon"}

# v4 SP Sum metric order (score 0-10 each, Sum 0-50)
_V4_SP_METRICS = ("ip_gs", "whiff_pct", "bb9", "gb_pct", "xwobacon")

_V4_SP_LABELS = {
    "ip_gs": "IP/GS",
    "whiff_pct": "Whiff%",
    "bb9": "BB/9",
    "gb_pct": "GB%",
    "xwobacon": "xwOBACON",
}


def v4_metric_to_score(value, metric: str) -> int:
    """Convert value → 0-10 score using 2025 v4 percentile bands.

    Returns 0 for None. P90+=10, P80=9, P70=8, P60=7, P50=6, P40=5, P25=3, <P25=1.
    Handles reverse metrics (bb9, xwobacon) by swapping comparison.
    """
    if value is None:
        return 0
    bp = PITCHER_V4_PCTILES.get(metric)
    if not bp:
        return 0
    reverse = metric in _V4_REVERSE_METRICS
    # bp is listed in elite direction: for forward, ascending thresholds;
    # for reverse, we still iterate but compare lower-is-better.
    matched = 0
    for pct, thresh in bp:
        if reverse:
            # For reverse metrics: value <= threshold means AT LEAST that elite
            # percentile. bp ordered by elite-pct ascending, but threshold is
            # in descending real-value order (P25=3.47, P90=1.96 for BB/9).
            if value <= thresh:
                matched = pct
        else:
            if value >= thresh:
                matched = pct
    if matched >= 90:
        return 10
    if matched >= 80:
        return 9
    if matched >= 70:
        return 8
    if matched >= 60:
        return 7
    if matched >= 50:
        return 6
    if matched >= 40:
        return 5
    if matched >= 25:
        return 3
    return 1


def compute_sum_score_v4_sp(data: dict) -> tuple[int, dict]:
    """v4 SP Sum: 5 indicators × 0-10, max 50.

    Args:
        data: {ip_gs, whiff_pct, bb9, gb_pct, xwobacon}

    Returns:
        (sum_score, breakdown) where breakdown is {"IP/GS": n, "Whiff%": n, ...}
    """
    breakdown = {}
    total = 0
    for metric in _V4_SP_METRICS:
        s = v4_metric_to_score(data.get(metric), metric)
        breakdown[_V4_SP_LABELS[metric]] = s
        total += s
    return total, breakdown


def rotation_gate_v4(g: int, gs: int) -> tuple[str, str]:
    """Pre-filter SP by role, from GS/G ratio + absolute GS.

    🟢 Active   — GS/G ≥ 0.6 AND GS ≥ 3  (full rotation member)
    ⚠️ Swingman — 0.3 ≤ GS/G < 0.6 OR GS ∈ {1,2}  (partial / new-up)
    🚫 Excluded — GS/G < 0.3 OR GS = 0  (pure RP / long relief)

    Returns (icon, descriptor) — icon for display, descriptor for logic.
    """
    if g == 0 or gs == 0:
        return ("🚫", "pure-RP/bench")
    ratio = gs / g
    if ratio < 0.3:
        return ("🚫", "pure-RP/long-relief")
    if ratio < 0.6 or gs < 3:
        return ("⚠️", "swingman/new-up")
    return ("🟢", "rotation-SP")


def luck_tag_v4(
    xera: float | None,
    era: float | None,
    bbe: int | None = None,
) -> str | None:
    """xERA − ERA ≤ -0.81 → ✅ 撿便宜運氣; ≥ +0.81 → ⚠️ 賣高運氣; else None.

    v2 logic already uses era_diff in derived; this is the explicit tag form.

    bbe: optional BBE for small-sample suppression. When given and below
    ``_LUCK_TAG_BBE_MIN``, returns None (xERA unstable, diff is noise not luck).
    """
    if xera is None or era is None:
        return None
    if bbe is not None and bbe < _LUCK_TAG_BBE_MIN:
        return None
    diff = xera - era
    if diff <= -0.81:
        return "✅ 撿便宜運氣"
    if diff >= 0.81:
        return "⚠️ 賣高運氣"
    return None


def v4_add_tags_sp(fa: dict) -> list[str]:
    """v4 ✅ tags for SP FA candidate.

    Expects fa dict with:
      savant_v4: {ip_gs, whiff_pct, bb9, gb_pct, xwobacon, xera, era, bbe}
      prior_stats: 2025 data for 雙年菁英 check
      rolling_21d: optional {xwobacon, bbe}
    """
    tags = []
    sv = fa.get("savant_v4") or {}
    prior = fa.get("prior_stats") or {}
    rolling = fa.get("rolling_21d") or {}

    # ✅ 雙年菁英 — 2025 v4 Sum ≥ 40 AND 2025 IP ≥ 50
    prior_ip = prior.get("ip")
    if prior_ip and prior_ip >= 50:
        prior_v4_data = {
            "ip_gs": prior.get("ip_gs"),
            "whiff_pct": prior.get("whiff_pct"),
            "bb9": prior.get("bb9"),
            "gb_pct": prior.get("gb_pct"),
            "xwobacon": prior.get("xwobacon"),
        }
        prior_sum, _ = compute_sum_score_v4_sp(prior_v4_data)
        if prior_sum >= 40:
            tags.append("✅ 雙年菁英")

    # ✅ 深投型 — IP/GS > 5.7
    if sv.get("ip_gs") and sv["ip_gs"] > 5.7:
        tags.append("✅ 深投型")

    # ✅ GB 重型 — GB% > 50
    if sv.get("gb_pct") and sv["gb_pct"] > 50.0:
        tags.append("✅ GB 重型")

    # ✅ K 壓制 — Whiff% > P70 (26.5)
    if sv.get("whiff_pct") and sv["whiff_pct"] > 26.5:
        tags.append("✅ K 壓制")

    # ✅ 撿便宜運氣 — xERA - ERA ≤ -0.81 (BBE ≥ 40，避免崩盤中誤判為運氣加持)
    luck = luck_tag_v4(sv.get("xera"), sv.get("era"), sv.get("bbe"))
    if luck and luck.startswith("✅"):
        tags.append(luck)

    # ✅ 近況確認 — 21d Δ xwOBACON ≤ -0.035 (improving)
    if rolling.get("bbe", 0) >= 20:
        r_x = rolling.get("xwobacon")
        s_x = sv.get("xwobacon")
        if r_x is not None and s_x is not None and (r_x - s_x) <= -0.035:
            tags.append("✅ 近況確認")

    return tags


def v4_warn_tags_sp(fa: dict) -> list[str]:
    """v4 ⚠️ tags for SP FA candidate."""
    tags = []
    sv = fa.get("savant_v4") or {}
    prior = fa.get("prior_stats") or {}
    rolling = fa.get("rolling_21d") or {}
    gate = fa.get("rotation_gate")

    bbe = sv.get("bbe") or 0
    ip_2026 = sv.get("ip") or 0
    prior_ip = prior.get("ip")

    # ⚠️ 樣本小 — BBE < 30 OR IP < 20 (strong warning)
    if bbe < 30 or ip_2026 < 20:
        tags.append("⚠️ 樣本小")

    # ⚠️ 短局 — IP/GS < 5.0
    if sv.get("ip_gs") and sv["ip_gs"] < 5.0 and sv["ip_gs"] > 0:
        tags.append("⚠️ 短局")

    # ⚠️ Swingman 角色 — Rotation gate 黃色
    if gate == "⚠️":
        tags.append("⚠️ Swingman 角色")

    # ⚠️ xwOBACON 極端 — <P25 (.386)
    if sv.get("xwobacon") and sv["xwobacon"] >= 0.386:
        tags.append("⚠️ xwOBACON 極端")

    # ⚠️ K 壓制不足 — Whiff% < P40 (23.1)
    if sv.get("whiff_pct") and sv["whiff_pct"] < 23.1:
        tags.append("⚠️ K 壓制不足")

    # ⚠️ Command 警示 — BB/9 > 3.5
    if sv.get("bb9") and sv["bb9"] > 3.5:
        tags.append("⚠️ Command 警示")

    # ⚠️ 賣高運氣 — xERA - ERA ≥ +0.81 (BBE ≥ 40，避免崩盤中誤判為運氣加持)
    luck = luck_tag_v4(sv.get("xera"), sv.get("era"), sv.get("bbe"))
    if luck and luck.startswith("⚠️"):
        tags.append(luck)

    # ⚠️ 近況下滑 — 21d Δ xwOBACON ≥ +0.035 (getting worse)
    if rolling.get("bbe", 0) >= 20:
        r_x = rolling.get("xwobacon")
        s_x = sv.get("xwobacon")
        if r_x is not None and s_x is not None and (r_x - s_x) >= 0.035:
            tags.append("⚠️ 近況下滑")

    # ⚠️ Breakout 待驗 — 2025 Sum < 25 或無 prior
    if not prior or not prior.get("ip"):
        tags.append("⚠️ Breakout 待驗")
    else:
        prior_v4_data = {
            "ip_gs": prior.get("ip_gs"),
            "whiff_pct": prior.get("whiff_pct"),
            "bb9": prior.get("bb9"),
            "gb_pct": prior.get("gb_pct"),
            "xwobacon": prior.get("xwobacon"),
        }
        prior_sum, _ = compute_sum_score_v4_sp(prior_v4_data)
        if prior_sum < 25:
            tags.append("⚠️ Breakout 待驗")

    return tags


_V4_STRONG_WARN_TAGS = {"⚠️ 樣本小", "⚠️ 短局", "⚠️ Swingman 角色"}


def v4_decision_sp(sum_diff: int, breakdown_diff: dict,
                   add_tags: list[str], warn_tags: list[str]) -> str:
    """v4 upgrade decision.

    Win gate: Sum diff ≥ 5 AND ≥ 3 positive (of 5).
    Then:
      ≥ 2 ✅ AND no strong warn → 立即取代
      ≥ 1 ✅ AND no strong warn → 取代
      else → 觀察

    NOTE: this Python decision function is used by fa_scan_v4.py CLI tool
    only. The Phase 6 production path uses compute_fa_tags_v4_sp() which
    intentionally omits the decision field — Claude decides in the
    multi-agent decision layer per docs/fa_scan-claude-decision-layer-design.md.
    """
    positive_count = sum(1 for d in breakdown_diff.values() if d >= 0)
    if sum_diff < 5 or positive_count < 3:
        return "pass"

    has_strong = any(w in _V4_STRONG_WARN_TAGS for w in warn_tags)
    if has_strong:
        return "觀察"
    if not add_tags:
        return "觀察"
    if len(add_tags) >= 2 and not any(w for w in warn_tags):
        return "立即取代"
    return "取代"


def compute_fa_tags_v4_sp(fa_player: dict, anchor_player: dict) -> dict:
    """v4 SP signals for Phase 6 multi-agent decision layer (no Python decision).

    Mirrors compute_fa_tags() shape but intentionally omits the "decision"
    field. The Phase 6 design (docs/fa_scan-claude-decision-layer-design.md)
    moves decision authority from Python to Claude with multi-agent review;
    Python's role here is to compute mechanical signals (sum_diff, breakdown,
    tags, win_gate) and let Claude integrate them with non-mechanical context
    (roster needs, %owned trends, role changes) for the final call.

    Args:
        fa_player: FA candidate with v4 fields {name, score, breakdown,
                   savant_2026, prior_stats, rolling_21d, derived}
        anchor_player: weakest team SP to compare against (must have
                       {name, score, breakdown})

    Returns:
        {
            sum_diff: int,                 # fa.score - anchor.score
            breakdown_diff: dict,          # per-slot diff (5 v4 slots)
            win_gate_passed: bool,         # v4 gate: sum_diff ≥ 5 AND ≥ 3 positive
            add_tags: list[str],           # v4 ✅ tags from v4_add_tags_sp
            warn_tags: list[str],          # v4 ⚠️ tags from v4_warn_tags_sp
            anchor_name: str,
        }

    Note: when win_gate_passed is False, add_tags and warn_tags are
    returned empty (gate fail = no point computing tags). Claude is told
    via prompt that gate-fail FAs are pre-filtered as "not worth taking".
    """
    sum_diff = fa_player["score"] - anchor_player["score"]
    anchor_bd = anchor_player.get("breakdown") or {}
    fa_bd = fa_player.get("breakdown") or {}
    breakdown_diff = {k: fa_bd.get(k, 0) - anchor_bd.get(k, 0) for k in fa_bd}

    positive_count = sum(1 for d in breakdown_diff.values() if d >= 0)
    win_gate_passed = sum_diff >= 5 and positive_count >= 3

    if not win_gate_passed:
        return {
            "sum_diff": sum_diff,
            "breakdown_diff": breakdown_diff,
            "win_gate_passed": False,
            "add_tags": [],
            "warn_tags": [],
            "anchor_name": anchor_player["name"],
        }

    return {
        "sum_diff": sum_diff,
        "breakdown_diff": breakdown_diff,
        "win_gate_passed": True,
        "add_tags": v4_add_tags_sp(fa_player),
        "warn_tags": v4_warn_tags_sp(fa_player),
        "anchor_name": anchor_player["name"],
    }


# ── Phase 6 / v4 cutover Stage D: picker + urgency for SP v4 ──
# v4 SP framework moves from v2 (3 indicators × 0-30 Sum) to v4 (5 indicators
# × 0-50 Sum). The v2 pick_weakest / compute_urgency functions assume v2
# Sum thresholds and v2 BBE rules; v4 needs its own picker + urgency that
# 1) sorts by v4 Sum (not v2 Sum)
# 2) keeps the same BBE<30 low_confidence_excluded gate (Savant signal stability)
# 3) uses v4 Sum bucket thresholds (0-50 not 0-30) for urgency factor 1
# 4) uses v4 prior Sum thresholds for urgency factor 2 (slump-hold = ≥40+IP≥50)
# 5) returns 0 for urgency factor 3 (21d Δ xwOBACON — Python doesn't score, see
#    docs/sp-framework-v4-balanced.md decision 1/4 & CLAUDE.md TODO)
# 6) replaces v2 IP/Team_G factor with luck-regression (xera-era ± 0.81, BBE≥40)
#    per docs/sp-framework-v4-balanced.md decision 4 (Lopez triview teaching)


def _factor_2026_sum_v4(sum_2026: int) -> int:
    """v4 SP urgency factor (1): 2026 v4 Sum bucket (0-50 range).

    < 15 = +5, 15-22 = +4, 23-30 = +3, 31-38 = +2, 39-44 = +1, ≥ 45 = +0.
    Per docs/sp-framework-v4-balanced.md §「Step 2 — Urgency 排序」table.
    """
    if sum_2026 < 15:
        return 5
    if sum_2026 <= 22:
        return 4
    if sum_2026 <= 30:
        return 3
    if sum_2026 <= 38:
        return 2
    if sum_2026 <= 44:
        return 1
    return 0


def _factor_2025_sum_v4(sum_2025: int) -> int:
    """v4 SP urgency factor (2): 2025 v4 prior Sum bucket.

    Slump hold (≥40 + IP≥50) is detected separately by caller and excluded
    from urgency ranking. This function only handles non-slump-hold cases:

    ≥ 40 (low IP, kept for ranking) = +0  (菁英底但低樣本)
    35-39 = +0  (灰色帶)
    28-34 = +1
    < 28  = +2  (結構性確認)
    """
    if sum_2025 == 0:
        return 0  # no prior (or prior IP <20, zeroed by caller)
    if sum_2025 >= 40:
        return 0  # slump-hold gated by caller; low-IP also +0
    if sum_2025 >= 35:
        return 0
    if sum_2025 >= 28:
        return 1
    return 2


def _factor_luck_regression_v4(xera: float | None, era: float | None,
                               bbe: int | None) -> int:
    """v4 SP urgency factor (4): luck regression via xERA - ERA diff.

    Replaces v2's IP/Team_G factor (Lopez 2026-04-22 triview teaching:
    xERA-ERA -1.11 = ERA will regress, lowering drop urgency).

    Threshold: ±0.81 (P70 absolute diff), gated by BBE ≥ _LUCK_TAG_BBE_MIN
    (40, complementary to luck_tag_v4 — same gate, different output form).

    diff ≤ -0.81 → -2 (ERA will rise back to xERA → less urgent to drop)
    diff ≥ +0.81 → +2 (ERA will drop, holder will look bad → more urgent)
    BBE < 40 or no diff → 0
    """
    if xera is None or era is None or bbe is None:
        return 0
    if bbe < _LUCK_TAG_BBE_MIN:
        return 0
    diff = xera - era
    if diff <= -0.81:
        return -2
    if diff >= 0.81:
        return 2
    return 0


def pick_weakest_v4_sp(
    players: list[dict],
    n: int = 4,
    cant_cut: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Pick weakest N SPs by v4 Sum asc + low_confidence_excluded.

    v4 differences from pick_weakest:
    - Sum scoring uses compute_sum_score_v4_sp (5 indicators × 0-50)
    - Reads savant_v4 dict (ip_gs/whiff_pct/bb9/gb_pct/xwobacon) instead of
      savant_2026 (xera/xwoba/hh_pct/barrel_pct)
    - Same BBE<30 gate as v2 (signal stability not framework-specific)
    - SP-only (no batter line)

    Args:
        players: list of SP dicts, each with savant_v4 + savant_2026 (BBE)
        n: number of weakest to pick (default 4)
        cant_cut: set of names to exclude (case-insensitive)

    Returns:
        (weakest, excluded) — same shape as v2 pick_weakest but with v4 Sum
    """
    cant_cut_lower = {c.lower() for c in (cant_cut or set())}

    pool = []
    excluded = []

    for p in players:
        if p.get("name", "").lower() in cant_cut_lower:
            continue

        # BBE gate uses savant_2026 (where bbe lives) — same as v2
        savant_2026 = p.get("savant_2026") or {}
        bbe = int(savant_2026.get("bbe") or 0)

        if _sp_bbe_excluded(bbe):
            excluded.append({
                "name": p["name"],
                "mlb_id": p.get("mlb_id"),
                "bbe": bbe,
                "note": "BBE 小樣本，驗證期暫不排序",
            })
            continue

        # v4 Sum from savant_v4 (Stage A backfilled this for prior_stats; for
        # 2026 current-season the caller is expected to attach savant_v4 too)
        savant_v4 = p.get("savant_v4") or {}
        score, breakdown = compute_sum_score_v4_sp(savant_v4)
        confidence = _confidence_label(bbe, "sp")

        pool.append({
            **p,
            "score": score,
            "breakdown": breakdown,
            "confidence": confidence,
            "bbe": bbe,
        })

    pool.sort(key=lambda e: e["score"])
    return pool[:n], excluded


def compute_urgency_v4_sp(weakest_n: list[dict]) -> dict:
    """v4 SP urgency four-factor scoring for weakest-N SPs.

    Factor weights per docs/sp-framework-v4-balanced.md decisions 1-4 (2026-04-25):
        1. 2026 v4 Sum bucket (_factor_2026_sum_v4)
        2. 2025 prior v4 Sum bucket (_factor_2025_sum_v4) + slump-hold gate
        3. 21d Δ xwOBACON: Python returns 0 (Claude reads raw delta from prompt;
           thresholds will be calibrated 1-2 months post-cutover, see CLAUDE.md TODO)
        4. Luck regression (_factor_luck_regression_v4) — replaces v2 IP/TG factor

    Slump-hold detection: 2025 v4 Sum ≥ 40 AND prior IP ≥ 50 → moved to
    `slump_hold` list, NOT in `weakest_ranked` (won't be selected as anchor,
    per design decision 4/4 in v4 doc).

    Tied urgency: Python does NOT pick a winner. The Phase 6 multi-agent
    decision layer reads the tied list and picks via Claude judgment
    (per design decision 3/4 in v4 doc).

    Each weakest entry should include:
        score          — 2026 v4 Sum (from pick_weakest_v4_sp)
        breakdown      — v4 5-slot breakdown (from pick_weakest_v4_sp)
        prior_stats    — 2025 prior dict with v4 metrics (ip_gs/whiff/bb9/gb/xwobacon)
                         — backfilled by Stage A backfill_prior_stats_v4
        savant_v4      — current-season v4 metrics (xera/era/bbe for luck factor)
        rolling_21d    — 21d {xwobacon, bbe} or None (Python doesn't score it,
                         but caller passes through to Claude prompt)

    Returns:
        {
            "weakest_ranked": [{name, urgency, factors, prior_sum, prior_ip,
                                rolling_delta_xwobacon, rolling_bbe, ...weakest entry}],
            "slump_hold": [{name, prior_sum, prior_ip, sum_2026, note}]
        }
    """
    ranked = []
    slump_hold = []

    for w in weakest_n:
        name = w["name"]
        sum_2026 = w.get("score", 0)
        prior = w.get("prior_stats") or {}
        prior_ip = prior.get("ip")

        # Compute 2025 prior v4 Sum (only valid if prior IP ≥ _PRIOR_IP_MIN)
        notes = []
        if prior and prior_ip is not None and prior_ip < _PRIOR_IP_MIN:
            sum_2025 = 0
            prior_breakdown = {}
            notes.append(
                f"2025 prior IP {prior_ip:.1f} <{_PRIOR_IP_MIN} 無效（樣本過小），視為無 prior"
            )
        elif prior and prior_ip is not None:
            prior_v4_data = {
                "ip_gs": prior.get("ip_gs"),
                "whiff_pct": prior.get("whiff_pct"),
                "bb9": prior.get("bb9"),
                "gb_pct": prior.get("gb_pct"),
                "xwobacon": prior.get("xwobacon"),
            }
            sum_2025, prior_breakdown = compute_sum_score_v4_sp(prior_v4_data)
        else:
            sum_2025 = 0
            prior_breakdown = {}

        # Slump hold detection: 2025 v4 Sum ≥ 40 AND IP ≥ 50
        if sum_2025 >= 40 and prior_ip is not None and prior_ip >= _PRIOR_IP_SLUMP_HOLD_MIN:
            slump_hold.append({
                "name": name,
                "mlb_id": w.get("mlb_id"),
                "prior_sum": sum_2025,
                "prior_ip": prior_ip,
                "prior_breakdown": prior_breakdown,
                "sum_2026": sum_2026,
                "note": "菁英底，slump 候選（v4 Sum ≥40 + IP ≥50）",
            })
            continue

        # Four factors
        f_2026 = _factor_2026_sum_v4(sum_2026)
        f_2025 = _factor_2025_sum_v4(sum_2025)
        f_rolling = 0  # v4 decision 1/4: Python doesn't score 21d Δ; Claude reads raw
        savant_v4 = w.get("savant_v4") or {}
        f_luck = _factor_luck_regression_v4(
            savant_v4.get("xera"),
            savant_v4.get("era"),
            savant_v4.get("bbe"),
        )

        urgency = f_2026 + f_2025 + f_rolling + f_luck

        # Pass through 21d rolling for Claude prompt (raw, no score)
        rolling_21d = w.get("rolling_21d") or {}
        rolling_xwobacon = rolling_21d.get("xwobacon")
        season_xwobacon = savant_v4.get("xwobacon")
        rolling_delta = (
            rolling_xwobacon - season_xwobacon
            if rolling_xwobacon is not None and season_xwobacon is not None
            else None
        )

        ranked.append({
            **w,
            "urgency": urgency,
            "factors": {
                "sum_2026": f_2026,
                "sum_2025": f_2025,
                "rolling": f_rolling,
                "luck": f_luck,
            },
            "prior_sum": sum_2025,
            "prior_ip": prior_ip,
            "prior_breakdown": prior_breakdown,
            "rolling_delta_xwobacon": rolling_delta,
            "rolling_bbe": rolling_21d.get("bbe"),
            "notes": notes,
        })

    # Per design decision 3/4: Python doesn't break ties. Sort by urgency desc;
    # ties keep original order (caller / Claude breaks via raw material).
    ranked.sort(key=lambda e: e["urgency"], reverse=True)

    return {
        "weakest_ranked": ranked,
        "slump_hold": slump_hold,
    }
