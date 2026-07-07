"""LLM-safe SP payload slimming for B2 thin pipeline.

Keeps raw SP signals visible to the LLM while removing mechanical anchors that
short-circuit independent reasoning: v4 Sum, urgency factors, 2025 prior data,
and obsolete evaluation verdict tags. B2 thin design: 2026-only data, expanded
2026/21d-based tag whitelist.
"""

from __future__ import annotations

import sys
from typing import Literal

import fa_compute
from payload_budget import PayloadBudget, PayloadBudgetExceeded

Role = Literal["my_team", "fa"]

# 318b B6 injection budget (design doc Q2/Q3): base pool ≤3 lines per
# candidate — ledger memory (churn core, up to 2) outranks the 046 starts
# line, which outranks the 050 velo/kbb dicts; a velo alarm still surfaces
# via its 0-line tag when the dict yields. Swap rides its own 1-line pool
# (Q3) and never competes with the base.
_INJECTION_BASE_MAX_LINES = 3
_SWAP_POOL_MAX_LINES = 1

_V4_SLOT_KEYS = ("ip_gs", "whiff_pct", "bb9", "gb_pct", "xwobacon")
_V4_SLOT_LABELS = {
    "ip_gs": "IP/GS",
    "whiff_pct": "Whiff%",
    "bb9": "BB/9",
    "gb_pct": "GB%",
    "xwobacon": "xwOBACON",
}
_PA_TAGS = {"✅ 球隊主力", "⚠️ 上場有限"}
_SAMPLE_TAGS = {"⚠️ 樣本小", "⚠️ 短局", "⚠️ IL 短期", "⚠️ Swingman 角色"}
_ADD_TAGS_2026 = {
    "✅ 深投型",
    "✅ GB 重型",
    "✅ K 壓制",
    "✅ 撿便宜運氣",
    "✅ 近況確認",
}
_WARN_TAGS_2026 = {
    "⚠️ xwOBACON 極端",
    "⚠️ K 壓制不足",
    "⚠️ Command 警示",
    "⚠️ 賣高運氣",
    "⚠️ 近況下滑",
}
_ALLOWED_TAGS = _PA_TAGS | _SAMPLE_TAGS | _ADD_TAGS_2026 | _WARN_TAGS_2026
# 050 velo tags carry a variable magnitude suffix ("⚠️ 球速下滑 (FF -1.3 vs
# season)") — whitelisted by prefix, not exact match.
_ALLOWED_TAG_PREFIXES = ("⚠️ 球速下滑", "✅ 球速上升")


def _v4_percentile(value, metric: str) -> int | None:
    """v4 SP percentile bucket in elite direction (display: ≥P90 shown as 95).
    The band walk itself lives in fa_compute.v4_percentile_of."""
    if value is None or metric not in fa_compute.PITCHER_V4_PCTILES:
        return None
    matched = fa_compute.v4_percentile_of(value, metric)
    if matched >= 90:
        return 95
    return matched


def _slot_metrics(source: dict) -> dict:
    return {
        _V4_SLOT_LABELS[key]: {
            "raw": source.get(key),
            "percentile": _v4_percentile(source.get(key), key),
        }
        for key in _V4_SLOT_KEYS
    }


def _rolling_payload(entry: dict, sv4: dict) -> dict:
    rolling_21d = entry.get("rolling_21d") or {}
    rolling_xwobacon = rolling_21d.get("xwobacon")
    season_xwobacon = sv4.get("xwobacon")
    delta = entry.get("rolling_delta_xwobacon")
    if delta is None and rolling_xwobacon is not None and season_xwobacon is not None:
        delta = rolling_xwobacon - season_xwobacon

    payload = {
        "xwobacon": rolling_xwobacon,
        "season_xwobacon": season_xwobacon,
        "delta": delta,
        "bbe": entry.get("rolling_bbe", rolling_21d.get("bbe")),
    }
    # 050: CSW% 21d rides the existing rolling dict (0 budget lines). Season
    # CSW is unobtainable (custom-leaderboard csw_percent returns empty via
    # CSV, verified 2026-07-07) — a context LEVEL, never in Sum.
    if rolling_21d.get("csw_pct") is not None:
        payload["csw_pct"] = rolling_21d["csw_pct"]
        payload["pitches"] = rolling_21d.get("pitches")
    return payload


