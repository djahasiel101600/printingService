"""Checkout + webhook orchestration for PayMongo QR Ph payments."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.orders.models import Order

from .models import Payment, PaymentSettings
from .paymongo import PayMongoClient, PayMongoError

log = logging.getLogger(__name__)


def parse_expiry(value) -> datetime | None:
    """Normalise a PayMongo QR expiry into an aware ``datetime``.

    Live PayMongo returns ``next_action.code.expires_at`` as an **ISO-8601
    string** (e.g. ``"2026-10-03T08:17:56.000Z"``), while mock mode (and some
    older API versions) use a Unix timestamp — an int, or occasionally a
    numeric string. ``datetime.fromtimestamp`` only accepts the numeric form,
    so passing the live string straight through raised ``TypeError: 'str'
    object cannot be interpreted as an integer`` and turned every live checkout
    into a 502 *after* PayMongo had already generated the QR. Accept every
    shape and degrade to ``None`` rather than failing the checkout on an
    unknown format.
    """
    if value is None or value == "" or isinstance(value, bool):
        return None

    seconds: float | None = None
    if isinstance(value, (int, float)):
        seconds = value
    elif isinstance(value, str):
        try:
            seconds = float(value)
        except ValueError:
            parsed = parse_datetime(value.strip())
            if parsed is None:
                log.warning("Unrecognised PayMongo QR expiry value: %r", value)
                return None
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            return parsed
    else:
        log.warning("Unrecognised PayMongo QR expiry type: %r", type(value))
        return None

    try:
        return datetime.fromtimestamp(seconds, tz=timezone.get_current_timezone())
    except (OverflowError, OSError, ValueError) as exc:
        log.warning("Could not interpret PayMongo QR expiry %r: %s", value, exc)
        return None


def create_checkout(order: Order, payment_type: str) -> Payment:
    """Create a PaymentIntent for the full amount or the required down payment,
    attach a QR Ph payment method, and return the Payment carrying the QR."""
    if payment_type == Order.PaymentType.PARTIAL:
        min_amount = order.subtotal * settings.MIN_PARTIAL_PERCENT // 100
        amount = max(min_amount, 100)  # PayMongo minimum is PHP 1
        label = "Down payment"
    else:
        amount = order.subtotal
        label = "Full payment"

    if amount <= 0:
        raise PayMongoError("Nothing to pay for this order.")

    client = PayMongoClient()
    intent = client.create_payment_intent(
        amount=amount,
        description=f"{label} for order {order.tracking_id}",
    )
    payment_method = client.create_payment_method(
        amount=amount,
        name=order.client_display_name,
        email=order.contact_email,
        phone=order.guest_contact_value if order.guest_contact_method == Order.ContactMethod.PHONE else "",
        expiry_seconds=1800,  # 30 minutes, matching PayMongo's default QR lifetime
    )
    attached = client.attach_payment_method(
        intent_id=intent["id"],
        payment_method_id=payment_method["id"],
        client_key=intent.get("client_key", ""),
        return_url=f"{settings.FRONTEND_URL}/track",
    )

    # A checkout without a QR image is useless to the customer: surface it as an
    # actionable error instead of showing an empty placeholder they cannot pay.
    qr_image_url = attached.get("image_url") or ""
    if not qr_image_url:
        raise PayMongoError(
            "PayMongo attached the payment method but returned no QR Ph code image."
        )

    expires_at = parse_expiry(attached.get("expires_at"))

    payment = Payment.objects.create(
        order=order,
        payment_intent_id=intent["id"],
        amount=amount,
        method="qrph",
        status=Payment.Status.PENDING,
        qr_image_url=qr_image_url,
        checkout_expires_at=expires_at,
        raw_response={"attach": attached},
    )
    order.payment_type = payment_type
    order.payment_method = Order.PaymentMethod.QRPH
    if order.status == Order.Status.DRAFT:
        order.set_status(Order.Status.AWAITING_PAYMENT, note="QR Ph checkout generated")
    order.save(update_fields=["payment_type", "payment_method", "status"])
    return payment


def choose_pay_on_pickup(order: Order) -> None:
    """Customer opts to settle the balance when collecting the printout.

    The order moves straight into the review queue — nothing is collected now,
    so staff simply cash it in later via the `record_payment` admin action.
    """
    if not PaymentSettings.get_solo().allow_pay_on_pickup:
        raise PayMongoError("Pay upon pickup is currently disabled by the shop.")
    order.payment_method = Order.PaymentMethod.PICKUP
    if order.status in (Order.Status.DRAFT, Order.Status.AWAITING_PAYMENT):
        balance = order.balance_due
        order.set_status(
            Order.Status.PENDING_REVIEW,
            note=f"Customer chose to pay upon pickup; balance PHP {balance / 100:.2f} due on collection",
        )
    else:
        order.save(update_fields=["payment_method"])


def record_manual_payment(order: Order, actor=None) -> int:
    """Record a payment collected at the shop (cash or scanned QR Ph at pickup).

    Returns the amount recorded in centavos (0 when there is nothing due).
    """
    amount = order.balance_due
    if amount <= 0:
        return 0
    Payment.objects.create(
        order=order,
        payment_id=f"manual_{order.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}",
        amount=amount,
        method="cash",
        status=Payment.Status.PAID,
        paid_at=timezone.now(),
        raw_response={"recorded_by": getattr(actor, "email", "") or "staff"},
    )
    old_status = order.status
    order.amount_paid = min(order.subtotal, order.amount_paid + amount)
    if not order.payment_method:
        order.payment_method = Order.PaymentMethod.CASH
    order.save(update_fields=["amount_paid", "payment_method"])

    note = f"Payment of PHP {amount / 100:.2f} recorded at the shop"
    if old_status in (Order.Status.DRAFT, Order.Status.AWAITING_PAYMENT):
        order.set_status(Order.Status.PENDING_REVIEW, note=note, actor=actor)
    else:
        from apps.orders.models import OrderStatusHistory

        OrderStatusHistory.objects.create(
            order=order, from_status=old_status, to_status=old_status,
            note=note, actor=actor if getattr(actor, "is_authenticated", False) else None,
        )
    return amount


def mark_payment_paid(payment: Payment, paymongo_payment_id: str = "") -> None:
    """Apply a successful payment to its order (webhook or simulated)."""
    if payment.status == Payment.Status.PAID:
        return
    payment.status = Payment.Status.PAID
    payment.paid_at = timezone.now()
    if paymongo_payment_id:
        payment.payment_id = paymongo_payment_id
    payment.save(update_fields=["status", "paid_at", "payment_id", "updated_at"])

    order = payment.order
    order.amount_paid = min(order.subtotal, order.amount_paid + payment.amount)
    order.save(update_fields=["amount_paid"])

    if order.status in (Order.Status.AWAITING_PAYMENT, Order.Status.DRAFT):
        balance = order.balance_due
        note = "Payment received" if balance == 0 else f"Down payment received; balance due {balance / 100:.2f} PHP"
        order.set_status(Order.Status.PENDING_REVIEW, note=note)


def mark_payment_failed(payment: Payment, status_value: str) -> None:
    payment.status = Payment.Status.FAILED if status_value == "payment.failed" else Payment.Status.EXPIRED
    payment.save(update_fields=["status", "updated_at"])


def refund_payment(payment: Payment, reason: str = "requested_by_customer") -> bool:
    """Refund via PayMongo's Refunds API (mock mode simulates success)."""
    client = PayMongoClient()
    try:
        result = client.create_refund(payment_id=payment.payment_id, amount=payment.amount, reason=reason)
    except PayMongoError as exc:
        log.error("Refund failed for payment %s: %s", payment.id, exc)
        payment.refund_status = f"failed: {exc}"
        payment.save(update_fields=["refund_status", "updated_at"])
        return False
    payment.refund_status = result.get("status", "processing")
    payment.status = Payment.Status.REFUNDED
    payment.save(update_fields=["refund_status", "status", "updated_at"])
    return True


def refund_order(order: Order, reason: str) -> int:
    """Refund every paid payment of an order; returns count of refunds."""
    refunded = 0
    for payment in order.payments.filter(status=Payment.Status.PAID):
        if refund_payment(payment, reason=reason):
            refunded += 1
    return refunded
