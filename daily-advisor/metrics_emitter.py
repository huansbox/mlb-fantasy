"""Emit Phase 6 metrics as parseable issue-body metadata.

The block is intentionally an HTML comment so it is invisible in GitHub's
rendered issue view while remaining easy to extract from raw issue bodies.
"""

from __future__ import annotations

import json
from typing import Any


def emit_metric_block(
    date,
    sp_step1_results,
    sp_master,
    fa_classify_results,
    fa_master,
    anchor,
    fa_top,
) -> str:
    """Return a deterministic Phase 6 metrics HTML comment.

    Pure string assembly only: no IO, no clock reads, no mutation.
    """
    metrics = {
        "date": str(date),
        "sp_p1_match": _all_match(_values_at_path(sp_step1_results, ["ranking", 0])),
        "sp_review_triggered": _has_borderline_pairs(sp_master),
        "sp_p1_pair_borderline": _has_top_pair_borderline(sp_master, "P"),
        "sp_anchor_name": _name_of(anchor),
        "fa_p1_match": _fa_classify_match(fa_classify_results, _name_of(fa_top)),
        "fa_review_triggered": _has_borderline_pairs(fa_master),
        "fa_top1_pair_borderline": _has_top_pair_borderline(fa_master, "top"),
        "fa_top_name": _name_of(fa_top),
    }
    payload = json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=False)
    return f"<!-- phase6_metrics:\n{payload}\n-->"


def _parsed(result: Any) -> dict | None:
    if result is None:
        return None
    if isinstance(result, dict):
        return result
    parsed = getattr(result, "parsed", None)
    return parsed if isinstance(parsed, dict) else None


def _values_at_path(results: Any, key_path: list[Any]) -> list[Any] | None:
    if not results:
        return []
    values = []
    for result in results:
        current = _parsed(result)
        if current is None:
            return None
        try:
            for key in key_path:
                current = current[key]
        except (KeyError, IndexError, TypeError):
            return None
        values.append(current)
    return values


def _all_match(values: list[Any] | None) -> bool:
    if not values:
        return False
    return len({_canonical(v) for v in values}) == 1


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _has_borderline_pairs(master: Any) -> bool:
    parsed = _parsed(master)
    if not parsed:
        return False
    return bool(parsed.get("borderline_pairs"))


def _has_top_pair_borderline(master: Any, prefix: str) -> bool:
    # M4' refined metric: the any-pair signal saturates at ~100% in baseline
    # (master flags P2-P3 / P3-P4 most days). The actionable dissent — master
    # uncertain about the actual recommendation — is the P1-P2 / top1-top2 pair.
    # Prompts emit string tokens like "P1-P2" / "top1-top2" (see prompt_phase6_*).
    parsed = _parsed(master)
    if not parsed:
        return False
    target = f"{prefix}1-{prefix}2"
    return any(
        isinstance(p, str) and p.strip() == target
        for p in (parsed.get("borderline_pairs") or [])
    )


def _name_of(entry: Any) -> str | None:
    if not entry:
        return None
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return entry.get("name")
    return getattr(entry, "name", None)


def _fa_classify_match(results: Any, fa_top_name: str | None) -> bool:
    if not results:
        return False

    values = []
    for result in results:
        parsed = _parsed(result)
        if parsed is None:
            return False
        classifications = parsed.get("classifications") or []
        by_name = {
            item.get("name"): item.get("verdict")
            for item in classifications
            if isinstance(item, dict) and item.get("name")
        }
        if fa_top_name:
            if fa_top_name not in by_name:
                return False
            values.append(by_name[fa_top_name])
        else:
            values.append(sorted(by_name.items()))

    return _all_match(values)
