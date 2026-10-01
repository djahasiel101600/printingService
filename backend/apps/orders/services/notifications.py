"""Status-change notifications (PRD §2.1: email / on-site tracking page).

Emails go through Django's email backend (console in development). Every
transition is also recorded in OrderStatusHistory, which powers the tracking
page timeline.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.orders.models import Order

log = logging.getLogger(__name__)

CLIENT_MESSAGES = {
    Order.Status.PENDING_REVIEW: "We received your payment and your order is now in the review queue.",
    Order.Status.REVISION_REQUESTED: "Our staff requested a few changes to your order before we can print it.",
    Order.Status.APPROVED_QUEUED: "Your order was approved and is queued for printing.",
    Order.Status.PRINTING: "Your order is currently printing.",
    Order.Status.ON_HOLD: "Your order is temporarily on hold due to a printer issue. We're on it.",
    Order.Status.PRINTED_READY: "Your printouts are ready for pickup! Present your tracking ID.",
    Order.Status.REJECTED: "Unfortunately your order was rejected. Any paid amount will be refunded.",
    Order.Status.CANCELLED: "Your order was cancelled. Any paid amount will be refunded.",
    Order.Status.COMPLETED: "Your order is complete. Thank you for printing with us!",
}


def notify_status_change(order: Order, old_status: str, new_status: str, note: str = "") -> None:
    """Email the client on status changes that matter to them."""
    message = CLIENT_MESSAGES.get(new_status)
    if not message:
        return
    recipient = order.contact_email
    if not recipient:
        log.info("No email for order %s; skipping notification", order.tracking_id)
        return
    body = [
        f"Hi {order.client_display_name},",
        "",
        message,
        "",
        f"Order: {order.tracking_id}",
        f"Status: {order.get_status_display()}",
        f"Balance due: PHP {order.balance_due / 100:.2f}",
        "",
        f"Track your order any time at {settings.FRONTEND_URL}/track using your tracking ID.",
    ]
    if note:
        body.insert(4, f"Note from our staff: {note}")
    try:
        send_mail(
            subject=f"Order {order.tracking_id} — {order.get_status_display()}",
            message="\n".join(body),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:  # noqa: BLE001 - notifications must never break orders
        log.exception("Notification failed for order %s", order.tracking_id)
