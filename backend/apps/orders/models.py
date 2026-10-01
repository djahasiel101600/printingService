import secrets

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


def generate_tracking_id() -> str:
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no easily-confused chars
    body = "-".join(
        "".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2)
    )
    return f"PSP-{body}"


class Order(models.Model):
    """A print order. Follows the status lifecycle in PRD §8."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting Payment"
        PENDING_REVIEW = "pending_review", "Pending Review"
        REVISION_REQUESTED = "revision_requested", "Revision Requested"
        APPROVED_QUEUED = "approved_queued", "Approved / Queued"
        PRINTING = "printing", "Printing"
        ON_HOLD = "on_hold", "On Hold - Printer Issue"
        PRINTED_READY = "printed_ready", "Printed - Ready for Pickup"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    class PaymentType(models.TextChoices):
        FULL = "full", "Full payment"
        PARTIAL = "partial", "Partial / down payment"

    class PaymentMethod(models.TextChoices):
        QRPH = "qrph", "QR Ph (online)"
        PICKUP = "pickup", "Pay upon pickup"
        CASH = "cash", "Cash / recorded at the shop"

    class ContactMethod(models.TextChoices):
        EMAIL = "email", "Email"
        PHONE = "phone", "Phone"
        FACEBOOK = "facebook", "Facebook Messenger"

    tracking_id = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="orders",
    )
    # Guest contact snapshot (PRD §9)
    guest_name = models.CharField(max_length=128, blank=True)
    guest_contact_method = models.CharField(max_length=16, choices=ContactMethod.choices, blank=True)
    guest_contact_value = models.CharField(max_length=254, blank=True)

    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    payment_type = models.CharField(max_length=16, choices=PaymentType.choices, blank=True)
    # How the customer chose to settle the bill: QR Ph checkout, pay upon
    # pickup, or a payment recorded by staff at the counter.
    payment_method = models.CharField(max_length=16, choices=PaymentMethod.choices, blank=True)

    subtotal = models.PositiveIntegerField(default=0, help_text="Centavos")
    amount_paid = models.PositiveIntegerField(default=0, help_text="Centavos")

    admin_notes = models.TextField(blank=True, help_text="Internal notes, never shown to clients")
    revision_note = models.TextField(blank=True, help_text="Sent to the client when a revision is requested")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.tracking_id} ({self.get_status_display()})"

    # ------------------------------------------------------------- helpers
    @property
    def balance_due(self) -> int:
        return max(0, self.subtotal - self.amount_paid)

    @property
    def is_paid_in_full(self) -> bool:
        return self.amount_paid >= self.subtotal and self.subtotal > 0

    @property
    def client_display_name(self) -> str:
        if self.user:
            return self.user.get_full_name() or self.user.email
        return self.guest_name or "Guest"

    @property
    def contact_email(self) -> str:
        if self.guest_contact_method == self.ContactMethod.EMAIL:
            return self.guest_contact_value
        return self.user.email if self.user else ""

    def contact_matches(self, value: str) -> bool:
        """Guest tracking requires the tracking ID plus a contact match (PRD §6)."""
        if not value:
            return False
        candidates = [self.guest_contact_value]
        if self.user:
            candidates += [self.user.email, self.user.phone]
        value = value.strip().lower()
        return any(value == str(candidate).strip().lower() for candidate in candidates if candidate)

    def set_status(self, new_status: str, note: str = "", actor=None, save: bool = True):
        """Transition status, record history, and stamp lifecycle timestamps."""
        old = self.status
        self.status = new_status
        now = timezone.now()
        if new_status == self.Status.APPROVED_QUEUED and not self.approved_at:
            self.approved_at = now
        if new_status == self.Status.COMPLETED:
            self.completed_at = now
        if save:
            self.save()
            OrderStatusHistory.objects.create(
                order=self, from_status=old, to_status=new_status,
                note=note,
                actor=actor if getattr(actor, "is_authenticated", False) else None,
            )
            from .services.notifications import notify_status_change

            notify_status_change(self, old, new_status, note)

    def quote_specs(self) -> list[dict]:
        specs = []
        for order_file in self.files.all():
            spec = getattr(order_file, "specification", None)
            specs.append({
                "label": order_file.file_name,
                "page_count": order_file.page_count,
                "media_size": spec.media_size if spec else "ps_a4",
                "media_type": spec.media_type if spec else "pt_plainpaper",
                "color_mode": spec.color_mode if spec else "mono",
                "print_quality": spec.print_quality if spec else "normal",
                "sides": spec.sides if spec else "none",
                "copies": spec.copies if spec else 1,
            })
        return specs

    def save(self, *args, **kwargs):
        if not self.tracking_id:
            for _ in range(10):
                candidate = generate_tracking_id()
                if not Order.objects.filter(tracking_id=candidate).exists():
                    self.tracking_id = candidate
                    break
        super().save(*args, **kwargs)


def order_file_upload_to(instance, filename: str) -> str:
    return f"orders/{instance.order.tracking_id}/original/{filename}"


def order_edited_upload_to(instance, filename: str) -> str:
    return f"orders/{instance.order.tracking_id}/edited/{filename}"


class OrderFile(models.Model):
    """An uploaded (and optionally edited) file belonging to an order."""

    class FileType(models.TextChoices):
        PDF = "pdf", "PDF document"
        IMAGE = "image", "Image"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(
        upload_to=order_file_upload_to,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "jpg", "jpeg", "png"])],
    )
    edited_file = models.FileField(upload_to=order_edited_upload_to, blank=True, null=True)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=8, choices=FileType.choices)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    page_count = models.PositiveIntegerField(default=1)
    # Chronological metadata of applied edits: [{action: crop|split|resize|center, ...args}]
    edit_actions = models.JSONField(default=list, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self) -> str:
        return f"{self.file_name} ({self.order.tracking_id})"

    @property
    def print_file(self):
        """The file that goes to the printer: edited version if present."""
        return self.edited_file or self.file


class PrintSpecification(models.Model):
    """Client-facing print options, mapped 1:1 to Epson Connect v2 parameters."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="specifications")
    order_file = models.OneToOneField(
        OrderFile, on_delete=models.CASCADE, related_name="specification", null=True, blank=True,
    )

    media_size = models.CharField(max_length=32, default="ps_a4")
    media_type = models.CharField(max_length=32, default="pt_plainpaper")
    color_mode = models.CharField(max_length=16, default="mono")          # color | mono
    sides = models.CharField(max_length=8, default="none")                # none | long | short
    print_quality = models.CharField(max_length=16, default="normal")     # draft | normal | high
    copies = models.PositiveSmallIntegerField(default=1)
    borderless = models.BooleanField(default=False)
    source = models.CharField(max_length=16, default="auto")              # Epson paperSource
    # Advanced options (hidden behind the Advanced toggle in the UI)
    reverse_order = models.BooleanField(default=False)
    collate = models.BooleanField(default=True)

    free_text_instructions = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        target = self.order_file.file_name if self.order_file else "order-wide"
        return f"Spec for {target}"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24)
    note = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "Order status histories"

    def __str__(self) -> str:
        return f"{self.order.tracking_id}: {self.from_status or '∅'} → {self.to_status}"

