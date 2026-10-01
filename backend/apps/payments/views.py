import hmac
import hashlib

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order

from apps.pricing.views import IsShopAdmin

from .models import Payment
from . import services


class CheckoutSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    payment_type = serializers.ChoiceField(choices=[Order.PaymentType.FULL, Order.PaymentType.PARTIAL])

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


class CheckoutView(APIView):
    """Create a QR Ph checkout (PaymentIntent -> attach -> QR image URL)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = Order.objects.get(id=serializer.validated_data["order_id"])
        payment = services.create_checkout(order, serializer.validated_data["payment_type"])
        return Response({
            "payment_id": payment.id,
            "amount": payment.amount,
            "amount_peso": payment.amount / 100,
            "payment_type": order.payment_type,
            "qr_image_url": payment.qr_image_url,
            "expires_at": payment.checkout_expires_at,
            "status": payment.status,
        }, status=201)


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
        resource = attributes.get("data", {}).get("attributes", {}) if isinstance(attributes, dict) else {}
        intent_id = resource.get("payment_intent_id", "")

        payment = Payment.objects.filter(payment_intent_id=intent_id).first()
        if not payment:
            return Response({"detail": "Unknown payment intent ignored"}, status=200)

        if event_type == "payment.paid":
            services.mark_payment_paid(payment, paymongo_payment_id=resource.get("id", ""))
        elif event_type in ("payment.failed", "qrph.expired"):
            services.mark_payment_failed(payment, event_type)
        return HttpResponse(status=200)


class PayMongoTestConnectionView(APIView):
    """Test the PayMongo API connection with current credentials."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def post(self, request):
        mock_mode = request.data.get("mock_mode")
        from .paymongo import PayMongoClient, PayMongoError
        client = PayMongoClient(mock_mode=mock_mode if mock_mode is not None else None)
        result = {"mock_mode": client.mock_mode, "tests": {}}

        # Test 1: Create payment intent
        try:
            intent = client.create_payment_intent(1000, "Test connection")
            result["tests"]["create_intent"] = {"status": "success", "intent_id": intent.get("id", "")}
        except Exception as exc:
            result["tests"]["create_intent"] = {"status": "failed", "error": str(exc)[:200]}

        # Test 2: Create payment method
        try:
            method = client.create_payment_method(1000, "Test", "test@example.com", "09171234567")
            result["tests"]["create_payment_method"] = {"status": "success", "method_id": method.get("id", "")}
        except Exception as exc:
            result["tests"]["create_payment_method"] = {"status": "failed", "error": str(exc)[:200]}

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
    """PayMongo signs webhooks as '<timestamp>,<hmac-hex>' pairs."""
    try:
        parts = dict(part.split("=", 1) for part in signature_header.split(",") if "=" in part)
        timestamp, received = parts["t"], parts.get("v1", "")
    except (KeyError, ValueError):
        return False
    payload = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)