def _tag_allowed(tag: str) -> bool:
    return tag in _ALLOWED_TAGS or tag.startswith(_ALLOWED_TAG_PREFIXES)


def _filtered_tags(entry: dict) -> tuple[list[str], list[str]]:
    add_tags = [t for t in (entry.get("add_tags") or []) if _tag_allowed(t)]
    warn_tags = [t for t in (entry.get("warn_tags") or []) if _tag_allowed(t)]
    return add_tags, warn_tags


def slim_entry(full_entry: dict, role: Role) -> dict:
    """Return a B2 LLM-safe payload for one SP entry.

    Args:
        full_entry: Full my-team or FA entry from the SP compute layer.
        role: ``"my_team"`` or ``"fa"``. FA role keeps ownership fields.
    """
    if role not in ("my_team", "fa"):
        raise ValueError(f"unknown payload role: {role}")

    sv4 = full_entry.get("savant_v4") or {}
    bbe = sv4.get("bbe", full_entry.get("bbe"))
    add_tags, warn_tags = _filtered_tags(full_entry)
    pa_tags = [t for t in add_tags + warn_tags if t in _PA_TAGS]
    sample_tags = [t for t in add_tags + warn_tags if t in _SAMPLE_TAGS]

    payload = {
        "name": full_entry["name"],
        "team": full_entry.get("team"),
        "position": full_entry.get("position") or "SP",
        "selected_pos": full_entry.get("selected_pos"),
        "status": full_entry.get("status"),
        "season_v4": {
            "slots": _slot_metrics(sv4),
            "context": {
                "xera": sv4.get("xera"),
                "era": sv4.get("era"),
                "bbe": sv4.get("bbe"),
                "ip": sv4.get("ip"),
                "g": sv4.get("g"),
                "gs": sv4.get("gs"),
                "k9": sv4.get("k9"),
                "whip": sv4.get("whip"),
            },
        },
        "rolling_21d": _rolling_payload(full_entry, sv4),
        "pa_tags": pa_tags,
        "sample_tags": sample_tags,
        "add_tags": add_tags,
        "warn_tags": warn_tags,
        "low_confidence": bool(
            full_entry.get("low_confidence")
            or full_entry.get("confidence") == "低"
            or (bbe is not None and bbe < 30)
        ),
        "notes": full_entry.get("notes") or [],
    }

    if role == "fa":
        payload.update({
            "pct": full_entry.get("pct"),
            "d1": full_entry.get("d1"),
            "d3": full_entry.get("d3"),
            "waiver_date": full_entry.get("waiver_date"),
        })

    _inject_318b(full_entry, payload)
    return payload


def _inject_318b(full_entry: dict, payload: dict) -> None:
    """318b B6 field passthrough under the payload budget (docs/318b-
    injection-design.md). Base pool priority: ledger memory (up to 2 lines,
    the churn-protection core) > 046 next-week starts (the volume headline) >
    050 velo dict > 050 K-BB ladder; lower priorities yield gracefully. The
    048 swap line rides its own pool (Q3). All fields are attached upstream
    by _phase6_sp best-effort — absent keys inject nothing.

    Budget unit note: this payload is a JSON dict, so a "line" here is one
    injected FIELD (the Q2 batter text-line analog); the actual token cost is
    owned by the 段③ paired A/B, not this count."""
    base = PayloadBudget(max_lines=_INJECTION_BASE_MAX_LINES)

    # inject exactly what is registered — a future >ceiling note is truncated,
    # never silently smuggled past the budget
    note = (full_entry.get("ledger_note") or [])[:_INJECTION_BASE_MAX_LINES]
    base.register("ledger", len(note))
    if note:
        payload["ledger_note"] = note

    for slice_id, key in (("starts", "next_week_starts"),
                          ("velo", "micro_velo"),
                          ("kbb", "kbb_small_sample")):
        value = full_entry.get(key)
        if value and base.remaining() >= 1:
            payload[key if key != "micro_velo" else "velo"] = value
            base.register(slice_id, 1)

    try:
        base.assert_within(full_entry.get("name", "?"))
    except PayloadBudgetExceeded as e:  # never abort the scan
        print(f"  payload-budget: {e}", file=sys.stderr)

    swap = full_entry.get("swap_vs_incumbent")
    if swap:
        pool = PayloadBudget(max_lines=_SWAP_POOL_MAX_LINES)
        pool.register("swap", 1)
        if pool.within():
            payload["swap_vs_incumbent"] = swap
