"""Admin file-review tests: preview, page selection, reprint, printer cancel.

Split out from tests.py because the admin review surface (PRD §4.2) has grown
into its own feature area: the admin inspects uploads, chooses which pages
print, and recovers failed or printer-cancelled jobs.
"""
import io
import json
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from pypdf import PdfReader, PdfWriter

from apps.orders.models import Order
from apps.pricing.models import PriceRule

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
BASE_SPEC = {
    "media_size": "ps_a4", "media_type": "pt_plainpaper", "color_mode": "mono",
    "print_quality": "normal", "sides": "none", "copies": 1,
}


def make_pdf(pages: int = 3) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def make_image() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), "tomato").save(buffer, format="PNG")
    return buffer.getvalue()


def make_docx(paragraphs: list[str]) -> bytes:
    """Minimal but valid .docx (a ZIP holding word/document.xml)."""
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


class AdminReviewTestCase(TestCase):
    """Shared fixtures: a signed-in shop admin plus small order helpers."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        User.objects.create_user(
            username="reviewer@print.local", email="reviewer@print.local",
            password="review1234", role=User.Role.ADMIN, is_staff=True,
        )
        PriceRule.objects.create(media_size="ps_a4", media_type="pt_plainpaper",
                                 color_mode="mono", print_quality="normal",
                                 price_per_page=300)
        self.api = APIClient()
        login = self.api.post("/api/auth/token/", {
            "email": "reviewer@print.local", "password": "review1234"}, format="json")
        self.assertEqual(login.status_code, 200, login.content)
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")

    def submit(self, uploads, spec=None) -> dict:
        response = self.api.post("/api/orders/", {
            "files": uploads,
            "guest_name": "Ana Reyes",
            "guest_contact_method": "email",
            "guest_contact_value": "ana@example.com",
            "spec": json.dumps(spec or BASE_SPEC),
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["order"]

    def order_with_pdf(self, pages: int = 5, copies: int = 1) -> dict:
        return self.submit(
            [SimpleUploadedFile("report.pdf", make_pdf(pages), content_type="application/pdf")],
            spec={**BASE_SPEC, "copies": copies},
        )

    def order_with_docx(self) -> dict:
        return self.submit([SimpleUploadedFile(
            "essay.docx", make_docx(["Title Page", "Body paragraph"]),
            content_type=DOCX_CONTENT_TYPE)])

    def pay(self, order: dict) -> None:
        checkout = self.api.post("/api/payments/checkout/", {
            "order_id": order["id"], "method": "qrph",
            "payment_type": "full"}, format="json")
        # Checkout creates a Payment row, so DRF answers 201.
        self.assertIn(checkout.status_code, (200, 201), checkout.content)
        self.api.post("/api/payments/webhook/simulate/",
                      {"payment_id": checkout.json()["payment_id"]}, format="json")

    def act(self, order: dict, action: str, payload=None):
        return self.api.post(f"/api/admin/orders/{order['id']}/actions/{action}/",
                             payload or {}, format="json")

    def pages_url(self, order: dict, file_id: int) -> str:
        return f"/api/admin/orders/{order['id']}/files/{file_id}/pages/"

    def preview_url(self, order: dict, file_id: int, query: str = "") -> str:
        return f"/api/orders/{order['id']}/files/{file_id}/preview/{query}"

    def read_pdf(self, response, pages: int) -> None:
        """FileResponse streams — join it before handing bytes to pypdf."""
        payload = b"".join(response.streaming_content)
        self.assertEqual(len(PdfReader(io.BytesIO(payload)).pages), pages)


class AdminQueueTests(AdminReviewTestCase):
    def test_admin_orders_list_serialises_every_status_tab(self):
        """Regression: the admin queue 500'd on every tab (missing columns)."""
        order = self.order_with_pdf()
        self.pay(order)
        for status in ("pending_review", "revision_requested", "approved_queued",
                       "printing", "on_hold", "printed_ready", "print_cancelled",
                       "completed"):
            response = self.api.get("/api/admin/orders/", {"status": status})
            self.assertEqual(response.status_code, 200, f"{status}: {response.content}")
            self.assertIsInstance(response.json(), list)
        unfiltered = self.api.get("/api/admin/orders/")
        self.assertEqual(unfiltered.status_code, 200, unfiltered.content)
        detail = self.api.get(f"/api/admin/orders/{order['id']}/")
        self.assertEqual(detail.status_code, 200, detail.content)

    def test_print_jobs_sync_endpoint(self):
        order = self.order_with_pdf()
        self.pay(order)
        self.assertEqual(self.act(order, "approve").status_code, 200)
        sync = self.api.post("/api/admin/print-jobs/", {}, format="json")
        self.assertEqual(sync.status_code, 200, sync.content)

    def test_admin_notes_are_saved(self):
        order = self.order_with_pdf()
        response = self.api.patch(f"/api/admin/orders/{order['id']}/notes/",
                                  {"admin_notes": "Customer asked for thicker paper."},
                                  format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["admin_notes"],
                         "Customer asked for thicker paper.")


