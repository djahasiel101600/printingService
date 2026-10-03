"""PayMongo API client — Payment Intent + QR Ph workflow (PRD §7.2).

Flow implemented (https://developers.paymongo.com):
1. POST /v1/payment_intents         amount, payment_method_allowed=[qrph]
2. POST /v1/payment_methods         type=qrph + billing details
3. POST /v1/payment_intents/{id}/attach   with client_key -> QR code image
4. Webhooks: payment.paid / payment.failed / qrph.expired
5. POST /v1/refunds                 for rejected/cancelled paid orders

All amounts are integers in centavos. Authentication is HTTP Basic with the
secret key as username. ``PAYMONGO_MOCK_MODE`` replaces every call with an
in-memory simulator (including a scannable-looking placeholder QR) so the
checkout flow can be demoed without live keys.
"""
from __future__ import annotations

import base64
import logging
import uuid

import requests
from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)

API_BASE = "https://api.paymongo.com/v1"


class PayMongoError(Exception):
    pass


class PayMongoClient:
    def __init__(self, mock_mode: bool | None = None):
        self.mock_mode = settings.PAYMONGO_MOCK_MODE if mock_mode is None else mock_mode
        self.secret_key = settings.PAYMONGO_SECRET_KEY

    # ------------------------------------------------------------------ http
    @staticmethod
    def _normalise_qr_image(url: str) -> str:
        """Ensure the QR value is something an ``<img src>`` can render.

        PayMongo documents ``next_action.code.image_url`` as "a Base64-encoded
        string". In practice it is normally a full ``data:image/...`` URL, but
        when it is a bare Base64 blob the frontend would show a broken image
        instead of a scannable QR Ph code. Pass through anything already
        renderable (data/HTTP URLs); prefix only a bare blob.
        """
        value = (url or "").strip()
        if not value:
            return ""
        if value.startswith(("data:", "http://", "https://")):
            return value
        return "data:image/png;base64," + "".join(value.split())

    def _auth_header(self) -> dict:
        encoded = base64.b64encode(f"{self.secret_key}:".encode()).decode()
        return {"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        response = requests.request(
            method, f"{API_BASE}{path}", headers=self._auth_header(), json=payload, timeout=30,
        )
        body = response.json() if response.content else {}
        if response.status_code >= 400:
            errors = body.get("errors", body)
            raise PayMongoError(f"PayMongo {method} {path} failed ({response.status_code}): {errors}")
        return body

    # ----------------------------------------------------------------- mocks
    def _mock_qr(self, intent_id: str) -> str:
        """1x1 transparent PNG data URL placeholder (no live QR in mock mode)."""
        return ("data:image/png;base64,"
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
                "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")

    # ------------------------------------------------------------------- api
    def create_payment_intent(self, amount: int, description: str, statement_descriptor: str = "PRINT SERVICE") -> dict:
        if self.mock_mode:
            return {"id": f"pi_mock_{uuid.uuid4().hex[:24]}", "client_key": "ck_mock_client",
                    "amount": amount, "status": "awaiting_payment_method", "next_action": None}
        body = {
            "data": {
                "attributes": {
                    "amount": amount,
                    "currency": "PHP",
                    "payment_method_allowed": ["qrph"],
                    "description": description,
                    "statement_descriptor": statement_descriptor[:24],
                }
            }
        }
        data = self._request("POST", "/payment_intents", body)["data"]
        return {"id": data["id"], "client_key": data["attributes"].get("client_key", ""),
                "amount": data["attributes"]["amount"], "status": data["attributes"].get("status"),
                "next_action": data["attributes"].get("next_action")}

    def create_payment_method(
        self, amount: int, name: str, email: str, phone: str, expiry_seconds: int | None = None,
    ) -> dict:
        """Create a QR Ph Payment Method.

        A QR Ph Payment Method carries no amount (the Payment Intent does):
        PayMongo only accepts ``type`` (plus the optional ``expiry_seconds`` /
        ``billing``), and rejects any other attribute with a 400. Sending
        ``amount`` / ``currency`` here previously made every live checkout fail.
        """
        if self.mock_mode:
            return {"id": f"pm_mock_{uuid.uuid4().hex[:24]}"}
        attributes: dict = {"type": "qrph"}
        if expiry_seconds:
            # Seconds until the generated QR expires after attaching (60-9000).
            attributes["expiry_seconds"] = expiry_seconds
        # Only include billing fields we actually have — an empty-string email
        # or phone is itself a validation error on PayMongo's side.
        billing = {"name": (name or "").strip(), "email": (email or "").strip(), "phone": (phone or "").strip()}
        billing = {key: value for key, value in billing.items() if value}
        if billing:
            attributes["billing"] = billing
        body = {"data": {"attributes": attributes}}
        return {"id": self._request("POST", "/payment_methods", body)["data"]["id"]}

    def attach_payment_method(self, intent_id: str, payment_method_id: str, client_key: str, return_url: str) -> dict:
        """Attach -> returns next_action with the QR Ph image URL."""
        if self.mock_mode:
            next_action = {
                "code": {"image_url": self._mock_qr(intent_id),
                         "expires_at": int(timezone.now().timestamp()) + 30 * 60},
            }
            return {
                "status": "awaiting_payment_method",
                "next_action": next_action,
                "image_url": next_action["code"]["image_url"],
                "expires_at": next_action["code"]["expires_at"],
            }
        body_attributes = {"payment_method": payment_method_id}
        # Only send optional fields when we actually have a value: an empty
        # `client_key` is rejected as an invalid client key, and an empty
        # `return_url` is worse than omitting it.
        if client_key:
            body_attributes["client_key"] = client_key
        if return_url:
            body_attributes["return_url"] = return_url
        body = {"data": {"attributes": body_attributes}}
        data = self._request("POST", f"/payment_intents/{intent_id}/attach", body)["data"]["attributes"]
        next_action = data.get("next_action") or {}
        return {
            "status": data.get("status"),
            "next_action": next_action,
            "image_url": self._normalise_qr_image(
                (next_action.get("code") or {}).get("image_url", "")
            ),
            "expires_at": (next_action.get("code") or {}).get("expires_at"),
        }

    def create_refund(self, payment_id: str, amount: int, reason: str) -> dict:
        if self.mock_mode:
            return {"id": f"rf_mock_{uuid.uuid4().hex[:24]}", "status": "succeeded", "amount": amount}
        body = {"data": {"attributes": {"payment_id": payment_id, "amount": amount, "reason": reason}}}
        return self._request("POST", "/refunds", body)["data"]["attributes"]
