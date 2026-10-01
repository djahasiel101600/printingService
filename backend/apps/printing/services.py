"""Submit approved orders to the Epson printer and track job progress.

Implements PRD §7.1: for every file of an approved order create an Epson job
(job_name derived from the tracking ID), upload the (edited) file to the job's
uploadUri, then execute it. ``sync_print_jobs`` polls job status and maps the
Epson lifecycle back onto our order statuses.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from apps.orders.models import Order

from .constants import EPSON_STATUS_TO_ORDER_STATUS
from .epson import EpsonClient, EpsonError
from .models import PrintJob

log = logging.getLogger(__name__)


def _print_mode_for(file_type: str) -> str:
    """photo mode for images, document mode for PDFs (PRD §7.1)."""
    return "photo" if file_type == "image" else "document"


def _print_settings(spec) -> dict:
    """Map PrintSpecification -> Epson printSettings (camelCase API names)."""
    if spec is None:
        return {}
    return {
        "paperSize": spec.media_size,
        "paperType": spec.media_type,
        "borderless": spec.borderless,
        "printQuality": spec.print_quality,
        "paperSource": spec.source,
        "colorMode": spec.color_mode,
        "doubleSided": spec.sides,
        "reverseOrder": spec.reverse_order,
        "copies": min(99, max(1, spec.copies)),
        "collate": spec.collate,
    }


def submit_order_to_printer(order: Order) -> list[PrintJob]:
    """Create + upload + execute an Epson job for every file of the order."""
    client = EpsonClient()
    printer_name = _safe_printer_name(client)
    jobs: list[PrintJob] = []
    for order_file in order.files.all():
        spec = getattr(order_file, "specification", None)
        settings_snapshot = _print_settings(spec)
        job = PrintJob.objects.create(
            order=order,
            order_file=order_file,
            printer_name=printer_name,
            print_mode=_print_mode_for(order_file.file_type),
            print_settings_snapshot=settings_snapshot,
            status=PrintJob.JobStatus.CREATED,
        )
        try:
            result = client.create_job(
                job_name=f"{order.tracking_id}-{order_file.pk}",
                print_mode=job.print_mode,
                print_settings=settings_snapshot,
            )
            job.epson_job_id = result.job_id
            job.upload_uri = result.upload_uri
            with order_file.print_file.open("rb") as handle:
                content = handle.read()
            client.upload_file(result.upload_uri, order_file.file_name, content)
            client.execute_job(result.job_id)
            job.status = PrintJob.JobStatus.EXECUTED
            job.submitted_at = timezone.now()
            job.save(update_fields=["epson_job_id", "upload_uri", "status", "submitted_at", "updated_at"])
        except EpsonError as exc:
            log.exception("Epson submission failed for order %s", order.tracking_id)
            job.status = PrintJob.JobStatus.FAILED
            job.error_message = str(exc)
            job.save(update_fields=["status", "error_message", "updated_at"])
        jobs.append(job)
    return jobs


def _safe_printer_name(client: EpsonClient) -> str:
    try:
        info = client.get_device_info()
        return info.get("productName") or "Epson Printer"
    except EpsonError:
        return "Epson Printer"


def sync_print_jobs(order: Order | None = None) -> None:
    """Poll Epson for job status and fold it into PrintJob / Order statuses."""
    queryset = PrintJob.objects.exclude(status__in=[PrintJob.JobStatus.COMPLETED, PrintJob.JobStatus.FAILED])
    if order is not None:
        queryset = queryset.filter(order=order)
    client = EpsonClient()
    for job in queryset.select_related("order"):
        if not job.epson_job_id:
            continue
        try:
            status = client.get_job_status(job.epson_job_id)
        except EpsonError as exc:
            log.warning("Status poll failed for job %s: %s", job.epson_job_id, exc)
            continue
        job.epson_status = status.status
        job.pages_printed = status.total_pages or job.pages_printed
        if status.status == "completed":
            job.status = PrintJob.JobStatus.COMPLETED
            job.completed_at = timezone.now()
        elif status.status == "canceled":
            job.status = PrintJob.JobStatus.CANCELED
        elif status.status in ("media_empty", "media_jam", "marker_supply_empty", "stopped_other", "error_occurred", "expired"):
            job.status = PrintJob.JobStatus.ON_HOLD
            job.error_message = f"Printer reported: {status.status}"
        elif status.status in ("pending", "processing", "preparing", "reserved"):
            job.status = PrintJob.JobStatus.PRINTING
        job.save()

        new_order_status = EPSON_STATUS_TO_ORDER_STATUS.get(status.status)
        if new_order_status and job.order.status not in (
            Order.Status.PENDING_REVIEW, Order.Status.REJECTED, Order.Status.CANCELLED, Order.Status.COMPLETED,
            Order.Status.REVISION_REQUESTED,
        ):
            if job.order.status != new_order_status:
                job.order.set_status(new_order_status, note=f"Epson job {job.epson_job_id}: {status.status}")
