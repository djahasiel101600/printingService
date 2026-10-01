"""Server-side pre-print editing (PRD §2.1: crop, split, resize, center).

Images are processed with Pillow; PDFs with pypdf. Every action is recorded in
``OrderFile.edit_actions`` so admins can audit what was done before printing.

Action payloads:
* crop    -> {"x": 0.0-1.0, "y": ..., "w": ..., "h": ...}  (fractions of page)
* split   -> {"pages": [1, 3, 4]}                          (PDF only, 1-based)
* resize  -> {"paper_size": "ps_a4"}                        (scale onto paper)
* center  -> {"paper_size": "ps_a4"}                        (center on paper canvas)
"""
from __future__ import annotations

import io

from django.core.files.base import ContentFile
from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject

# Paper dimensions in PDF points (72 dpi units)
PAPER_DIMENSIONS: dict[str, tuple[float, float]] = {
    "ps_a3": (841.89, 1190.55),
    "ps_a4": (595.28, 841.89),
    "ps_a5": (419.53, 595.28),
    "ps_a6": (297.64, 419.53),
    "ps_b5": (498.90, 708.66),
    "ps_tabloid": (792.0, 1224.0),
    "ps_letter": (612.0, 792.0),
    "ps_legal": (612.0, 1008.0),
    "ps_halfletter": (396.0, 612.0),
    "ps_kg": (612.0, 936.0),        # Philippine "King" 8.5" x 13"
    "ps_l": (252.0, 360.0),         # 3.5" x 5"
    "ps_2l": (360.0, 504.0),        # 5" x 7"
    "ps_10x12": (720.0, 864.0),
    "ps_8x10": (576.0, 720.0),
    "ps_hivision": (907.09, 510.24),
    "ps_5x8": (360.0, 576.0),
    "ps_postcard": (283.46, 419.53),
}

RENDER_DPI = 150  # raster target when mapping images onto paper canvases


class FileEditError(Exception):
    pass


def _paper_points(paper_size: str) -> tuple[float, float]:
    return PAPER_DIMENSIONS.get(paper_size, PAPER_DIMENSIONS["ps_a4"])


def count_pages(file_type: str, content: bytes) -> int:
    if file_type == "pdf":
        try:
            return len(PdfReader(io.BytesIO(content)).pages)
        except Exception as exc:  # noqa: BLE001
            raise FileEditError(f"Unreadable PDF: {exc}") from exc
    return 1


# --------------------------------------------------------------------- PDF
def _pdf_crop(reader: PdfReader, box: dict) -> PdfWriter:
    writer = PdfWriter()
    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        x = min(max(float(box.get("x", 0)), 0.0), 1.0) * width
        y = min(max(float(box.get("y", 0)), 0.0), 1.0) * height
        w = min(max(float(box.get("w", 1)), 0.01), 1.0) * width
        h = min(max(float(box.get("h", 1)), 0.01), 1.0) * height
        crop_box = RectangleObject([x, height - y - h, x + w, height - y])
        page.cropbox = crop_box
        page.mediabox = crop_box
        writer.add_page(page)
    return writer


def _pdf_split(reader: PdfReader, pages: list[int]) -> PdfWriter:
    writer = PdfWriter()
    total = len(reader.pages)
    wanted = sorted({int(p) for p in pages})
    if not wanted:
        raise FileEditError("Split needs at least one page number.")
    for number in wanted:
        if not 1 <= number <= total:
            raise FileEditError(f"Page {number} out of range (1-{total}).")
        writer.add_page(reader.pages[number - 1])
    return writer


def _pdf_compose(reader: PdfReader, paper_size: str, center: bool = True) -> PdfWriter:
    """Scale every page onto the target paper size, optionally centered."""
    target_w, target_h = _paper_points(paper_size)
    writer = PdfWriter()
    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        scale = min(target_w / width, target_h / height)
        tx = (target_w - width * scale) / 2 if center else 0.0
        ty = (target_h - height * scale) / 2 if center else 0.0
        page.add_transformation(Transformation().scale(scale, scale).translate(tx, ty))
        page.mediabox = RectangleObject([0, 0, target_w, target_h])
        writer.add_page(page)
    return writer


def edit_pdf(content: bytes, action: str, params: dict) -> bytes:
    reader = PdfReader(io.BytesIO(content))
    if action == "crop":
        writer = _pdf_crop(reader, params)
    elif action == "split":
        writer = _pdf_split(reader, params.get("pages", []))
    elif action == "resize":
        writer = _pdf_compose(reader, params.get("paper_size", "ps_a4"), center=False)
    elif action == "center":
        writer = _pdf_compose(reader, params.get("paper_size", "ps_a4"), center=True)
    else:
        raise FileEditError(f"Unknown PDF action: {action}")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


