"""Print-area preparation: fit-to-paper, orientation, document page selection.

Covers the three print-preparation guarantees:

1. every file released to the printer fits inside the chosen paper's printable
   area (never clipped, never enlarged),
2. picture files honour the Portrait/Landscape orientation setting,
3. Word/Office/text documents have real pages the shop can select from — and
   can therefore be prepared and approved like any other upload.
"""
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageChops
from pypdf import PdfReader, PdfWriter

from apps.orders.services.print_prep import (
    PRINTABLE_MARGIN_MM, fit_image, fit_pdf, print_area_points,
)

from .test_admin_review import AdminReviewTestCase, make_docx, make_pdf

A4_W, A4_H = 595.28, 841.89
A4_PX = (round(A4_W / 72 * 150), round(A4_H / 72 * 150))   # 1240 × 1754 @150dpi


def sized_pdf(width: float, height: float, pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=width, height=height)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def sized_image(width: int, height: int, colour="tomato") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def content_bbox(image: Image.Image, threshold: int = 24) -> tuple | None:
    """Bounding box of the non-white content (JPEG noise is below threshold)."""
    white = Image.new("RGB", image.size, "white")
    difference = ImageChops.difference(image.convert("RGB"), white).convert("L")
    mask = difference.point(lambda pixel: 255 if pixel > threshold else 0)
    return mask.getbbox()


def pdf_bytes(response) -> PdfReader:
    payload = b"".join(response.streaming_content)
    return PdfReader(io.BytesIO(payload))


def jpeg(response) -> Image.Image:
    payload = b"".join(response.streaming_content)
    image = Image.open(io.BytesIO(payload))
    image.load()
    return image


class PrintAreaUnitTests(AdminReviewTestCase):
    """Pure geometry checks — no HTTP round trips."""

    def test_print_area_inset_is_the_unprintable_edge(self):
        area_w, area_h, margin = print_area_points("ps_a4")
        self.assertAlmostEqual(margin, 5 / 25.4 * 72, places=2)      # 5 mm
        self.assertAlmostEqual(area_w, A4_W - 2 * margin, places=2)
        self.assertAlmostEqual(area_h, A4_H - 2 * margin, places=2)

    def test_borderless_print_area_is_the_whole_sheet(self):
        area_w, area_h, margin = print_area_points("ps_a4", borderless=True)
        self.assertEqual(margin, 0.0)
        self.assertAlmostEqual(area_w, A4_W, places=2)
        self.assertAlmostEqual(area_h, A4_H, places=2)

    def test_small_image_is_centred_and_never_enlarged(self):
        fitted = fit_image(sized_image(400, 300), "ps_a4")
        canvas = Image.open(io.BytesIO(fitted))
        canvas.load()
        self.assertEqual(canvas.size, A4_PX)
        bbox = content_bbox(canvas)
        self.assertIsNotNone(bbox)
        left, top, right, bottom = bbox
        # 400×300 stays 400×300 (scaled down only), inside the printable area.
        self.assertLessEqual(abs((right - left) - 400), 4)
        self.assertLessEqual(abs((bottom - top) - 300), 4)
        area_w, area_h, margin = print_area_points("ps_a4")
        margin_px = margin / 72 * 150
        self.assertGreaterEqual(left, margin_px - 2)
        self.assertGreaterEqual(top, margin_px - 2)
        self.assertLessEqual(right, canvas.width - margin_px + 2)
        self.assertLessEqual(bottom, canvas.height - margin_px + 2)

    def test_oversized_image_is_scaled_down_into_the_printable_area(self):
        fitted = fit_image(sized_image(3000, 4000), "ps_a4")
        canvas = Image.open(io.BytesIO(fitted))
        canvas.load()
        self.assertEqual(canvas.size, A4_PX)
        left, top, right, bottom = content_bbox(canvas)
        area_w, area_h, margin = print_area_points("ps_a4")
        margin_px = margin / 72 * 150
        self.assertGreaterEqual(left, margin_px - 2)
        self.assertGreaterEqual(top, margin_px - 2)
        self.assertLessEqual(right, canvas.width - margin_px + 2)
        self.assertLessEqual(bottom, canvas.height - margin_px + 2)
        # Shrink-wrapped to the printable width, not the raw 3000 px.
        self.assertLess(right - left, 3000)

    def test_oversized_pdf_page_is_scaled_onto_the_paper(self):
        fitted = fit_pdf(sized_pdf(1200, 1600), "ps_a4")
        page = PdfReader(io.BytesIO(fitted)).pages[0]
        self.assertLessEqual(float(page.mediabox.width), A4_W + 1)
        self.assertLessEqual(float(page.mediabox.height), A4_H + 1)
        # After a real fit the page *is* the paper.
        self.assertAlmostEqual(float(page.mediabox.width), A4_W, delta=1)
        self.assertAlmostEqual(float(page.mediabox.height), A4_H, delta=1)

    def test_pdf_that_already_fits_is_left_alone(self):
        content = sized_pdf(500, 700)
        fitted = fit_pdf(content, "ps_a4")
        source = PdfReader(io.BytesIO(content)).pages[0]
        result = PdfReader(io.BytesIO(fitted)).pages[0]
        # Same geometry: no scaling means no needless resampling of the content.
        self.assertAlmostEqual(float(result.mediabox.width), float(source.mediabox.width), places=1)
        self.assertAlmostEqual(float(result.mediabox.height), float(source.mediabox.height), places=1)


