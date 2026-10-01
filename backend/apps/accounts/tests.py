"""First-run setup (admin bootstrap) tests."""
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class SetupFlowTests(TestCase):
    """GET reports whether setup is needed; POST creates the first admin once."""

    def setUp(self):
        from rest_framework.test import APIClient

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