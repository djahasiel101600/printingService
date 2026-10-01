"""End-to-end lifecycle tests using the Epson + PayMongo mock providers."""
import io
import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from pypdf import PdfWriter

from apps.orders.models import Order, OrderFile
from apps.payments.models import Payment
from apps.pricing.models import PriceRule
from apps.pricing.quotation import compute_quote, find_rule


def make_pdf(pages: int = 3) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def make_image() -> bytes:
    img = Image.new("RGB", (400, 300), "tomato")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class QuotationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        PriceRule.objects.create(media_size="ps_a4", media_type="pt_plainpaper",
                                 color_mode="mono", print_quality="normal", price_per_page=300)
        PriceRule.objects.create(media_size="any", media_type="any",
                                 color_mode="any", print_quality="any", price_per_page=500)

    def test_exact_rule_match(self):
        rule = find_rule("ps_a4", "pt_plainpaper", "mono", "normal")
        self.assertEqual(rule.price_per_page, 300)

    def test_wildcard_fallback(self):
        rule = find_rule("ps_a3", "pt_photopaper", "color", "draft")
        self.assertEqual(rule.price_per_page, 500)

    def test_quote_simple(self):
        quote = compute_quote([{"page_count": 4, "copies": 2, "media_size": "ps_a4",
                                "media_type": "pt_plainpaper", "color_mode": "mono",
                                "print_quality": "normal", "sides": "none"}])
        self.assertEqual(quote.subtotal, 4 * 2 * 300)

    def test_quote_duplex_discount(self):
        quote = compute_quote([{"page_count": 10, "copies": 1, "media_size": "ps_a4",
                                "media_type": "pt_plainpaper", "color_mode": "mono",
                                "print_quality": "normal", "sides": "long"}])
        expected = round(300 * 0.90) * 10
        self.assertEqual(quote.subtotal, expected)


