"""Customer email notifications (PRD §2.1: email + on-site tracking page).

Two kinds of email, both driven by ``Order.set_status``:

* **Order placed** — the first transition into ``awaiting_payment`` (what
  ``OrderCreateView`` does the moment an order exists) sends the tracking ID.
  That ID is the only handle a guest has on their order, so it must reach them
  by email, not just on the confirmation screen.
* **Status update** — every other customer-visible status change sends the new
  status, the staff note when there is one, and the tracking link.

Recipients come from ``Order.contact_email``: the account email for a signed-in
customer, the contact value when a guest picked email, and nobody when a guest
left only a phone/facebook handle (they already have the tracking page).

Notifications are best-effort by design: they are sent inline, every failure is
logged and swallowed, so a dead mail server can never fail an order or a status
transition. ``EMAIL_NOTIFICATIONS_ENABLED`` switches them off wholesale and
``EMAIL_TIMEOUT`` bounds how long a request can wait on SMTP.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.validators import ValidationError, validate_email
from django.template.loader import render_to_string

from apps.orders.models import Order

log = logging.getLogger(__name__)

# One message per customer-visible status, written the way a shop counter would
# say it. A status missing from this map still gets an email (with the neutral
# fallback below) so a new status can never silently stop notifying.
CLIENT_MESSAGES = {
    Order.Status.AWAITING_PAYMENT: "We've received your order. Please complete the payment to send it to print.",
    Order.Status.PENDING_REVIEW: "We received your payment and your order is now in the review queue.",
    Order.Status.REVISION_REQUESTED: "Our staff requested a few changes to your order before we can print it.",
    Order.Status.APPROVED_QUEUED: "Your order was approved and is queued for printing.",
    Order.Status.PRINTING: "Your order is currently printing.",
    Order.Status.ON_HOLD: "Your order is temporarily on hold due to a printer issue. We're on it.",
    Order.Status.PRINT_CANCELLED: "The printer couldn't finish this job, so nothing was printed yet. Our staff will reprint it — nothing for you to do.",
    Order.Status.PRINTED_READY: "Your printouts are ready for pickup! Present your tracking ID.",
    Order.Status.REJECTED: "Unfortunately your order was rejected. Any paid amount will be refunded.",
    Order.Status.CANCELLED: "Your order was cancelled. Any paid amount will be refunded.",
    Order.Status.COMPLETED: "Your order is complete. Thank you for printing with us!",
}

# A draft is an internal working state: orders are created with it directly
# (without going through set_status), so there is nothing to announce.
SILENT_STATUSES = {Order.Status.DRAFT}


def notify_status_change(order: Order, old_status: str, new_status: str, note: str = "") -> bool:
    """Email the customer about this transition. Returns True when one was sent."""
    if new_status in SILENT_STATUSES:
        return False
    if old_status == new_status:
        # The same status re-applied (the checkout endpoint repeating
        # "awaiting payment", an admin re-saving a note): the history keeps the
        # audit trail, the customer's inbox does not get a duplicate.
        return False
    if not getattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", True):
        log.info("Email notifications are disabled; skipped order %s", order.tracking_id)
        return False

    recipient = _recipient(order)
    if not recipient:
        log.info("No email address for order %s; notification skipped", order.tracking_id)
        return False

    context = _context(order, new_status, note)
    if _is_placement(old_status, new_status):
        subject = f"Your print order is in — tracking ID {order.tracking_id}"
        template = "emails/order_placed"
    else:
        subject = f"Order {order.tracking_id} — {order.get_status_display()}"
        template = "emails/order_status"
    return _send(subject, template, context, recipient, order)


def _is_placement(old_status: str, new_status: str) -> bool:
    """Placing an order is the first transition into ``awaiting_payment``."""
    return (
        new_status == Order.Status.AWAITING_PAYMENT
        and (old_status in ("", None) or old_status == Order.Status.DRAFT)
    )


def _recipient(order: Order) -> str:
    """The customer's email address, or "" when they cannot be emailed.

    Signed-in customers get their account address; guests only get one when the
    contact method they chose was email (a phone/facebook-only guest is reached
    through the tracking page instead).
    """
    email = (order.contact_email or "").strip()
    if not email:
        return ""
    try:
        validate_email(email)
    except ValidationError:
        log.warning(
            "Order %s has an unusable contact address (%r); notification skipped",
            order.tracking_id, email,
        )
        return ""
    return email


def _context(order: Order, status: str, note: str) -> dict:
    return {
        "order": order,
        "client_name": order.client_display_name,
        "tracking_id": order.tracking_id,
        "status_display": order.get_status_display(),
        "message": CLIENT_MESSAGES.get(status, "Your order has been updated."),
        "note": note or "",
        "subtotal": f"{order.subtotal / 100:.2f}",
        "balance_due": f"{order.balance_due / 100:.2f}",
        "file_count": order.files.count(),
        "track_url": f"{settings.FRONTEND_URL.rstrip('/')}/track",
    }


def _send(subject: str, template: str, context: dict, recipient: str, order: Order) -> bool:
    """Render and send one email; never let a mail problem reach the caller."""
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=render_to_string(f"{template}.txt", context),
            from_email=settings.DEFAULT_FROM_EMAIL or settings.SERVER_EMAIL,
            to=[recipient],
        )
        # Plain text first, HTML as the alternative — some mail clients and
        # spam filters still prefer the simple part.
        message.attach_alternative(render_to_string(f"{template}.html", context), "text/html")
        message.send()  # not fail_silently: we log the real reason ourselves
        return True
    except Exception:  # noqa: BLE001 - notifications must never break orders
        log.exception(
            "Could not send the '%s' email for order %s", context["status_display"],
            order.tracking_id,
        )
        return False
