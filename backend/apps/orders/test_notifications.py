"""Customer email notifications: tracking ID on placement, every status update.

Covers the two guarantees the shop asked for:

* placing an order emails the **tracking ID** to the customer's address — the
  account email when they are signed in, the contact address when a guest
  chose email, and nothing at all for a guest who left only a phone number;
* **every** customer-visible status change sends one email (and repeating the
  same status does not).

Also asserts that a mail outage can never fail an order, and that the switch
in settings silences the stream.
"""
import json
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.orders.services import notifications

from .tests import make_pdf

GUEST_EMAIL = "walkin@example.com"
CLIENT_EMAIL = "ana.signed@example.com"
ADMIN_EMAIL = "owner@shop.local"


def html_body(message) -> str:
    """The text/html alternative attached to an email."""
    return next(body for body, mimetype in message.alternatives if mimetype == "text/html")


class NotificationTestCase(TestCase):
    def setUp(self):
        mail.outbox.clear()
        User = get_user_model()
        self.customer = User.objects.create_user(
            username=CLIENT_EMAIL, email=CLIENT_EMAIL, password="clientpass12",
        )
        self.admin = User.objects.create_user(
            username=ADMIN_EMAIL, email=ADMIN_EMAIL, password="ownerpass123",
            role=User.Role.ADMIN, is_staff=True,
        )
        self.api = APIClient()

    # ------------------------------------------------------------- helpers
    @staticmethod
    def track_url() -> str:
        return f"{settings.FRONTEND_URL.rstrip('/')}/track"

    def login(self, email: str, password: str) -> APIClient:
        api = APIClient()
        response = api.post("/api/auth/token/", {"email": email, "password": password},
                            format="json")
        self.assertEqual(response.status_code, 200, response.content)
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
        return api

    @staticmethod
    def upload() -> SimpleUploadedFile:
        return SimpleUploadedFile("report.pdf", make_pdf(2), content_type="application/pdf")

    def place_guest_order(self, method: str = "email", value: str = GUEST_EMAIL) -> dict:
        response = self.api.post("/api/orders/", {
            "files": [self.upload()],
            "guest_name": "Ana Reyes",
            "guest_contact_method": method,
            "guest_contact_value": value,
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["order"]

    def place_signed_in_order(self) -> dict:
        api = self.login(CLIENT_EMAIL, "clientpass12")
        response = api.post("/api/orders/", {"files": [self.upload()]}, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["order"]

    @staticmethod
    def last_message():
        assert len(mail.outbox) >= 1, "expected at least one email"
        return mail.outbox[-1]

    def assert_tracking_id_sent(self, recipient: str, tracking_id: str, message=None) -> None:
        message = message or self.last_message()
        self.assertEqual(message.to, [recipient])
        self.assertIn(tracking_id, message.subject)
        self.assertIn(tracking_id, message.body)
        self.assertIn(self.track_url(), message.body)
        # A readable HTML alternative ships alongside the plain text.
        self.assertIn(tracking_id, html_body(message))


class PlacementNotificationTests(NotificationTestCase):
    """The tracking ID must reach the customer the moment an order exists."""

    def test_signed_in_customer_receives_the_tracking_id(self):
        order = self.place_signed_in_order()
        self.assertEqual(len(mail.outbox), 1)
        self.assert_tracking_id_sent(CLIENT_EMAIL, order["tracking_id"])
        self.assertIn("tracking ID", mail.outbox[0].subject)
        # The order is owned by the account, so the mail is the account address.
        live = Order.objects.get(pk=order["id"])
        self.assertEqual(live.user, self.customer)

    def test_guest_with_an_email_contact_receives_the_tracking_id(self):
        order = self.place_guest_order("email", GUEST_EMAIL)
        self.assertEqual(len(mail.outbox), 1)
        self.assert_tracking_id_sent(GUEST_EMAIL, order["tracking_id"])

    def test_guest_with_only_a_phone_receives_nothing(self):
        """No email address on file — the tracking page is their channel."""
        order = self.place_guest_order("phone", "+639171234567")
        self.assertEqual(mail.outbox, [])
        # ...and the order still exists normally.
        self.assertEqual(Order.objects.get(pk=order["id"]).status,
                         Order.Status.AWAITING_PAYMENT)

    def test_guest_with_an_unusable_address_receives_nothing(self):
        order = self.place_guest_order("email", "not-an-email")
        self.assertEqual(mail.outbox, [])
        self.assertEqual(Order.objects.get(pk=order["id"]).tracking_id, order["tracking_id"])

    def test_every_placed_order_gets_exactly_one_email(self):
        self.place_signed_in_order()
        mail.outbox.clear()
        self.place_guest_order()
        self.assertEqual(len(mail.outbox), 1)
class StatusNotificationTests(NotificationTestCase):
    """Every customer-visible transition sends exactly one email."""

    def setUp(self):
        super().setUp()
        self.order = Order.objects.get(pk=self.place_guest_order()["id"])
        mail.outbox.clear()

    def test_every_customer_visible_status_emails_the_customer(self):
        statuses = [
            Order.Status.PENDING_REVIEW,
            Order.Status.REVISION_REQUESTED,
            Order.Status.APPROVED_QUEUED,
            Order.Status.PRINTING,
            Order.Status.ON_HOLD,
            Order.Status.PRINT_CANCELLED,
            Order.Status.PRINTED_READY,
            Order.Status.REJECTED,
            Order.Status.CANCELLED,
            Order.Status.COMPLETED,
        ]
        for status in statuses:
            self.order.set_status(status, note=f"now {status}")

        self.assertEqual(len(mail.outbox), len(statuses))
        for message, status in zip(mail.outbox, statuses):
            self.assertEqual(message.to, [GUEST_EMAIL])
            self.assertIn(self.order.tracking_id, message.subject)
            self.assertIn(self.order.tracking_id, message.body)
            self.assertIn(f"now {status}", message.body)
            self.assertIn(self.track_url(), message.body)

    def test_repeating_the_same_status_does_not_resend(self):
        """Checkout re-saves "awaiting payment"; the inbox must stay clean."""
        self.order.set_status(self.order.status, note="QR Ph checkout generated")
        self.assertEqual(mail.outbox, [])
        # ...but the history still records it.
        self.assertTrue(self.order.history.filter(note="QR Ph checkout generated").exists())

    def test_draft_is_never_announced(self):
        self.order.set_status(Order.Status.DRAFT)
        self.assertEqual(mail.outbox, [])

    def test_staff_note_is_included_in_both_parts(self):
        self.order.set_status(Order.Status.REVISION_REQUESTED, note="Page 2 is cut off.")
        self.assertIn("Page 2 is cut off.", self.last_message().body)
        self.assertIn("Page 2 is cut off.", html_body(self.last_message()))

    def test_note_is_omitted_when_there_is_none(self):
        self.order.set_status(Order.Status.PRINTING)
        self.assertNotIn("Note from our staff", self.last_message().body)

    def test_status_update_carries_the_new_status(self):
        self.order.set_status(Order.Status.PRINTED_READY)
        message = self.last_message()
        self.assertIn("ready for pickup", message.body)
        self.assertIn("Ready for Pickup", html_body(message))

    def test_payment_pending_email_names_the_review_queue(self):
        self.order.set_status(Order.Status.PENDING_REVIEW)
        self.assertIn("review queue", self.last_message().body)
class NotificationResilienceTests(NotificationTestCase):
    """A mail outage must never take an order down with it."""

    def test_broken_mail_server_never_breaks_order_creation(self):
        with mock.patch.object(
            notifications.EmailMultiAlternatives, "send",
            side_effect=OSError("connection refused"),
        ):
            response = self.api.post("/api/orders/", {
                "files": [self.upload()],
                "guest_name": "Ana Reyes",
                "guest_contact_method": "email",
                "guest_contact_value": GUEST_EMAIL,
            }, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Order.objects.get(pk=response.json()["order"]["id"]).status,
                         Order.Status.AWAITING_PAYMENT)
        self.assertEqual(mail.outbox, [])

    def test_broken_mail_server_never_breaks_a_status_change(self):
        order = Order.objects.get(pk=self.place_guest_order()["id"])
        mail.outbox.clear()
        with mock.patch.object(
            notifications.EmailMultiAlternatives, "send",
            side_effect=OSError("connection refused"),
        ):
            order.set_status(Order.Status.PENDING_REVIEW)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING_REVIEW)
        self.assertTrue(order.history.filter(to_status=Order.Status.PENDING_REVIEW).exists())

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=False)
    def test_notifications_can_be_switched_off(self):
        order = Order.objects.get(pk=self.place_guest_order()["id"])
        mail.outbox.clear()
        order.set_status(Order.Status.PENDING_REVIEW)
        self.assertEqual(mail.outbox, [])


class AdminActionNotificationTests(NotificationTestCase):
    """End-to-end: the admin queue emails the customer at each decision."""

    def test_payment_and_revision_decisions_reach_the_customer(self):
        order = self.place_guest_order()
        checkout = self.api.post("/api/payments/checkout/", {
            "order_id": order["id"], "method": "qrph", "payment_type": "full",
        }, format="json")
        self.assertIn(checkout.status_code, (200, 201), checkout.content)

        mail.outbox.clear()
        self.api.post("/api/payments/webhook/simulate/",
                      {"payment_id": checkout.json()["payment_id"]}, format="json")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [GUEST_EMAIL])
        self.assertIn("review queue", mail.outbox[0].body)

        admin = self.login(ADMIN_EMAIL, "ownerpass123")
        mail.outbox.clear()
        revision = admin.post(
            f"/api/admin/orders/{order['id']}/actions/request_revision/",
            {"note": "Page 2 is cut off — please re-upload."}, format="json",
        )
        self.assertEqual(revision.status_code, 200, revision.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [GUEST_EMAIL])
        self.assertIn("Page 2 is cut off", mail.outbox[0].body)
        self.assertIn(order["tracking_id"], mail.outbox[0].subject)