class PrepareOnApprovalTests(AdminReviewTestCase):
    """Requirement: everything approved for print fits the selected paper."""

    def spec_id(self, order: dict, index: int = 0) -> int:
        return order["files"][index]["specification"]["id"]

    def prepare(self, order: dict, index: int = 0, **fields):
        return self.api.patch(
            f"/api/admin/orders/{order['id']}/specs/{self.spec_id(order, index)}/",
            fields, format="json",
        )

    def final_jpeg(self, order: dict, file_id: int) -> Image.Image:
        response = self.api.get(self.preview_url(order, file_id, "?variant=final"))
        # FileResponse streams — no .content, so assert on the status only.
        self.assertEqual(response.status_code, 200)
        return jpeg(response)

    def test_changing_the_paper_size_rebuilds_the_prepared_file(self):
        order = self.submit([SimpleUploadedFile("photo.png", sized_image(3000, 4000),
                                                content_type="image/png")])
        file_id = order["files"][0]["id"]
        response = self.prepare(order, media_size="ps_a5")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["files"][0]["has_final_file"])

        # A5 canvas, content inside A5's printable area.
        a5_w, a5_h = 419.53, 595.28
        canvas = self.final_jpeg(order, file_id)
        self.assertEqual(canvas.size, (round(a5_w / 72 * 150), round(a5_h / 72 * 150)))
        left, top, right, bottom = content_bbox(canvas)
        margin_px = PRINTABLE_MARGIN_MM / 25.4 * 72 / 72 * 150
        self.assertGreaterEqual(left, margin_px - 2)
        self.assertGreaterEqual(top, margin_px - 2)
        self.assertLess(right, canvas.width - margin_px + 3)
        self.assertLess(bottom, canvas.height - margin_px + 3)

    def test_approve_fits_every_file_before_releasing(self):
        order = self.submit([
            SimpleUploadedFile("huge.png", sized_image(3000, 4000), content_type="image/png"),
            SimpleUploadedFile("wide.pdf", sized_pdf(1200, 1600), content_type="application/pdf"),
        ])
        self.pay(order)
        response = self.act(order, "approve")
        self.assertEqual(response.status_code, 200, response.content)

        for entry in response.json()["files"]:
            self.assertTrue(entry["has_final_file"], entry["file_name"])
        # Image: paper-sized canvas.
        image = self.final_jpeg(order, order["files"][0]["id"])
        self.assertEqual(image.size, A4_PX)
        # PDF: page scaled onto A4.
        reader = pdf_bytes(self.api.get(
            self.preview_url(order, order["files"][1]["id"], "?variant=final")))
        self.assertAlmostEqual(float(reader.pages[0].mediabox.width), A4_W, delta=1)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.height), A4_H, delta=1)

    def test_borderless_lets_content_reach_the_sheet_edge(self):
        # A4-ratio source (2480×3508 = A4 @300dpi) so the fill reaches all
        # four edges instead of being letterboxed by the aspect mismatch.
        order = self.submit([SimpleUploadedFile("photo.png", sized_image(2480, 3508),
                                                content_type="image/png")])
        self.prepare(order, media_size="ps_a4", borderless=True)
        canvas = self.final_jpeg(order, order["files"][0]["id"])
        left, top, right, bottom = content_bbox(canvas)
        # No 5 mm inset: the content runs to within a couple of pixels.
        self.assertLess(left, 6)
        self.assertLess(top, 6)
        self.assertGreater(right, canvas.width - 6)
        self.assertGreater(bottom, canvas.height - 6)


