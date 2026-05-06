"""LLM-safe Phase 6 SP payload slimming.

B1 keeps raw SP signals visible to the LLM while removing mechanical anchors
that can short-circuit independent reasoning: v4 Sum, urgency factors, and
evaluation verdict tags.
"""

from __future__ import annotations

from typing import Literal

import fa_compute

Role = Literal["my_team", "fa"]

_V4_SLOT_KEYS = ("ip_gs", "whiff_pct", "bb9", "gb_pct", "xwobacon")
_V4_SLOT_LABELS = {
    "ip_gs": "IP/GS",
    "whiff_pct": "Whiff%",
    "bb9": "BB/9",
    "gb_pct": "GB%",
    "xwobacon": "xwOBACON",
}
_V4_REVERSE = {"bb9", "xwobacon"}

_PA_TAGS = {"✅ 球隊主力", "⚠️ 上場有限"}
_SAMPLE_TAGS = {"⚠️ 樣本小", "⚠️ 短局", "⚠️ IL 短期", "⚠️ Swingman 角色"}
_ALLOWED_TAGS = _PA_TAGS | _SAMPLE_TAGS


def _v4_percentile(value, metric: str) -> int | None:
    """Return the v4 SP percentile bucket in elite direction."""
    if value is None:
        return None
    bands = fa_compute.PITCHER_V4_PCTILES.get(metric)
    if not bands:
        return None

    reverse = metric in _V4_REVERSE
    matched = 0
    for pct, threshold in bands:
        if reverse:
            if value <= threshold:
                matched = pct
        elif value >= threshold:
            matched = pct
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

    return {
        "xwobacon": rolling_xwobacon,
        "season_xwobacon": season_xwobacon,
        "delta": delta,
        "bbe": entry.get("rolling_bbe", rolling_21d.get("bbe")),
    }


def _filtered_tags(entry: dict) -> tuple[list[str], list[str]]:
    add_tags = [t for t in (entry.get("add_tags") or []) if t in _ALLOWED_TAGS]
    warn_tags = [t for t in (entry.get("warn_tags") or []) if t in _ALLOWED_TAGS]
    return add_tags, warn_tags


def slim_entry(full_entry: dict, role: Role) -> dict:
    """Return a B1 LLM-safe payload for one SP entry.

    Args:
        full_entry: Full my-team or FA entry from the Phase 6 compute layer.
        role: ``"my_team"`` or ``"fa"``. FA role keeps ownership fields.
    """
    if role not in ("my_team", "fa"):
        raise ValueError(f"unknown payload role: {role}")

    sv4 = full_entry.get("savant_v4") or {}
    prior = full_entry.get("prior_stats") or {}
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
        "prior_v4": {
            "ip": prior.get("ip"),
            "slots": _slot_metrics(prior),
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

    return payload
