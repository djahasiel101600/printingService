"""Print-area preparation — the last step before a file reaches the printer.

Epson Connect v2 accepts no scaling, orientation, margin or page-range
parameters: the printer reproduces whatever geometry the uploaded file carries.
So the shop has to bake that geometry into the file, and this module is where
it happens:

* **fit** — a page larger than the chosen paper (or a picture of any size) is
  scaled *down* (never up) and centred inside the paper's printable area, so an
  approved job can never be clipped by the sheet or lost to the unprintable
  edge. Borderless printing uses the whole sheet instead of the inset area.
* **orientation** — picture files are rotated 90° for ``landscape`` so they use
  the long side of the sheet; PDFs and Office documents keep their own layout.
* **pages** — only the pages the shop selected survive into the output.

``final_file`` holds the result: ``OrderFile.print_file`` prefers it, so both
direct printing and reprints send exactly this artefact. It is always rebuilt
from the customer's own bytes (``edited_file`` or ``file``), never from a
previous preparation, so changing the paper size or the page selection can
never compound scaling errors.
"""
from __future__ import annotations

import io
import logging

from django.core.files.base import ContentFile
from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject

from . import document_render
from .document_preview import PreviewError
from .file_edits import PAPER_DIMENSIONS, RENDER_DPI, FileEditError, count_pages

log = logging.getLogger(__name__)

# Unprintable edge of a bordered sheet, all round (mm). Inkjet printers cannot
# reach the very edge of the paper; 5 mm is a safe inset that keeps content off
# the rollers on both plain and photo paper.
PRINTABLE_MARGIN_MM = 5.0
MM_PER_INCH = 25.4
POINTS_PER_INCH = 72.0

PREP_ACTION = "prepare"
RENDER_ACTION = "render"


def paper_size_points(media_size: str) -> tuple[float, float]:
    """Sheet size in PDF points (portrait orientation)."""
    return PAPER_DIMENSIONS.get(media_size, PAPER_DIMENSIONS["ps_a4"])


def print_area_points(media_size: str, borderless: bool = False) -> tuple[float, float, float]:
    """(width, height, margin) of the printable area, in PDF points."""
    paper_w, paper_h = paper_size_points(media_size)
    margin = 0.0 if borderless else PRINTABLE_MARGIN_MM / MM_PER_INCH * POINTS_PER_INCH
    # A tiny sheet must still leave room for content.
    margin = min(margin, paper_w / 4, paper_h / 4)
    return paper_w - 2 * margin, paper_h - 2 * margin, margin


def to_millimetres(points: float) -> int:
    return round(points / POINTS_PER_INCH * MM_PER_INCH)


def print_area_label(media_size: str, borderless: bool = False) -> str:
    """Human description used in API responses and audit entries."""
    paper_w, paper_h = paper_size_points(media_size)
    area_w, area_h, _ = print_area_points(media_size, borderless)
    sheet = f"{to_millimetres(paper_w)}×{to_millimetres(paper_h)} mm sheet"
    area = f"{to_millimetres(area_w)}×{to_millimetres(area_h)} mm printable area"
    if borderless:
        return f"Borderless: {sheet}, {area} (no margins)"
    return f"{sheet}, {area} ({PRINTABLE_MARGIN_MM:g} mm margins)"


# --------------------------------------------------------------------- PDF
def fit_pdf(content: bytes, media_size: str, borderless: bool = False) -> bytes:
    """Scale down + centre any page that is bigger than the chosen paper.

    Pages that already fit the sheet are passed through untouched — the printer
    then keeps the document's own margins, and re-running this is a no-op.
    """
    paper_w, paper_h = paper_size_points(media_size)
    area_w, area_h, margin = print_area_points(media_size, borderless)
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001 - surfaced as a clean API error
        raise FileEditError(f"Unreadable PDF: {exc}") from exc

    writer = PdfWriter()
    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if width <= 0 or height <= 0:
            raise FileEditError("This PDF has a page with no dimensions.")
        if width <= paper_w + 0.5 and height <= paper_h + 0.5:
            writer.add_page(page)
            continue
        scale = min(area_w / width, area_h / height)
        offset_x = margin + (area_w - width * scale) / 2
        offset_y = margin + (area_h - height * scale) / 2
        page.add_transformation(Transformation().scale(scale, scale).translate(offset_x, offset_y))
        page.mediabox = RectangleObject([0, 0, paper_w, paper_h])
        writer.add_page(page)
    return _write_pdf(writer)


