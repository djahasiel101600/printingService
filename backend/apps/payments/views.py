import hmac
import hashlib
import logging

import requests
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer

from apps.pricing.views import IsShopAdmin

from .models import Payment, PaymentSettings
from .paymongo import PayMongoClient, PayMongoError
from . import services

log = logging.getLogger(__name__)


class CheckoutSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    method = serializers.ChoiceField(choices=["qrph", "pickup"], default="qrph")
    payment_type = serializers.ChoiceField(
        choices=[Order.PaymentType.FULL, Order.PaymentType.PARTIAL], required=False,
    )

    def validate_order_id(self, value):
        order = Order.objects.filter(id=value).first()
        if not order:
            raise serializers.ValidationError("Order not found.")
        user = self.context["request"].user
        if order.user and order.user != user:
            raise serializers.ValidationError("You do not have access to this order.")
        if order.status not in (Order.Status.DRAFT, Order.Status.AWAITING_PAYMENT):
            raise serializers.ValidationError(f"Order is not payable (status: {order.status}).")
        return value

    def validate(self, attrs):
        if attrs.get("method", "qrph") == "qrph" and not attrs.get("payment_type"):
            raise serializers.ValidationError(
                {"payment_type": "Choose full or partial payment when paying by QR Ph."}
            )
        if attrs.get("method") == "pickup" and not PaymentSettings.get_solo().allow_pay_on_pickup:
            raise serializers.ValidationError(
                {"method": "Pay upon pickup is currently disabled by the shop."}
            )
        return attrs


class CheckoutView(APIView):
    """Create a QR Ph checkout (PaymentIntent -> attach -> QR image URL),
    or record the customer's choice to pay upon pickup."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = Order.objects.get(id=serializer.validated_data["order_id"])
        method = serializer.validated_data.get("method", "qrph")

        if method == "pickup":
            try:
                services.choose_pay_on_pickup(order)
            except PayMongoError as exc:
                return Response({"detail": str(exc)}, status=400)
            return Response({
                "method": "pickup",
                "detail": "Pay upon pickup selected. Pay the balance when you collect your order.",
                "order": OrderSerializer(order).data,
            }, status=201)

        # Talking to PayMongo can fail for reasons the customer can act on
        # (method not activated, bad key, amount outside limits) or that they
        # cannot (the shop's server can't reach PayMongo). Surface both as a
        # readable JSON error instead of an opaque 500.
        try:
            payment = services.create_checkout(order, serializer.validated_data["payment_type"])
        except PayMongoError as exc:
            # PayMongo itself rejected the request — actionable, answer 400.
            log.warning("PayMongo checkout rejected for order %s: %s", order.tracking_id, exc)
            return Response({"detail": str(exc)}, status=400)
        except requests.RequestException as exc:
            log.exception("PayMongo unreachable for order %s", order.tracking_id)
            return Response(
                {"detail": f"Could not reach PayMongo to start the payment: {exc}"}, status=503,
            )
        except Exception as exc:  # noqa: BLE001 - never a bare 500 on the payment path
            # Belt and braces: a malformed gateway response or a DB hiccup still
            # has to explain itself rather than become "Server Error (500)".
            log.exception("Unexpected checkout failure for order %s", order.tracking_id)
            return Response(
                {"detail": f"Checkout failed ({type(exc).__name__}): {exc}"}, status=502,
            )

        return Response({
            "method": "qrph",
            "payment_id": payment.id,
            "amount": payment.amount,
            "amount_peso": payment.amount / 100,
            "payment_type": order.payment_type,
            "qr_image_url": payment.qr_image_url,
            "expires_at": payment.checkout_expires_at,
            "status": payment.status,
            "mock_mode": settings.PAYMONGO_MOCK_MODE,
        }, status=201)


class PaymentSettingsView(APIView):
    """Public read / admin write for the shop's payment options."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        settings_obj = PaymentSettings.get_solo()
        return Response({
            "allow_pay_on_pickup": settings_obj.allow_pay_on_pickup,
            "updated_at": settings_obj.updated_at,
        })

    def put(self, request):
        if not (request.user and request.user.is_authenticated and request.user.is_shop_admin):
            return Response({"detail": "Admin access required."}, status=403)
        value = request.data.get("allow_pay_on_pickup")
        if not isinstance(value, bool):
            return Response({"detail": "allow_pay_on_pickup must be a boolean."}, status=400)
        settings_obj = PaymentSettings.get_solo()
        settings_obj.allow_pay_on_pickup = value
        settings_obj.save(update_fields=["allow_pay_on_pickup", "updated_at"])
        return Response({
            "allow_pay_on_pickup": settings_obj.allow_pay_on_pickup,
            "updated_at": settings_obj.updated_at,
        })


