"""Auto page-mode analysis, overrides and price recalculation."""
import json

from django.core.files.uploadedfile import SimpleUploadedFile
from apps.orders.models import Order, OrderFile
from apps.pricing.models import PriceRule

from .test_admin_review import AdminReviewTestCase, BASE_SPEC
from .test_color_analysis import mixed_pdf_bytes


class AutoColorOrderTests(AdminReviewTestCase):
    def setUp(self):
        super().setUp()
        PriceRule.objects.create(
            media_size="ps_a4", media_type="pt_plainpaper", color_mode="color",
            print_quality="normal", price_per_page=600,
        )
        self.auto_spec = {**BASE_SPEC, "color_mode": "auto"}

    def mixed_order(self):
        return self.submit([
            SimpleUploadedFile("mixed.pdf", mixed_pdf_bytes(), content_type="application/pdf"),
        ], spec=self.auto_spec)

    def color_url(self, order, file_id):
        return f"/api/admin/orders/{order['id']}/files/{file_id}/color/"

    def test_estimate_returns_in_memory_page_analysis(self):
        response = self.api.post("/api/orders/estimate/", {
            "files": [SimpleUploadedFile(
                "mixed.pdf", mixed_pdf_bytes(), content_type="application/pdf",
            )],
        }, format="multipart")
        self.assertEqual(response.status_code, 200, response.content)
        analysis = response.json()["files"][0]["color_analysis"]
        self.assertTrue(analysis["complete"])
        self.assertEqual([page["mode"] for page in analysis["pages"]], ["mono", "color"])
        self.assertEqual(Order.objects.count(), 0)

    def test_creation_persists_analysis_and_itemised_quote(self):
        order = self.mixed_order()
        self.assertEqual(order["subtotal"], 900)
        self.assertEqual(order["subtotal_peso"], 9.0)
        self.assertEqual([line["color_mode"] for line in order["quote_breakdown"]],
                         ["mono", "color"])
        file = order["files"][0]
        self.assertEqual(file["detected_mono_pages"], 1)
        self.assertEqual(file["detected_color_pages"], 1)
        self.assertEqual(file["effective_page_modes"], [
            {"page": 1, "mode": "mono"}, {"page": 2, "mode": "color"},
        ])
        saved = OrderFile.objects.get(pk=file["id"])
        self.assertEqual(saved.color_analysis["pages"][1]["mode"], "color")

    def test_page_selection_requotes_only_surviving_modes(self):
        order = self.mixed_order()
        file = order["files"][0]
        response = self.api.patch(self.pages_url(order, file["id"]),
                                  {"pages": [2]}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["order"]["subtotal"], 600)
        self.assertEqual(response.json()["order"]["quote_breakdown"][0]["color_mode"], "color")

    def test_overrides_reanalyze_and_spec_changes_requote(self):
        order = self.mixed_order()
        file = order["files"][0]
        url = self.color_url(order, file["id"])
        response = self.api.patch(url, {
            "overrides": {"1": "color", "2": "color"}, "reanalyze": True,
        }, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["order"]["subtotal"], 1200)
        self.assertEqual(response.json()["file"]["color_page_overrides"],
                         {"1": "color", "2": "color"})

        response = self.api.patch(url, {"overrides": {}}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["order"]["subtotal"], 900)

        spec_id = response.json()["file"]["specification"]["id"]
        response = self.api.patch(f"/api/admin/orders/{order['id']}/specs/{spec_id}/",
                                  {"color_mode": "mono"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["subtotal"], 600)
        response = self.api.patch(f"/api/admin/orders/{order['id']}/specs/{spec_id}/",
                                  {"color_mode": "auto"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["subtotal"], 900)

    def test_invalid_override_is_rejected_without_changing_price(self):
        order = self.mixed_order()
        file = order["files"][0]
        for overrides in ({"3": "mono"}, {"1": "blue"}, {"x": "mono"}):
            response = self.api.patch(self.color_url(order, file["id"]),
                                      {"overrides": overrides}, format="json")
            self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Order.objects.get(pk=order["id"]).subtotal, 900)

    def test_customer_edit_clears_stale_overrides_and_reanalyses(self):
        order = self.mixed_order()
        file = order["files"][0]
        self.api.patch(self.color_url(order, file["id"]),
                       {"overrides": {"1": "color"}}, format="json")
        response = self.api.post(
            f"/api/orders/{order['id']}/files/{file['id']}/edit/",
            {"action": "crop", "params": json.dumps({"x": 0, "y": 0, "w": 0.8, "h": 0.8}),
             "tracking_id": order["tracking_id"]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.content)
        saved = OrderFile.objects.get(pk=file["id"])
        self.assertEqual(saved.color_page_overrides, {})
        self.assertEqual(len(saved.color_analysis["pages"]), 2)
        self.assertEqual(Order.objects.get(pk=order["id"]).subtotal, 900)
