"""Submit approved orders to the Epson printer and track job progress.

Epson's ``colorMode`` applies to an entire job. Mixed Auto-mode PDFs are
therefore split into contiguous mono/color segments after page selection and
paper fitting have produced ``final_file``. ``sync_print_jobs`` aggregates the
latest submission run and waits for older active jobs before marking an order ready.
"""
from __future__ import annotations

import io
import logging
import uuid
from dataclasses import dataclass

from django.utils import timezone
from pypdf import PdfReader, PdfWriter

from apps.orders.models import Order
from apps.orders.services.color_analysis import effective_page_modes
from apps.orders.services.print_prep import prepare_order_for_print

from .epson import EpsonClient, EpsonError
from .models import PrintJob

log = logging.getLogger(__name__)
MAX_JOBS_PER_ORDER = 24


def _print_mode_for(file_type: str) -> str:
    """photo mode for images, document mode for PDFs (PRD §7.1)."""
    return "photo" if file_type == "image" else "document"


def _print_settings(spec, *, color_mode: str, copies: int) -> dict:
    """Map a specification to Epson settings with a concrete job-wide mode."""
    mode = color_mode if color_mode in ("color", "mono") else "color"
    settings = {} if spec is None else {
        "paperSize": spec.media_size,
        "paperType": spec.media_type,
        "borderless": spec.borderless,
        "printQuality": spec.print_quality,
        "paperSource": spec.source,
        "doubleSided": spec.sides,
        "reverseOrder": spec.reverse_order,
        "collate": spec.collate,
    }
    # ``auto`` is an application-only value and must never reach Epson.
    settings["colorMode"] = mode
    settings["copies"] = min(99, max(1, copies))
    return settings


@dataclass(frozen=True)
class _PrintSegment:
    mode: str
    output_pages: tuple[int, ...] = ()
    source_pages: tuple[int, ...] = ()
    segment_index: int = 1
    copy_index: int = 1
    segment_count: int = 1
    copies: int = 1
    whole_file: bool = True
    error: str = ""


def _page_segments(
    page_modes: list[tuple[int, str]], *, duplex: bool,
) -> list[tuple[str, tuple[int, ...], tuple[int, ...]]]:
    """Group prepared output pages into contiguous job-wide color modes.

    Output-page positions are 1-based in ``final_file``; source pages are the
    customer's original page numbers. Duplex jobs are grouped by physical sheet
    so a segment never ends halfway through a sheet.
    """
    entries = [
        (position, source_page, mode)
        for position, (source_page, mode) in enumerate(page_modes, start=1)
    ]
    if duplex:
        units = []
        for offset in range(0, len(entries), 2):
            sheet = entries[offset:offset + 2]
            mode = "color" if any(entry[2] == "color" for entry in sheet) else "mono"
            units.append((mode, sheet))
    else:
        units = [(entry[2], [entry]) for entry in entries]

    groups = []
    current_mode = None
    current = []
    for mode, unit in units:
        if current and mode != current_mode:
            groups.append((current_mode, current))
            current = []
        current_mode = mode
        current.extend(unit)
    if current:
        groups.append((current_mode, current))

    return [
        (mode, tuple(entry[0] for entry in group), tuple(entry[1] for entry in group))
        for mode, group in groups
    ]


def _read_print_file(order_file) -> bytes:
    field = order_file.print_file
    field.open("rb")
    try:
        return field.read()
    finally:
        field.close()


def _extract_pdf_pages(content: bytes, pages: tuple[int, ...]) -> bytes:
    reader = PdfReader(io.BytesIO(content))
    writer = PdfWriter()
    for page in pages:
        writer.add_page(reader.pages[page - 1])
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _whole_file_segment(order_file, mode: str, *, error: str = "") -> _PrintSegment:
    spec = getattr(order_file, "specification", None)
    copies = min(99, max(1, getattr(spec, "copies", 1) or 1))
    return _PrintSegment(
        mode=mode if mode in ("color", "mono") else "color",
        source_pages=tuple(order_file.selected_pages),
        copies=copies,
        error=error,
    )


