"""Checkout + webhook orchestration for PayMongo QR Ph payments."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.orders.models import Order

from .models import Payment
from .paymongo import PayMongoClient, PayMongoError

log = logging.getLogger(__name__)


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
    )
    attached = client.attach_payment_method(
        intent_id=intent["id"],
        payment_method_id=payment_method["id"],
        client_key=intent.get("client_key", ""),
        return_url=f"{settings.FRONTEND_URL}/track",
    )

    expires_at = None
    if attached.get("expires_at"):
        expires_at = timezone.datetime.fromtimestamp(attached["expires_at"], tz=timezone.get_current_timezone())

    payment = Payment.objects.create(
        order=order,
        payment_intent_id=intent["id"],
        amount=amount,
        method="qrph",
        status=Payment.Status.PENDING,
        qr_image_url=attached.get("image_url", ""),
        checkout_expires_at=expires_at,
        raw_response={"attach": attached},
    )
    order.payment_type = payment_type
    if order.status == Order.Status.DRAFT:
        order.set_status(Order.Status.AWAITING_PAYMENT, note="QR Ph checkout generated")
    order.save(update_fields=["payment_type", "status"])
    return payment


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