def select_pdf_pages(content: bytes, pages: list[int]) -> bytes:
    """Keep only ``pages`` (1-based) of a PDF, in ascending order."""
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise FileEditError(f"Unreadable PDF: {exc}") from exc
    total = len(reader.pages)
    wanted = sorted({int(page) for page in pages if 1 <= int(page) <= total})
    if not wanted:
        return content
    writer = PdfWriter()
    for number in wanted:
        writer.add_page(reader.pages[number - 1])
    return _write_pdf(writer)


def _write_pdf(writer: PdfWriter) -> bytes:
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


# ------------------------------------------------------------------- images
def fit_image(
    content: bytes, media_size: str, *, orientation: str = "portrait", borderless: bool = False,
) -> bytes:
    """Place a picture on a paper-sized canvas, inside the printable area.

    The picture is rotated for landscape sheets and only ever scaled *down*, so
    a small photo prints at its own resolution (centred) instead of being blown
    up into a blurry mess, and a huge photo cannot be clipped by the sheet.
    """
    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise FileEditError(f"Unreadable image: {exc}") from exc
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    if orientation == "landscape":
        # 90° clockwise: the picture's long side follows the sheet's long side.
        image = image.transpose(Image.Transpose.ROTATE_270)

    paper_w, paper_h = paper_size_points(media_size)
    area_w, area_h, margin = print_area_points(media_size, borderless)
    scale_dpi = RENDER_DPI / 72.0
    canvas = Image.new("RGB", (round(paper_w * scale_dpi), round(paper_h * scale_dpi)), "white")
    area_px = (area_w * scale_dpi, area_h * scale_dpi)
    factor = min(area_px[0] / image.width, area_px[1] / image.height, 1.0)
    resized = image.resize(
        (max(1, round(image.width * factor)), max(1, round(image.height * factor))), Image.LANCZOS,
    )
    offset = (
        round(margin * scale_dpi + (area_px[0] - resized.width) / 2),
        round(margin * scale_dpi + (area_px[1] - resized.height) / 2),
    )
    canvas.paste(resized, offset)
    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()

    """Human description used in API responses and audit entries."""
    paper_w, paper_h = paper_size_points(media_size)
    area_w, area_h, _ = print_area_points(media_size, borderless)
    sheet = f"{to_millimetres(paper_w)}×{to_millimetres(paper_h)} mm sheet"
    area = f"{to_millimetres(area_w)}×{to_millimetres(area_h)} mm printable area"
    if borderless:
        return f"Borderless: {sheet.split(' sheet')[0]} mm, {area}"
    return f"{sheet}, {area} ({PRINTABLE_MARGIN_MM:g} mm margins)"


# ------------------------------------------------------------ orchestration
def _last_action(order_file, action: str) -> dict | None:
    for entry in reversed(order_file.edit_actions or []):
        if entry.get("action") == action:
            return entry
    return None


def _record_action(order_file, entry: dict) -> None:
    """Append one audit entry, replacing any earlier entry of the same action."""
    actions = [a for a in (order_file.edit_actions or []) if a.get("action") != entry["action"]]
    actions.append(entry)
    order_file.edit_actions = actions


def _prep_params(order_file) -> dict:
    spec = getattr(order_file, "specification", None)
    return {
        "media_size": (getattr(spec, "media_size", "") or "ps_a4"),
        "orientation": (getattr(spec, "orientation", "") or "portrait"),
        "borderless": bool(getattr(spec, "borderless", False)),
        "pages": list(order_file.selected_pages),
    }


def _source_signature(order_file) -> str:
    """Identity of the exact customer bytes a prepared artefact was built from.

    Storage name + size catches a replaced/converted file, the count of
    customer edits catches crop/resize actions, and ``current_version`` catches
    a revision re-upload. Without this a stale ``final_file`` could be printed
    after the customer changed the file.
    """
    field = order_file.edited_file or order_file.file
    customer_edits = sum(
        1 for entry in (order_file.edit_actions or [])
        if entry.get("action") not in (PREP_ACTION, RENDER_ACTION)
    )
    return f"{field.name}|{field.size}|{customer_edits}|{order_file.current_version}"


