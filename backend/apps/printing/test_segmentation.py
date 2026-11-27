"""Mixed-page Epson segmentation and latest-run status regressions."""
import io
import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

from django.apps import apps
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter

from apps.orders.models import Order
from apps.orders.test_admin_review import AdminReviewTestCase, BASE_SPEC
from apps.pricing.models import PriceRule
from apps.printing.epson import EpsonJobResult, EpsonJobStatus
from apps.printing.models import PrintJob
from apps.printing.services import (
    _aggregate_order_status, _page_segments, submit_order_to_printer, sync_print_jobs,
)


def pdf_with_page_modes(modes: tuple[str, ...]) -> bytes:
    """Build a real PDF whose rendered pages match the requested visible modes."""
    writer = PdfWriter()
    for mode in modes:
        image = Image.new("RGB", (612, 792), "white")
        draw = ImageDraw.Draw(image)
        draw.text((72, 72), "Page text", fill="black")
        if mode == "color":
            draw.rectangle((100, 200, 400, 500), fill="tomato")
        buffer = io.BytesIO()
        image.save(buffer, format="PDF", resolution=72)
        writer.add_page(PdfReader(io.BytesIO(buffer.getvalue())).pages[0])
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def uploaded_pdf(modes: tuple[str, ...]):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(
        "mixed.pdf", pdf_with_page_modes(modes), content_type="application/pdf",
    )


class PageSegmentTests(SimpleTestCase):
    def test_single_sided_pages_form_contiguous_mode_runs(self):
        self.assertEqual(
            _page_segments(
                [(1, "mono"), (2, "mono"), (3, "color"), (4, "mono")],
                duplex=False,
            ),
            [
                ("mono", (1, 2), (1, 2)),
                ("color", (3,), (3,)),
                ("mono", (4,), (4,)),
            ],
        )

    def test_duplex_pages_are_grouped_by_physical_sheet(self):
        self.assertEqual(
            _page_segments(
                [(1, "mono"), (2, "color"), (3, "mono"), (4, "mono"), (5, "color")],
                duplex=True,
            ),
            [
                ("color", (1, 2), (1, 2)),
                ("mono", (3, 4), (3, 4)),
                ("color", (5,), (5,)),
            ],
        )