def _file_segments(order_file) -> list[_PrintSegment]:
    """Build Epson job descriptors for one prepared order file."""
    spec = getattr(order_file, "specification", None)
    if not order_file.print_ready:
        return [_whole_file_segment(order_file, "mono", error=(
            f"Skipped: '{order_file.file_name}' is a "
            f"{order_file.get_file_type_display().lower()} and cannot be sent to the printer. "
            "Convert it to PDF and replace the file before releasing the order."
        ))]

    requested = getattr(spec, "color_mode", "mono") or "mono"
    if requested != "auto":
        # Explicit mono/color keeps the original one-job-per-file behaviour,
        # including Epson's native multi-copy handling.
        return [_whole_file_segment(
            order_file, requested if requested in ("color", "mono") else "mono",
        )]

    try:
        page_modes = effective_page_modes(order_file, spec)
        if not page_modes:
            page_modes = [(1, "color")]
        if order_file.file_type in (order_file.FileType.PDF, order_file.FileType.DOCUMENT):
            prepared_pages = len(PdfReader(io.BytesIO(_read_print_file(order_file))).pages)
            if prepared_pages != len(page_modes):
                raise ValueError(
                    f"Prepared PDF has {prepared_pages} pages but page-mode analysis "
                    f"expects {len(page_modes)}; refusing to print the wrong page split."
                )
        if len({mode for _, mode in page_modes}) == 1:
            return [_whole_file_segment(order_file, page_modes[0][1])]

        logical = _page_segments(
            page_modes, duplex=(getattr(spec, "sides", "none") != "none"),
        )
        copies = min(99, max(1, getattr(spec, "copies", 1) or 1))
        segment_count = len(logical)
        indexed = list(enumerate(logical, start=1))
        ordered = list(reversed(indexed)) if getattr(spec, "reverse_order", False) else indexed
        descriptors = []
        # Collated output completes one whole document before the next copy.
        # Uncollated output keeps all copies of a segment together instead.
        if getattr(spec, "collate", True):
            triples = (
                (copy, position, segment)
                for copy in range(1, copies + 1)
                for position, segment in ordered
            )
        else:
            triples = (
                (copy, position, segment)
                for position, segment in ordered
                for copy in range(1, copies + 1)
            )
        for copy_index, position, (mode, output_pages, source_pages) in triples:
            # ``position`` is the segment's logical document index, independent
            # of reversed submission order.
            descriptors.append(_PrintSegment(
                mode=mode,
                output_pages=output_pages,
                source_pages=source_pages,
                segment_index=position,
                copy_index=copy_index,
                segment_count=segment_count,
                copies=1,
                whole_file=False,
            ))
        return descriptors
    except Exception as exc:  # noqa: BLE001 - record a failed job, never a 500
        log.warning("Could not segment '%s' of order %s: %s",
                    order_file.file_name, order_file.order.tracking_id, exc, exc_info=True)
        return [_whole_file_segment(order_file, "color", error=str(exc))]


def submit_order_to_printer(
    order: Order, reprint: bool = False, order_files=None,
) -> list[PrintJob]:
    """Create, upload and execute Epson jobs for the current submission run.

    Explicit mono/color files remain one job each. Mixed Auto-mode PDFs become
    one job per segment/copy because Epson cannot vary ``colorMode`` by page.
    """
    client = EpsonClient()
    printer_name = _safe_printer_name(client)
    files = list(order.files.all() if order_files is None else order_files)
    prepare_order_for_print(order, order_files=files)
    run_id = uuid.uuid4()
    jobs: list[PrintJob] = []
    remaining = MAX_JOBS_PER_ORDER
    color_fallback_files = []

    for order_file in files:
        spec = getattr(order_file, "specification", None)
        segments = _file_segments(order_file)
        submissions = sum(not segment.error for segment in segments)
        if submissions > remaining:
            if remaining == 0:
                segments = [_whole_file_segment(order_file, "color", error=(
                    f"Order reached the {MAX_JOBS_PER_ORDER}-job Epson submission limit. "
                    "Reprint this file separately."
                ))]
                submissions = 0
            else:
                log.warning(
                    "Order %s exceeded %s Epson jobs; sending '%s' as one color job",
                    order.tracking_id, MAX_JOBS_PER_ORDER, order_file.file_name,
                )
                segments = [_whole_file_segment(order_file, "color")]
                submissions = 1
                # The fallback changes the effective split to all-color. Persist
                # that conservative choice so the quote and future reprints match
                # what is actually sent to Epson.
                if getattr(spec, "color_mode", None) == "auto":
                    selected = order_file.selected_pages or list(
                        range(1, max(1, order_file.page_count) + 1)
                    )
                    order_file.color_page_overrides = {
                        str(page): "color" for page in selected
                    }
                    order_file.save(update_fields=["color_page_overrides"])
                    color_fallback_files.append(order_file)
        remaining -= submissions

        for segment in segments:
            settings_snapshot = _print_settings(
                spec, color_mode=segment.mode, copies=segment.copies,
            )
            job = PrintJob.objects.create(
                order=order,
                order_file=order_file,
                printer_name=printer_name,
                print_mode=_print_mode_for(order_file.file_type),
                print_settings_snapshot=settings_snapshot,
                pages_snapshot=list(segment.source_pages),
                run_id=run_id,
                segment_index=segment.segment_index,
                copy_index=segment.copy_index,
                segment_count=segment.segment_count,
                is_reprint=reprint,
                status=PrintJob.JobStatus.CREATED,
            )
            if segment.error:
                job.status = PrintJob.JobStatus.FAILED
                job.error_message = segment.error
                job.save(update_fields=["status", "error_message", "updated_at"])
                jobs.append(job)
                continue
            try:
                content = _read_print_file(order_file)
                upload_name = order_file.print_file_name
                if not segment.whole_file:
                    content = _extract_pdf_pages(content, segment.output_pages)
                    stem = upload_name.rsplit(".", 1)[0]
                    upload_name = (
                        f"{stem}-segment-{segment.segment_index}-copy-{segment.copy_index}.pdf"
                    )
                result = client.create_job(
                    job_name=(
                        f"{order.tracking_id}-{order_file.pk}-{run_id.hex[:8]}"
                        f"-s{segment.segment_index}c{segment.copy_index}"
                    ),
                    print_mode=job.print_mode,
                    print_settings=settings_snapshot,
                )
                job.epson_job_id = result.job_id
                job.upload_uri = result.upload_uri
                client.upload_file(result.upload_uri, upload_name, content)
                client.execute_job(result.job_id)
                job.status = PrintJob.JobStatus.EXECUTED
                job.submitted_at = timezone.now()
                job.save(update_fields=[
                    "epson_job_id", "upload_uri", "status", "submitted_at", "updated_at",
                ])
            except Exception as exc:  # noqa: BLE001 - submission failures must not become 500s
                log.exception("Epson submission failed for order %s", order.tracking_id)
                job.status = PrintJob.JobStatus.FAILED
                job.error_message = str(exc)
                job.save(update_fields=["status", "error_message", "updated_at"])
            jobs.append(job)

    if color_fallback_files:
        from apps.orders.services.repricing import reprice_order

        reprice_order(order)
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
    except Exception:  # noqa: BLE001 - the name is only a fallback label
        log.warning("Could not read Epson device info; using fallback printer name", exc_info=True)
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


