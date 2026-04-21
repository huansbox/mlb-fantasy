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

    # ✅ 撿便宜運氣 — xERA-ERA ≤ -0.81
    era_diff = derived.get("era_diff")
    if era_diff is not None and era_diff <= -0.81:
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

    # ⚠️ 賣高運氣 — xERA-ERA ≥ +0.81
    if era_diff is not None and era_diff >= 0.81:
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
    """Same as compute_sum_score but maps SP prior_stats keys (_allowed suffix).

    Args:
        prior_stats: roster_config prior_stats dict (or None for no prior)

    Returns:
        (sum_score, breakdown). Returns (0, zero-filled breakdown) if prior is
        empty/None — caller handles "no prior" semantics.
    """
    if not prior_stats:
        labels = _BREAKDOWN_LABELS[player_type]
        return 0, {label: 0 for label in labels.values()}

    key_map = _PRIOR_KEY_MAP[player_type]
    metrics = {metric: prior_stats.get(prior_key) for metric, prior_key in key_map.items()}
    return compute_sum_score(metrics, player_type)