class AutoColorPrintingTests(AdminReviewTestCase):
    def setUp(self):
        super().setUp()
        PriceRule.objects.create(
            media_size="ps_a4", media_type="pt_plainpaper", color_mode="color",
            print_quality="normal", price_per_page=600,
        )

    def make_auto_order(self, modes=("mono", "color"), **options):
        spec = {**BASE_SPEC, "color_mode": "auto", **options}
        return self.submit([uploaded_pdf(tuple(modes))], spec=spec)

    def submit_jobs(self, order):
        client = Mock()
        client.get_device_info.return_value = {"productName": "Epson Test"}
        client.create_job.side_effect = lambda **kwargs: EpsonJobResult(
            job_id=f"job-{kwargs['job_name']}",
            upload_uri=f"https://epson.test/{kwargs['job_name']}",
        )
        model = Order.objects.get(pk=order["id"])
        with patch("apps.printing.services.EpsonClient", return_value=client):
            jobs = submit_order_to_printer(model)
        return jobs, client

    def test_mixed_auto_splits_prepared_pdf_into_concrete_jobs(self):
        order = self.make_auto_order()
        jobs, client = self.submit_jobs(order)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(len({job.run_id for job in jobs}), 1)
        self.assertEqual(
            [job.print_settings_snapshot["colorMode"] for job in jobs],
            ["mono", "color"],
        )
        self.assertEqual([job.segment_index for job in jobs], [1, 2])
        self.assertEqual([job.copy_index for job in jobs], [1, 1])
        self.assertEqual([job.segment_count for job in jobs], [2, 2])
        self.assertEqual([job.pages_snapshot for job in jobs], [[1], [2]])
        self.assertTrue(all(job.print_settings_snapshot["copies"] == 1 for job in jobs))

        uploads = client.upload_file.call_args_list
        self.assertEqual(len(uploads), 2)
        for upload in uploads:
            self.assertEqual(len(PdfReader(io.BytesIO(upload.args[2])).pages), 1)

    def test_explicit_modes_keep_one_whole_file_job_with_native_copies(self):
        for mode in ("mono", "color"):
            with self.subTest(mode=mode):
                order = self.submit(
                    [uploaded_pdf(("mono", "color"))],
                    spec={**BASE_SPEC, "color_mode": mode, "copies": 3},
                )
                jobs, client = self.submit_jobs(order)
                self.assertEqual(len(jobs), 1)
                self.assertEqual(jobs[0].print_settings_snapshot["colorMode"], mode)
                self.assertEqual(jobs[0].print_settings_snapshot["copies"], 3)
                self.assertEqual(jobs[0].segment_count, 1)
                self.assertEqual(jobs[0].pages_snapshot, [])
                self.assertEqual(client.create_job.call_count, 1)
                payload = client.upload_file.call_args.args[2]
                self.assertEqual(len(PdfReader(io.BytesIO(payload)).pages), 2)

    def test_duplex_segments_never_split_a_sheet(self):
        order = self.make_auto_order(("mono", "color", "mono", "mono"), sides="long")
        jobs, _ = self.submit_jobs(order)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(
            [job.print_settings_snapshot["colorMode"] for job in jobs],
            ["color", "mono"],
        )
        self.assertEqual([job.pages_snapshot for job in jobs], [[1, 2], [3, 4]])
        self.assertTrue(all(job.print_settings_snapshot["doubleSided"] == "long" for job in jobs))

    def test_mixed_multi_copy_jobs_use_one_copy_per_epson_job(self):
        cases = (
            (True, [(1, 1), (2, 1), (1, 2), (2, 2)]),
            (False, [(1, 1), (1, 2), (2, 1), (2, 2)]),
        )
        for collate, expected in cases:
            with self.subTest(collate=collate):
                order = self.make_auto_order(copies=2, collate=collate)
                jobs, _ = self.submit_jobs(order)
                self.assertEqual(
                    [(job.segment_index, job.copy_index) for job in jobs], expected,
                )
                self.assertTrue(all(job.print_settings_snapshot["copies"] == 1 for job in jobs))

    def test_reverse_order_reverses_submission_but_keeps_logical_indices(self):
        order = self.make_auto_order(reverse_order=True)
        jobs, client = self.submit_jobs(order)

        self.assertEqual(
            [(job.segment_index, job.copy_index) for job in jobs], [(2, 1), (1, 1)],
        )
        self.assertEqual(
            [call.kwargs["print_settings"]["colorMode"] for call in client.create_job.call_args_list],
            ["color", "mono"],
        )
        self.assertTrue(all(job.print_settings_snapshot["reverseOrder"] for job in jobs))

    def test_job_limit_falls_back_to_all_color_and_updates_the_quote(self):
        order = self.make_auto_order(copies=13)
        self.assertEqual(order["subtotal"], 13 * (300 + 600))

        jobs, client = self.submit_jobs(order)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(client.create_job.call_count, 1)
        self.assertEqual(jobs[0].print_settings_snapshot["colorMode"], "color")
        self.assertEqual(jobs[0].print_settings_snapshot["copies"], 13)
        saved_file = Order.objects.get(pk=order["id"]).files.get()
        self.assertEqual(saved_file.color_page_overrides, {"1": "color", "2": "color"})
        saved_order = Order.objects.get(pk=order["id"])
        self.assertEqual(saved_order.subtotal, 13 * 2 * 600)
        self.assertEqual(len(saved_order.quote_breakdown), 1)
        self.assertEqual(saved_order.quote_breakdown[0]["color_mode"], "color")

    def test_approval_waits_for_every_segment_and_exposes_run_metadata(self):
        order = self.make_auto_order()
        self.pay(order)
        client = Mock()
        client.get_device_info.return_value = {"productName": "Epson Test"}
        client.create_job.side_effect = lambda **kwargs: EpsonJobResult(
            job_id=f"job-{kwargs['job_name']}",
            upload_uri=f"https://epson.test/{kwargs['job_name']}",
        )
        with patch("apps.printing.services.EpsonClient", return_value=client):
            response = self.act(order, "approve")
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["status"], Order.Status.APPROVED_QUEUED)
        self.assertEqual(len(payload["print_jobs"]), 2)

        ready = self.act(order, "ready")
        self.assertEqual(ready.status_code, 409, ready.content)
        self.assertEqual(Order.objects.get(pk=order["id"]).status, Order.Status.APPROVED_QUEUED)

        for job in payload["print_jobs"]:
            for field in (
                "run_id", "segment_index", "copy_index", "segment_count",
                "print_settings_snapshot",
            ):
                self.assertIn(field, job)

        model = Order.objects.get(pk=order["id"])
        jobs = list(model.print_jobs.order_by("created_at", "pk"))
        statuses = {jobs[0].epson_job_id: "completed", jobs[1].epson_job_id: "processing"}
        client.get_job_status.side_effect = lambda job_id: EpsonJobStatus(status=statuses[job_id])
        with patch("apps.printing.services.EpsonClient", return_value=client):
            sync_print_jobs(model)
        model.refresh_from_db()
        self.assertEqual(model.status, Order.Status.PRINTING)
        self.assertNotEqual(model.status, Order.Status.PRINTED_READY)

        statuses[jobs[1].epson_job_id] = "completed"
        with patch("apps.printing.services.EpsonClient", return_value=client):
            sync_print_jobs(model)
        model.refresh_from_db()
        self.assertEqual(model.status, Order.Status.PRINTED_READY)


class PrintRunStatusTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            tracking_id="PSP-AAAA-BBBB", status=Order.Status.APPROVED_QUEUED,
        )

    def job(self, run_id, status, **kwargs):
        return PrintJob.objects.create(
            order=self.order, run_id=run_id, status=status, **kwargs,
        )

    def test_one_completed_segment_cannot_complete_the_order(self):
        run_id = uuid.uuid4()
        self.job(run_id, PrintJob.JobStatus.COMPLETED)
        self.job(run_id, PrintJob.JobStatus.PRINTING)

        _aggregate_order_status(self.order)

        self.assertEqual(self.order.status, Order.Status.PRINTING)

    def test_failure_and_cancellation_are_aggregated_across_segments(self):
        run_id = uuid.uuid4()
        self.job(run_id, PrintJob.JobStatus.COMPLETED)
        self.job(run_id, PrintJob.JobStatus.FAILED, error_message="upload failed")
        _aggregate_order_status(self.order)
        self.assertEqual(self.order.status, Order.Status.ON_HOLD)

        self.order.status = Order.Status.APPROVED_QUEUED
        self.order.save(update_fields=["status"])
        PrintJob.objects.filter(run_id=run_id).update(status=PrintJob.JobStatus.CANCELED)
        _aggregate_order_status(self.order)
        self.assertEqual(self.order.status, Order.Status.PRINT_CANCELLED)

    def test_cancelled_segment_does_not_cancel_while_another_is_active(self):
        run_id = uuid.uuid4()
        self.job(run_id, PrintJob.JobStatus.CANCELED)
        active = self.job(run_id, PrintJob.JobStatus.PRINTING)

        _aggregate_order_status(self.order)
        self.assertEqual(self.order.status, Order.Status.PRINTING)

        active.status = PrintJob.JobStatus.COMPLETED
        active.save(update_fields=["status"])
        _aggregate_order_status(self.order)
        self.assertEqual(self.order.status, Order.Status.PRINT_CANCELLED)

    def test_completed_latest_run_waits_for_an_older_active_job(self):
        old_run = uuid.uuid4()
        latest_run = uuid.uuid4()
        older_active = self.job(old_run, PrintJob.JobStatus.PRINTING)
        self.job(latest_run, PrintJob.JobStatus.COMPLETED)

        _aggregate_order_status(self.order)
        self.assertEqual(self.order.status, Order.Status.PRINTING)

        older_active.status = PrintJob.JobStatus.COMPLETED
        older_active.save(update_fields=["status"])
        _aggregate_order_status(self.order)
        self.assertEqual(self.order.status, Order.Status.PRINTED_READY)

    def test_older_run_cannot_control_the_latest_run_status(self):
        old_run = uuid.uuid4()
        latest_run = uuid.uuid4()
        self.job(old_run, PrintJob.JobStatus.FAILED, error_message="old failure")
        self.job(latest_run, PrintJob.JobStatus.COMPLETED)
        active = self.job(latest_run, PrintJob.JobStatus.PRINTING)

        with patch("apps.printing.services.EpsonClient"):
            sync_print_jobs(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PRINTING)

        active.status = PrintJob.JobStatus.COMPLETED
        active.save(update_fields=["status"])
        with patch("apps.printing.services.EpsonClient"):
            sync_print_jobs(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PRINTED_READY)


class PrintRunMigrationTests(TestCase):
    def test_legacy_jobs_are_grouped_into_submission_batches(self):
        order = Order.objects.create(tracking_id="PSP-CCCC-DDDD")
        now = timezone.now()
        first = PrintJob.objects.create(order=order, status=PrintJob.JobStatus.COMPLETED)
        second = PrintJob.objects.create(order=order, status=PrintJob.JobStatus.COMPLETED)
        reprint = PrintJob.objects.create(
            order=order, status=PrintJob.JobStatus.EXECUTED, is_reprint=True,
        )
        PrintJob.objects.filter(pk=first.pk).update(created_at=now)
        PrintJob.objects.filter(pk=second.pk).update(created_at=now + timedelta(seconds=30))
        PrintJob.objects.filter(pk=reprint.pk).update(created_at=now + timedelta(seconds=60))
        # The migration module is imported lazily so normal app startup does not
        # depend on migration helpers.
        import importlib

        migration = importlib.import_module(
            "apps.printing.migrations.0004_printjob_runs_and_segments"
        )
        migration.backfill_print_runs(apps, None)

        first.refresh_from_db()
        second.refresh_from_db()
        reprint.refresh_from_db()
        self.assertEqual(first.run_id, second.run_id)
        self.assertNotEqual(first.run_id, reprint.run_id)
        self.assertTrue(all(job.run_id for job in (first, second, reprint)))