class PageSelectionTests(AdminReviewTestCase):
    def test_selection_trims_the_pdf_and_requotes_the_order(self):
        order = self.order_with_pdf(pages=5)
        order_file = order["files"][0]
        full_price = order["subtotal_peso"]

        response = self.api.patch(self.pages_url(order, order_file["id"]),
                                  {"pages": [1, 2, 5]}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["selected_pages"], [1, 2, 5])
        self.assertEqual(body["label"], "1-2, 5 of 5 pages")

        # Only the surviving pages are charged for.
        self.assertEqual(body["order"]["subtotal_peso"], 3 * 300 / 100)
        self.assertLess(body["order"]["subtotal_peso"], full_price)

        updated = body["order"]["files"][0]
        self.assertTrue(updated["has_final_file"])
        self.assertTrue(updated["page_selection_active"])
        self.assertTrue(updated["print_ready"])
        self.assertEqual(updated["selected_page_count"], 3)

        # What actually reaches the printer is the trimmed file.
        final = self.api.get(self.preview_url(order, order_file["id"], "?variant=final"))
        self.assertEqual(final.status_code, 200)
        self.read_pdf(final, 3)

    def test_clearing_the_selection_restores_the_whole_document(self):
        order = self.order_with_pdf(pages=4)
        order_file = order["files"][0]
        self.api.patch(self.pages_url(order, order_file["id"]),
                       {"pages": [2]}, format="json")
        cleared = self.api.patch(self.pages_url(order, order_file["id"]),
                                 {"pages": []}, format="json")
        self.assertEqual(cleared.status_code, 200, cleared.content)
        restored = cleared.json()["order"]["files"][0]
        self.assertEqual(restored["selected_pages"], [])
        self.assertFalse(restored["has_final_file"])
        self.assertFalse(restored["page_selection_active"])
        self.assertEqual(restored["page_selection_label"], "All 4 pages")

    def test_selecting_every_page_matches_selecting_none(self):
        order = self.order_with_pdf(pages=3)
        order_file = order["files"][0]
        response = self.api.patch(self.pages_url(order, order_file["id"]),
                                  {"pages": [1, 2, 3]}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        updated = response.json()["order"]["files"][0]
        self.assertEqual(updated["selected_pages"], [])
        self.assertFalse(updated["page_selection_active"])

    def test_selection_is_rejected_for_non_pdfs(self):
        order = self.submit([SimpleUploadedFile("shot.png", make_image(),
                                                content_type="image/png")])
        response = self.api.patch(self.pages_url(order, order["files"][0]["id"]),
                                  {"pages": [1]}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_out_of_range_and_non_numeric_pages(self):
        order = self.order_with_pdf(pages=2)
        order_file = order["files"][0]
        response = self.api.patch(self.pages_url(order, order_file["id"]),
                                  {"pages": [1, 99]}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["selected_pages"], [1])
        bad = self.api.patch(self.pages_url(order, order_file["id"]),
                             {"pages": ["one"]}, format="json")
        self.assertEqual(bad.status_code, 400)


class DocumentHandlingTests(AdminReviewTestCase):
    def test_document_can_be_read_before_it_can_be_printed(self):
        order = self.order_with_docx()
        order_file = order["files"][0]
        self.assertEqual(order_file["file_type"], "document")
        self.assertFalse(order_file["print_ready"])

        contents = self.api.get(
            f"/api/orders/{order['id']}/files/{order_file['id']}/contents/")
        self.assertEqual(contents.status_code, 200, contents.content)
        self.assertEqual(contents.json()["kind"], "document")
        texts = [b["text"] for b in contents.json()["blocks"]]
        self.assertIn("Title Page", texts)
        self.assertIn("Body paragraph", texts)

    def test_approval_is_blocked_until_the_document_is_converted(self):
        order = self.order_with_docx()
        self.pay(order)
        approve = self.act(order, "approve")
        self.assertEqual(approve.status_code, 409)
        self.assertIn("essay.docx", approve.json()["detail"])
        self.assertEqual(Order.objects.get(pk=order["id"]).status,
                         Order.Status.PENDING_REVIEW)

    def test_reprint_is_also_blocked_for_unconverted_documents(self):
        order = self.order_with_docx()
        self.pay(order)
        self.assertEqual(self.act(order, "reprint").status_code, 409)

    def test_shop_replaces_a_document_with_a_converted_pdf(self):
        order = self.order_with_docx()
        order_file = order["files"][0]
        self.pay(order)

        replaced = self.api.post(
            f"/api/admin/orders/{order['id']}/files/{order_file['id']}/replace/",
            {"file": SimpleUploadedFile("essay.pdf", make_pdf(4),
                                        content_type="application/pdf")},
            format="multipart")
        self.assertEqual(replaced.status_code, 200, replaced.content)
        updated = replaced.json()["files"][0]
        self.assertEqual(updated["file_type"], "pdf")
        self.assertTrue(updated["print_ready"])
        self.assertTrue(updated["replaced_by_admin"])
        self.assertEqual(updated["page_count"], 4)
        self.assertTrue(any("converted PDF" in h["note"] for h in replaced.json()["history"]))
        self.assertEqual(self.act(order, "approve").status_code, 200)

    def test_replacement_rejects_an_unprintable_upload(self):
        order = self.order_with_docx()
        response = self.api.post(
            f"/api/admin/orders/{order['id']}/files/{order['files'][0]['id']}/replace/",
            {"file": SimpleUploadedFile("again.docx", make_docx(["x"]),
                                        content_type=DOCX_CONTENT_TYPE)},
            format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_unsupported_format_is_refused_at_upload(self):
        response = self.api.post("/api/orders/", {
            "files": [SimpleUploadedFile("legacy.doc", b"\xd0\xcf\x11\xe0",
                                         content_type="application/msword")],
            "guest_name": "Ana Reyes", "guest_contact_method": "email",
            "guest_contact_value": "ana@example.com", "spec": json.dumps(BASE_SPEC),
        }, format="multipart")
        self.assertEqual(response.status_code, 400)


class PreviewTests(AdminReviewTestCase):
    def test_variants_and_download_disposition(self):
        order = self.order_with_pdf(pages=3)
        order_file = order["files"][0]
        self.api.patch(self.pages_url(order, order_file["id"]),
                       {"pages": [2]}, format="json")

        original = self.api.get(self.preview_url(order, order_file["id"], "?variant=original"))
        self.assertEqual(original.status_code, 200)
        self.assertEqual(original["Content-Type"], "application/pdf")
        self.assertIn("inline", original["Content-Disposition"])
        self.read_pdf(original, 3)

        final = self.api.get(self.preview_url(order, order_file["id"], "?variant=final"))
        self.read_pdf(final, 1)

        download = self.api.get(self.preview_url(order, order_file["id"], "?download=1"))
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download["Content-Disposition"])

    def test_unknown_variant_is_rejected(self):
        order = self.order_with_pdf()
        response = self.api.get(self.preview_url(order, order["files"][0]["id"],
                                                 "?variant=nope"))
        self.assertEqual(response.status_code, 400)

    def test_guest_preview_requires_the_tracking_id(self):
        order = self.order_with_pdf()
        file_id = order["files"][0]["id"]
        self.assertEqual(
            self.client.get(f"/api/orders/{order['id']}/files/{file_id}/preview/").status_code,
            403)
        allowed = self.client.get(
            f"/api/orders/{order['id']}/files/{file_id}/preview/"
            f"?tracking_id={order['tracking_id']}")
        self.assertEqual(allowed.status_code, 200)


class ReprintTests(AdminReviewTestCase):
    def approved_order(self) -> dict:
        order = self.order_with_pdf(pages=2)
        self.pay(order)
        self.assertEqual(self.act(order, "approve").status_code, 200)
        return order

    def test_reprint_creates_tagged_jobs_and_bumps_the_counter(self):
        order = self.approved_order()
        reprint = self.act(order, "reprint", {"note": "Faded output"})
        self.assertEqual(reprint.status_code, 200, reprint.content)
        body = reprint.json()
        self.assertEqual(body["reprint_count"], 1)
        self.assertEqual(body["status"], "approved_queued")
        self.assertTrue([j for j in body["print_jobs"] if j["is_reprint"]])
        self.assertTrue(any("Faded output" in h["note"] for h in body["history"]))
        # The original run is preserved for the audit trail.
        self.assertTrue([j for j in body["print_jobs"] if not j["is_reprint"]])

    def test_reprint_can_target_a_single_file(self):
        order = self.approved_order()
        target = order["files"][0]["id"]
        reprint = self.act(order, "reprint", {"file_id": target})
        self.assertEqual(reprint.status_code, 200, reprint.content)
        jobs = [j for j in reprint.json()["print_jobs"] if j["is_reprint"]]
        self.assertTrue(jobs)
        self.assertTrue(all(j["order_file"] == target for j in jobs))

    def test_reprint_is_refused_before_the_order_reaches_the_printer(self):
        order = self.order_with_pdf()
        self.pay(order)
        self.assertEqual(self.act(order, "reprint").status_code, 409)

    def test_reprint_is_allowed_after_completion(self):
        order = self.approved_order()
        self.api.post("/api/admin/print-jobs/", {}, format="json")
        self.assertEqual(self.act(order, "ready").status_code, 200)
        self.assertEqual(self.act(order, "complete").status_code, 200)
        reprint = self.act(order, "reprint", {"note": "Customer lost the first copy"})
        self.assertEqual(reprint.status_code, 200, reprint.content)
        self.assertEqual(reprint.json()["reprint_count"], 1)

    def test_reprint_respects_the_page_selection(self):
        order = self.order_with_pdf(pages=4)
        order_file = order["files"][0]
        self.pay(order)
        self.api.patch(self.pages_url(order, order_file["id"]),
                       {"pages": [1, 3]}, format="json")
        self.assertEqual(self.act(order, "approve").status_code, 200)
        reprint = self.act(order, "reprint")
        self.assertEqual(reprint.status_code, 200, reprint.content)
        jobs = [j for j in reprint.json()["print_jobs"] if j["is_reprint"]]
        self.assertTrue(jobs)
        self.assertEqual(jobs[0]["pages_snapshot"], [1, 3])
        self.assertEqual(jobs[0]["pages_label"], "1, 3")


class PrinterCancellationTests(AdminReviewTestCase):
    def test_printer_cancelled_job_marks_the_order_and_allows_reprint(self):
        from apps.printing.models import PrintJob

        order = self.order_with_pdf(pages=1)
        self.pay(order)
        self.assertEqual(self.act(order, "approve").status_code, 200)

        job = PrintJob.objects.filter(order_id=order["id"]).first()
        self.assertIsNotNone(job)
        job.status = PrintJob.JobStatus.CANCELED
        job.epson_status = "canceled"
        job.error_message = "The printer cancelled this job before it finished."
        job.save()
        Order.objects.get(pk=order["id"]).set_status(
            Order.Status.PRINT_CANCELLED, note="Printer cancelled the job")
        sync = self.api.post("/api/admin/print-jobs/", {}, format="json")
        self.assertEqual(sync.status_code, 200, sync.content)

        detail = self.api.get(f"/api/admin/orders/{order['id']}/")
        self.assertEqual(detail.status_code, 200, detail.content)
        body = detail.json()
        # Printer-side cancellation is its own status, not a "Cancelled" order.
        self.assertEqual(body["status"], "print_cancelled")
        self.assertEqual(body["status_display"], "Cancelled at Printer")
        cancelled = [j for j in body["print_jobs"] if j["is_printer_cancelled"]]
        self.assertTrue(cancelled)
        self.assertIn("cancelled", cancelled[0]["error_message"].lower())

        track = self.api.get(f"/api/track/{body['tracking_id']}/",
                             {"contact": "ana@example.com"})
        self.assertEqual(track.status_code, 200)
        self.assertEqual(track.json()["status"], "print_cancelled")
        self.assertEqual(track.json()["status_display"], "Cancelled at Printer")

        reprint = self.act(order, "reprint")
        self.assertEqual(reprint.status_code, 200, reprint.content)
        self.assertEqual(reprint.json()["status"], "approved_queued")
        self.assertEqual(reprint.json()["reprint_count"], 1)

    def test_one_cancelled_sheet_does_not_cancel_the_whole_order(self):
        """Two sheets, one cancelled: the order is not left in a dead state."""
        from apps.printing.models import PrintJob

        order = self.submit([
            SimpleUploadedFile("a.pdf", make_pdf(1), content_type="application/pdf"),
            SimpleUploadedFile("b.pdf", make_pdf(1), content_type="application/pdf"),
        ])
        self.pay(order)
        self.assertEqual(self.act(order, "approve").status_code, 200)

        jobs = list(PrintJob.objects.filter(order_id=order["id"]))
        self.assertEqual(len(jobs), 2)
        jobs[0].status = PrintJob.JobStatus.COMPLETED
        jobs[0].epson_status = "completed"
        jobs[0].save()
        jobs[1].status = PrintJob.JobStatus.CANCELED
        jobs[1].epson_status = "canceled"
        jobs[1].save()
        sync = self.api.post("/api/admin/print-jobs/", {}, format="json")
        self.assertEqual(sync.status_code, 200, sync.content)

        # The cancelled sheet is flagged for the admin...
        detail = self.api.get(f"/api/admin/orders/{order['id']}/").json()
        self.assertTrue([j for j in detail["print_jobs"] if j["is_printer_cancelled"]])
        # ...and a reprint of just that sheet is available.
        self.assertEqual(self.act(order, "reprint", {"file_id": jobs[1].order_file_id}
                                  ).status_code, 200)
