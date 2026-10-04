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
from apps.orders.services.print_prep import prepare_order_for_print

from .constants import EPSON_STATUS_LABELS, EPSON_STATUS_TO_ORDER_STATUS
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


def submit_order_to_printer(
    order: Order, reprint: bool = False, order_files=None,
) -> list[PrintJob]:
    """Create + upload + execute an Epson job for every printable file.

    ``reprint=True`` tags the jobs so the admin can tell a re-run apart from
    the original run in the job history. ``order_files`` narrows the run to a
    subset (reprinting only the sheet the printer cancelled, say).
    Files that are not print-ready (a .docx waiting to be converted) are
    skipped with a recorded reason rather than pushed to Epson, which would
    only reject them.
    """
    client = EpsonClient()
    printer_name = _safe_printer_name(client)
    files = list(order.files.all() if order_files is None else order_files)
    # Single choke point for every release path (approve, reprint, resubmit):
    # bake the fit onto each paper's printable area, plus the page selection,
    # into the file that is about to be uploaded. See orders.services.print_prep.
    prepare_order_for_print(order, order_files=files)
    jobs: list[PrintJob] = []
    for order_file in files:
        spec = getattr(order_file, "specification", None)
        settings_snapshot = _print_settings(spec)
        job = PrintJob.objects.create(
            order=order,
            order_file=order_file,
            printer_name=printer_name,
            print_mode=_print_mode_for(order_file.file_type),
            print_settings_snapshot=settings_snapshot,
            pages_snapshot=order_file.selected_pages,
            is_reprint=reprint,
            status=PrintJob.JobStatus.CREATED,
        )
        if not order_file.print_ready:
            job.status = PrintJob.JobStatus.FAILED
            job.error_message = (
                f"Skipped: '{order_file.file_name}' is a "
                f"{order_file.get_file_type_display().lower()} and cannot be sent to the printer. "
                "Convert it to PDF and replace the file before releasing the order."
            )
            job.save(update_fields=["status", "error_message", "updated_at"])
            jobs.append(job)
            continue
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
            client.upload_file(result.upload_uri, order_file.print_file_name, content)
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


def printable_files(order: Order):
    """Files that can actually be sent to the printer right now."""
    return [order_file for order_file in order.files.all() if order_file.print_ready]


def unprintable_files(order: Order):
    """Files blocking release (unconverted Office/text uploads)."""
    return [order_file for order_file in order.files.all() if not order_file.print_ready]


def _safe_printer_name(client: EpsonClient) -> str:
    try:
        info = client.get_device_info()
        return info.get("productName") or "Epson Printer"
    except EpsonError:
        return "Epson Printer"


ACTIVE_JOB_STATUSES = (
    PrintJob.JobStatus.CREATED, PrintJob.JobStatus.SUBMITTED,
    PrintJob.JobStatus.EXECUTED, PrintJob.JobStatus.PRINTING,
)

# Jobs in these states will never change again, so there is nothing to poll.
# CANCELED matters most: without it a job the printer dropped would be picked
# up by the next sync and resurrected as "printing".
TERMINAL_JOB_STATUSES = (
    PrintJob.JobStatus.COMPLETED, PrintJob.JobStatus.FAILED, PrintJob.JobStatus.CANCELED,
)


def _has_active_jobs(order: Order) -> bool:
    """True while any sheet of the order is still queued or printing."""
    return order.print_jobs.filter(status__in=ACTIVE_JOB_STATUSES).exists()


def sync_print_jobs(order: Order | None = None) -> None:
    """Poll Epson for job status and fold it into PrintJob / Order statuses."""
    queryset = PrintJob.objects.exclude(status__in=TERMINAL_JOB_STATUSES)
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
        elif status.status in ("canceled", "expired"):
            # The printer dropped the job on its own — nothing was printed.
            job.status = PrintJob.JobStatus.CANCELED
            job.error_message = (
                "The printer cancelled this job before it finished "
                f"(printer reported: {status.status}). Reprint it from the admin order page."
            )
        elif status.status in ("media_empty", "media_jam", "marker_supply_empty", "stopped_other", "error_occurred"):
            job.status = PrintJob.JobStatus.ON_HOLD
            job.error_message = f"Printer reported: {status.status}"
        elif status.status in ("pending", "processing", "preparing", "reserved"):
            job.status = PrintJob.JobStatus.PRINTING
        job.save()

        new_order_status = EPSON_STATUS_TO_ORDER_STATUS.get(status.status)
        if not new_order_status:
            continue
        # Orders the admin or customer already decided on are never overridden
        # by a printer poll.
        if job.order.status in (
            Order.Status.PENDING_REVIEW, Order.Status.REJECTED, Order.Status.CANCELLED,
            Order.Status.COMPLETED, Order.Status.REVISION_REQUESTED,
            Order.Status.PRINT_CANCELLED,
        ):
            continue
        if new_order_status == Order.Status.PRINT_CANCELLED and _has_active_jobs(job.order):
            # Other sheets of the same order are still going — keep the order in
            # its current state and let the admin reprint the cancelled file.
            continue
        if job.order.status != new_order_status:
            label = EPSON_STATUS_LABELS.get(status.status, status.status)
            job.order.set_status(
                new_order_status,
                note=(
                    f"Printer cancelled job {job.epson_job_id} ({label}). "
                    "Nothing was printed — reprint from the admin page."
                    if new_order_status == Order.Status.PRINT_CANCELLED
                    else f"Epson job {job.epson_job_id}: {label}"
                ),
            )
