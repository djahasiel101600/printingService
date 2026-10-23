"""Render Office / text uploads into a printable PDF.

The printer only accepts PDF and image files, and a small shop deployment has no
LibreOffice to convert a ``.docx`` with. So a Word/Excel/PowerPoint/text upload
is laid out as *pages* and written as a multi-page PDF with Pillow (which needs
nothing beyond what the project already ships).

Unlike a plain text dump, this is a **structured** layout that follows the
document's own shape (see services/document_preview.py for where that shape
comes from): tables print as ruled grids, headings print larger and bold,
slides print their title plus bullets, and paragraphs are word-wrapped.

Pagination is shared by ``page_count`` and ``render_pdf`` (both go through
``_prepare``), so the page numbers the admin picks are exactly the pages that
come out of the printer.

Caveat (documented for the shop): this is a *layout* render, so embedded
images, exact fonts and colours of the original document are not reproduced —
the text, structure and tabular data are. ``MAX_PAGES`` keeps one hostile/large
upload from turning an HTTP request into a memory bomb.
"""
from __future__ import annotations

import io
import re

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter

from .document_preview import build_preview
from .file_edits import PAPER_DIMENSIONS, RENDER_DPI

# Page geometry (PDF points; 72 points = 1 inch).
PAGE_MARGIN_PT = 40.0
BODY_PT = 11.0
TABLE_PT = 9.5
LINE_SPACING = 1.4
TABLE_LINE_SPACING = 1.25
PARA_SPACE_PT = 6.0
HEADING_SPACE_BEFORE_PT = 10.0
HEADING_SPACE_AFTER_PT = 3.0
TABLE_CELL_PAD_PT = 3.0
HEADING_SIZES = {1: 19.0, 2: 15.5, 3: 13.0, 4: 12.0, 5: 11.5, 6: 11.0}
MAX_PAGES = 150

_INK = (17, 17, 17)
_RULE = (150, 150, 150)
_HEADER_FILL = (233, 236, 239)


class DocumentRenderError(Exception):
    """Raised when an upload cannot be turned into printable pages."""


# ------------------------------------------------------------------ geometry
class _Layout:
    """Pixel geometry of one paper size at the rendering DPI."""

    def __init__(self, media_size: str):
        paper_w, paper_h = PAPER_DIMENSIONS.get(media_size, PAPER_DIMENSIONS["ps_a4"])
        self.scale = RENDER_DPI / 72.0
        self.width = round(paper_w * self.scale)
        self.height = round(paper_h * self.scale)
        self.margin = round(PAGE_MARGIN_PT * self.scale)
        self.usable_w = self.width - 2 * self.margin
        self.usable_h = self.height - 2 * self.margin
        self._fonts: dict[int, ImageFont.ImageFont] = {}

    def font(self, pt: float) -> ImageFont.ImageFont:
        px = max(6, round(pt * self.scale))
        if px not in self._fonts:
            self._fonts[px] = ImageFont.load_default(size=px)
        return self._fonts[px]

    def line_h(self, pt: float, spacing: float = LINE_SPACING) -> int:
        return max(1, round(pt * self.scale * spacing))


