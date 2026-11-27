from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.activitylog.models import ActivityLog
seed_id_picture = import_module(
    "apps.catalogue.migrations.0002_seed_id_picture"
).seed_id_picture
from apps.catalogue.models import Product
from apps.catalogue.validators import validate_default_spec, validate_quantity


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
