"""Parse stream-sp-pending.md (H2 ET sections + TBD bullets + eval table rows).

Pure-function parser — input markdown str, output dict keyed by ET date:

    {
        "2026-05-26": {
            "tbd_games": [{"away": "MIA", "home": "TOR", "side": "home"}, ...],
            "evaluations": [{"name": "Griffin Canning", "team": "SD", "is_home": True}, ...],
        },
        ...
    }

Used by stream_sp_scan.py --pending-file to compute pending_diff vs today's
scan (issue 014 — auto-diff补查 mode). Graceful on malformed input — unknown
lines / corrupt rows / unknown subsections are silently skipped so user
free-form notes in `### 備註` don't break the run.
"""

from __future__ import annotations

import re

_H2_ET_RE = re.compile(r"^## ET (\d{4}-\d{2}-\d{2})\s*$")
_TBD_LINE_RE = re.compile(r"^([A-Z]{2,3}) @ ([A-Z]{2,3}) \((.+)\)$")
_TEAM_CELL_RE = re.compile(r"^([A-Z]{2,3})\s+(home|away)$")
_SEP_CELL_RE = re.compile(r"^[-:]+$")

_SEC_TBD = "TBD"
_SEC_EVAL = "EVAL"
_SEC_NOTE = "NOTE"
_SEC_OTHER = "OTHER"


def parse_pending(text: str) -> dict:
    """Parse pending markdown into dict keyed by ET date.

    Empty / no-H2 input returns {}. Malformed rows / unknown subsections /
    free-form notes are silently skipped.
    """
    if not text:
        return {}
    result: dict[str, dict] = {}
    current_date: str | None = None
    current_section = _SEC_OTHER

    for raw in text.splitlines():
        line = raw.rstrip()
        # H2 ET date — start a new section
        m = _H2_ET_RE.match(line)
        if m:
            current_date = m.group(1)
            result[current_date] = {"tbd_games": [], "evaluations": []}
            current_section = _SEC_OTHER
            continue
        # Other H2 (non-ET) — reset, ignore until next ET H2
        if line.startswith("## "):
            current_date = None
            current_section = _SEC_OTHER
            continue
        if current_date is None:
            continue
        # H3 subsection dispatch
        if line.startswith("### "):
            heading = line[4:].strip()
            if heading.startswith("TBD 場次"):
                current_section = _SEC_TBD
            elif heading.startswith("已評估"):
                current_section = _SEC_EVAL
            elif heading.startswith("備註"):
                current_section = _SEC_NOTE
            else:
                current_section = _SEC_OTHER
            continue
        # Section-specific parsing
        if current_section == _SEC_TBD:
            tbd = _parse_tbd_line(line)
            if tbd:
                result[current_date]["tbd_games"].append(tbd)
        elif current_section == _SEC_EVAL:
            ev = _parse_eval_row(line)
            if ev:
                result[current_date]["evaluations"].append(ev)
        # NOTE / OTHER → skip silently (free-form text)
    return result


def _parse_tbd_line(line: str) -> dict | None:
    """Parse `- AWAY @ HOME (... TBD)` bullet. None for non-matching lines."""
    if not line.startswith("- "):
        return None
    body = line[2:].strip()
    m = _TBD_LINE_RE.match(body)
    if not m:
        return None
    away, home, paren = m.group(1), m.group(2), m.group(3).strip()
    if paren == "both TBD":
        side = "both"
    elif paren == f"{away} away TBD":
        side = "away"
    elif paren == f"{home} home TBD":
        side = "home"
    else:
        return None
    return {"away": away, "home": home, "side": side}


def _parse_eval_row(line: str) -> dict | None:
    """Parse a markdown table data row → {name, team, is_home}.

    Returns None for header / separator / malformed rows.
    """
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.split("|")]
    # Strip leading/trailing empty cells from |...|...| edges
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    if len(cells) < 2:
        return None
    # Header row (first cell literally "SP")
    if cells[0] == "SP":
        return None
    # Separator row — all cells are dashes/colons
    if all(_SEP_CELL_RE.match(c) for c in cells):
        return None
    name = cells[0]
    if not name:
        return None
    m = _TEAM_CELL_RE.match(cells[1])
    if not m:
        return None
    return {"name": name, "team": m.group(1), "is_home": m.group(2) == "home"}
