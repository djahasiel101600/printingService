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
        # The printer (or its queue) dropped the job — nothing was printed.
        # Deliberately distinct from CANCELLED, which means the *customer* or
        # the shop called the whole order off. Recovery is a reprint, so the
        # job stays open and the admin gets a "Reprint" button.
        PRINT_CANCELLED = "print_cancelled", "Cancelled at Printer"
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

    # How many times the shop has re-sent this order to the printer. Reprints
    # keep the original order (and its audit trail) and add a new set of jobs.
    reprint_count = models.PositiveSmallIntegerField(default=0)

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
                # Only the pages the admin kept are charged for — an order where
                # pages 4-9 were dropped must not be billed for them.
                "page_count": order_file.selected_page_count,
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


def order_final_upload_to(instance, filename: str) -> str:
    """Storage for the admin-prepared file (page selection applied)."""
    return f"orders/{instance.order.tracking_id}/final/{filename}"


# Extensions we can render a preview for. ``PRINTABLE_EXTENSIONS`` is the much
# smaller set Epson Connect accepts on the upload endpoint (openapi.spec
# ``components.requestBodies.File``), so anything else must be converted to PDF
# by the shop before the job is released to the printer.
PREVIEWABLE_EXTENSIONS = (
    "pdf", "jpg", "jpeg", "png", "webp",
    "docx", "xlsx", "pptx", "txt", "md", "csv",
)
PRINTABLE_EXTENSIONS = ("pdf", "jpg", "jpeg", "png")
IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp")
# Sheet orientation for the printed page. Epson Connect v2 has no orientation
# parameter, so the shop applies it to the file itself before upload. Picture
# files are rotated to fill the sheet; PDFs and Word documents already carry
# their own page layout and ignore this value (see services/print_prep.py).
ORIENTATIONS = (
    ("portrait", "Portrait"),
    ("landscape", "Landscape"),
)

# Legacy binary Office formats cannot be parsed with the standard library and
# are rejected at upload time with a pointer to the modern equivalents.
LEGACY_EXTENSIONS = ("doc", "xls", "ppt")


def file_extension(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


class OrderFile(models.Model):
    """An uploaded (and optionally edited) file belonging to an order."""

    class FileType(models.TextChoices):
        PDF = "pdf", "PDF document"
        IMAGE = "image", "Image"
        DOCUMENT = "document", "Office / text document"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(
        upload_to=order_file_upload_to,
        validators=[FileExtensionValidator(allowed_extensions=list(PREVIEWABLE_EXTENSIONS))],
    )
    edited_file = models.FileField(upload_to=order_edited_upload_to, blank=True, null=True)
    # Produced by the shop: the customer's file with the admin's page selection
    # applied. Highest priority in ``print_file``.
    final_file = models.FileField(upload_to=order_final_upload_to, blank=True, null=True)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=8, choices=FileType.choices)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    page_count = models.PositiveIntegerField(default=1)
    # Chronological metadata of applied edits: [{action: crop|split|resize|center, ...args}]
    edit_actions = models.JSONField(default=list, blank=True)
    # 1-based page numbers the admin kept, e.g. [1, 2, 5]. An empty list means
    # "print the whole document" and is the default.
    page_selection = models.JSONField(default=list, blank=True)
    # Set when the shop replaces an un-printable upload (e.g. a .docx) with a
    # converted PDF, so the UI can explain why the file changed.
    replaced_by_admin = models.BooleanField(default=False)
    # Set when the shop rendered an Office/text upload into a printable PDF
    # itself (services/document_render.py) instead of converting it by hand.
    rendered_by_admin = models.BooleanField(default=False)
    # Customer re-upload counter: bumped each time the client replaces this
    # file after a revision request. Starts at 1 (the original upload);
    # superseded bytes live on OrderFileVersion rows.
    current_version = models.PositiveIntegerField(default=1)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self) -> str:
        return f"{self.file_name} ({self.order.tracking_id})"

    @property
    def extension(self) -> str:
        return file_extension(self.file_name)

    @property
    def print_ready(self) -> bool:
        """True when this file can be sent to Epson as-is.

        PDFs and images always qualify. An Office/text upload qualifies as
        soon as the shop has produced a print-ready version of it — either a
        converted upload the admin pasted in, or one rendered here
        (``edited_file``/``final_file``).
        """
        if self.file_type in {self.FileType.PDF, self.FileType.IMAGE}:
            return True
        return bool(self.edited_file or self.final_file)

    @property
    def selected_pages(self) -> list[int]:
        """Valid, sorted, de-duplicated 1-based page numbers to print."""
        try:
            numbers = {int(p) for p in (self.page_selection or [])}
        except (TypeError, ValueError):
            return []
        return sorted(n for n in numbers if 1 <= n <= self.page_count)

    @property
    def selected_page_count(self) -> int:
        """Number of pages actually printed (and charged for)."""
        selected = self.selected_pages
        return len(selected) if selected else max(1, self.page_count)

    @property
    def page_selection_active(self) -> bool:
        return bool(self.selected_pages) and len(self.selected_pages) < self.page_count

    @property
    def page_selection_label(self) -> str:
        """Human summary: 'All 8 pages' or '1–3, 7 of 8 pages'."""
        total = max(1, self.page_count)
        selected = self.selected_pages
        if not selected:
            return f"All {total} page{'s' if total != 1 else ''}"
        return f"{format_page_selection(selected)} of {total} page{'s' if total != 1 else ''}"

    @property
    def print_file(self):
        """The file that goes to the printer: shop-prepared > edited > original."""
        return self.final_file or self.edited_file or self.file

    @property
    def print_file_name(self) -> str:
        field = self.print_file
        name = field.name or f"{self.pk}.pdf"
        return name.rsplit("/", 1)[-1]

    @property
    def print_content_type(self) -> str:
        """Content type for ``print_file``.

        Anything the shop prepared is a PDF (page selection, a rendered
        document, a converted upload); a customer image edit lands as JPEG.
        """
        if self.final_file or self.edited_file:
            # Rendered documents and trimmed PDFs are always PDFs.
            pdf = {self.FileType.PDF, self.FileType.DOCUMENT}
            return "application/pdf" if self.file_type in pdf else "image/jpeg"
        return self.content_type or "application/octet-stream"


