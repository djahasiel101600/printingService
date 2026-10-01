"""Server-side content preview for non-renderable uploads.

PDFs and images are previewed natively by the browser. Office documents and
plain-text files are not, so this module pulls their text out of the container
and returns a structured payload the UI can render:

* ``.docx``  -> ``word/document.xml`` paragraphs (+ heading styles)
* ``.xlsx``  -> ``xl/worksheets/*.xml`` resolved through ``xl/sharedStrings.xml``
* ``.pptx``  -> one block per ``ppt/slides/slideN.xml``
* ``.txt`` / ``.md`` / ``.csv`` -> decoded verbatim

Every format except the plain-text ones is a ZIP of XML parts, so this needs
nothing beyond the standard library — no LibreOffice, no extra pip packages.
"""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree

# Guard rails: a hostile/large document must not be able to hang the preview.
MAX_CHARS = 200_000
MAX_BLOCKS = 2_000
MAX_TABLE_ROWS = 300
MAX_TABLE_COLS = 30
MAX_SLIDES = 200

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

SUPPORTED_FORMATS = ("docx", "xlsx", "pptx", "txt", "md", "csv")


class PreviewError(Exception):
    """Raised when a document cannot be turned into a readable preview."""


class DocumentPreview:
    """Structured, UI-ready representation of a document's contents."""

    def __init__(self, kind: str, fmt: str, blocks: list[dict], truncated: bool = False):
        self.kind = kind          # document | spreadsheet | slides | text
        self.format = fmt        # docx | xlsx | pptx | txt | md | csv
        self.blocks = blocks
        self.truncated = truncated

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "format": self.format,
            "blocks": self.blocks,
            "truncated": self.truncated,
            "block_count": len(self.blocks),
        }


# ------------------------------------------------------------------ helpers
def _safe_xml(archive: zipfile.ZipFile, name: str):
    """Parse one XML part, returning None for missing/oversized/broken parts."""
    try:
        info = archive.getinfo(name)
    except KeyError:
        return None
    if info.file_size > 12_000_000:
        return None
    try:
        with archive.open(name) as handle:
            return ElementTree.parse(io.BytesIO(handle.read())).getroot()
    except (ElementTree.ParseError, zipfile.BadZipFile, OSError, RuntimeError):
        return None


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _heading_level(style: str) -> int:
    match = re.search(r"(\d+)", style or "")
    return min(6, max(1, int(match.group(1)))) if match else 2


def _blocks(pairs: list[tuple[str, str]]) -> tuple[list[dict], bool]:
    """Turn (style, text) pairs into blocks, honouring the output limits."""
    blocks: list[dict] = []
    budget = MAX_CHARS
    for style, text in pairs:
        text = re.sub(r"[ \t\u00a0]+", " ", text).strip()
        if not text:
            continue
        blocks.append({
            "type": "heading" if style.startswith("Heading") else "paragraph",
            "level": _heading_level(style),
            "text": text[:budget],
        })
        budget -= len(text)
        if budget <= 0 or len(blocks) >= MAX_BLOCKS:
            return blocks, True
    return blocks, False


def _node_text(node) -> str:
    return "".join(node.itertext()).strip() if node is not None else ""


