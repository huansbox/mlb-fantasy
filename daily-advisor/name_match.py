"""Shared player-name normalization for fuzzy matching.

Single source of truth so the Yahoo `query_fa --names` filter and the
RP-SV+H scan's MLB↔Yahoo cross-check normalize names identically — a
divergence would silently drop accented / apostrophe names on one side.

Intentionally dependency-free (no daily_advisor / zoneinfo import) so
pure-function unit tests can import it without tzdata.
"""

from __future__ import annotations

import unicodedata


def normalize_name(name: str) -> str:
    """Strip accents + apostrophes + lowercase for fuzzy name matching.

    Jesús → jesus; Riley O'Brien / O’Brien → riley obrien. Used across the
    MLB Stats API, Yahoo, and Baseball Savant name spellings, which disagree
    on accents and on the apostrophe character (U+0027 vs U+2019).
    """
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    )
    return stripped.replace("'", "").replace("’", "").lower()