# ------------------------------------------------------------------ images
def _image_crop(img: Image.Image, box: dict) -> Image.Image:
    width, height = img.size
    x0 = round(min(max(float(box.get("x", 0)), 0.0), 1.0) * width)
    y0 = round(min(max(float(box.get("y", 0)), 0.0), 1.0) * height)
    x1 = round(min(max(float(box.get("x", 0)) + float(box.get("w", 1)), 0.01), 1.0) * width)
    y1 = round(min(max(float(box.get("y", 0)) + float(box.get("h", 1)), 0.01), 1.0) * height)
    if x1 - x0 < 8 or y1 - y0 < 8:
        raise FileEditError("Crop box is too small.")
    return img.crop((x0, y0, x1, y1))


def _image_compose(img: Image.Image, paper_size: str, center: bool) -> Image.Image:
    paper_w, paper_h = _paper_points(paper_size)
    dpi_scale = RENDER_DPI / 72.0
    canvas_w = round(paper_w * dpi_scale)
    canvas_h = round(paper_h * dpi_scale)
    scale = min(canvas_w / img.width, canvas_h / img.height)
    resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    offset = ((canvas_w - resized.width) // 2, (canvas_h - resized.height) // 2) if center else (0, 0)
    canvas.paste(resized, offset)
    return canvas


def edit_image(content: bytes, action: str, params: dict) -> bytes:
    img = Image.open(io.BytesIO(content))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if action == "crop":
        img = _image_crop(img, params)
    elif action == "resize":
        img = _image_compose(img, params.get("paper_size", "ps_a4"), center=False)
    elif action == "center":
        img = _image_compose(img, params.get("paper_size", "ps_a4"), center=True)
    elif action == "split":
        raise FileEditError("Splitting is only available for PDF files.")
    else:
        raise FileEditError(f"Unknown image action: {action}")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


# ----------------------------------------------------------------- service
def apply_edit(order_file, action: str, params: dict | None = None) -> None:
    """Apply one edit to an OrderFile: store result as edited_file, refresh the
    page count, and append the action to the edit_actions audit trail."""
    params = params or {}
    source = order_file.edited_file or order_file.file
    source.open("rb")
    content = source.read()
    source.close()

    if order_file.file_type == "pdf":
        new_content = edit_pdf(content, action, params)
        new_name = _edited_name(order_file.file_name, "pdf")
    else:
        new_content = edit_image(content, action, params)
        new_name = _edited_name(order_file.file_name, "jpg")

    order_file.edited_file.save(new_name, ContentFile(new_content), save=False)
    order_file.page_count = count_pages(order_file.file_type, new_content)
    # A customer edit changes the document, so any admin page selection made
    # against the previous revision no longer lines up.
    order_file.page_selection = []
    order_file.final_file = None
    actions = list(order_file.edit_actions or [])
    actions.append({"action": action, **params})
    order_file.edit_actions = actions
    order_file.save()


def select_pages(order_file, pages: list[int] | None) -> list[int]:
    """Admin page selection ("which pages should be printed?").

    Physically trims the PDF into ``final_file`` so the printer receives exactly
    the chosen sheets — Epson Connect has no page-range parameter, so the work
    has to happen before upload. Passing an empty selection (or ``None``) clears
    it and prints the whole document again.

    Returns the normalised selection actually stored.
    """
    from apps.orders.models import format_page_selection

    if order_file.file_type != "pdf":
        # Images are a single sheet; nothing to select.
        order_file.page_selection = []
        order_file.save(update_fields=["page_selection"])
        return []

    source = order_file.edited_file or order_file.file
    source.open("rb")
    content = source.read()
    source.close()

    try:
        total = count_pages("pdf", content)
    except FileEditError:
        total = order_file.page_count
    order_file.page_count = total

    wanted = sorted({int(p) for p in (pages or [])})
    wanted = [p for p in wanted if 1 <= p <= total]
    if not wanted or wanted == list(range(1, total + 1)):
        # Nothing to trim — drop the prepared file so the original goes out.
        order_file.page_selection = []
        if order_file.final_file:
            order_file.final_file.delete(save=False)
            order_file.final_file = None
        order_file.save(update_fields=["page_selection", "final_file"])
        return []

    trimmed = edit_pdf(content, "split", {"pages": wanted})
    name = _final_name(order_file.file_name)
    order_file.final_file.save(name, ContentFile(trimmed), save=False)
    order_file.page_selection = wanted
    actions = list(order_file.edit_actions or [])
    actions.append({"action": "select_pages", "pages": format_page_selection(wanted)})
    order_file.edit_actions = actions
    order_file.save(update_fields=["final_file", "page_selection", "edit_actions"])
    return wanted


def _edited_name(original: str, extension: str) -> str:
    stem = original.rsplit(".", 1)[0][:180]
    return f"{stem}-edited.{extension}"


def _final_name(original: str) -> str:
    stem = original.rsplit(".", 1)[0][:180]
    return f"{stem}-final.pdf"

