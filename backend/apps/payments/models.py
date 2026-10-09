from django.db import models

from apps.orders.models import Order


class Payment(models.Model):
    """A PayMongo Payment Intent attached to an order (QR Ph)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting scan"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    payment_intent_id = models.CharField(max_length=64, blank=True, db_index=True)
    payment_id = models.CharField(max_length=64, blank=True)  # PayMongo payment resource id
    amount = models.PositiveIntegerField(help_text="Centavos charged for this intent")
    method = models.CharField(max_length=16, default="qrph")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    qr_image_url = models.TextField(blank=True)
    checkout_expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    refund_status = models.CharField(max_length=32, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Payment {self.payment_intent_id or '?'} {self.amount / 100:.2f} ({self.status})"


class PaymentSettings(models.Model):
    """Shop-wide payment options (singleton row, always pk=1).

    GET is public so the checkout UI knows which options to offer; writes are
    restricted to shop admins (see PaymentSettingsView).
    """

    allow_pay_on_pickup = models.BooleanField(
        default=True,
        help_text="Customers may choose to settle the balance when they pick up their printout.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Payment settings (pay upon pickup: {self.allow_pay_on_pickup})"

    @classmethod
    def get_solo(cls) -> "PaymentSettings":
        settings_obj, _ = cls.objects.get_or_create(pk=1)
        return settings_obj


class SalesEntry(models.Model):
    """Append-only sales ledger — the shop's book of record.

    Rows are written the moment money moves (QR payment confirmed, cash
    recorded, refund issued) and are **never deleted**: the sales
    dashboard reads this table instead of Order/Payment, so hard-deleting
    an order cannot erase revenue from the books. ``order``/``payment``
    use SET_NULL and ``tracking_id``/``method`` are snapshotted, so a
    deleted order leaves a traceable entry behind instead of a hole.

    Refunds append their own entry, so net sales (payments − refunds)
    always equals what the shop actually kept: deleting a paid order
    refunds it first, which nets it out of sales without losing the
    audit trail.

    ``kind`` decides the sign — payment = +, refund = − (amount stays
    positive centavos on the row itself).
    """

    class Kind(models.TextChoices):
        PAYMENT = "payment", "Payment"
        REFUND = "refund", "Refund"

    payment = models.ForeignKey(
        Payment, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="sales_entries",
    )
    order = models.ForeignKey(
        Order, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="sales_entries",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    amount = models.PositiveIntegerField(
        help_text="Centavos; kind decides the sign (+payment / −refund).")
    method = models.CharField(max_length=16, default="qrph")       # snapshot
    tracking_id = models.CharField(max_length=20, db_index=True)   # snapshot
    reason = models.CharField(max_length=64, blank=True)           # refund reason / recorder
    occurred_at = models.DateTimeField(db_index=True)              # paid_at / refund time
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "kind"],
                name="unique_sales_entry_per_payment_and_kind",
            ),
        ]

    def __str__(self) -> str:
        sign = "+" if self.kind == self.Kind.PAYMENT else "-"
        return f"{self.kind} {sign}{self.amount / 100:.2f} PHP ({self.tracking_id})"

    @property
    def amount_peso(self) -> float:
        return self.amount / 100

    @property
    def signed_amount(self) -> int:
        return self.amount if self.kind == self.Kind.PAYMENT else -self.amount

    @classmethod
    def record_payment(cls, payment: Payment) -> "SalesEntry | None":
        """Ledger one confirmed payment. Idempotent for webhook retries."""
        if cls.objects.filter(payment=payment, kind=cls.Kind.PAYMENT).exists():
            return None
        return cls.objects.create(
            payment=payment, order=payment.order, kind=cls.Kind.PAYMENT,
            amount=payment.amount, method=payment.method,
            tracking_id=payment.order.tracking_id,
            reason=((payment.raw_response or {}).get("recorded_by") or "")[:64],
            occurred_at=payment.paid_at or timezone.now(),
        )

    @classmethod
    def record_refund(cls, payment: Payment, reason: str = "") -> "SalesEntry | None":
        """Ledger a completed refund (mirrors record_payment)."""
        if cls.objects.filter(payment=payment, kind=cls.Kind.REFUND).exists():
            return None
        return cls.objects.create(
            payment=payment, order=payment.order, kind=cls.Kind.REFUND,
            amount=payment.amount, method=payment.method,
            tracking_id=payment.order.tracking_id,
            reason=(reason or "")[:64], occurred_at=timezone.now(),
        )
