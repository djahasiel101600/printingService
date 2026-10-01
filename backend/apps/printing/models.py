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
