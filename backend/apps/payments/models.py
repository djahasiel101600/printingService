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
