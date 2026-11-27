"""Per-page visible-colour analysis for PDF and image uploads.

The printer applies ``colorMode`` to an entire Epson job, so the shop needs a
per-page classification before it can price or split a mixed document. This
module renders one page at a time and measures visible chroma. Black text,
gray tables, and grayscale scans therefore remain mono without relying on the
PDF's internal operators or colour-space declarations.
"""
from __future__ import annotations

import hashlib
import io
import logging
import math
import time

import pypdfium2 as pdfium
from PIL import Image, ImageChops

log = logging.getLogger(__name__)

ANALYSIS_VERSION = 1
ANALYSIS_DPI = 100
CHROMA_THRESHOLD = 32
MIN_COLOR_PIXELS = 40
MIN_COLOR_RATIO = 0.0001
MAX_ANALYSIS_PAGES = 150
MAX_ANALYSIS_SECONDS = 8.0
MAX_RENDER_PIXELS = 4_000_000


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _page_result(page: int, mode: str, *, analyzed: bool = True,
                 color_ratio: float = 0.0, max_chroma: int = 0,
                 confidence: str = "high") -> dict:
    return {
        "page": page,
        "mode": mode,
        "analyzed": analyzed,
        "color_ratio": round(color_ratio, 6),
        "max_chroma": max_chroma,
        "confidence": confidence,
    }


def _image_stats(image: Image.Image) -> dict:
    """Return chroma statistics without bringing NumPy into the backend."""
    if "A" in image.getbands() or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        rgb = background.convert("RGB")
    else:
        rgb = image.convert("RGB")
    pixels = rgb.width * rgb.height
    if pixels > MAX_RENDER_PIXELS:
        scale = math.sqrt(MAX_RENDER_PIXELS / pixels)
        size = (max(1, round(rgb.width * scale)), max(1, round(rgb.height * scale)))
        rgb = rgb.resize(size, Image.Resampling.LANCZOS)
        pixels = rgb.width * rgb.height

    red, green, blue = rgb.split()
    chroma = ImageChops.lighter(ImageChops.difference(red, green),
                                ImageChops.difference(red, blue))
    chroma = ImageChops.lighter(chroma, ImageChops.difference(green, blue))
    mask = chroma.point(lambda value: 255 if value >= CHROMA_THRESHOLD else 0)
    colored_pixels = sum(mask.histogram()[1:])
    color_ratio = colored_pixels / pixels if pixels else 0.0
    max_chroma = chroma.getextrema()[1]
    minimum = max(MIN_COLOR_PIXELS, math.ceil(MIN_COLOR_RATIO * pixels))
    is_color = colored_pixels >= minimum
    if is_color:
        confidence = "high" if color_ratio >= 0.005 else (
            "medium" if color_ratio >= 0.001 else "low"
        )
    else:
        confidence = "medium" if max_chroma >= CHROMA_THRESHOLD else "high"
    return {
        "mode": "color" if is_color else "mono",
        "analyzed": True,
        "color_ratio": color_ratio,
        "max_chroma": max_chroma,
        "confidence": confidence,
    }


def analyze_image(content: bytes, *, source: str = "") -> dict:
    result = {
        "version": ANALYSIS_VERSION,
        "dpi": ANALYSIS_DPI,
        "source": source or content_hash(content),
        "pages": [],
        "complete": True,
        "warning": "",
    }
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            stats = _image_stats(image)
        result["pages"] = [_page_result(1, **stats)]
    except Exception as exc:  # noqa: BLE001 - uncertain pages are conservatively colour
        log.warning("Could not analyse an image for page colour: %s", exc, exc_info=True)
        result["pages"] = [_page_result(
            1, "color", analyzed=False, confidence="low",
        )]
        result["complete"] = False
        result["warning"] = f"Image analysis failed; treating the page as color. {exc}"
    return result


