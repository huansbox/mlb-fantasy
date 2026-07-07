"""Parse stream-sp-pending.md (H2 ET sections + TBD bullets + eval table rows).

Pure-function parser — input markdown str, output dict keyed by ET date:

    {
        "2026-05-26": {
            "tbd_games": [{"away": "MIA", "home": "TOR", "side": "home"}, ...],
            "evaluations": [{"name": "Griffin Canning", "team": "SD", "is_home": True,
                             "mlb_id": 656288, "sum26": 27, "sum25": 20,
                             "opp_abbr": "PHI"}, ...],
        },
        ...
    }

Eval columns are resolved from the table header row (header-driven — schema
versions with/without 近況 / mlb_id columns both parse). Columns absent from
the header (old-format rows) yield None for mlb_id / sum26 / sum25 / opp_abbr.

Used by stream_sp_scan.py --pending-file to compute pending_diff vs today's
scan (issue 014 — auto-diff补查 mode), and by mlb_query.py deep --pending-file
to build the deep_batch players list (issue #406). Graceful on malformed
input — unknown lines / corrupt rows / unknown subsections are silently
skipped so user free-form notes in `### 備註` don't break the run.
"""

from __future__ import annotations

import re

_H2_ET_RE = re.compile(r"^## ET (\d{4}-\d{2}-\d{2})\s*$")
_TBD_LINE_RE = re.compile(r"^([A-Z]{2,3}) @ ([A-Z]{2,3}) \((.+)\)$")
_TEAM_CELL_RE = re.compile(r"^([A-Z]{2,3})\s+(home|away)$")
_SEP_CELL_RE = re.compile(r"^[-:]+$")
_SUM_CELL_RE = re.compile(r"^(\d+|-)/(\d+|-)$")
_OPP_ABBR_RE = re.compile(r"^([A-Z]{2,3})\b")

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
    eval_header: list[str] | None = None

    for raw in text.splitlines():
        line = raw.rstrip()
        # H2 ET date — start a new section
        m = _H2_ET_RE.match(line)
        if m:
            current_date = m.group(1)
            result[current_date] = {"tbd_games": [], "evaluations": []}
            current_section = _SEC_OTHER
            eval_header = None
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
                eval_header = None
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
            cells = _split_row_cells(line)
            if not cells:
                continue
            if "SP" in cells:  # header row（欄序任意，data cell 不會恰為 "SP"）
                eval_header = cells
                continue
            ev = _parse_eval_cells(cells, eval_header)
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


def _split_row_cells(line: str) -> list[str] | None:
    """Split a `| a | b |` table line into stripped cells. None for non-table lines."""
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.split("|")]
    # Strip leading/trailing empty cells from |...|...| edges
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def _parse_eval_cells(cells: list[str], header: list[str] | None) -> dict | None:
    """Parse table data cells → evaluation dict, columns resolved via header.

    Header absent (degenerate table) → positional fallback: SP=0, 隊=1.
    Columns missing from the header / row (old-format) → None values.
    Returns None for separator / malformed rows.
    """
    if len(cells) < 2:
        return None
    # Separator row — all cells are dashes/colons
    if all(_SEP_CELL_RE.match(c) for c in cells):
        return None
    if header:
        col: dict[str, int] = {}
        for i, h in enumerate(header):
            if h == "SP":
                col["sp"] = i
            elif h == "隊":
                col["team"] = i
            elif h.startswith("對手"):
                col["opp"] = i
            elif h.startswith("Sum26/25"):
                col["sum"] = i
            elif h == "mlb_id":
                col["id"] = i
    else:
        col = {"sp": 0, "team": 1}

    def _cell(key: str) -> str | None:
        i = col.get(key)
        return cells[i] if i is not None and i < len(cells) else None

    name = _cell("sp")
    if not name:
        return None
    team_cell = _cell("team")
    m = _TEAM_CELL_RE.match(team_cell) if team_cell else None
    if not m:
        return None

    mlb_id = None
    id_cell = _cell("id")
    if id_cell and id_cell.isdigit():
        mlb_id = int(id_cell)

    sum26 = sum25 = None
    sum_cell = _cell("sum")
    if sum_cell:
        sm = _SUM_CELL_RE.match(sum_cell)
        if sm:
            sum26 = int(sm.group(1)) if sm.group(1) != "-" else None
            sum25 = int(sm.group(2)) if sm.group(2) != "-" else None

    opp_abbr = None
    opp_cell = _cell("opp")
    if opp_cell:
        om = _OPP_ABBR_RE.match(opp_cell)
        if om:
            opp_abbr = om.group(1)

    return {
        "name": name,
        "team": m.group(1),
        "is_home": m.group(2) == "home",
        "mlb_id": mlb_id,
        "sum26": sum26,
        "sum25": sum25,
        "opp_abbr": opp_abbr,
    }
