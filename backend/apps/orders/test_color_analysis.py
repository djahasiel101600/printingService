"""Visible per-page colour detection and conservative fallbacks."""
import io
from unittest.mock import patch

from django.test import SimpleTestCase
from PIL import Image, ImageDraw
from pypdf import PdfWriter

from .services.color_analysis import (
    analyze_document_pages, analyze_image, analyze_pdf, effective_page_modes,
)


def image_bytes(mode: str = "RGB", *, transparent_color: bool = False) -> bytes:
    image = Image.new(mode, (400, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 120, 120), fill="black")
    if mode == "RGB":
        draw.rectangle((180, 60, 360, 240), fill="tomato")
    else:
        draw.rectangle((180, 60, 360, 240), fill=80)
    if transparent_color:
        image = image.convert("RGBA")
        image.putalpha(Image.new("L", image.size, 255))
        # Fully transparent coloured pixels must not count as visible ink.
        image.paste((255, 0, 255, 0), (0, 0, 400, 300))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def mixed_pdf_bytes() -> bytes:
    writer = PdfWriter()
    for mode in ("L", "RGB"):
        image = Image.new(mode, (612, 792), "white")
        draw = ImageDraw.Draw(image)
        draw.text((72, 72), "Page text", fill="black")
        if mode == "RGB":
            draw.rectangle((100, 200, 400, 500), fill="tomato")
        buffer = io.BytesIO()
        image.save(buffer, format="PDF", resolution=72)
        from pypdf import PdfReader

        writer.add_page(PdfReader(io.BytesIO(buffer.getvalue())).pages[0])
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class ColorAnalyzerTests(SimpleTestCase):
    def test_mixed_pdf_detects_mono_then_color(self):
        result = analyze_pdf(mixed_pdf_bytes())
        self.assertTrue(result["complete"], result["warning"])
        self.assertEqual([page["mode"] for page in result["pages"]], ["mono", "color"])
        self.assertGreaterEqual(result["pages"][1]["max_chroma"], 100)

    def test_grayscale_and_black_images_are_mono(self):
        self.assertEqual(analyze_image(image_bytes("L"))["pages"][0]["mode"], "mono")

    def test_visible_color_image_is_color(self):
        self.assertEqual(analyze_image(image_bytes("RGB"))["pages"][0]["mode"], "color")

    def test_transparent_pixels_do_not_create_false_color(self):
        content = image_bytes("L", transparent_color=True)
        result = analyze_image(content)
        self.assertEqual(result["pages"][0]["mode"], "mono")

    def test_malformed_pdf_falls_back_to_color_for_every_page(self):
        result = analyze_pdf(b"not a PDF", page_count=3)
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["pages"]), 3)
        self.assertTrue(all(page["mode"] == "color" for page in result["pages"]))
        self.assertTrue(all(not page["analyzed"] for page in result["pages"]))
        self.assertIn("treating every page as color", result["warning"])

    def test_one_page_render_failure_does_not_abort_other_pages(self):
        content = mixed_pdf_bytes()
        from pypdfium2 import PdfPage

        original = PdfPage.render
        calls = 0

        def fail_first(page, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("bad page")
            return original(page, *args, **kwargs)

        with patch.object(PdfPage, "render", fail_first):
            result = analyze_pdf(content)
        self.assertFalse(result["complete"])
        self.assertEqual([page["mode"] for page in result["pages"]], ["color", "color"])
        self.assertFalse(result["pages"][0]["analyzed"])
        self.assertTrue(result["pages"][1]["analyzed"])

    def test_large_pdf_page_is_rendered_at_a_bounded_size(self):
        writer = PdfWriter()
        writer.add_blank_page(width=20000, height=20000)
        output = io.BytesIO()
        writer.write(output)
        result = analyze_pdf(output.getvalue())
        self.assertTrue(result["complete"], result["warning"])
        self.assertEqual(result["pages"][0]["mode"], "mono")

    def test_documents_are_mono_and_effective_modes_honor_overrides(self):
        analysis = analyze_document_pages(3)
        self.assertTrue(analysis["complete"])
        self.assertEqual(analysis["warning"], "")
        self.assertEqual([page["mode"] for page in analysis["pages"]], ["mono"] * 3)

        class FileStub:
            page_count = 3
            selected_pages = [1, 3]
            color_analysis = {
                "pages": [
                    {"page": 1, "mode": "mono"},
                    {"page": 2, "mode": "color"},
                    {"page": 3, "mode": "mono"},
                ],
            }
            color_page_overrides = {"1": "color"}

        class SpecStub:
            color_mode = "auto"

        self.assertEqual(
            effective_page_modes(FileStub(), SpecStub()),
            [(1, "color"), (3, "mono")],
        )

    def test_missing_detection_defaults_to_color_in_auto_mode(self):
        class FileStub:
            page_count = 1
            selected_pages = []
            color_analysis = {}
            color_page_overrides = {}

        class SpecStub:
            color_mode = "auto"

        self.assertEqual(effective_page_modes(FileStub(), SpecStub()), [(1, "color")])
