import io
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from pypdf import PdfWriter
from rest_framework.test import APIClient

from apps.activitylog.models import ActivityLog
from apps.catalogue.models import Product
from apps.orders.models import Order, OrderFile
from apps.orders.services.print_prep import prepare_order_for_print
from apps.orders.services.repricing import reprice_order


def make_pdf(pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def make_image() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), "tomato").save(buffer, format="PNG")
    return buffer.getvalue()


@override_settings(EMAIL_NOTIFICATIONS_ENABLED=False, EPSON_MOCK_MODE=True)
class CatalogueOrderTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create(
            username="order-admin@example.com", email="order-admin@example.com",
            role=User.Role.ADMIN,
        )
        self.approver = User.objects.create(
            username="order-approver@example.com", email="order-approver@example.com",
            role=User.Role.APPROVER,
        )
        self.customer = User.objects.create(
            username="order-customer@example.com", email="order-customer@example.com",
            role=User.Role.CLIENT,
        )
        self.guest = APIClient()
        self.admin_api = APIClient()
        self.admin_api.force_authenticate(user=self.admin)
        self.approver_api = APIClient()
        self.approver_api.force_authenticate(user=self.approver)
        self.customer_api = APIClient()
        self.customer_api.force_authenticate(user=self.customer)
        self.product = Product.objects.create(
            name="2x2 ID Picture", slug="test-2x2-id-picture", category="ID photos",
            price=3000, unit_label="piece", min_quantity=1, max_quantity=99,
            is_active=True, is_featured=True,
            default_spec={
                "media_size": "ps_a4", "media_type": "pt_photopaper",
                "color_mode": "color", "print_quality": "high", "sides": "none",
                "orientation": "portrait", "copies": 1,
            },
            instructions="Upload one clear photo; the shop prepares the 2x2 layout.",
        )

    def payload(self, *, quantity=2, files=None, spec=None, guest=True):
        data = {
            "order_mode": "catalogue",
            "product_id": self.product.id,
            "product_quantity": quantity,
            "files": files or [SimpleUploadedFile(
                "photo.png", make_image(), content_type="image/png",
            )],
            "spec": json.dumps(spec or {}),
            "per_file_specs": "[]",
        }
        if guest:
            data.update({
                "guest_name": "Ana Reyes",
                "guest_contact_method": "email",
                "guest_contact_value": "ana@example.com",
            })
        return data

    def create_guest_order(self, **kwargs):
        response = self.guest.post("/api/orders/", self.payload(**kwargs), format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def create_customer_order(self):
        response = self.customer_api.post(
            "/api/orders/", self.payload(guest=False), format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def set_review_status(self, order):
        Order.objects.filter(pk=order["id"]).update(status=Order.Status.PENDING_REVIEW)

    def replace_file(self, order):
        response = self.admin_api.post(
            f"/api/admin/orders/{order['id']}/files/{order['files'][0]['id']}/replace/",
            {"file": SimpleUploadedFile("prepared-layout.pdf", make_pdf(1),
                                        content_type="application/pdf")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_fixed_catalogue_quote_and_custom_line_kind(self):
        response = self.guest.post("/api/orders/quote/", {
            "order_mode": "catalogue", "product_id": self.product.id,
            "product_quantity": 2,
        }, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        quote = response.json()
        self.assertEqual(quote["subtotal"], 6000)
        line = quote["lines"][0]
        self.assertEqual(line["kind"], "catalogue")
        self.assertEqual(line["quantity"], 2)
        self.assertEqual(line["unit_label"], "piece")
        self.assertEqual(line["unit_price"], 3000)
        self.assertEqual(line["amount"], 6000)
        self.assertIsNone(line["pages"])
        self.assertIsNone(line["copies"])
        self.assertIsNone(line["sides"])
        self.assertIsNone(line["color_mode"])

        custom = self.guest.post("/api/orders/quote/", {"page_count": 1}, format="json")
        self.assertEqual(custom.status_code, 200)
        self.assertEqual(custom.json()["lines"][0]["kind"], "custom")

    def test_quote_rejects_invalid_inactive_and_out_of_bounds_products(self):
        for quantity in (0, 100, 1.5, "many"):
            with self.subTest(quantity=quantity):
                response = self.guest.post("/api/orders/quote/", {
                    "order_mode": "catalogue", "product_id": self.product.id,
                    "product_quantity": quantity,
                }, format="json")
                self.assertEqual(response.status_code, 400)
        self.product.is_active = False
        self.product.save()
        inactive = self.guest.post("/api/orders/quote/", {
            "order_mode": "catalogue", "product_id": self.product.id,
            "product_quantity": 1,
        }, format="json")
        self.assertEqual(inactive.status_code, 404)

    def test_guest_creation_snapshots_product_and_merges_default_spec(self):
        payload = self.create_guest_order(spec={
            "media_size": "ps_a6", "copies": 4,
            "free_text_instructions": "Please keep the full head and shoulders.",
        }, files=[SimpleUploadedFile("photo.png", make_image(), content_type="image/png")])
        order = payload["order"]
        self.assertEqual(order["subtotal"], 6000)
        self.assertEqual(order["order_mode"], "catalogue")
        self.assertEqual(order["product_name_snapshot"], "2x2 ID Picture")
        self.assertEqual(order["product_unit_price_snapshot"], 3000)
        self.assertEqual(order["product_unit_label_snapshot"], "piece")
        self.assertEqual(order["product_quantity"], 2)
        self.assertEqual(order["product_min_quantity_snapshot"], 1)
        self.assertEqual(order["product_max_quantity_snapshot"], 99)
        self.assertEqual(order["product_instructions_snapshot"], self.product.instructions)
        self.assertEqual(len(order["files"]), 1)

        spec = order["files"][0]["specification"]
        self.assertEqual(spec["media_size"], "ps_a6")
        self.assertEqual(spec["media_type"], "pt_photopaper")
        self.assertEqual(spec["color_mode"], "color")
        self.assertEqual(spec["print_quality"], "high")
        self.assertEqual(spec["copies"], 1)
        self.assertIn("Please keep the full head and shoulders.", spec["free_text_instructions"])
        self.assertIn(self.product.instructions, spec["free_text_instructions"])
        self.assertEqual(payload["quote"]["lines"][0]["product_id"], self.product.id)

    def test_catalogue_creation_requires_exactly_one_file(self):
        response = self.guest.post("/api/orders/", self.payload(files=[
            SimpleUploadedFile("one.png", make_image(), content_type="image/png"),
            SimpleUploadedFile("two.png", make_image(), content_type="image/png"),
        ]), format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_authenticated_customer_and_admin_proxy_creation(self):
        customer_order = self.create_customer_order()["order"]
        self.assertEqual(customer_order["client_name"], self.customer.get_full_name() or self.customer.email)
        self.assertEqual(customer_order["guest_name"], "")

        proxy = self.payload(guest=False)
        proxy["customer_user_id"] = self.customer.id
        response = self.admin_api.post("/api/orders/", proxy, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["order"]["client_name"],
                         self.customer.get_full_name() or self.customer.email)

        walk_in = self.admin_api.post("/api/orders/", self.payload(), format="multipart")
        self.assertEqual(walk_in.status_code, 201, walk_in.content)
        self.assertEqual(walk_in.json()["order"]["guest_name"], "Ana Reyes")

    def test_product_edits_and_deactivation_never_reprice_historical_orders(self):
        order = self.create_guest_order()["order"]
        self.product.price = 3500
        self.product.name = "Renamed Product"
        self.product.is_active = False
        self.product.save()
        saved = Order.objects.get(pk=order["id"])
        saved.files.first().page_count = 20
        reprice_order(saved)
        saved.refresh_from_db()
        self.assertEqual(saved.subtotal, 6000)
        self.assertEqual(saved.product_name_snapshot, "2x2 ID Picture")
        self.assertEqual(saved.quote_breakdown[0]["label"], "2x2 ID Picture")

    def test_missing_catalogue_snapshot_fails_closed(self):
        order = self.create_guest_order()["order"]
        saved = Order.objects.get(pk=order["id"])
        saved.product_unit_price_snapshot = None
        saved.save(update_fields=["product_unit_price_snapshot"])
        with self.assertRaises(ValueError):
            reprice_order(saved)

    def test_file_page_color_spec_and_replacement_changes_keep_fixed_subtotal(self):
        order = self.create_guest_order(files=[SimpleUploadedFile(
            "source.pdf", make_pdf(3), content_type="application/pdf",
        )])["order"]
        self.set_review_status(order)
        file_id = order["files"][0]["id"]
        spec_id = order["files"][0]["specification"]["id"]

        pages = self.admin_api.patch(
            f"/api/admin/orders/{order['id']}/files/{file_id}/pages/",
            {"pages": [1]}, format="json",
        )
        self.assertEqual(pages.status_code, 200, pages.content)
        self.assertEqual(pages.json()["order"]["subtotal"], 6000)

        color = self.admin_api.patch(
            f"/api/admin/orders/{order['id']}/files/{file_id}/color/",
            {"overrides": {"1": "mono"}}, format="json",
        )
        self.assertEqual(color.status_code, 200, color.content)
        self.assertEqual(color.json()["order"]["subtotal"], 6000)

        spec = self.admin_api.patch(
            f"/api/admin/orders/{order['id']}/specs/{spec_id}/",
            {"copies": 9, "color_mode": "mono", "sides": "long"}, format="json",
        )
        self.assertEqual(spec.status_code, 200, spec.content)
        self.assertEqual(spec.json()["subtotal"], 6000)
        self.assertEqual(spec.json()["files"][0]["specification"]["copies"], 1)

        replaced = self.replace_file(order)
        self.assertEqual(replaced["subtotal"], 6000)

    def test_quantity_adjustment_permissions_and_validation(self):
        order = self.create_guest_order()["order"]
        url = f"/api/admin/orders/{order['id']}/product/"
        self.assertIn(self.guest.patch(url, {"product_quantity": 3}, format="json").status_code,
                      (401, 403))
        self.assertEqual(self.customer_api.patch(url, {"product_quantity": 3}, format="json").status_code,
                         403)
        self.assertEqual(self.approver_api.patch(url, {"product_quantity": 3}, format="json").status_code,
                         403)
        for quantity in (0, 100, 2.5):
            with self.subTest(quantity=quantity):
                self.assertEqual(self.admin_api.patch(
                    url, {"product_quantity": quantity}, format="json",
                ).status_code, 400)

        custom = Order.objects.create(status=Order.Status.AWAITING_PAYMENT)
        self.assertEqual(self.admin_api.patch(
            f"/api/admin/orders/{custom.id}/product/", {"product_quantity": 2}, format="json",
        ).status_code, 409)

    def test_quantity_adjustment_reprices_from_snapshot_and_invalidates_output(self):
        order = self.create_guest_order()["order"]
        order_file = OrderFile.objects.get(order_id=order["id"])
        order_file.final_file.save("prepared.pdf", ContentFile(make_pdf(1)), save=True)
        order_file.page_selection = [1]
        order_file.replaced_by_admin = True
        order_file.save(update_fields=["page_selection", "replaced_by_admin"])
        self.product.price = 3500
        self.product.save()

        response = self.admin_api.patch(
            f"/api/admin/orders/{order['id']}/product/", {"product_quantity": 3}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["product_quantity"], 3)
        self.assertEqual(body["subtotal"], 9000)
        self.assertEqual(body["quote_breakdown"][0]["unit_price"], 3000)
        order_file.refresh_from_db()
        self.assertFalse(order_file.final_file)
        self.assertFalse(order_file.replaced_by_admin)
        self.assertEqual(order_file.page_selection, [])
        history = body["history"][-1]
        self.assertEqual(history["from_status"], history["to_status"])
        self.assertIn("2 -> 3", history["note"])
        self.assertTrue(ActivityLog.objects.filter(
            action="order.product_quantity", object_id=order["id"],
        ).exists())

    def test_paid_and_post_approval_quantity_changes_are_rejected(self):
        order = self.create_guest_order()["order"]
        url = f"/api/admin/orders/{order['id']}/product/"
        Order.objects.filter(pk=order["id"]).update(amount_paid=1)
        self.assertEqual(self.admin_api.patch(url, {"product_quantity": 3}, format="json").status_code,
                         409)
        Order.objects.filter(pk=order["id"]).update(
            amount_paid=0, status=Order.Status.APPROVED_QUEUED,
        )
        self.assertEqual(self.admin_api.patch(url, {"product_quantity": 3}, format="json").status_code,
                         409)

    def test_raw_printer_compatible_files_cannot_be_approved(self):
        for name, content, content_type in (
            ("photo.png", make_image(), "image/png"),
            ("source.pdf", make_pdf(1), "application/pdf"),
        ):
            with self.subTest(name=name):
                order = self.create_guest_order(files=[SimpleUploadedFile(
                    name, content, content_type=content_type,
                )])["order"]
                self.set_review_status(order)
                history_count = Order.objects.get(pk=order["id"]).history.count()
                with patch("apps.orders.views.prepare_order_for_print") as prepare:
                    response = self.admin_api.post(
                        f"/api/admin/orders/{order['id']}/actions/approve/", {}, format="json",
                    )
                self.assertEqual(response.status_code, 409, response.content)
                prepare.assert_not_called()
                saved = Order.objects.get(pk=order["id"])
                self.assertEqual(saved.status, Order.Status.PENDING_REVIEW)
                self.assertEqual(saved.print_jobs.count(), 0)
                self.assertEqual(saved.history.count(), history_count)
                self.assertFalse(saved.files.first().final_file)
                self.assertFalse(ActivityLog.objects.filter(
                    action="order.approve", object_id=order["id"],
                ).exists())

    def test_automatic_final_file_without_staff_replacement_is_still_blocked(self):
        order = self.create_guest_order(files=[SimpleUploadedFile(
            "source.pdf", make_pdf(1), content_type="application/pdf",
        )])["order"]
        self.set_review_status(order)
        saved = Order.objects.get(pk=order["id"])
        prepare_order_for_print(saved)
        self.assertTrue(saved.files.first().final_file)
        self.assertFalse(saved.files.first().replaced_by_admin)
        response = self.admin_api.post(
            f"/api/admin/orders/{order['id']}/actions/approve/", {}, format="json",
        )
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(Order.objects.get(pk=order["id"]).print_jobs.count(), 0)

    def test_staff_prepared_layout_can_be_approved(self):
        order = self.create_guest_order()["order"]
        self.set_review_status(order)
        replaced = self.replace_file(order)
        self.assertTrue(replaced["files"][0]["replaced_by_admin"])
        self.assertTrue(replaced["files"][0]["has_final_file"])
        response = self.admin_api.post(
            f"/api/admin/orders/{order['id']}/actions/approve/", {}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        saved = Order.objects.get(pk=order["id"])
        self.assertEqual(saved.status, Order.Status.APPROVED_QUEUED)
        self.assertEqual(saved.print_jobs.count(), 1)
        self.assertEqual(saved.print_jobs.first().print_settings_snapshot["copies"], 1)

    def test_customer_reupload_reactivates_prepared_layout_guard(self):
        order = self.create_guest_order()["order"]
        self.replace_file(order)
        Order.objects.filter(pk=order["id"]).update(status=Order.Status.REVISION_REQUESTED)
        reupload = self.guest.post(
            f"/api/orders/{order['id']}/files/{order['files'][0]['id']}/reupload/",
            {"tracking_id": order["tracking_id"], "file": SimpleUploadedFile(
                "new-photo.png", make_image(), content_type="image/png",
            )}, format="multipart",
        )
        self.assertEqual(reupload.status_code, 200, reupload.content)
        live = OrderFile.objects.get(order_id=order["id"])
        self.assertFalse(live.replaced_by_admin)
        self.assertFalse(live.final_file)
        resubmit = self.guest.post(
            f"/api/orders/{order['id']}/resubmit/", {"tracking_id": order["tracking_id"]},
            format="json",
        )
        self.assertEqual(resubmit.status_code, 200, resubmit.content)
        blocked = self.admin_api.post(
            f"/api/admin/orders/{order['id']}/actions/approve/", {}, format="json",
        )
        self.assertEqual(blocked.status_code, 409, blocked.content)