def analyze_pdf(content: bytes, *, source: str = "", page_count: int = 1) -> dict:
    result = {
        "version": ANALYSIS_VERSION,
        "dpi": ANALYSIS_DPI,
        "source": source or content_hash(content),
        "pages": [],
        "complete": True,
        "warning": "",
    }
    started = time.monotonic()
    document = None
    try:
        document = pdfium.PdfDocument(content)
        total = max(1, len(document))
        result["pages"] = []
        limit = min(total, MAX_ANALYSIS_PAGES)
        for index in range(limit):
            if index and time.monotonic() - started >= MAX_ANALYSIS_SECONDS:
                break
            page = document[index]
            try:
                width = max(1.0, page.get_width())
                height = max(1.0, page.get_height())
                scale = min(
                    ANALYSIS_DPI / 72.0,
                    math.sqrt(MAX_RENDER_PIXELS / (width * height)),
                )
                bitmap = page.render(scale=scale, may_draw_forms=True)
                try:
                    stats = _image_stats(bitmap.to_pil())
                finally:
                    bitmap.close()
                result["pages"].append(_page_result(index + 1, **stats))
            except Exception as exc:  # noqa: BLE001 - one bad page must not abort the scan
                log.warning("Could not analyse PDF page %s: %s", index + 1, exc, exc_info=True)
                result["pages"].append(_page_result(
                    index + 1, "color", analyzed=False, confidence="low",
                ))
                result["complete"] = False
                result["warning"] = f"Some PDF pages could not be analysed and were treated as color. {exc}"
            finally:
                page.close()

        if len(result["pages"]) < total:
            result["complete"] = False
            result["warning"] = (
                f"Analysis stopped after {len(result['pages'])} of {total} pages; "
                "remaining pages are treated as color."
            )
            for number in range(len(result["pages"]) + 1, total + 1):
                result["pages"].append(_page_result(number, "color", analyzed=False, confidence="low"))
    except Exception as exc:  # noqa: BLE001 - encrypted or malformed PDFs use the safe fallback
        log.warning("Could not analyse PDF for page colour: %s", exc, exc_info=True)
        total = max(1, int(page_count or 1))
        result["pages"] = [
            _page_result(number, "color", analyzed=False, confidence="low")
            for number in range(1, total + 1)
        ]
        result["complete"] = False
        result["warning"] = f"PDF analysis failed; treating every page as color. {exc}"
    finally:
        if document is not None:
            document.close()
    return result


def analyze_document_pages(page_count: int, *, source: str = "") -> dict:
    """Office/text uploads are rendered locally as monochrome pages."""
    total = max(1, int(page_count or 1))
    return {
        "version": ANALYSIS_VERSION,
        "dpi": ANALYSIS_DPI,
        "source": source,
        "pages": [_page_result(number, "mono") for number in range(1, total + 1)],
        "complete": True,
        "warning": "",
        "note": "Office and text documents are rendered in black and white.",
    }


def _read_source(order_file) -> bytes:
    field = order_file.edited_file or order_file.file
    field.open("rb")
    try:
        return field.read()
    finally:
        field.close()


def ensure_order_file_analysis(order_file, *, force: bool = False) -> dict:
    """Analyze and persist the current source bytes, clearing stale overrides."""
    current = order_file.color_analysis or {}
    if order_file.file_type == OrderFileTypes.DOCUMENT and not order_file.edited_file:
        source = f"document:{order_file.current_version}"
        if (
            not force
            and current.get("version") == ANALYSIS_VERSION
            and current.get("source") == source
            and len(current.get("pages") or []) == max(1, order_file.page_count)
        ):
            return current
        result = analyze_document_pages(order_file.page_count, source=source)
        if current.get("source") not in (None, "", source):
            order_file.color_page_overrides = {}
    else:
        content = _read_source(order_file)
        digest = content_hash(content)
        if (
            not force
            and current.get("version") == ANALYSIS_VERSION
            and current.get("source") == digest
            and len(current.get("pages") or []) == max(1, order_file.page_count)
        ):
            return current
        if order_file.file_type == OrderFileTypes.IMAGE:
            result = analyze_image(content, source=digest)
        else:
            result = analyze_pdf(
                content, source=digest, page_count=order_file.page_count,
            )
        if current.get("source") not in (None, "", digest):
            order_file.color_page_overrides = {}

    order_file.color_analysis = result
    order_file.save(update_fields=["color_analysis", "color_page_overrides"])
    return result


class OrderFileTypes:
    """String constants kept here to avoid importing models and creating a cycle."""
    PDF = "pdf"
    IMAGE = "image"
    DOCUMENT = "document"


def effective_page_modes(order_file, spec=None) -> list[tuple[int, str]]:
    """Return the selected output-page order with its concrete print mode."""
    selected = order_file.selected_pages or list(range(1, max(1, order_file.page_count) + 1))
    spec = spec or getattr(order_file, "specification", None)
    requested = getattr(spec, "color_mode", "mono") or "mono"
    if requested != "auto":
        mode = requested if requested in ("color", "mono") else "mono"
        return [(page, mode) for page in selected]

    analysis = order_file.color_analysis or {}
    detected = {}
    for entry in analysis.get("pages") or []:
        if not isinstance(entry, dict) or entry.get("page") is None:
            continue
        try:
            detected[int(entry["page"])] = entry.get("mode")
        except (TypeError, ValueError):
            continue
    overrides = order_file.color_page_overrides or {}
    modes = []
    for page in selected:
        override = overrides.get(str(page), overrides.get(page))
        mode = override or detected.get(page) or "color"
        modes.append((page, mode if mode in ("color", "mono") else "color"))
    return modes
