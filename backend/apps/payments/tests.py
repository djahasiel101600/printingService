"""Regression tests for the PayMongo QR Ph checkout integration.

These pin down the things that broke the live flow:

* the exact QR Ph ``Payment Method`` payload sent to PayMongo (no ``amount`` /
  ``currency`` — those attributes are rejected),
* the ``attach`` payload (empty ``client_key`` is omitted), and
* that a gateway failure becomes a readable JSON error instead of an opaque
  HTTP 500 (the incident: ``/api/payments/checkout/`` returned the Django
  "Server Error (500)" page).

``_live_paymongo_response`` feeds the code realistic non-mock API bodies so the
whole checkout path is exercised without real credentials.
"""
import hashlib
import hmac
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.orders.models import Order

from .models import Payment
from .paymongo import PayMongoClient, PayMongoError
from .views import _signature_valid


def _live_paymongo_response(method, path, payload=None):
    """Stand-in for PayMongoClient._request using real API response shapes."""
    if path == "/payment_intents":
        return {"data": {"id": "pi_live_1", "type": "payment_intent", "attributes": {
            "amount": payload["data"]["attributes"]["amount"],
            "client_key": "pi_live_1_client_abc",
            "status": "awaiting_payment_method",
        }}}
    if path == "/payment_methods":
        return {"data": {"id": "pm_live_1", "type": "payment_method", "attributes": {"type": "qrph"}}}
    if path.endswith("/attach"):
        return {"data": {"id": "pi_live_1", "type": "payment_intent", "attributes": {
            "status": "awaiting_next_action",
            "next_action": {"type": "display", "code": {
                "image_url": "data:image/png;base64,LIVERESPONSE==",
                "expires_at": 1800000000,
            }},
        }}}
    raise AssertionError(f"unexpected PayMongo path: {path}")


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


class QrPhAttachPayloadTests(TestCase):
    """Attach must never send an empty client_key (rejected by PayMongo)."""

    def _attach(self, **kwargs):
        captured = {}

        def fake_request(method, path, payload=None):
            captured.update(method=method, path=path, payload=payload)
            return {"data": {"attributes": {"status": "awaiting_next_action",
                                            "next_action": {"code": {"image_url": "x", "expires_at": 1}}}}}

        client = PayMongoClient(mock_mode=False)
        with patch.object(client, "_request", side_effect=fake_request):
            client.attach_payment_method(**kwargs)
        return captured

    def test_empty_client_key_and_return_url_are_omitted(self):
        captured = self._attach(intent_id="pi_1", payment_method_id="pm_1",
                                client_key="", return_url="")
        attributes = captured["payload"]["data"]["attributes"]
        self.assertEqual(attributes, {"payment_method": "pm_1"})
        self.assertEqual(captured["path"], "/payment_intents/pi_1/attach")

    def test_provided_client_key_and_return_url_are_sent(self):
        captured = self._attach(intent_id="pi_1", payment_method_id="pm_1",
                                client_key="pi_1_client_abc", return_url="https://x/track")
        attributes = captured["payload"]["data"]["attributes"]
        self.assertEqual(attributes["client_key"], "pi_1_client_abc")
        self.assertEqual(attributes["return_url"], "https://x/track")


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

    def test_unexpected_error_is_reported_not_a_500(self):
        """Any other failure still explains itself instead of a bare 500."""
        with patch(
            "apps.payments.services.create_checkout",
            side_effect=KeyError("attributes"),
        ):
            response = self._checkout()
        self.assertEqual(response.status_code, 502, response.content)
        self.assertIn("KeyError", response.json()["detail"])


class LiveCheckoutFlowTests(TestCase):
    """Drive /payments/checkout/ against realistic (non-mock) API responses."""

    def setUp(self):
        self.api = APIClient()
        self.order = Order.objects.create(subtotal=1800)

    @override_settings(PAYMONGO_MOCK_MODE=False)
    def test_live_checkout_returns_the_qr_image(self):
        with patch.object(PayMongoClient, "_request", side_effect=_live_paymongo_response):
            response = self.api.post(
                "/api/payments/checkout/",
                {"order_id": self.order.id, "method": "qrph", "payment_type": "full"},
                format="json",
            )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["qr_image_url"], "data:image/png;base64,LIVERESPONSE==")
        self.assertFalse(body["mock_mode"])
        self.assertEqual(body["amount"], 1800)

    @override_settings(PAYMONGO_MOCK_MODE=False)
    def test_live_attach_payload_matches_the_documented_shape(self):
        captured = []

        def capture(method, path, payload=None):
            captured.append((path, payload))
            return _live_paymongo_response(method, path, payload)

        with patch.object(PayMongoClient, "_request", side_effect=capture):
            self.api.post(
                "/api/payments/checkout/",
                {"order_id": self.order.id, "method": "qrph", "payment_type": "full"},
                format="json",
            )
        attach_path, attach_body = captured[-1]
        self.assertTrue(attach_path.endswith("/attach"))
        attributes = attach_body["data"]["attributes"]
        self.assertEqual(attributes["payment_method"], "pm_live_1")
        self.assertEqual(attributes["client_key"], "pi_live_1_client_abc")
        # The intent must allow QR Ph and the method must be a bare `qrph` type
        # (no amount/currency — those are rejected for QR Ph Payment Methods).
        self.assertEqual(captured[0][1]["data"]["attributes"]["payment_method_allowed"], ["qrph"])
        method_attributes = captured[1][1]["data"]["attributes"]
        self.assertEqual(method_attributes["type"], "qrph")
        self.assertNotIn("amount", method_attributes)
        self.assertNotIn("currency", method_attributes)


class PayMongoTestConnectionEndpointTests(TestCase):
    """The admin "Test Connection" button must cover attach — the step that failed."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        self.api = APIClient()
        User = get_user_model()
        admin = User.objects.create_user(
            username="paymongo-admin@print.local", email="paymongo-admin@print.local",
            password="s3cretpass!", role=User.Role.ADMIN,
        )
        self.api.force_authenticate(admin)

    @override_settings(PAYMONGO_MOCK_MODE=False)
    def test_endpoint_runs_intent_method_and_attach(self):
        with patch.object(PayMongoClient, "_request", side_effect=_live_paymongo_response):
            response = self.api.post(
                "/api/admin/paymongo/test-connection/", {"mock_mode": False}, format="json",
            )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["overall"], "success")
        self.assertIn("attach_payment_method", body["tests"])
        self.assertEqual(body["tests"]["attach_payment_method"]["status"], "success")
        self.assertTrue(body["tests"]["attach_payment_method"]["has_qr_image"])
        self.assertFalse(body["mock_mode"])

    def test_endpoint_reports_attach_failure(self):
        def fail_attach(method, path, payload=None):
            if path.endswith("/attach"):
                raise PayMongoError("PayMongo POST /payment_intents/x/attach failed (400): nope")
            return _live_paymongo_response(method, path, payload)

        with patch.object(PayMongoClient, "_request", side_effect=fail_attach):
            response = self.api.post(
                "/api/admin/paymongo/test-connection/", {"mock_mode": False}, format="json",
            )
        body = response.json()
        self.assertEqual(body["overall"], "failed")
        self.assertEqual(body["tests"]["attach_payment_method"]["status"], "failed")
        self.assertIn("attach", body["tests"]["attach_payment_method"]["error"])


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
