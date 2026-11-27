from importlib import import_module
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.activitylog.models import ActivityLog
from apps.orders.models import Order, OrderFile
seed_id_picture = import_module(
    "apps.catalogue.migrations.0002_seed_id_picture"
).seed_id_picture
from apps.catalogue.models import Product
from apps.catalogue.validators import validate_cover_image, validate_default_spec, validate_quantity


def cover_upload(filename="cover.png", image_format="PNG"):
    buffer = BytesIO()
    Image.new("RGB", (32, 24), "blue").save(buffer, format=image_format)
    content_type = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "GIF": "image/gif",
    }[image_format]
    return SimpleUploadedFile(filename, buffer.getvalue(), content_type=content_type)


class ProductValidationTests(TestCase):
    def product_data(self, **overrides):
        return {
            "name": "Test Product",
            "slug": "test-product",
            "description": "A test service",
            "category": "Test category",
            "price": 2500,
            "unit_label": "piece",
            "min_quantity": 1,
            "max_quantity": 10,
            "default_spec": {"media_size": "ps_a4", "copies": 1},
            **overrides,
        }

    def test_price_and_quantity_bounds_are_validated(self):
        for changes in (
            {"price": 0},
            {"min_quantity": 0},
            {"min_quantity": 5, "max_quantity": 4},
        ):
            with self.subTest(changes=changes):
                product = Product(**self.product_data(**changes))
                with self.assertRaises(ValidationError):
                    product.full_clean()

    def test_default_spec_rejects_unknown_fields_and_bad_epson_values(self):
        for spec in (
            {"page_count": 2},
            {"media_size": "A4"},
            {"copies": 2},
            {"borderless": "yes"},
        ):
            with self.subTest(spec=spec):
                with self.assertRaises(ValidationError):
                    validate_default_spec(spec)

    def test_quantity_must_be_a_whole_number_inside_bounds(self):
        product = Product(min_quantity=2, max_quantity=4)
        self.assertEqual(validate_quantity(product, "3"), 3)
        for value in (True, 1, 5, 2.5, "many"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_quantity(product, value)

    def test_slugs_are_generated_with_collision_suffixes(self):
        first = Product.objects.create(**self.product_data(slug="", name="Photo Print"))
        second = Product.objects.create(**self.product_data(slug="", name="Photo Print"))
        self.assertEqual(first.slug, "photo-print")
        self.assertEqual(second.slug, "photo-print-2")

    def test_cover_image_rejects_bad_content_extensions_and_excessive_dimensions(self):
        invalid = SimpleUploadedFile("cover.png", b"not an image", content_type="image/png")
        with self.assertRaisesMessage(ValidationError, "valid JPEG, PNG, or WebP"):
            validate_cover_image(invalid)

        with self.assertRaisesMessage(ValidationError, "extension must match"):
            validate_cover_image(cover_upload(filename="cover.jpg", image_format="PNG"))

        with self.assertRaisesMessage(ValidationError, "JPEG, PNG, or WebP"):
            validate_cover_image(cover_upload(filename="cover.gif", image_format="GIF"))

        webp = cover_upload(filename="cover.webp", image_format="WEBP")
        self.assertEqual(validate_cover_image(webp).name, "cover.webp")

        with patch("apps.catalogue.validators.COVER_IMAGE_MAX_PIXELS", 1):
            with self.assertRaisesMessage(ValidationError, "dimensions are too large"):
                validate_cover_image(cover_upload())

    def test_seed_migration_never_overwrites_admin_edits(self):
        Product.objects.filter(slug="2x2-id-picture").delete()
        seed_id_picture(apps, None)
        seeded = Product.objects.get(slug="2x2-id-picture")
        self.assertEqual(seeded.price, 3000)
        self.assertEqual(seeded.default_spec["copies"], 1)

        seeded.price = 4100
        seeded.name = "Admin Edited ID Picture"
        seeded.save()
        seed_id_picture(apps, None)
        seeded.refresh_from_db()
        self.assertEqual(seeded.price, 4100)
        self.assertEqual(seeded.name, "Admin Edited ID Picture")


class CatalogueAPITests(TestCase):
    def setUp(self):
        Product.objects.all().delete()
        self.api = APIClient()
        self.active = Product.objects.create(
            name="2x2 ID Picture", category="ID photos", price=3000,
            unit_label="piece", min_quantity=1, max_quantity=99,
            is_active=True, is_featured=True,
            default_spec={"media_size": "ps_a4", "copies": 1},
        )
        self.other = Product.objects.create(
            name="Photo Prints", category="Photos", price=1500,
            unit_label="piece", display_order=1,
        )
        self.archived = Product.objects.create(
            name="Old Service", category="Archive", price=900,
            is_active=False, is_featured=True,
        )
        User = get_user_model()
        self.admin = User.objects.create(
            username="catalogue-admin@example.com", email="catalogue-admin@example.com",
            role=User.Role.ADMIN,
        )
        self.approver = User.objects.create(
            username="catalogue-approver@example.com", email="catalogue-approver@example.com",
            role=User.Role.APPROVER,
        )
        self.customer = User.objects.create(
            username="catalogue-customer@example.com", email="catalogue-customer@example.com",
            role=User.Role.CLIENT,
        )

    def admin_client(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        return client

    def test_public_list_filters_active_search_category_and_featured(self):
        response = self.api.get("/api/catalogue/products/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["id"] for item in response.json()["results"]},
                         {self.active.id, self.other.id})

        featured = self.api.get("/api/catalogue/products/", {"featured": "true"})
        self.assertEqual([item["id"] for item in featured.json()["results"]], [self.active.id])
        category = self.api.get("/api/catalogue/products/", {"category": "photos"})
        self.assertEqual([item["id"] for item in category.json()["results"]], [self.other.id])
        search = self.api.get("/api/catalogue/products/", {"search": "2x2"})
        self.assertEqual([item["id"] for item in search.json()["results"]], [self.active.id])

    def test_inactive_product_detail_is_public_404(self):
        self.assertEqual(self.api.get(f"/api/catalogue/products/{self.active.slug}/").status_code, 200)
        self.assertEqual(self.api.get(f"/api/catalogue/products/{self.archived.slug}/").status_code, 404)

    def test_anonymous_customer_and_approver_cannot_manage_products(self):
        clients = [self.api]
        for user in (self.approver, self.customer):
            client = APIClient()
            client.force_authenticate(user=user)
            clients.append(client)
        payload = {"name": "Blocked", "category": "Test", "price": 100}
        for client in clients:
            with self.subTest(client=client):
                self.assertIn(client.post("/api/admin/catalogue/products/", payload,
                                          format="json").status_code, (401, 403))

    def test_admin_can_create_update_filter_and_archive(self):
        client = self.admin_client()
        created = client.post("/api/admin/catalogue/products/", {
            "name": "Business Cards", "category": "Cards", "price": 1200,
            "unit_label": "piece", "min_quantity": 10, "max_quantity": 500,
            "is_featured": True, "default_spec": {"media_size": "ps_a4", "copies": 1},
        }, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        product_id = created.json()["id"]
        self.assertEqual(created.json()["slug"], "business-cards")

        updated = client.patch(f"/api/admin/catalogue/products/{product_id}/",
                               {"price": 1300}, format="json")
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()["price"], 1300)

        self.assertEqual(client.delete(f"/api/admin/catalogue/products/{product_id}/").status_code, 204)
        self.assertTrue(Product.objects.get(pk=product_id).is_active is False)
        archived = client.get("/api/admin/catalogue/products/", {"status": "archived"})
        self.assertIn(product_id, {item["id"] for item in archived.json()["results"]})
        self.assertEqual(client.delete(f"/api/admin/catalogue/products/{product_id}/").status_code, 204)
        self.assertEqual(ActivityLog.objects.filter(
            action="catalogue.product.archive", object_id=product_id,
        ).count(), 1)

    def test_admin_validation_returns_structured_errors(self):
        client = self.admin_client()
        response = client.post("/api/admin/catalogue/products/", {
            "name": "Bad Spec", "category": "Test", "price": 100,
            "default_spec": {"copies": 2},
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("default_spec", response.json())


@override_settings(DEBUG=False)
class CatalogueCoverImageAPITests(TestCase):
    def setUp(self):
        media_dir = TemporaryDirectory()
        self.addCleanup(media_dir.cleanup)
        media_override = override_settings(MEDIA_ROOT=Path(media_dir.name))
        media_override.enable()
        self.addCleanup(media_override.disable)

        Product.objects.all().delete()
        self.product = Product.objects.create(
            name="2x2 ID Picture", category="ID photos", price=3000,
            is_active=True, is_featured=True,
        )
        User = get_user_model()
        self.admin = User.objects.create(
            username="cover-admin@example.com", email="cover-admin@example.com",
            role=User.Role.ADMIN,
        )
        self.approver = User.objects.create(
            username="cover-approver@example.com", email="cover-approver@example.com",
            role=User.Role.APPROVER,
        )
        self.api = APIClient()
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_admin_upload_is_stored_and_exposed_publicly(self):
        response = self.client.post("/api/admin/catalogue/products/", {
            "name": "Business Cards",
            "category": "Cards",
            "price": 1200,
            "is_active": "true",
            "default_spec": '{"media_size":"ps_a4","copies":1}',
            "cover_image": cover_upload(),
        }, format="multipart")

        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertNotIn("cover_image", data)
        self.assertTrue(data["cover_image_url"].startswith(
            "http://testserver/media/catalogue/products/business-cards/"
        ))
        self.assertTrue(data["cover_image_url"].endswith(".png"))
        product = Product.objects.get(pk=data["id"])
        self.assertTrue(default_storage.exists(product.cover_image.name))

        public = self.api.get("/api/catalogue/products/")
        self.assertEqual(public.status_code, 200)
        public_product = next(item for item in public.json()["results"] if item["id"] == product.id)
        self.assertEqual(public_product["cover_image_url"], data["cover_image_url"])

    def test_json_update_preserves_cover_and_null_removes_it(self):
        self.product.cover_image = cover_upload()
        self.product.save(update_fields=["cover_image", "updated_at"])
        old_name = self.product.cover_image.name
        original_url = self.api.get(f"/api/catalogue/products/{self.product.slug}/").json()["cover_image_url"]

        preserved = self.client.patch(
            f"/api/admin/catalogue/products/{self.product.id}/",
            {"price": 3100}, format="json",
        )
        self.assertEqual(preserved.status_code, 200, preserved.content)
        self.assertEqual(preserved.json()["cover_image_url"], original_url)
        self.assertTrue(default_storage.exists(old_name))

        with self.captureOnCommitCallbacks(execute=True):
            removed = self.client.patch(
                f"/api/admin/catalogue/products/{self.product.id}/",
                {"cover_image": None}, format="json",
            )
        self.assertEqual(removed.status_code, 200, removed.content)
        self.assertIsNone(removed.json()["cover_image_url"])
        self.product.refresh_from_db()
        self.assertFalse(self.product.cover_image.name)
        self.assertFalse(default_storage.exists(old_name))

    def test_replacing_cover_uses_a_new_file_and_removes_the_old_one(self):
        self.product.cover_image = cover_upload()
        self.product.save(update_fields=["cover_image", "updated_at"])
        old_name = self.product.cover_image.name
        old_url = self.api.get(f"/api/catalogue/products/{self.product.slug}/").json()["cover_image_url"]

        with self.captureOnCommitCallbacks(execute=True):
            replaced = self.client.patch(
                f"/api/admin/catalogue/products/{self.product.id}/",
                {"cover_image": cover_upload(filename="cover.jpg", image_format="JPEG")},
                format="multipart",
            )
        self.assertEqual(replaced.status_code, 200, replaced.content)
        self.assertNotEqual(replaced.json()["cover_image_url"], old_url)
        self.assertTrue(replaced.json()["cover_image_url"].endswith(".jpg"))
        self.product.refresh_from_db()
        self.assertTrue(default_storage.exists(self.product.cover_image.name))
        self.assertFalse(default_storage.exists(old_name))

    def test_multipart_cover_update_can_clear_maximum_quantity(self):
        self.product.max_quantity = 99
        self.product.save(update_fields=["max_quantity", "updated_at"])

        response = self.client.patch(
            f"/api/admin/catalogue/products/{self.product.id}/",
            {"max_quantity": "", "cover_image": cover_upload()},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()["max_quantity"])
        self.assertIsNotNone(response.json()["cover_image_url"])
        self.product.refresh_from_db()
        self.assertIsNone(self.product.max_quantity)

    def test_invalid_and_unsupported_uploads_are_rejected(self):
        invalid_uploads = [
            SimpleUploadedFile("cover.png", b"not an image", content_type="image/png"),
            cover_upload(filename="cover.gif", image_format="GIF"),
            cover_upload(filename="cover.jpg", image_format="PNG"),
        ]
        original_count = Product.objects.count()
        for upload in invalid_uploads:
            with self.subTest(filename=upload.name):
                response = self.client.post("/api/admin/catalogue/products/", {
                    "name": f"Invalid {upload.name}",
                    "category": "Test",
                    "price": 100,
                    "cover_image": upload,
                }, format="multipart")
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn("cover_image", response.json())
                self.assertEqual(Product.objects.count(), original_count)

    def test_cover_size_limit_is_enforced(self):
        original_count = Product.objects.count()
        with patch("apps.catalogue.validators.COVER_IMAGE_MAX_BYTES", 1):
            response = self.client.post("/api/admin/catalogue/products/", {
                "name": "Too Large", "category": "Test", "price": 100,
                "cover_image": cover_upload(),
            }, format="multipart")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("5 MB or smaller", str(response.json()["cover_image"]))
        self.assertEqual(Product.objects.count(), original_count)

    def test_approver_cannot_upload_a_cover(self):
        client = APIClient()
        client.force_authenticate(user=self.approver)
        response = client.patch(
            f"/api/admin/catalogue/products/{self.product.id}/",
            {"cover_image": cover_upload()}, format="multipart",
        )
        self.assertEqual(response.status_code, 403)


class CatalogueInHouseCompletionTests(TestCase):
    def setUp(self):
        Product.objects.all().delete()
        self.product = Product.objects.create(
            name="2x2 ID Picture", category="ID photos", price=3000,
            is_active=True, is_featured=True,
        )
        User = get_user_model()
        self.admin = User.objects.create(
            username="inhouse-admin@example.com", email="inhouse-admin@example.com",
            role=User.Role.ADMIN,
        )
        self.approver = User.objects.create(
            username="inhouse-approver@example.com", email="inhouse-approver@example.com",
            role=User.Role.APPROVER,
        )
        self.order = Order.objects.create(
            catalogue_product=self.product,
            product_name_snapshot=self.product.name,
            product_unit_price_snapshot=self.product.price,
            product_unit_label_snapshot=self.product.unit_label,
            product_min_quantity_snapshot=self.product.min_quantity,
            product_max_quantity_snapshot=self.product.max_quantity,
            product_quantity=2,
            subtotal=6000,
            status=Order.Status.PENDING_REVIEW,
            guest_name="Ada Customer",
            guest_contact_method="email",
            guest_contact_value="ada@example.com",
        )
        self.order_file = OrderFile.objects.create(
            order=self.order,
            file="orders/inhouse/original/photo.jpg",
            final_file="orders/inhouse/final/layout.pdf",
            file_name="layout.pdf",
            file_type=OrderFile.FileType.PDF,
            replaced_by_admin=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_admin_completes_prepared_catalogue_order_without_printer_jobs(self):
        with patch("apps.orders.views.submit_order_to_printer") as submit, \
                patch("apps.orders.views.prepare_order_for_print") as prepare:
            response = self.client.post(
                f"/api/admin/orders/{self.order.id}/actions/complete_in_house/",
                {}, format="json",
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], Order.Status.COMPLETED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.COMPLETED)
        self.assertIsNotNone(self.order.completed_at)
        self.assertEqual(self.order.print_jobs.count(), 0)
        self.assertEqual(
            self.order.history.order_by("-created_at").first().note,
            "Printed in-house; no Epson job submitted.",
        )
        submit.assert_not_called()
        prepare.assert_not_called()
        self.assertTrue(ActivityLog.objects.filter(
            action="order.complete_in_house", object_id=self.order.id,
        ).exists())

    def test_approver_cannot_complete_catalogue_order_in_house(self):
        client = APIClient()
        client.force_authenticate(user=self.approver)
        response = client.post(
            f"/api/admin/orders/{self.order.id}/actions/complete_in_house/",
            {}, format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_REVIEW)
        self.assertFalse(ActivityLog.objects.filter(action="order.complete_in_house").exists())

    def test_custom_and_unprepared_catalogue_orders_cannot_complete_in_house(self):
        custom = Order.objects.create(status=Order.Status.PENDING_REVIEW, subtotal=1000)
        response = self.client.post(
            f"/api/admin/orders/{custom.id}/actions/complete_in_house/",
            {}, format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("catalogue orders", response.json()["detail"])

        self.order_file.final_file = ""
        self.order_file.replaced_by_admin = False
        self.order_file.save(update_fields=["final_file", "replaced_by_admin"])
        response = self.client.post(
            f"/api/admin/orders/{self.order.id}/actions/complete_in_house/",
            {}, format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("shop-prepared layout", response.json()["detail"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_REVIEW)
        self.assertEqual(self.order.print_jobs.count(), 0)

    def test_in_house_completion_is_limited_to_pending_review(self):
        self.order.status = Order.Status.PRINTED_READY
        self.order.save(update_fields=["status"])
        response = self.client.post(
            f"/api/admin/orders/{self.order.id}/actions/complete_in_house/",
            {}, format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PRINTED_READY)