class OrderLifecycleTests(TestCase):
    """guest upload -> quote -> checkout -> pay -> admin approve -> print -> pickup."""

    def setUp(self):
        from rest_framework.test import APIClient

        self.client_api = APIClient()
        PriceRule.objects.create(media_size="ps_a4", media_type="pt_plainpaper",
                                 color_mode="mono", print_quality="normal", price_per_page=300)

    def _create_order(self) -> dict:
        pdf = make_pdf(3)
        response = self.client_api.post("/api/orders/", {
            "files": [SimpleUploadedFile("notes.pdf", pdf, content_type="application/pdf")],
            "guest_name": "Juan Dela Cruz",
            "guest_contact_method": "email",
            "guest_contact_value": "juan@example.com",
            "spec": json.dumps({
                "media_size": "ps_a4", "media_type": "pt_plainpaper",
                "color_mode": "mono", "print_quality": "normal",
                "sides": "none", "copies": 2,
                "free_text_instructions": "Please print double spaced if possible.",
            }),
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_guest_order_creation_and_quote(self):
        payload = self._create_order()
        order = payload["order"]
        self.assertEqual(order["status"], "awaiting_payment")
        self.assertEqual(order["guest_name"], "Juan Dela Cruz")
        self.assertEqual(order["files"][0]["page_count"], 3)
        # 3 pages x 2 copies x 300 centavos
        self.assertEqual(order["subtotal"], 1800)
        self.assertEqual(payload["quote"]["subtotal"], 1800)
        self.assertTrue(order["tracking_id"].startswith("PSP-"))

    def test_file_edit_and_requote(self):
        payload = self._create_order()
        order_id = payload["order"]["id"]
        file_id = payload["order"]["files"][0]["id"]
        tracking_id = payload["order"]["tracking_id"]
        response = self.client_api.post(
            f"/api/orders/{order_id}/files/{file_id}/edit/",
            {"action": "crop", "params": json.dumps({"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.5}),
             "tracking_id": tracking_id},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.content)
        order_file = OrderFile.objects.get(pk=file_id)
        self.assertTrue(order_file.edited_file)
        self.assertEqual(order_file.edit_actions[-1]["action"], "crop")
        self.assertEqual(order_file.page_count, 3)

    def test_split_pdf_pages(self):
        payload = self._create_order()
        file_id = payload["order"]["files"][0]["id"]
        order_id = payload["order"]["id"]
        response = self.client_api.post(
            f"/api/orders/{order_id}/files/{file_id}/edit/",
            {"action": "split", "params": json.dumps({"pages": [1, 3]}),
             "tracking_id": payload["order"]["tracking_id"]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(OrderFile.objects.get(pk=file_id).page_count, 2)

    def test_checkout_pay_and_track(self):
        payload = self._create_order()
        order = payload["order"]

        checkout = self.client_api.post("/api/payments/checkout/", {
            "order_id": order["id"], "payment_type": "full",
        }, format="json")
        self.assertEqual(checkout.status_code, 201, checkout.content)
        self.assertTrue(checkout.json()["qr_image_url"].startswith("data:image"))

        payment = Payment.objects.get(pk=checkout.json()["payment_id"])
        self.assertEqual(payment.status, Payment.Status.PENDING)

        # Simulated webhook (mock mode)
        webhook = self.client_api.post("/api/payments/webhook/simulate/", {
            "payment_id": payment.pk,
        }, format="json")
        self.assertEqual(webhook.status_code, 200, webhook.content)

        order_obj = Order.objects.get(pk=order["id"])
        self.assertEqual(order_obj.status, Order.Status.PENDING_REVIEW)
        self.assertEqual(order_obj.amount_paid, 1800)

        # Guest tracking with the correct contact succeeds
        track = self.client_api.get(
            f"/api/track/{order_obj.tracking_id}/", {"contact": "juan@example.com"})
        self.assertEqual(track.status_code, 200)
        self.assertEqual(track.json()["status"], "pending_review")

        # Wrong contact is rejected
        track_bad = self.client_api.get(
            f"/api/track/{order_obj.tracking_id}/", {"contact": "whoever@else.com"})
        self.assertEqual(track_bad.status_code, 404)

    def _admin_client(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        User.objects.get_or_create(
            username="admin@print.local", email="admin@print.local",
            defaults={"first_name": "Shop", "last_name": "Admin",
                      "role": User.Role.ADMIN, "is_staff": True, "is_superuser": True},
        )
        admin = APIClient()
        password = "admin1234"
        user = User.objects.get(email="admin@print.local")
        user.set_password(password)
        user.save()
        login = admin.post("/api/auth/token/", {
            "email": "admin@print.local", "password": password}, format="json")
        self.assertEqual(login.status_code, 200, login.content)
        admin.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        return admin

    def test_full_admin_lifecycle_through_epson_mock(self):
        payload = self._create_order()
        order_id = payload["order"]["id"]

        # Partial payment
        checkout = self.client_api.post("/api/payments/checkout/", {
            "order_id": order_id, "payment_type": "partial",
        }, format="json")
        payment_id = checkout.json()["payment_id"]
        self.client_api.post("/api/payments/webhook/simulate/", {"payment_id": payment_id}, format="json")

        admin = self._admin_client()
        queue = admin.get("/api/admin/orders/", {"status": "pending_review"})
        self.assertEqual(queue.status_code, 200)
        self.assertTrue(any(o["id"] == order_id for o in queue.json()))

        # Approve -> Epson mock job created, uploaded, executed
        approve = admin.post(f"/api/admin/orders/{order_id}/actions/approve/", {}, format="json")
        self.assertEqual(approve.status_code, 200, approve.content)
        order_obj = Order.objects.get(pk=order_id)
        self.assertEqual(order_obj.print_jobs.count(), 1)
        job = order_obj.print_jobs.first()
        self.assertTrue(job.epson_job_id)
        self.assertEqual(job.print_mode, "document")
        self.assertEqual(job.print_settings_snapshot["copies"], 2)
        self.assertEqual(job.print_settings_snapshot["colorMode"], "mono")

        # Sync until completed (mock advances one step per poll)
        from apps.printing.services import sync_print_jobs
        for _ in range(4):
            sync_print_jobs(order_obj)
        order_obj.refresh_from_db()
        self.assertEqual(order_obj.status, Order.Status.PRINTED_READY)

        # Ready -> Complete
        complete = admin.post(f"/api/admin/orders/{order_id}/actions/complete/", {}, format="json")
        self.assertEqual(complete.status_code, 200, complete.content)
        self.assertEqual(Order.objects.get(pk=order_id).status, Order.Status.COMPLETED)

    def test_rejection_refunds(self):
        payload = self._create_order()
        order_id = payload["order"]["id"]
        checkout = self.client_api.post("/api/payments/checkout/", {
            "order_id": order_id, "payment_type": "full"}, format="json")
        payment_id = checkout.json()["payment_id"]
        self.client_api.post("/api/payments/webhook/simulate/", {"payment_id": payment_id}, format="json")

        admin = self._admin_client()
        response = admin.post(f"/api/admin/orders/{order_id}/actions/reject/",
                              {"reason": "Copyrighted material"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        order_obj = Order.objects.get(pk=order_id)
        self.assertEqual(order_obj.status, Order.Status.REJECTED)
        payment = Payment.objects.get(pk=payment_id)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)


class RegistrationAndAuthTests(TestCase):
    def test_register_login_me(self):
        from rest_framework.test import APIClient

        api = APIClient()
        response = api.post("/api/auth/register/", {
            "email": "new@user.com", "password": "s3cretpass!",
            "first_name": "New", "last_name": "User",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.content)

        login = api.post("/api/auth/token/", {
            "email": "new@user.com", "password": "s3cretpass!"}, format="json")
        self.assertEqual(login.status_code, 200)
        token = login.json()["access"]

        me = api.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "new@user.com")
        self.assertEqual(me.json()["role"], "client")


class CapabilitiesViewTests(TestCase):
    def test_capabilities_mock_payload(self):
        from rest_framework.test import APIClient

        api = APIClient()
        response = api.get("/api/printing/capabilities/", {"print_mode": "document"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("paperSizes", body)
        self.assertIn("colorModes", body)
        sizes = [entry["paperSize"] for entry in body["paperSizes"]]
        self.assertIn("ps_a4", sizes)


class OrderFlowRegressionTests(TestCase):
    """Customer -> confirmation -> My Orders -> Admin, both as guest and as a
    logged-in user, including the pay-on-pickup option and admin tooling."""

    def setUp(self):
        from rest_framework.test import APIClient

        self.client_api = APIClient()
        PriceRule.objects.create(media_size="ps_a4", media_type="pt_plainpaper",
                                 color_mode="mono", print_quality="normal", price_per_page=300)

    # ------------------------------------------------------------- helpers
    def _create_guest_order(self) -> dict:
        response = self.client_api.post("/api/orders/", {
            "files": [SimpleUploadedFile("notes.pdf", make_pdf(3), content_type="application/pdf")],
            "guest_name": "Juan Dela Cruz",
            "guest_contact_method": "email",
            "guest_contact_value": "juan@example.com",
            "spec": json.dumps({"media_size": "ps_a4", "media_type": "pt_plainpaper",
                                "color_mode": "mono", "print_quality": "normal",
                                "sides": "none", "copies": 2}),
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def _admin_client(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        User.objects.get_or_create(
            username="admin@print.local", email="admin@print.local",
            defaults={"first_name": "Shop", "last_name": "Admin",
                      "role": User.Role.ADMIN, "is_staff": True, "is_superuser": True},
        )
        admin = APIClient()
        user = User.objects.get(email="admin@print.local")
        user.set_password("admin1234")
        user.save()
        login = admin.post("/api/auth/token/", {
            "email": "admin@print.local", "password": "admin1234"}, format="json")
        self.assertEqual(login.status_code, 200, login.content)
        admin.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        return admin

    # ------------------------------------------------- serialization (bug)
    def test_peso_fields_always_serialized(self):
        payload = self._create_guest_order()
        order = payload["order"]
        self.assertEqual(order["subtotal_peso"], 18.0)
        self.assertEqual(order["amount_paid_peso"], 0.0)
        self.assertEqual(order["balance_due_peso"], 18.0)
        self.assertIn("min_partial_peso", order)
        self.assertIn("payment_method", order)

        # The admin list used to drop subtotal_peso entirely (blank page crash).
        admin = self._admin_client()
        listed = admin.get("/api/admin/orders/")
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(len(listed.json()) > 0)
        for entry in listed.json():
            self.assertIn("subtotal_peso", entry)
            self.assertIn("balance_due_peso", entry)

    # ------------------------------------------- guest order confirmation
    def test_guest_order_detail_requires_tracking_proof(self):
        payload = self._create_guest_order()
        order_id, tracking_id = payload["order"]["id"], payload["order"]["tracking_id"]

        denied = self.client_api.get(f"/api/orders/{order_id}/")
        self.assertEqual(denied.status_code, 403)

        wrong = self.client_api.get(f"/api/orders/{order_id}/", {"tracking_id": "PSP-XXXX-XXXX"})
        self.assertEqual(wrong.status_code, 403)

        ok = self.client_api.get(f"/api/orders/{order_id}/", {"tracking_id": tracking_id})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["tracking_id"], tracking_id)

    def test_track_result_includes_order_id(self):
        payload = self._create_guest_order()
        response = self.client_api.get(
            f"/api/track/{payload['order']['tracking_id']}/", {"contact": "juan@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], payload["order"]["id"])

    # ------------------------------------------------------- pay on pickup
    def test_pay_on_pickup_submits_straight_to_review(self):
        payload = self._create_guest_order()
        order_id = payload["order"]["id"]

        response = self.client_api.post("/api/payments/checkout/", {
            "order_id": order_id, "method": "pickup",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["method"], "pickup")

        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.status, Order.Status.PENDING_REVIEW)
        self.assertEqual(order.payment_method, Order.PaymentMethod.PICKUP)
        self.assertEqual(order.payments.count(), 0)
        self.assertEqual(order.balance_due, 1800)

        # Admin sees it in the review queue (guest orders stay traceable).
        admin = self._admin_client()
        queue = admin.get("/api/admin/orders/", {"status": "pending_review"})
        self.assertTrue(any(o["id"] == order_id for o in queue.json()))

    def test_admin_can_disable_pay_on_pickup(self):
        # Anonymous writers are rejected.
        anon = self.client_api.put("/api/payments/settings/",
                                   {"allow_pay_on_pickup": False}, format="json")
        self.assertIn(anon.status_code, (401, 403))

        admin = self._admin_client()
        put = admin.put("/api/payments/settings/", {"allow_pay_on_pickup": False}, format="json")
        self.assertEqual(put.status_code, 200, put.content)
        self.assertFalse(put.json()["allow_pay_on_pickup"])

        # Public read reflects the toggle for the checkout UI.
        settings_view = self.client_api.get("/api/payments/settings/")
        self.assertEqual(settings_view.status_code, 200)
        self.assertFalse(settings_view.json()["allow_pay_on_pickup"])

        payload = self._create_guest_order()
        blocked = self.client_api.post("/api/payments/checkout/", {
            "order_id": payload["order"]["id"], "method": "pickup",
        }, format="json")
        self.assertEqual(blocked.status_code, 400, blocked.content)

        # QR Ph checkout still works while pickup is disabled.
        qr = self.client_api.post("/api/payments/checkout/", {
            "order_id": payload["order"]["id"], "payment_type": "full",
        }, format="json")
        self.assertEqual(qr.status_code, 201, qr.content)
        self.assertEqual(qr.json()["method"], "qrph")

    def test_record_payment_closes_out_pickup_order(self):
        payload = self._create_guest_order()
        order_id = payload["order"]["id"]
        self.client_api.post("/api/payments/checkout/", {
            "order_id": order_id, "method": "pickup",
        }, format="json")

        admin = self._admin_client()
        record = admin.post(f"/api/admin/orders/{order_id}/actions/record_payment/",
                            {}, format="json")
        self.assertEqual(record.status_code, 200, record.content)

        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.amount_paid, order.subtotal)
        self.assertEqual(order.balance_due, 0)
        cash = order.payments.filter(method="cash", status=Payment.Status.PAID)
        self.assertEqual(cash.count(), 1)

        # Nothing left to collect -> conflict.
        again = admin.post(f"/api/admin/orders/{order_id}/actions/record_payment/",
                           {}, format="json")
        self.assertEqual(again.status_code, 409)

    # --------------------------------------------- admin creating orders
    def test_admin_creates_order_for_walk_in_customer(self):
        admin = self._admin_client()
        response = admin.post("/api/orders/", {
            "files": [SimpleUploadedFile("walkin.pdf", make_pdf(2), content_type="application/pdf")],
            "guest_name": "Maria Santos",
            "guest_contact_method": "phone",
            "guest_contact_value": "09171234567",
            "spec": json.dumps({"media_size": "ps_a4", "media_type": "pt_plainpaper",
                                "color_mode": "mono", "print_quality": "normal",
                                "sides": "none", "copies": 1}),
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        order = response.json()["order"]
        self.assertIsNone(Order.objects.get(pk=order["id"]).user)
        self.assertEqual(order["guest_name"], "Maria Santos")
        self.assertEqual(order["client_name"], "Maria Santos")

        # Traceable in the admin queue by customer name.
        listed = admin.get("/api/admin/orders/", {"search": "Maria"})
        self.assertTrue(any(o["id"] == order["id"] for o in listed.json()))

    def test_admin_creates_order_linked_to_registered_customer(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        customer = User.objects.create_user(
            username="marie@example.com", email="marie@example.com",
            first_name="Marie", last_name="Cruz", role=User.Role.CLIENT,
        )
        customer.set_password("mariepass1")
        customer.save()

        admin = self._admin_client()
        response = admin.post("/api/orders/", {
            "files": [SimpleUploadedFile("linked.pdf", make_pdf(1), content_type="application/pdf")],
            "customer_user_id": str(customer.id),
            "spec": json.dumps({"media_size": "ps_a4", "media_type": "pt_plainpaper",
                                "color_mode": "mono", "print_quality": "normal",
                                "sides": "none", "copies": 1}),
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        order = response.json()["order"]
        self.assertEqual(Order.objects.get(pk=order["id"]).user_id, customer.id)
        self.assertEqual(order["client_name"], "Marie Cruz")

        # The customer sees it in their own My Orders.
        client = APIClient()
        login = client.post("/api/auth/token/", {
            "email": "marie@example.com", "password": "mariepass1"}, format="json")
        self.assertEqual(login.status_code, 200, login.content)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
        mine = client.get("/api/orders/mine/")
        self.assertEqual(mine.status_code, 200)
        self.assertTrue(any(o["id"] == order["id"] for o in mine.json()))

    def test_admin_customer_search_endpoint(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        User.objects.create_user(
            username="unique-search@example.com", email="unique-search@example.com",
            first_name="Zedrick", last_name="Quinto", role=User.Role.CLIENT,
        )
        admin = self._admin_client()
        found = admin.get("/api/admin/customers/", {"search": "Zedrick"})
        self.assertEqual(found.status_code, 200)
        self.assertTrue(any(c["email"] == "unique-search@example.com" for c in found.json()))

        # Admins never show up as order targets.
        emails = [c["email"] for c in found.json()]
        self.assertNotIn("admin@print.local", emails)

        anonymous = APIClient().get("/api/admin/customers/")
        self.assertIn(anonymous.status_code, (401, 403))

