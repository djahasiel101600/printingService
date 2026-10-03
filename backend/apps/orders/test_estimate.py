"""POST /api/orders/estimate/ — page counts without order creation (PRD FR-16)."""
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.orders.views import EstimateThrottle

from .tests import make_image, make_pdf


def pdf_upload(pages: int = 1, name: str = "document.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, make_pdf(pages), content_type="application/pdf")


class EstimateEndpointTests(TestCase):
    def setUp(self):
        # The estimate endpoint is throttled per-process via the cache;
        # reset counters so tests never bleed into each other's budget.
        cache.clear()
        self.api = APIClient()

    def test_counts_pages_for_pdf_without_persisting(self):
        response = self.api.post(
            "/api/orders/estimate/",
            {"files": [pdf_upload(3)]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["total_pages"], 3)
        self.assertEqual(len(body["files"]), 1)
        entry = body["files"][0]
        self.assertEqual(entry["name"], "document.pdf")
        self.assertEqual(entry["page_count"], 3)
        self.assertEqual(entry["file_type"], "pdf")
        self.assertTrue(entry["print_ready"])
        # Nothing may be written — this is a pure estimate.
        self.assertEqual(Order.objects.count(), 0)

    def test_counts_multiple_files(self):
        pdf = pdf_upload(2, "report.pdf")
        image = SimpleUploadedFile("photo.png", make_image(), content_type="image/png")
        response = self.api.post(
            "/api/orders/estimate/",
            {"files": [pdf, image]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["total_pages"], 3)  # 2-page PDF + 1-page image
        self.assertEqual(
            [entry["file_type"] for entry in body["files"]], ["pdf", "image"],
        )
        self.assertTrue(all(entry["print_ready"] for entry in body["files"]))

    def test_rejects_empty_request(self):
        response = self.api.post("/api/orders/estimate/", {}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("At least one file", response.json()["detail"])

    def test_rejects_unsupported_extension(self):
        response = self.api.post(
            "/api/orders/estimate/",
            {"files": [SimpleUploadedFile("malware.exe", b"MZ fake binary",
                                          content_type="application/octet-stream")]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("unsupported file type", response.json()["detail"])

    def test_rejects_legacy_office_format_with_hint(self):
        response = self.api.post(
            "/api/orders/estimate/",
            {"files": [SimpleUploadedFile("report.doc", b"\xd0\xcf\x11\xe0 old compound file",
                                          content_type="application/msword")]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertIn("legacy '.doc' format", detail)
        self.assertIn("'.docx'", detail)

    @override_settings(MAX_UPLOAD_MB=0)
    def test_rejects_oversize_file(self):
        response = self.api.post(
            "/api/orders/estimate/",
            {"files": [pdf_upload(1)]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("exceeds", response.json()["detail"])

    def test_bad_file_fails_the_whole_estimate(self):
        """Strict like order creation: no partial success the wizard would regret."""
        response = self.api.post(
            "/api/orders/estimate/",
            {"files": [pdf_upload(1),
                       SimpleUploadedFile("notes.xyz", b"nope",
                                          content_type="application/octet-stream")]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("notes.xyz", response.json()["detail"])
        self.assertEqual(Order.objects.count(), 0)

    def test_throttle_allows_60_per_minute_then_blocks(self):
        throttle = EstimateThrottle()
        self.assertEqual(throttle.rate, "60/min")
        self.assertEqual(throttle.num_requests, 60)
        # DRF Request (not a raw HttpRequest) so AnonRateThrottle can read .user.
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        request = Request(APIRequestFactory().post("/api/orders/estimate/"))
        allowed = sum(
            1 for _ in range(throttle.num_requests + 1)
            if throttle.allow_request(request, None)
        )
        self.assertEqual(allowed, throttle.num_requests)