class OrientationTests(AdminReviewTestCase):
    """Picture files can be printed Portrait or Landscape (PRD §1.2)."""

    def prepare(self, order: dict, **fields):
        spec_id = order["files"][0]["specification"]["id"]
        return self.api.patch(f"/api/admin/orders/{order['id']}/specs/{spec_id}/",
                              fields, format="json")

    def final_canvas(self, order: dict) -> Image.Image:
        response = self.api.get(
            self.preview_url(order, order["files"][0]["id"], "?variant=final"))
        # FileResponse streams — no .content, so assert on the status only.
        self.assertEqual(response.status_code, 200)
        return jpeg(response)

    def test_portrait_leaves_the_picture_upright(self):
        order = self.submit([SimpleUploadedFile("shot.png", sized_image(400, 300),
                                                content_type="image/png")])
        response = self.prepare(order, orientation="portrait")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["files"][0]["specification"]["orientation"], "portrait")
        left, top, right, bottom = content_bbox(self.final_canvas(order))
        self.assertGreater(right - left, bottom - top)   # 400 wide vs 300 tall

    def test_landscape_rotates_the_picture_to_use_the_long_side(self):
        order = self.submit([SimpleUploadedFile("shot.png", sized_image(400, 300),
                                                content_type="image/png")])
        response = self.prepare(order, orientation="landscape")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["files"][0]["specification"]["orientation"], "landscape")
        canvas = self.final_canvas(order)
        left, top, right, bottom = content_bbox(canvas)
        # Rotated 90°: the picture stands on its end — and stays on the sheet.
        self.assertGreater(bottom - top, right - left)
        margin_px = PRINTABLE_MARGIN_MM / 25.4 * 72 / 72 * 150
        self.assertGreaterEqual(left, margin_px - 2)
        self.assertLess(bottom, canvas.height - margin_px + 3)

    def test_orientation_is_stored_but_pdfs_keep_their_own_layout(self):
        """Orientation only applies to picture files."""
        order = self.submit([SimpleUploadedFile("report.pdf", make_pdf(2),
                                                content_type="application/pdf")])
        response = self.prepare(order, orientation="landscape")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["files"][0]["specification"]["orientation"], "landscape")
        final = self.api.get(self.preview_url(order, order["files"][0]["id"], "?variant=final"))
        page = pdf_bytes(final).pages[0]
        # The sheet stays A4 portrait — a PDF's own page layout is untouched.
        self.assertAlmostEqual(float(page.mediabox.width), A4_W, delta=1)
        self.assertAlmostEqual(float(page.mediabox.height), A4_H, delta=1)
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class DocumentPageSelectionTests(AdminReviewTestCase):
    """Word/Office documents gain real pages the shop can choose from."""

    def long_docx(self) -> SimpleUploadedFile:
        paragraphs = [
            f"Paragraph {index}: " + "lorem ipsum dolor sit amet consectetur " * 5
            for index in range(120)
        ]
        return SimpleUploadedFile("essay.docx", make_docx(paragraphs),
                                  content_type=DOCX_CONTENT_TYPE)

    def test_documents_report_their_rendered_page_count(self):
        order = self.submit([self.long_docx()])
        self.assertGreater(order["files"][0]["page_count"], 1)

    def test_pages_of_a_word_document_can_be_selected(self):
        order = self.submit([self.long_docx()])
        order_file = order["files"][0]
        total = order_file["page_count"]

        response = self.api.patch(self.pages_url(order, order_file["id"]),
                                  {"pages": [2]}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        updated = response.json()["order"]["files"][0]
        self.assertEqual(updated["selected_pages"], [2])
        self.assertTrue(updated["page_selection_active"])
        self.assertTrue(updated["rendered_by_admin"])
        self.assertEqual(response.json()["label"], f"2 of {total} pages")
        # The render made it printable without the shop converting it by hand.
        self.assertTrue(updated["print_ready"])

        final = self.api.get(self.preview_url(order, order_file["id"], "?variant=final"))
        reader = pdf_bytes(final)
        self.assertEqual(len(reader.pages), 1)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.width), A4_W, delta=1)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.height), A4_H, delta=1)

    def test_clearing_the_selection_keeps_the_whole_rendered_document(self):
        order = self.submit([self.long_docx()])
        order_file = order["files"][0]
        total = order_file["page_count"]
        response = self.api.patch(self.pages_url(order, order_file["id"]),
                                  {"pages": []}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        updated = response.json()["order"]["files"][0]
        self.assertEqual(updated["selected_pages"], [])
        self.assertTrue(updated["print_ready"])
        final = self.api.get(self.preview_url(order, order_file["id"], "?variant=final"))
        self.assertEqual(len(pdf_bytes(final).pages), total)

    def test_selecting_pages_unblocks_approval_for_a_document(self):
        from apps.orders.models import Order

        order = self.submit([self.long_docx()])
        self.pay(order)
        # Not printable yet: the printer cannot take a raw .docx.
        self.assertEqual(self.act(order, "approve").status_code, 409)

        pages = self.api.patch(self.pages_url(order, order["files"][0]["id"]),
                               {"pages": [1, 2]}, format="json")
        self.assertEqual(pages.status_code, 200, pages.content)
        self.assertEqual(self.act(order, "approve").status_code, 200)
        self.assertIn(Order.objects.get(pk=order["id"]).status,
                      (Order.Status.APPROVED_QUEUED, Order.Status.PRINTING,
                       Order.Status.ON_HOLD))