# --------------------------------------------------------------------- Word
def _read_docx(content: bytes) -> DocumentPreview:
    """Walk the body in document order so headings, paragraphs and tables keep
    their original sequence (iterating every <w:p> would repeat table cells)."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        root = _safe_xml(archive, "word/document.xml")
        if root is None:
            raise PreviewError("This .docx looks corrupted or password protected.")
        body = root.find(f"{_W}body")
        pairs: list[tuple[str, str]] = []
        for element in (body if body is not None else root):
            if element.tag == f"{_W}p":
                style_node = element.find(f"{_W}pPr/{_W}pStyle")
                style = (style_node.get(f"{_W}val", "") or "") if style_node is not None else ""
                pairs.append((style, "".join(element.itertext())))
            elif element.tag == f"{_W}tbl":
                for row in element.iter(f"{_W}tr"):
                    cells = [_node_text(cell) for cell in row.findall(f"{_W}tc")]
                    if any(cells):
                        pairs.append(("Table", "  |  ".join(cells)))
    blocks, truncated = _blocks(pairs)
    return DocumentPreview("document", "docx", blocks, truncated)


# ------------------------------------------------------------------- Excel
def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    root = _safe_xml(archive, "xl/sharedStrings.xml")
    if root is None:
        return []
    return ["".join(item.itertext()).strip() for item in root.iter(f"{_S}si")]


def _read_xlsx(content: bytes) -> DocumentPreview:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        strings = _shared_strings(archive)
        sheets = sorted(
            name for name in archive.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        if not sheets:
            raise PreviewError("No worksheets found in this workbook.")
        blocks: list[dict] = []
        truncated = False
        for index, sheet_name in enumerate(sheets[:20], start=1):
            root = _safe_xml(archive, sheet_name)
            if root is None:
                continue
            rows: list[list[str]] = []
            for row in root.iter(f"{_S}row"):
                if len(rows) >= MAX_TABLE_ROWS:
                    truncated = True
                    break
                cells: list[str] = []
                for cell in row.findall(f"{_S}c"):
                    if len(cells) >= MAX_TABLE_COLS:
                        break
                    value = _node_text(cell.find(f"{_S}v"))
                    if cell.get("t") == "s" and value.isdigit():
                        position = int(value)
                        value = strings[position] if position < len(strings) else ""
                    elif cell.get("t") == "inlineStr":
                        value = _node_text(cell.find(f"{_S}is"))
                    cells.append(value)
                if any(cells):
                    rows.append(cells)
            if rows:
                blocks.append({"type": "table", "label": f"Sheet {index}", "rows": rows})
        if not blocks:
            raise PreviewError("This workbook has no readable cells.")
    return DocumentPreview("spreadsheet", "xlsx", blocks, truncated)




# ------------------------------------------------------------- PowerPoint
def _read_pptx(content: bytes) -> DocumentPreview:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        slides = sorted(
            name for name in archive.namelist()
            if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
        )
        if not slides:
            raise PreviewError("No slides found in this presentation.")
        blocks: list[dict] = []
        for position, slide_name in enumerate(slides[:MAX_SLIDES], start=1):
            root = _safe_xml(archive, slide_name)
            if root is None:
                continue
            lines = [
                re.sub(r"[ \t\u00a0]+", " ", "".join(para.itertext())).strip()
                for para in root.iter(f"{_A}p")
            ]
            lines = [line for line in lines if line][:200]
            blocks.append({
                "type": "slide",
                "label": f"Slide {position}",
                "title": lines[0][:200] if lines else f"Slide {position}",
                "items": lines,
            })
    return DocumentPreview("slides", "pptx", blocks, len(slides) > MAX_SLIDES)


# ------------------------------------------------------------- plain text
def _read_plain(content: bytes, fmt: str) -> DocumentPreview:
    text = _decode(content)
    lines = text.splitlines()
    if fmt == "csv":
        rows = [line.split(",")[:MAX_TABLE_COLS] for line in lines[:MAX_TABLE_ROWS]]
        return DocumentPreview(
            "spreadsheet", fmt,
            [{"type": "table", "label": "CSV", "rows": [r for r in rows if r]}],
            len(lines) > MAX_TABLE_ROWS,
        )
    blocks = [
        {"type": "paragraph" if line.strip() else "spacer", "text": line}
        for line in text[:MAX_CHARS].splitlines()
    ]
    return DocumentPreview("text", fmt, blocks[:MAX_BLOCKS], len(text) > MAX_CHARS)


# ------------------------------------------------------------------ facade
def build_preview(filename: str, content: bytes) -> DocumentPreview:
    """Extract a previewable representation of ``content``.

    Raises ``PreviewError`` with a human-readable reason for anything this
    module cannot handle, which the API surfaces directly to the browser.
    """
    fmt = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if fmt not in SUPPORTED_FORMATS:
        raise PreviewError(
            f"No preview available for '.{fmt or 'unknown'}' files — "
            "upload a PDF or an image to print this one."
        )
    try:
        if fmt == "docx":
            return _read_docx(content)
        if fmt == "xlsx":
            return _read_xlsx(content)
        if fmt == "pptx":
            return _read_pptx(content)
        return _read_plain(content, fmt)
    except zipfile.BadZipFile as exc:
        raise PreviewError(f"This .{fmt} file is not a valid Office document.") from exc