def order_file_version_upload_to(instance, filename: str) -> str:
    """Archive path for a superseded upload: unique per order file + version."""
    safe = (filename or "file").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return f"orders/{instance.order_file.order.tracking_id}/versions/{instance.order_file_id}_v{instance.version_number}_{safe}"


class OrderFileVersion(models.Model):
    """Immutable snapshot of an OrderFile before a customer re-upload.

    Created by the customer re-upload endpoint: the previous ``file`` (plus
    the metadata the quote depends on) is copied here, then the live
    OrderFile row is replaced. Edits (``edited_file``) and shop-prepared
    output (``final_file``) both derive from the old bytes, so the snapshot
    only keeps the original upload — derived artefacts are discarded with
    the old version.
    """

    order_file = models.ForeignKey(OrderFile, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    file = models.FileField(upload_to=order_file_version_upload_to)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=16, choices=OrderFile.FileType.choices)
    content_type = models.CharField(max_length=128, blank=True)
    size = models.PositiveIntegerField(default=0)
    page_count = models.PositiveIntegerField(default=0)
    edit_actions = models.JSONField(default=list)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="file_version_uploads",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["order_file", "version_number"], name="unique_file_version_number",
            ),
        ]

    def __str__(self) -> str:
        return f"v{self.version_number} of {self.file_name}"


def format_page_selection(pages: list[int]) -> str:
    """[1,2,3,7] -> '1-3, 7' (used in the UI and in status history notes)."""
    if not pages:
        return ""
    ordered = sorted(set(pages))
    groups: list[tuple[int, int]] = []
    start = prev = ordered[0]
    for number in ordered[1:]:
        if number == prev + 1:
            prev = number
            continue
        groups.append((start, prev))
        start = prev = number
    groups.append((start, prev))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in groups)


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
    # Portrait | Landscape. Applies to picture files only: the shop rotates the
    # picture so it fills the sheet in that orientation (Epson Connect has no
    # orientation setting, so it must be baked into the uploaded file).
    orientation = models.CharField(max_length=10, choices=ORIENTATIONS, default="portrait")
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