def _current_run_jobs(order: Order) -> list[PrintJob]:
    latest = order.print_jobs.order_by("-created_at", "-pk").first()
    if latest is None:
        return []
    return list(order.print_jobs.filter(run_id=latest.run_id))


def _aggregate_order_status(order: Order) -> None:
    """Derive order status from every job in the latest submission run."""
    jobs = _current_run_jobs(order)
    if not jobs:
        return
    statuses = [job.status for job in jobs]
    active = any(status in ACTIVE_JOB_STATUSES for status in statuses)
    problem = next(
        (job for job in jobs if job.status in (PrintJob.JobStatus.ON_HOLD, PrintJob.JobStatus.FAILED)),
        None,
    )
    if problem is not None:
        new_status = Order.Status.ON_HOLD
        note = f"Print job needs attention: {problem.error_message or problem.get_status_display()}"
    elif any(status == PrintJob.JobStatus.CANCELED for status in statuses) and not active:
        new_status = Order.Status.PRINT_CANCELLED
        note = (
            "The printer cancelled one or more jobs in the current print run. "
            "Reprint the affected file from the admin page."
        )
    elif all(status == PrintJob.JobStatus.COMPLETED for status in statuses):
        # A reprint can be submitted while an older physical job is still
        # running. The latest run controls failures/cancellations, but readiness
        # must wait until every active Epson job has actually finished.
        older_active = order.print_jobs.exclude(run_id=jobs[0].run_id).filter(
            status__in=ACTIVE_JOB_STATUSES,
        ).exists()
        if older_active:
            new_status = Order.Status.PRINTING
            note = "The current print run completed; waiting for an earlier Epson job to finish."
        else:
            new_status = Order.Status.PRINTED_READY
            note = "All Epson jobs in the current print run completed."
    elif any(status == PrintJob.JobStatus.PRINTING for status in statuses):
        new_status = Order.Status.PRINTING
        note = "The current Epson print run is in progress."
    else:
        new_status = Order.Status.APPROVED_QUEUED
        note = "The current Epson print run is queued."

    # Orders the admin or customer already decided on are never overridden
    # by a printer poll. A reprint explicitly moves the order back into the
    # queue, so it is not blocked by the previous run's terminal status.
    if order.status in (
        Order.Status.PENDING_REVIEW, Order.Status.REJECTED, Order.Status.CANCELLED,
        Order.Status.COMPLETED, Order.Status.REVISION_REQUESTED,
        Order.Status.PRINT_CANCELLED,
    ):
        return
    if order.status != new_status:
        order.set_status(new_status, note=note)


def sync_print_jobs(order: Order | None = None) -> None:
    """Poll Epson jobs, then aggregate the latest run into the order status."""
    queryset = PrintJob.objects.exclude(status__in=TERMINAL_JOB_STATUSES)
    if order is not None:
        queryset = queryset.filter(order=order)
    client = EpsonClient()
    touched_orders = {order.pk} if order is not None else set()
    for job in queryset.select_related("order"):
        touched_orders.add(job.order_id)
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

    for order_id in touched_orders:
        current = Order.objects.get(pk=order_id)
        _aggregate_order_status(current)