class WebhookView(APIView):
    """PayMongo webhook receiver: payment.paid / payment.failed / qrph.expired."""

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request):
        secret = settings.PAYMONGO_WEBHOOK_SECRET
        if secret:
            signature = request.headers.get("Paymongo-Signature", "")
            if not _signature_valid(request.body, signature, secret):
                return Response({"detail": "Invalid signature"}, status=400)
        event = request.data.get("data", {})
        attributes = event.get("attributes", {}) if isinstance(event, dict) else {}
        event_type = attributes.get("type", "")
        resource_data = attributes.get("data", {}) if isinstance(attributes, dict) else {}
        resource = resource_data.get("attributes", {}) if isinstance(resource_data, dict) else {}
        resource_type = resource_data.get("type", "") if isinstance(resource_data, dict) else ""
        # `payment.paid` / `payment.failed` point at the payment, which carries
        # `payment_intent_id`. `qrph.expired` instead points at the Payment
        # Intent itself, whose resource id *is* the intent id.
        intent_id = resource.get("payment_intent_id", "")
        if not intent_id and resource_type == "payment_intent":
            intent_id = resource.get("id", "")

        payment = Payment.objects.filter(payment_intent_id=intent_id).first()
        if not payment:
            return Response({"detail": "Unknown payment intent ignored"}, status=200)

        if event_type == "payment.paid":
            services.mark_payment_paid(payment, paymongo_payment_id=resource.get("id", ""))
        elif event_type in ("payment.failed", "qrph.expired"):
            services.mark_payment_failed(payment, event_type)
        return HttpResponse(status=200)


class PayMongoTestConnectionView(APIView):
    """Test the PayMongo API connection with current credentials.

    Mirrors the customer's real QR Ph checkout (intent -> payment method ->
    attach) so a passing result means checkout will actually work. Note that
    ``mock_mode=True`` exercises the simulator, which always succeeds and so
    proves nothing about the live secret key.
    """

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def post(self, request):
        mock_mode = request.data.get("mock_mode")
        client = PayMongoClient(mock_mode=mock_mode if mock_mode is not None else None)
        result = {"mock_mode": client.mock_mode, "tests": {}}

        intent = None
        method = None

        # Test 1: Create payment intent
        try:
            intent = client.create_payment_intent(1000, "Test connection")
            result["tests"]["create_intent"] = {"status": "success", "intent_id": intent.get("id", "")}
        except Exception as exc:
            result["tests"]["create_intent"] = {"status": "failed", "error": str(exc)[:300]}

        # Test 2: Create payment method (QR Ph)
        try:
            method = client.create_payment_method(1000, "Test", "test@example.com", "09171234567")
            result["tests"]["create_payment_method"] = {"status": "success", "method_id": method.get("id", "")}
        except Exception as exc:
            result["tests"]["create_payment_method"] = {"status": "failed", "error": str(exc)[:300]}

        # Test 3: Attach — the step that produces the QR image. Checkout used to
        # fail here even when the two tests above passed, so it must be covered.
        if intent and method:
            try:
                attached = client.attach_payment_method(
                    intent_id=intent["id"],
                    payment_method_id=method["id"],
                    client_key=intent.get("client_key", ""),
                    return_url=f"{settings.FRONTEND_URL}/track",
                )
                has_qr = bool(attached.get("image_url"))
                result["tests"]["attach_payment_method"] = {
                    "status": "success" if has_qr else "failed",
                    "intent_status": attached.get("status"),
                    "has_qr_image": has_qr,
                    "error": None if has_qr else "Attach succeeded but returned no QR image URL.",
                }
            except Exception as exc:
                result["tests"]["attach_payment_method"] = {"status": "failed", "error": str(exc)[:300]}
        else:
            result["tests"]["attach_payment_method"] = {
                "status": "skipped",
                "error": "Skipped: the payment intent or payment method could not be created.",
            }

        all_passed = all(t["status"] == "success" for t in result["tests"].values())
        result["overall"] = "success" if all_passed else "failed"
        return Response(result)


class SimulatePaymentView(APIView):
    """DEV ONLY (mock mode): simulate the payment.paid webhook for a Payment."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not settings.PAYMONGO_MOCK_MODE:
            return Response({"detail": "Only available in PayMongo mock mode."}, status=403)
        payment = Payment.objects.filter(id=request.data.get("payment_id")).first()
        if not payment:
            return Response({"detail": "Payment not found"}, status=404)
        services.mark_payment_paid(payment, paymongo_payment_id=f"pay_mock_{payment.id}")
        order = payment.order
        return Response({
            "detail": "Payment simulated as paid.",
            "order": {"id": order.id, "tracking_id": order.tracking_id,
                      "status": order.status, "amount_paid": order.amount_paid,
                      "balance_due": order.balance_due},
        })


def _signature_valid(body: bytes, signature_header: str, secret: str) -> bool:
    """PayMongo signs webhooks as a comma-separated list of ``key=value`` pairs.

    The current header is ``t=<unix>,te=<test-hmac>,li=<live-hmac>``; older
    integrations used ``t=<unix>,v1=<hmac>``. The signed string is
    ``"<timestamp>." + <raw body>``. Accept whichever digest PayMongo sends.
    """
    try:
        parts = dict(part.split("=", 1) for part in signature_header.split(",") if "=" in part)
        timestamp = parts["t"]
    except (KeyError, ValueError):
        return False
    payload = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    for key in ("v1", "te", "li"):
        received = parts.get(key, "")
        if received and hmac.compare_digest(expected, received):
            return True
    return False
