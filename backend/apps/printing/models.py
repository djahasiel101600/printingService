from django.db import models

from apps.orders.models import Order


class PrintJob(models.Model):
    """One Epson Connect print job (one per order file)."""

    class JobStatus(models.TextChoices):
        CREATED = "created", "Created"
        SUBMITTED = "submitted", "Submitted to Epson"
        EXECUTED = "executed", "Executed"
        PRINTING = "printing", "Printing"
        COMPLETED = "completed", "Completed"
        ON_HOLD = "on_hold", "On Hold - Printer Issue"
        CANCELED = "canceled", "Canceled"
        FAILED = "failed", "Failed"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="print_jobs")
    order_file = models.ForeignKey("orders.OrderFile", null=True, on_delete=models.SET_NULL, related_name="print_jobs")
    epson_job_id = models.CharField(max_length=64, blank=True)
    upload_uri = models.CharField(max_length=512, blank=True)
    printer_name = models.CharField(max_length=128, blank=True)
    print_mode = models.CharField(max_length=16, blank=True)          # document | photo
    print_settings_snapshot = models.JSONField(default=dict, blank=True)
    # Page numbers actually sent for this file (empty = every page). Snapshot so
    # the history of a reprint still shows what each run contained.
    pages_snapshot = models.JSONField(default=list, blank=True)
    is_reprint = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=JobStatus.choices, default=JobStatus.CREATED)
    epson_status = models.CharField(max_length=32, blank=True)        # raw Epson status enum
    pages_printed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"PrintJob {self.epson_job_id or '?'} for {self.order.tracking_id}"

    @property
    def is_printer_cancelled(self) -> bool:
        """The printer dropped the job rather than the shop or the client."""
        return self.status == self.JobStatus.CANCELED

    @property
    def pages_label(self) -> str:
        from apps.orders.models import format_page_selection

        pages = self.pages_snapshot or []
        return format_page_selection(pages) if pages else "All pages"


class EpsonCredential(models.Model):
    """Singleton holding the rotating Epson OAuth device refresh token.

    Epson issues a brand-new refresh token every time one is redeemed, so the
    value pasted into the environment goes stale after the first refresh. The
    live token is persisted here instead — it survives restarts and is shared by
    every gunicorn worker, which is what makes unattended printing keep working.
    """

    refresh_token = models.TextField(blank=True)
    # Anti-CSRF value for the in-flight authorization-code flow (PRD §7.1 setup).
    pending_state = models.CharField(max_length=128, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Epson credential"
        verbose_name_plural = "Epson credential"

    def __str__(self) -> str:
        state = "connected" if self.refresh_token else "not connected"
        return f"Epson device credential ({state})"

    @classmethod
    def load(cls) -> "EpsonCredential":
        """Fetch (or create) the single credential row."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