# ------------------------------------------------------------------- drawing
def _stroke_for(px: int) -> int:
    """Faux-bold stroke width — there is no bold variant of the built-in font."""
    return max(1, px // 18)


def _text_drawer(text, font, layout: _Layout, *, bold=False, x_offset=0):
    def draw(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        draw.text(
            (x + x_offset, y), text, font=font, fill=_INK,
            stroke_width=_stroke_for(round(font.size)) if bold else 0,
            stroke_fill=_INK if bold else None,
        )
    return draw


def _is_number(text: str) -> bool:
    return bool(re.fullmatch(r"[-+]?[\d,]*\.?\d+%?", (text or "").strip()))


def _wrap(text: str, font, max_w: float) -> list[str]:
    """Greedy word wrap measured with the real font (no metrics guesswork)."""
    if not text.strip():
        return [""]
    words = re.split(r"\s+", text.strip())
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        # Long unbroken tokens (URLs, hashes) still have to be split somewhere.
        while font.getlength(candidate) > max_w and len(candidate) > 1:
            cut = max(1, len(candidate) // 2)
            keep, candidate = candidate[:cut], candidate[cut:]
            lines.append(keep)
        current = candidate
    if current:
        lines.append(current)
    return lines or [""]


# ------------------------------------------------------------------ flowables
def _heading_atoms(block: dict, layout: _Layout) -> list[dict]:
    level = min(6, max(1, int(block.get("level", 2))))
    pt = HEADING_SIZES[level]
    font = layout.font(pt)
    lh = layout.line_h(pt, 1.25)
    atoms: list[dict] = [{"h": round(HEADING_SPACE_BEFORE_PT * layout.scale), "space": True}]
    for line in _wrap(str(block.get("text", "")), font, layout.usable_w):
        atoms.append({"h": lh, "draw": _text_drawer(line, font, layout, bold=True)})
    atoms.append({"h": round(HEADING_SPACE_AFTER_PT * layout.scale), "space": True})
    return atoms


def _paragraph_atoms(block: dict, layout: _Layout) -> list[dict]:
    font = layout.font(BODY_PT)
    lh = layout.line_h(BODY_PT)
    atoms = [
        {"h": lh, "draw": _text_drawer(line, font, layout)}
        for line in _wrap(str(block.get("text", "")), font, layout.usable_w)
    ]
    atoms.append({"h": round(PARA_SPACE_PT * layout.scale), "space": True})
    return atoms


def _table_row_drawer(cells, col_w, pad, lh, font, layout, header, last, raw_cells, row_h):
    def draw(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        total_w = sum(col_w)
        if header:
            draw.rectangle([x, y, x + total_w, y + row_h], fill=_HEADER_FILL)
        cx = x
        for ci, lines in enumerate(cells):
            draw.line([cx, y, cx, y + row_h], fill=_RULE, width=1)
            right = _is_number(raw_cells[ci])
            ty = y + pad
            for line in lines:
                tx = cx + (col_w[ci] - pad - font.getlength(line)) if right else cx + pad
                draw.text((tx, ty), line, font=font, fill=_INK,
                          stroke_width=_stroke_for(round(font.size)) if header else 0,
                          stroke_fill=_INK if header else None)
                ty += lh
            cx += col_w[ci]
        draw.line([cx, y, cx, y + row_h], fill=_RULE, width=1)   # right edge
        draw.line([x, y, x + total_w, y], fill=_RULE, width=1)   # top edge
        if last:
            draw.line([x, y + row_h, x + total_w, y + row_h], fill=_RULE, width=1)
    return draw


def _table_atoms(block: dict, layout: _Layout) -> list[dict]:
    rows = [list(r) for r in block.get("rows", []) if any(str(c).strip() for c in r)]
    if not rows:
        return []
    n_cols = max(len(r) for r in rows)
    rows = [r + [""] * (n_cols - len(r)) for r in rows]
    pad = round(TABLE_CELL_PAD_PT * layout.scale)
    font = layout.font(TABLE_PT)
    lh = layout.line_h(TABLE_PT, TABLE_LINE_SPACING)

    # Column widths proportional to the widest cell, with a sane minimum so a
    # short header never collapses a data column.
    weights = [max(3, max(len(r[i]) for r in rows)) for i in range(n_cols)]
    col_w = [max(pad * 5, layout.usable_w * w / sum(weights)) for w in weights]
    col_w = [w * layout.usable_w / sum(col_w) for w in col_w]  # renormalise to the sheet

    atoms: list[dict] = []
    if block.get("label"):
        label_font = layout.font(BODY_PT)
        atoms.append({
            "h": layout.line_h(BODY_PT),
            "draw": _text_drawer(str(block["label"]), label_font, layout, bold=True),
        })

    wrapped = [[_wrap(str(r[i]), font, col_w[i] - 2 * pad) for i in range(n_cols)] for r in rows]
    for ri, cells in enumerate(wrapped):
        row_h = max(len(c) for c in cells) * lh + 2 * pad
        atoms.append({
            "h": row_h,
            "draw": _table_row_drawer(
                cells, col_w, pad, lh, font, layout,
                header=(ri == 0), last=(ri == len(wrapped) - 1),
                raw_cells=rows[ri], row_h=row_h,
            ),
        })
    atoms.append({"h": round(PARA_SPACE_PT * layout.scale), "space": True})
    return atoms



def _slide_atoms(block: dict, layout: _Layout) -> list[dict]:
    items = [str(i) for i in block.get("items", [])]
    title = block.get("title") or (items[0] if items else block.get("label") or "Slide")
    atoms: list[dict] = []
    if block.get("label"):
        label_font = layout.font(BODY_PT)
        atoms.append({
            "h": layout.line_h(BODY_PT),
            "draw": _text_drawer(str(block["label"]), label_font, layout),
        })
    atoms.append({"h": round(HEADING_SPACE_BEFORE_PT * layout.scale), "space": True})
    title_font = layout.font(HEADING_SIZES[2])
    title_lh = layout.line_h(HEADING_SIZES[2], 1.25)
    for line in _wrap(str(title), title_font, layout.usable_w):
        atoms.append({"h": title_lh, "draw": _text_drawer(line, title_font, layout, bold=True)})
    atoms.append({"h": round(HEADING_SPACE_AFTER_PT * layout.scale), "space": True})

    bullet_font = layout.font(BODY_PT)
    bullet_lh = layout.line_h(BODY_PT)
    indent = round(14 * layout.scale)
    start = 1 if items and items[0] == str(title) else 0
    for item in items[start:]:
        for li, line in enumerate(_wrap(item, bullet_font, layout.usable_w - indent)):
            prefix = "•  " if li == 0 else "   "
            atoms.append({
                "h": bullet_lh,
                "draw": _text_drawer(prefix + line, bullet_font, layout, x_offset=indent if li else 0),
            })
    atoms.append({"h": round(PARA_SPACE_PT * layout.scale), "space": True})
    return atoms


def _atoms(blocks: list[dict], layout: _Layout) -> list[dict]:
    """Flatten preview blocks into positioned draw-atoms (each with a height)."""
    atoms: list[dict] = []
    for block in blocks:
        kind = block.get("type")
        if kind == "spacer":
            atoms.append({"h": layout.line_h(BODY_PT) // 2, "space": True})
        elif kind == "heading":
            atoms.extend(_heading_atoms(block, layout))
        elif kind == "table":
            atoms.extend(_table_atoms(block, layout))
        elif kind == "slide":
            atoms.extend(_slide_atoms(block, layout))
        else:  # paragraph / anything unknown -> body text
            atoms.extend(_paragraph_atoms(block, layout))
    return atoms


# ----------------------------------------------------------------- pagination
def _paginate(blocks: list[dict], layout: _Layout) -> list[list[tuple[dict, int]]]:
    """Greedily place draw-atoms onto pages. Returns pages of (atom, y-offset)."""
    pages: list[list[tuple[dict, int]]] = []
    current: list[tuple[dict, int]] = []
    y = 0
    for atom in _atoms(blocks, layout):
        # Never open a page with blank space (a heading's lead-in, say).
        if atom.get("space") and not current:
            continue
        if y + atom["h"] > layout.usable_h and current:
            pages.append(current)
            current, y = [], 0
            if atom.get("space"):
                continue
        current.append((atom, y))
        y += atom["h"]
    if current:
        pages.append(current)
    return pages or [[]]


# ------------------------------------------------------------------ facade
def _prepare(filename: str, content: bytes, media_size: str):
    """Single source of truth: (pages, layout) — shared by count and render."""
    layout = _Layout(media_size)
    pages = _paginate(build_preview(filename, content).blocks, layout)
    if len(pages) > MAX_PAGES:
        raise DocumentRenderError(
            f"This document is {len(pages)} pages long — too long to render here. "
            "Convert it to PDF (Word → Save as PDF) and use the Upload PDF action instead."
        )
    return pages, layout


def paginate(filename: str, content: bytes, media_size: str = "ps_a4") -> list:
    """Split an upload into laid-out pages (no rasterising yet).

    Raises ``PreviewError`` for formats ``document_preview`` cannot read and
    ``DocumentRenderError`` when the document is too long to render inline.
    """
    return _prepare(filename, content, media_size)[0]


def page_count(filename: str, content: bytes, media_size: str = "ps_a4") -> int:
    """Number of pages this upload would print as (always >= 1)."""
    return max(1, len(_prepare(filename, content, media_size)[0]))


def render_pdf(filename: str, content: bytes, media_size: str = "ps_a4") -> bytes:
    """Render the upload as laid-out pages and return a multi-page PDF.

    Pages are rasterised one at a time and folded straight into the writer, so
    memory stays flat no matter how long the document is.
    """
    pages, layout = _prepare(filename, content, media_size)
    writer = PdfWriter()
    try:
        for page in pages:
            sheet = Image.new("RGB", (layout.width, layout.height), "white")
            draw = ImageDraw.Draw(sheet)
            for atom, y in page:
                if atom.get("draw"):
                    atom["draw"](draw, layout.margin, layout.margin + y)
            buffer = io.BytesIO()
            sheet.save(buffer, format="PDF", resolution=RENDER_DPI)
            sheet.close()
            writer.add_page(PdfReader(io.BytesIO(buffer.getvalue())).pages[0])
    except (OSError, ValueError) as exc:  # pragma: no cover - defensive
        raise DocumentRenderError(f"Could not render this document: {exc}") from exc
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

