"""DELETE /api/admin/orders/{pk}/ — the missing D of admin CRUD.

The admin side could already create, read and update customer orders
(create-for-customer, list/detail views, notes/spec/page edits, status
actions) but never remove one — junk and test orders had nowhere to go.
Deletion is irreversible, so it follows the money-action rules of
``AdminOrderActionView``: shop-admin only (approvers only work the
queue), paid payments refunded first (like cancel/reject), and refused
while an Epson job is still in flight so the printer never prints an
order with no record left behind.
"""
import io
import json
from unittest.mock import patch

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from pypdf import PdfWriter

from apps.orders.models import Order, OrderFile, OrderFileVersion, OrderStatusHistory
from apps.payments.models import Payment
from apps.printing.models import PrintJob
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


class AdminOrderDeleteTests(TestCase):
    """Permissions, guards and full cleanup for admin order deletion."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        User.objects.create_user(
            username="admin@print.local", email="admin@print.local",
            password="review1234", role=User.Role.ADMIN, is_staff=True)
        User.objects.create_user(
            username="approver@print.local", email="approver@print.local",
            password="review1234", role=User.Role.APPROVER, is_staff=True)
        PriceRule.objects.create(media_size="ps_a4", media_type="pt_plainpaper",
                                 color_mode="mono", print_quality="normal",
                                 price_per_page=300)
        self.api = self._login(APIClient(), "admin@print.local")
        self.approver_api = self._login(APIClient(), "approver@print.local")
        # Credential-free client = a guest watching their order.
        self.guest_api = APIClient()

    @staticmethod
    def _login(client, email):
        login = client.post("/api/auth/token/",
                            {"email": email, "password": "review1234"},
                            format="json")
        assert login.status_code == 200, login.content
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        return client

    # -- helpers --------------------------------------------------------

    def submit(self) -> dict:
        response = self.api.post("/api/orders/", {
            "files": [SimpleUploadedFile("report.pdf", make_pdf(3),
                                         content_type="application/pdf")],
            "guest_name": "Ana Reyes",
            "guest_contact_method": "email",
            "guest_contact_value": "ana@example.com",
            "spec": json.dumps(BASE_SPEC),
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["order"]

    def pay(self, order: dict) -> None:
        checkout = self.api.post("/api/payments/checkout/", {
            "order_id": order["id"], "method": "qrph",
            "payment_type": "full"}, format="json")
        self.assertIn(checkout.status_code, (200, 201), checkout.content)
        self.api.post("/api/payments/webhook/simulate/",
                      {"payment_id": checkout.json()["payment_id"]}, format="json")

    def delete(self, order: dict, client=None):
        return (client or self.api).delete(f"/api/admin/orders/{order['id']}/")

    # -- tests ----------------------------------------------------------

    def test_admin_delete_removes_order_files_payments_and_history(self):
        order = self.submit()
        self.pay(order)
        stored_name = OrderFile.objects.get().file.name
        self.assertTrue(default_storage.exists(stored_name))

        response = self.delete(order)
        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(Order.objects.filter(pk=order["id"]).exists())
        self.assertFalse(OrderFile.objects.exists())
        self.assertFalse(OrderFileVersion.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(OrderStatusHistory.objects.exists())
        # The bytes go too — Django never deletes files with rows.
        self.assertFalse(default_storage.exists(stored_name))

    def test_paid_orders_are_refunded_before_the_rows_disappear(self):
        order = self.submit()
        self.pay(order)
        with patch("apps.payments.services.refund_order") as refund:
            response = self.delete(order)
        self.assertEqual(response.status_code, 204, response.content)
        refund.assert_called_once()
        self.assertEqual(refund.call_args.kwargs["reason"], "deleted_by_shop")

    def test_approver_cannot_delete(self):
        """Approvers work the queue; deleting money records is owner-only."""
        order = self.submit()
        response = self.delete(order, client=self.approver_api)
        self.assertEqual(response.status_code, 403, response.content)
        self.assertTrue(Order.objects.filter(pk=order["id"]).exists())

    def test_anonymous_cannot_delete(self):
        order = self.submit()
        response = self.delete(order, client=self.guest_api)
        self.assertIn(response.status_code, (401, 403))
        self.assertTrue(Order.objects.filter(pk=order["id"]).exists())

    def test_delete_waits_for_in_flight_print_jobs(self):
        order = self.submit()
        job = PrintJob.objects.create(
            order_id=order["id"], status=PrintJob.JobStatus.PRINTING,
            epson_job_id="ep-123")

        blocked = self.delete(order)
        self.assertEqual(blocked.status_code, 409, blocked.content)
        self.assertTrue(Order.objects.filter(pk=order["id"]).exists())

        job.status = PrintJob.JobStatus.COMPLETED
        job.save(update_fields=["status"])
        allowed = self.delete(order)
        self.assertEqual(allowed.status_code, 204, allowed.content)
        self.assertFalse(Order.objects.filter(pk=order["id"]).exists())