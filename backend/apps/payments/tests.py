"""Regression tests for the PayMongo QR Ph checkout integration.

These pin down two things that used to break the live flow:

* the exact QR Ph ``Payment Method`` payload sent to PayMongo (no ``amount`` /
  ``currency`` — those attributes are rejected), and
* that a gateway failure becomes a readable JSON error instead of an opaque
  HTTP 500 (the initial incident: ``/api/payments/checkout/`` returned the
  Django "Server Error (500)" page).
"""
import hashlib
import hmac
from unittest.mock import patch

import requests
from django.test import TestCase
from rest_framework.test import APIClient

from apps.orders.models import Order

from .models import Payment
from .paymongo import PayMongoClient, PayMongoError
from .views import _signature_valid


class QrPhPaymentMethodPayloadTests(TestCase):
    """A QR Ph Payment Method carries only the attributes PayMongo allows."""

    def _create_payment_method(self, **kwargs):
        captured = {}

        def fake_request(method, path, payload=None):
            captured.update(method=method, path=path, payload=payload)
            return {"data": {"id": "pm_test_123"}}

        client = PayMongoClient(mock_mode=False)
        with patch.object(client, "_request", side_effect=fake_request):
            result = client.create_payment_method(**kwargs)
        return result, captured

    def test_amount_and_currency_are_not_sent(self):
        result, captured = self._create_payment_method(
            amount=1800, name="Juan Dela Cruz", email="juan@example.com",
            phone="09171234567", expiry_seconds=1800,
        )
        self.assertEqual(result["id"], "pm_test_123")
        self.assertEqual(captured["path"], "/payment_methods")
        attributes = captured["payload"]["data"]["attributes"]
        self.assertEqual(attributes["type"], "qrph")
        self.assertNotIn("amount", attributes)
        self.assertNotIn("currency", attributes)
        self.assertEqual(attributes["expiry_seconds"], 1800)
        self.assertEqual(
            attributes["billing"],
            {"name": "Juan Dela Cruz", "email": "juan@example.com", "phone": "09171234567"},
        )

    def test_blank_billing_fields_are_dropped(self):
        _, captured = self._create_payment_method(amount=100, name="", email="", phone="  ")
        attributes = captured["payload"]["data"]["attributes"]
        self.assertEqual(attributes, {"type": "qrph"})


class CheckoutErrorHandlingTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.order = Order.objects.create(subtotal=1800)

    def _checkout(self):
        return self.api.post(
            "/api/payments/checkout/",
            {"order_id": self.order.id, "method": "qrph", "payment_type": "full"},
            format="json",
        )

    def test_paymongo_rejection_is_not_a_500(self):
        with patch(
            "apps.payments.services.create_checkout",
            side_effect=PayMongoError("PayMongo POST /payment_methods failed (400): bad attribute"),
        ):
            response = self._checkout()
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("PayMongo", response.json()["detail"])

    def test_unreachable_paymongo_returns_503(self):
        with patch(
            "apps.payments.services.create_checkout",
            side_effect=requests.ConnectionError("connection refused"),
        ):
            response = self._checkout()
        self.assertEqual(response.status_code, 503, response.content)
        self.assertIn("Could not reach PayMongo", response.json()["detail"])


class WebhookRoutingTests(TestCase):
    def test_root_webhook_alias_is_routable(self):
        """The /webhook path registered in the PayMongo dashboard reaches us."""
        response = APIClient().post("/webhook", {"data": {}}, format="json")
        self.assertEqual(response.status_code, 200, response.content)

    def test_qrph_expired_marks_payment_expired(self):
        """qrph.expired points at the Payment Intent, whose id is the intent id."""
        order = Order.objects.create(subtotal=1800)
        payment = Payment.objects.create(
            order=order, payment_intent_id="pi_test_1", amount=1800,
        )
        payload = {
            "data": {
                "attributes": {
                    "type": "qrph.expired",
                    "data": {"type": "payment_intent", "attributes": {"id": "pi_test_1"}},
                }
            }
        }
        response = APIClient().post("/webhook", payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.EXPIRED)


class WebhookSignatureTests(TestCase):
    def test_current_te_format_is_accepted(self):
        body = b'{"data":{"id":"evt_1"}}'
        secret = "whsec_test"
        timestamp = "1700000000"
        digest = hmac.new(
            secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
        self.assertTrue(_signature_valid(body, f"t={timestamp},te={digest},li=deadbeef", secret))

    def test_legacy_v1_format_still_accepted(self):
        body = b'{"data":{"id":"evt_1"}}'
        secret = "whsec_test"
        timestamp = "1700000000"
        digest = hmac.new(
            secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
        self.assertTrue(_signature_valid(body, f"t={timestamp},v1={digest}", secret))

    def test_tampered_body_is_rejected(self):
        self.assertFalse(_signature_valid(b"{}", "t=1,te=deadbeef", "whsec_test"))