def rebuild_print_file(order_file) -> bool:
    """(Re)build ``final_file`` for the current paper/selection.

    Returns ``True`` when a print-ready artefact exists afterwards. Documents
    that have not been rendered or converted yet return ``False`` — they stay
    blocked for approval, which is the documented shop workflow.
    """
    if order_file.file_type == "document" and not order_file.edited_file:
        return False

    params = _prep_params(order_file)
    fingerprint = {
        "action": PREP_ACTION,
        **params,
        "source": _source_signature(order_file),
    }
    if order_file.final_file and _last_action(order_file, PREP_ACTION) == fingerprint:
        return True

    source = order_file.edited_file or order_file.file
    source.open("rb")
    try:
        content = source.read()
    finally:
        source.close()

    if order_file.file_type == "image":
        prepared = fit_image(
            content, params["media_size"],
            orientation=params["orientation"], borderless=params["borderless"],
        )
        extension = "jpg"
    else:
        prepared = fit_pdf(content, params["media_size"], params["borderless"])
        if params["pages"]:
            prepared = select_pdf_pages(prepared, params["pages"])
        extension = "pdf"

    name = _prepared_name(order_file.file_name, extension)
    if order_file.final_file:
        order_file.final_file.delete(save=False)
    order_file.final_file.save(name, ContentFile(prepared), save=False)
    _record_action(order_file, fingerprint)
    order_file.save(update_fields=["final_file", "edit_actions"])
    return True


def render_document(order_file) -> int:
    """Render an Office/text upload into a printable PDF of text pages.

    Stores the result as ``edited_file`` (the print source) and refreshes the
    page count so the admin's page picker works on the rendered pagination.
    Returns the number of pages.
    """
    params = _prep_params(order_file)
    with order_file.file.open("rb") as handle:
        content = handle.read()
    try:
        rendered = document_render.render_pdf(order_file.file_name, content, params["media_size"])
    except (PreviewError, document_render.DocumentRenderError) as exc:
        raise FileEditError(str(exc)) from exc

    if order_file.edited_file:
        order_file.edited_file.delete(save=False)
    order_file.edited_file.save(_prepared_name(order_file.file_name, "pdf"),
                                ContentFile(rendered), save=False)
    order_file.page_count = count_pages("pdf", rendered)
    # Pagination changed under the admin's feet, so the old selection is void.
    order_file.page_selection = []
    order_file.rendered_by_admin = True
    _record_action(order_file, {
        "action": RENDER_ACTION, "media_size": params["media_size"], "pages": order_file.page_count,
    })
    order_file.save()
    rebuild_print_file(order_file)
    return order_file.page_count


def prepare_order_for_print(order, order_files=None) -> list:
    """Guarantee every printable file is fitted to its paper before printing.

    Called on approval/reprint (and from the print service itself, which is the
    single choke point for anything sent to Epson), so the "fits inside the
    printable area" rule holds no matter which code path releases a job.
    """
    files = list(order.files.all()) if order_files is None else list(order_files)
    prepared = []
    for order_file in files:
        try:
            if rebuild_print_file(order_file):
                prepared.append(order_file)
        except (FileEditError, OSError, ValueError) as exc:
            # Never block a release on this: log it, and let the job go out
            # with the best artefact available.
            log.warning(
                "Could not prepare '%s' of order %s for printing: %s",
                order_file.file_name, order.tracking_id, exc,
            )
    return prepared


def page_count_for(file_type: str, content: bytes, file_name: str = "", media_size: str = "ps_a4") -> int:
    """Page count for an upload: real pages for PDFs, text pages for documents."""
    if file_type == "pdf":
        return count_pages("pdf", content)
    if file_type == "document":
        try:
            return document_render.page_count(file_name, content, media_size)
        except (PreviewError, document_render.DocumentRenderError) as exc:
            raise FileEditError(str(exc)) from exc
    return 1


def _prepared_name(original: str, extension: str) -> str:
    stem = original.rsplit(".", 1)[0][:180]
    return f"{stem}-print.{extension}"

