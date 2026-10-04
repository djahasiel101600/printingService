"""Render Office / text uploads into a printable PDF.

The printer only accepts PDF and image files, and a small shop deployment has no
LibreOffice to convert a ``.docx`` with. So a Word/Excel/PowerPoint/text upload
is re-flowed as *text pages* onto the target paper and written as a multi-page
PDF with Pillow (which needs nothing beyond what the project already ships).

This is what makes page selection meaningful for those uploads: the same layout
function both counts and renders the pages, so the page numbers the admin picks
in the UI are exactly the pages that come out of the printer.

Caveat (documented for the shop): this is a text rendering, so images, fonts
and page furniture of the original document are not reproduced. ``MAX_PAGES``
keeps one hostile/large upload from turning an HTTP request into a memory bomb.
"""
from __future__ import annotations

import io
import re

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter

from .document_preview import build_preview
from .file_edits import PAPER_DIMENSIONS, RENDER_DPI

# Text page layout (PDF points; 72 points = 1 inch).
PAGE_MARGIN_PT = 36.0          # 0.5" all round
FONT_SIZE_PT = 11.0
LINE_SPACING = 1.45
# Rendering more than this in a single request is refused: the shop should
# convert a book-sized document in Word instead.
MAX_PAGES = 150


class DocumentRenderError(Exception):
    """Raised when an upload cannot be turned into printable pages."""


# ------------------------------------------------------------------ layout
def _paper_points(media_size: str) -> tuple[float, float]:
    return PAPER_DIMENSIONS.get(media_size, PAPER_DIMENSIONS["ps_a4"])


class _Layout:
    """Pixel geometry of one paper size at the rendering DPI."""

    def __init__(self, media_size: str):
        paper_w, paper_h = _paper_points(media_size)
        self.dpi_scale = RENDER_DPI / 72.0
        self.canvas = (round(paper_w * self.dpi_scale), round(paper_h * self.dpi_scale))
        self.margin = round(PAGE_MARGIN_PT * self.dpi_scale)
        self.text_width = self.canvas[0] - 2 * self.margin
        self.font = ImageFont.load_default(size=round(FONT_SIZE_PT * self.dpi_scale))
        usable_height = self.canvas[1] - 2 * self.margin
        self.lines_per_page = max(1, usable_height // round(FONT_SIZE_PT * self.dpi_scale * LINE_SPACING))
        self.line_height = max(1, usable_height // self.lines_per_page)


_LAYOUTS: dict[str, _Layout] = {}


def _layout(media_size: str) -> _Layout:
    """Layouts are deterministic per paper size, so cache them."""
    if media_size not in _LAYOUTS:
        _LAYOUTS[media_size] = _Layout(media_size)
    return _LAYOUTS[media_size]



# ---------------------------------------------------------------- text flow
def _lines_from_blocks(blocks: list[dict]) -> list[str]:
    """Flatten the preview blocks into printable lines."""
    lines: list[str] = []
    for block in blocks:
        kind = block.get("type")
        if kind == "table":
            lines.append(f"[{block.get('label') or 'Table'}]")
            for row in block.get("rows", []):
                lines.append(" | ".join(row))
            lines.append("")
        elif kind == "slide":
            lines.append(f"— {block.get('label') or 'Slide'} —")
            lines.extend(block.get("items", []))
            lines.append("")
        elif kind == "spacer":
            lines.append("")
        else:
            lines.append(str(block.get("text", "")))
    return lines


def _wrap_line(text: str, font, max_width: float) -> list[str]:
    """Greedy word wrap measured with the real font (no metrics guesswork)."""
    if not text.strip():
        return [""]
    words = re.split(r"\s+", text.strip())
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        # Long unbroken tokens (URLs, hashes) still have to be split somewhere.
        while font.getlength(candidate) > max_width and len(candidate) > 1:
            cut = max(1, len(candidate) // 2)
            keep, candidate = candidate[:cut], candidate[cut:]
            lines.append(keep)
        current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def paginate(filename: str, content: bytes, media_size: str = "ps_a4") -> list[list[str]]:
    """Split an upload into pages of wrapped lines (no rasterising).

    Raises ``PreviewError`` for formats ``document_preview`` cannot read and
    ``DocumentRenderError`` when the document is too long to render inline.
    """
    preview = build_preview(filename, content)
    layout = _layout(media_size)
    wrapped: list[str] = []
    for line in _lines_from_blocks(preview.blocks):
        wrapped.extend(_wrap_line(line, layout.font, layout.text_width))
    per_page = layout.lines_per_page
    pages = [wrapped[i:i + per_page] for i in range(0, len(wrapped), per_page)] or [[]]
    if len(pages) > MAX_PAGES:
        raise DocumentRenderError(
            f"This document is {len(pages)} text pages long — too long to render here. "
            "Convert it to PDF (Word → Save as PDF) and use the Upload PDF action instead."
        )
    return pages


def page_count(filename: str, content: bytes, media_size: str = "ps_a4") -> int:
    """Number of text pages this upload would print as (always >= 1)."""
    return max(1, len(paginate(filename, content, media_size)))


# ----------------------------------------------------------------- raster
def _render_page(lines: list[str], layout: _Layout) -> Image.Image:
    page = Image.new("RGB", layout.canvas, "white")
    draw = ImageDraw.Draw(page)
    y = layout.margin
    for line in lines:
        if line:
            draw.text((layout.margin, y), line, fill="black", font=layout.font)
        y += layout.line_height
    return page


def render_pdf(filename: str, content: bytes, media_size: str = "ps_a4") -> bytes:
    """Render the upload as text pages and return a multi-page PDF.

    Pages are rasterised one at a time and folded straight into the writer, so
    memory stays flat no matter how long the document is.
    """
    pages = paginate(filename, content, media_size)
    layout = _layout(media_size)
    writer = PdfWriter()
    try:
        for lines in pages:
            page = _render_page(lines, layout)
            buffer = io.BytesIO()
            page.save(buffer, format="PDF", resolution=RENDER_DPI)
            page.close()
            writer.add_page(PdfReader(io.BytesIO(buffer.getvalue())).pages[0])
    except (OSError, ValueError) as exc:  # pragma: no cover - defensive
        raise DocumentRenderError(f"Could not render this document: {exc}") from exc
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
