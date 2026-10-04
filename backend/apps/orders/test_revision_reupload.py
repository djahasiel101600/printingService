"""Customer re-upload + version tracking tests (PRD §4.3 revision workflow).

When the shop cannot print an upload it sends the order back with
``request_revision``. The customer then replaces individual files: every
superseded upload is archived as an ``OrderFileVersion`` snapshot, the live
``OrderFile`` row is bumped (``current_version``) and the order stays in
``revision_requested`` until the client calls ``resubmit``.

Split out from tests.py because this is its own feature surface: version
history, the ownership gate for guests, and the hand-back transition.
"""
import io
import json

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from pypdf import PdfReader, PdfWriter

from apps.orders.models import Order, OrderFile, OrderFileVersion
from apps.pricing.models import PriceRule

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


def pdf_pages(payload: bytes) -> int:
    return len(PdfReader(io.BytesIO(payload)).pages)


class RevisionReuploadTestCase(TestCase):
    """Shared fixtures: a shop admin plus a walk-in (guest) order helper."""

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
        # Credential-free client = the guest experience on the tracking page.
        self.guest_api = APIClient()

    # -- helpers --------------------------------------------------------

    def submit(self, pages: int = 5, name: str = "report.pdf") -> dict:
        """The admin places a walk-in order, so ``user_id`` stays NULL."""
        response = self.api.post("/api/orders/", {
            "files": [SimpleUploadedFile(name, make_pdf(pages), content_type="application/pdf")],
            "guest_name": "Ana Reyes",
            "guest_contact_method": "email",
            "guest_contact_value": "ana@example.com",
            "spec": json.dumps(BASE_SPEC),
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["order"]

    def pay(self, order: dict) -> None:
        checkout = self.api.post("/api/payments/checkout/", {
            "order_id": order["id"], "method": "qrph", "payment_type": "full"}, format="json")
        # Checkout creates a Payment row, so DRF answers 201.
        self.assertIn(checkout.status_code, (200, 201), checkout.content)
        self.api.post("/api/payments/webhook/simulate/",
                      {"payment_id": checkout.json()["payment_id"]}, format="json")

    def request_revision(self, order: dict, note: str = "Please fix the header.") -> None:
        """Pay the order, then send it back to the client with a note."""
        self.pay(order)
        response = self.api.post(
            f"/api/admin/orders/{order['id']}/actions/request_revision/",
            {"note": note}, format="json")
        self.assertEqual(response.status_code, 200, response.content)

    def revision_order(self, pages: int = 5) -> tuple[dict, int]:
        """Order mid-revision: paid, revision requested, one original upload."""
        order = self.submit(pages=pages)
        self.request_revision(order)
        return order, order["files"][0]["id"]

    def reupload(self, order: dict, file_id: int, *, pages: int = 2,
                 name: str = "report-v2.pdf", content_type: str = "application/pdf",
                 tracking_id: str | None = None, client=None, with_file: bool = True):
        payload = {}
        if with_file:
            payload["file"] = SimpleUploadedFile(name, make_pdf(pages), content_type=content_type)
        if tracking_id:
            payload["tracking_id"] = tracking_id
        return (client or self.api).post(
            f"/api/orders/{order['id']}/files/{file_id}/reupload/",
            payload, format="multipart")

    def resubmit(self, order: dict, tracking_id: str | None = None, client=None):
        payload = {"tracking_id": tracking_id} if tracking_id else {}
        return (client or self.api).post(
            f"/api/orders/{order['id']}/resubmit/", payload, format="json")


class ReuploadVersioningTests(RevisionReuploadTestCase):
    """Replacing a file archives the old one and bumps ``current_version``."""

    def test_reupload_archives_the_superseded_upload(self):
        order, file_id = self.revision_order(pages=5)
        response = self.reupload(order, file_id, pages=2, name="report-v2.pdf")
        self.assertEqual(response.status_code, 200, response.content)

        live = OrderFile.objects.get(pk=file_id)
        self.assertEqual(live.current_version, 2)
        self.assertEqual(live.file_name, "report-v2.pdf")
        self.assertEqual(live.page_count, 2)

        versions = list(live.versions.all())
        self.assertEqual(len(versions), 1)
        archived = versions[0]
        self.assertEqual(archived.version_number, 1)
        self.assertEqual(archived.file_name, "report.pdf")
        self.assertEqual(archived.page_count, 5)

        # The archive is a real copy: different storage path, original bytes.
        self.assertNotEqual(archived.file.name, live.file.name)
        self.assertIn(f"/versions/{file_id}_v1_", archived.file.name)
        with archived.file.open("rb") as handle:
            self.assertEqual(pdf_pages(handle.read()), 5)
        with live.file.open("rb") as handle:
            self.assertEqual(pdf_pages(handle.read()), 2)

    def test_reupload_is_rejected_outside_a_requested_revision(self):
        order = self.submit()
        self.pay(order)  # -> pending_review, no revision asked for yet
        response = self.reupload(order, order["files"][0]["id"])
        self.assertEqual(response.status_code, 409, response.content)
        self.assertFalse(OrderFileVersion.objects.exists())
        self.assertEqual(OrderFile.objects.get(pk=order["files"][0]["id"]).current_version, 1)

    def test_reupload_requires_ownership_proof(self):
        order, file_id = self.revision_order()
        self.assertEqual(self.reupload(order, file_id, client=self.guest_api).status_code, 403)
        # The tracking ID is the guest's proof of ownership (PRD §6).
        allowed = self.reupload(order, file_id, tracking_id=order["tracking_id"],
                                client=self.guest_api)
        self.assertEqual(allowed.status_code, 200, allowed.content)

    def test_reupload_rejects_missing_and_unsupported_files(self):
        order, file_id = self.revision_order()
        missing = self.reupload(order, file_id, with_file=False)
        self.assertEqual(missing.status_code, 400, missing.content)
        unsupported = self.reupload(order, file_id, name="archive.zip",
                                    content_type="application/zip")
        self.assertEqual(unsupported.status_code, 400, unsupported.content)
        self.assertFalse(OrderFileVersion.objects.exists())

    def test_reupload_discards_shop_prepared_artefacts(self):
        order, file_id = self.revision_order()
        live = OrderFile.objects.get(pk=file_id)
        live.edited_file.save("edited.pdf", ContentFile(make_pdf(5)), save=True)
        live.final_file.save("final.pdf", ContentFile(make_pdf(2)), save=True)
        live.page_selection = [1, 2]
        live.replaced_by_admin = True
        live.edit_actions = [{"action": "center"}]
        live.save()

        response = self.reupload(order, file_id, pages=3)
        self.assertEqual(response.status_code, 200, response.content)
        live.refresh_from_db()
        # Derived artefacts belong to the old bytes: the new version needs a
        # fresh admin review, so they are dropped with it.
        self.assertFalse(live.edited_file)
        self.assertFalse(live.final_file)
        self.assertEqual(live.page_selection, [])
        self.assertFalse(live.replaced_by_admin)
        self.assertEqual(live.edit_actions, [])
        # ...but the snapshot keeps what the customer originally sent.
        self.assertEqual(live.versions.get(version_number=1).edit_actions, [{"action": "center"}])

    def test_reupload_requotes_the_surviving_pages(self):
        order, file_id = self.revision_order(pages=5)
        before = Order.objects.get(pk=order["id"]).subtotal
        self.reupload(order, file_id, pages=2)
        after = Order.objects.get(pk=order["id"])
        self.assertEqual(after.subtotal, 2 * 300)
        self.assertLess(after.subtotal, before)

    def test_reupload_keeps_the_order_in_revision_requested(self):
        order, file_id = self.revision_order()
        payload = self.reupload(order, file_id).json()
        self.assertEqual(payload["status"], Order.Status.REVISION_REQUESTED)
        self.assertEqual(payload["revision_note"], "Please fix the header.")

    def test_reupload_appends_to_the_version_chain(self):
        order, file_id = self.revision_order(pages=5)
        self.assertEqual(self.reupload(order, file_id, pages=4, name="v2.pdf").status_code, 200)
        self.assertEqual(self.reupload(order, file_id, pages=3, name="v3.pdf").status_code, 200)
        live = OrderFile.objects.get(pk=file_id)
        self.assertEqual(live.current_version, 3)
        self.assertEqual([v.version_number for v in live.versions.all()], [1, 2])
        self.assertEqual([v.file_name for v in live.versions.all()], ["report.pdf", "v2.pdf"])

    def test_reupload_logs_an_audit_note_without_changing_status(self):
        order, file_id = self.revision_order()
        self.reupload(order, file_id)
        history = Order.objects.get(pk=order["id"]).history.latest("created_at")
        self.assertEqual(history.note, "Client uploaded v2 of 'report-v2.pdf'")
        self.assertEqual(history.from_status, history.to_status)


class ResubmitTests(RevisionReuploadTestCase):
    """Handing the order back: revision_requested -> pending_review."""

    def test_resubmit_is_blocked_until_a_file_is_replaced(self):
        order, _ = self.revision_order()
        response = self.resubmit(order)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(Order.objects.get(pk=order["id"]).status, Order.Status.REVISION_REQUESTED)

    def test_resubmit_returns_the_order_to_review_with_history(self):
        order, file_id = self.revision_order()
        self.reupload(order, file_id)
        response = self.resubmit(order)
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["status"], Order.Status.PENDING_REVIEW)
        self.assertEqual(payload["files"][0]["current_version"], 2)
        self.assertEqual(payload["files"][0]["versions"][0]["version_label"], "v1 · report.pdf")

        history = Order.objects.get(pk=order["id"]).history.latest("created_at")
        self.assertEqual(history.from_status, Order.Status.REVISION_REQUESTED)
        self.assertEqual(history.to_status, Order.Status.PENDING_REVIEW)
        self.assertEqual(history.note, "Client resubmitted revised files")

    def test_resubmit_needs_the_same_ownership_proof(self):
        order, file_id = self.revision_order()
        self.reupload(order, file_id)
        self.assertEqual(self.resubmit(order, client=self.guest_api).status_code, 403)
        allowed = self.resubmit(order, tracking_id=order["tracking_id"], client=self.guest_api)
        self.assertEqual(allowed.status_code, 200, allowed.content)

    def test_resubmit_rejected_when_not_awaiting_a_revision(self):
        order = self.submit()
        self.pay(order)
        response = self.resubmit(order)
        self.assertEqual(response.status_code, 409, response.content)

    def test_order_detail_exposes_the_version_history_to_the_client(self):
        order, file_id = self.revision_order()
        self.reupload(order, file_id)
        response = self.guest_api.get(f"/api/orders/{order['id']}/",
                                      {"tracking_id": order["tracking_id"]})
        self.assertEqual(response.status_code, 200, response.content)
        file_payload = response.json()["files"][0]
        self.assertEqual(file_payload["current_version"], 2)
        self.assertEqual([v["version_number"] for v in file_payload["versions"]], [1])
        self.assertEqual(file_payload["versions"][0]["file_name"], "report.pdf")

    def test_admin_detail_also_carries_the_versions(self):
        order, file_id = self.revision_order()
        self.reupload(order, file_id)
        response = self.api.get(f"/api/admin/orders/{order['id']}/")
        self.assertEqual(response.status_code, 200, response.content)
        file_payload = response.json()["files"][0]
        self.assertEqual(file_payload["current_version"], 2)
        self.assertTrue(file_payload["versions"][0]["file"])
