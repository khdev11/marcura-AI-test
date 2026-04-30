"""Extract text from a charter party PDF, omitting struck-through characters.

Charter parties are routinely amended by drawing a horizontal line through
existing clause text and writing replacement language alongside or below.
``pdftotext``-style extractors keep the struck text, so we do our own pass
with PyMuPDF: we collect every horizontal line and rectangle drawn on the
page, then drop any character whose bounding box is bisected by one of them.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import fitz  # PyMuPDF


# Drawn lines whose y-position falls inside the middle (1 - 2*MARGIN) band of
# a glyph's bounding box are treated as strikethroughs. 0.20 keeps underlines
# (which sit at the baseline) from being mistaken for strikes.
_STRIKE_BAND_MARGIN = 0.20

# Filled rectangles thinner than this many points act as strikethrough lines.
_RECT_LINE_THICKNESS = 1.5

# Bbox type alias for raw PyMuPDF character bbox tuples (x0, y0, x1, y1).
_Bbox = tuple[float, float, float, float]


class _HLine(NamedTuple):
    """A horizontal line segment drawn on a page."""

    x0: float
    x1: float
    y: float


def _horizontal_lines(page: fitz.Page) -> list[_HLine]:
    lines: list[_HLine] = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            op = item[0]
            if op == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.y - p2.y) < 0.5:
                    lines.append(_HLine(min(p1.x, p2.x), max(p1.x, p2.x), p1.y))
            elif op == "re":
                rect = item[1]
                if rect.height < _RECT_LINE_THICKNESS:
                    y = (rect.y0 + rect.y1) / 2
                    lines.append(_HLine(rect.x0, rect.x1, y))
    return lines


def _is_struck(bbox: _Bbox, lines: list[_HLine]) -> bool:
    x0, y0, x1, y1 = bbox
    height = y1 - y0
    if height <= 0:
        return False
    band_top = y0 + height * _STRIKE_BAND_MARGIN
    band_bottom = y1 - height * _STRIKE_BAND_MARGIN
    for line in lines:
        if band_top <= line.y <= band_bottom and line.x0 <= x1 and line.x1 >= x0:
            return True
    return False


def _iter_page_lines(page: fitz.Page) -> Iterator[str]:
    """Yield one cleaned text line per visual line on the page."""
    strikes = _horizontal_lines(page)
    for block in page.get_text("rawdict")["blocks"]:
        if block["type"] != 0:  # 0 = text
            continue
        for line in block["lines"]:
            text = "".join(
                ch["c"]
                for span in line["spans"]
                for ch in span["chars"]
                if not _is_struck(ch["bbox"], strikes)
            ).rstrip()
            stripped = text.strip()
            if not stripped:
                continue
            # Drop right-margin line numbers (pure digit artefacts like "67", "102").
            if stripped.isdigit():
                continue
            yield text


def extract_pages(pdf_path: Path | str, *, first: int, last: int) -> str:
    """Return the text of pages ``first..last`` (1-indexed, inclusive).

    Each page is preceded by a ``=== PAGE n ===`` marker so the LLM can keep
    its bearings, and struck-through characters are dropped.

    Raises ``ValueError`` for invalid page ranges.
    """
    if first < 1:
        raise ValueError(f"first must be >= 1, got {first}")
    if first > last:
        raise ValueError(f"first ({first}) must be <= last ({last})")
    out: list[str] = []
    with fitz.open(Path(pdf_path)) as doc:
        if last > doc.page_count:
            last = doc.page_count
        for page_index in range(first - 1, last):
            page = doc[page_index]
            out.append(f"=== PAGE {page_index + 1} ===")
            out.extend(_iter_page_lines(page))
            out.append("")
    return "\n".join(out)
