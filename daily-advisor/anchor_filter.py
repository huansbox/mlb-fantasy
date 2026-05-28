"""Anchor SP filter — pure function for SP B2 thin mechanical layer.

Removes anchored SPs (cant_cut lifetime + weekly_anchor_sp weekly-mutable)
from a roster before downstream candidate-pool ranking. Single call site:
`fa_compute.pick_weakest_v4_sp` (invoked once; `_phase6_sp.py` receives the
already-filtered pool and never re-applies anchor filtering).

Name matching mirrors `rp_svh_scan.py` — case-insensitive, accent-stripped,
apostrophe-stripped via `name_match.normalize_name`. Aligns with Yahoo /
MLB / Savant name-spelling disagreements (Jesús vs Jesus, O'Brien vs
O’Brien).

YAGNI: no `player_type` parameter. Batter anchor mechanism, if introduced
later, will add it then — current consumers all SP.
"""

from __future__ import annotations

from name_match import normalize_name as _normalize


def filter_anchors(
    roster: list[dict],
    cant_cut_names: list[str] | None,
    weekly_anchor_names: list[str] | None,
) -> list[dict]:
    """Return roster minus any player whose name matches an anchor.

    Args:
        roster: list of player dicts; each must carry a `"name"` key.
        cant_cut_names: lifetime no-touch names. `None` and `[]` equivalent.
        weekly_anchor_names: this-week no-touch names. `None` and `[]` equivalent.

    Returns:
        Subset of `roster` preserving original order. Idempotent — applying
        the function twice with the same anchors yields the same result.
    """
    anchors = {_normalize(n) for n in (cant_cut_names or [])}
    anchors |= {_normalize(n) for n in (weekly_anchor_names or [])}
    if not anchors:
        return list(roster)
    return [p for p in roster if _normalize(p.get("name", "")) not in anchors]
