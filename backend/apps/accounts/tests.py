"""Account setup, staff access, and customer-directory tests."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.orders.models import Order

User = get_user_model()


class SetupFlowTests(TestCase):
    """GET reports whether setup is needed; POST creates the first admin once."""

    def setUp(self):
        self.api = APIClient()

    def _payload(self, email: str = "owner@print.local") -> dict:
        return {
            "email": email, "password": "s3cretpass!",
            "first_name": "Shop", "last_name": "Owner",
        }

    def test_status_reports_setup_needed_on_empty_database(self):
        response = self.api.get("/api/auth/setup/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["needs_setup"])

    def test_first_admin_creation_returns_tokens_and_admin_user(self):
        response = self.api.post("/api/auth/setup/", self._payload(), format="json")
        self.assertEqual(response.status_code, 201, response.content)

        body = response.json()
        self.assertIn("access", body)
        self.assertIn("refresh", body)
        self.assertEqual(body["user"]["email"], "owner@print.local")
        self.assertTrue(body["user"]["is_shop_admin"])

        user = User.objects.get(email="owner@print.local")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("s3cretpass!"))

    def test_created_admin_can_log_in(self):
        self.api.post("/api/auth/setup/", self._payload(), format="json")

        login = self.api.post("/api/auth/token/", {
            "email": "owner@print.local", "password": "s3cretpass!",
        }, format="json")
        self.assertEqual(login.status_code, 200, login.content)
        token = login.json()["access"]

        me = self.api.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["role"], "admin")

    def test_endpoint_locks_after_first_admin(self):
        self.api.post("/api/auth/setup/", self._payload(), format="json")

        status = self.api.get("/api/auth/setup/")
        self.assertFalse(status.json()["needs_setup"])

        again = self.api.post("/api/auth/setup/", self._payload("second@print.local"), format="json")
        self.assertEqual(again.status_code, 403)
        self.assertEqual(User.objects.filter(role=User.Role.ADMIN).count(), 1)

    def test_weak_password_rejected(self):
        response = self.api.post("/api/auth/setup/", {
            "email": "owner@print.local", "password": "short",
            "first_name": "Shop", "last_name": "Owner",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.exists())


class AdminCustomerDirectoryTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.admin = User.objects.create(
            username="owner@print.local", email="owner@print.local", role=User.Role.ADMIN,
        )
        self.approver = User.objects.create(
            username="approver@print.local", email="approver@print.local", role=User.Role.APPROVER,
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin)

    def test_signup_is_visible_with_contact_details_and_order_count(self):
        signup = self.api.post("/api/auth/register/", {
            "email": "ada@example.com", "password": "s3cretpass!",
            "first_name": "Ada", "last_name": "Customer", "phone": "09171234567",
        }, format="json")
        self.assertEqual(signup.status_code, 201, signup.content)
        login = self.api.post("/api/auth/token/", {
            "email": "ada@example.com", "password": "s3cretpass!",
        }, format="json")
        self.assertEqual(login.status_code, 200, login.content)
        customer = User.objects.get(email="ada@example.com")
        Order.objects.create(
            user=customer, tracking_id="PSP-CUST-0001", subtotal=1800,
        )

        response = self.admin_client.get("/api/admin/customers/", {"page": 1})
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["count"], 1)
        record = body["results"][0]
        self.assertEqual(record["email"], "ada@example.com")
        self.assertEqual(record["first_name"], "Ada")
        self.assertEqual(record["last_name"], "Customer")
        self.assertEqual(record["phone"], "09171234567")
        self.assertEqual(record["order_count"], 1)
        self.assertIsNotNone(record["last_order_at"])
        self.assertIsNotNone(record["date_joined"])
        self.assertIsNotNone(record["last_login"])

    def test_directory_is_admin_only_and_excludes_staff(self):
        User.objects.create(
            username="client@example.com", email="client@example.com", role=User.Role.CLIENT,
        )
        self.assertIn(self.api.get("/api/admin/customers/").status_code, (401, 403))
        approver_client = APIClient()
        approver_client.force_authenticate(user=self.approver)
        self.assertEqual(approver_client.get("/api/admin/customers/").status_code, 403)

        response = self.admin_client.get("/api/admin/customers/", {"page": 1})
        self.assertEqual([row["email"] for row in response.json()["results"]], [
            "client@example.com",
        ])

    def test_directory_paginates_and_searches_all_customers(self):
        User.objects.bulk_create([
            User(
                username=f"client{index}@example.com", email=f"client{index}@example.com",
                role=User.Role.CLIENT, first_name=f"Client {index}",
            )
            for index in range(26)
        ])
        first = self.admin_client.get("/api/admin/customers/", {
            "page": 1, "page_size": 25,
        })
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(len(first.json()["results"]), 25)
        self.assertEqual(first.json()["count"], 26)
        self.assertEqual(first.json()["num_pages"], 2)
        self.assertTrue(first.json()["has_next"])

        second = self.admin_client.get("/api/admin/customers/", {
            "page": 2, "page_size": 25,
        })
        self.assertEqual(len(second.json()["results"]), 1)
        self.assertFalse(second.json()["has_next"])

        search = self.admin_client.get("/api/admin/customers/", {
            "page": 1, "search": "Client 17",
        })
        self.assertEqual(search.json()["count"], 1)
        self.assertEqual(search.json()["results"][0]["email"], "client17@example.com")

    def test_legacy_typeahead_remains_a_twenty_item_list(self):
        User.objects.bulk_create([
            User(
                username=f"typeahead{index}@example.com", email=f"typeahead{index}@example.com",
                role=User.Role.CLIENT,
            )
            for index in range(25)
        ])
        response = self.admin_client.get("/api/admin/customers/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsInstance(response.json(), list)
        self.assertEqual(len(response.json()), 20)
        self.assertEqual(response.json()[0]["email"], "typeahead0@example.com")
