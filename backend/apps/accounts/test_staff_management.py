"""User management: approver accounts and what they may (and may not) do.

The approver role exists so a shop can hand the approval queue — "release this
paid submission to the printer" — to a second person without handing over the
pricing table, the PayMongo/Epson credentials or the staff list (PRD §3
separates Admin/Staff from Super Admin for exactly these reasons).
"""
import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.orders.tests import make_pdf

User = get_user_model()

BASE_SPEC = {
    "media_size": "ps_a4", "media_type": "pt_plainpaper", "color_mode": "mono",
    "print_quality": "normal", "sides": "none", "copies": 1,
}


class StaffManagementTestCase(TestCase):
    """Owner + approver + client accounts, and helpers to sign in as each."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner@shop.local", email="owner@shop.local",
            password="ownerpass123", role=User.Role.ADMIN, is_staff=True,
        )
        self.approver = User.objects.create_user(
            username="mara@shop.local", email="mara@shop.local",
            password="mara1234pass", role=User.Role.APPROVER,
        )
        self.client_user = User.objects.create_user(
            username="ana@example.com", email="ana@example.com",
            password="clientpass12", role=User.Role.CLIENT,
        )

    def login(self, email: str, password: str) -> APIClient:
        api = APIClient()
        response = api.post("/api/auth/token/", {"email": email, "password": password},
                            format="json")
        self.assertEqual(response.status_code, 200, response.content)
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
        return api

    def submit_and_pay(self) -> dict:
        """A paid order waiting in the review queue, placed by the client."""
        api = self.login("ana@example.com", "clientpass12")
        response = api.post("/api/orders/", {
            "files": [SimpleUploadedFile("report.pdf", make_pdf(3),
                                         content_type="application/pdf")],
            "spec": json.dumps(BASE_SPEC),
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        order = response.json()["order"]
        checkout = api.post("/api/payments/checkout/", {
            "order_id": order["id"], "method": "qrph", "payment_type": "full",
        }, format="json")
        self.assertIn(checkout.status_code, (200, 201), checkout.content)
        api.post("/api/payments/webhook/simulate/",
                 {"payment_id": checkout.json()["payment_id"]}, format="json")
        return order

    @property
    def owner_api(self) -> APIClient:
        return self.login("owner@shop.local", "ownerpass123")

    @property
    def approver_api(self) -> APIClient:
        return self.login("mara@shop.local", "mara1234pass")

    @property
    def client_api(self) -> APIClient:
        return self.login("ana@example.com", "clientpass12")


class StaffCreationTests(StaffManagementTestCase):
    def test_owner_creates_an_approver_who_can_sign_in(self):
        response = self.owner_api.post("/api/admin/users/", {
            "email": "Noel@Shop.Local", "first_name": "Noel", "last_name": "Diaz",
            "role": "approver", "password": "strongpass123",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        payload = response.json()
        self.assertEqual(payload["role"], "approver")
        self.assertTrue(payload["is_approver"])
        self.assertFalse(payload["is_shop_admin"])
        self.assertTrue(payload["is_active"])
        self.assertEqual(payload["email"], "noel@shop.local")   # normalised

        # The new account can sign in and reports review capability.
        me = self.login("noel@shop.local", "strongpass123").get("/api/auth/me/")
        self.assertEqual(me.status_code, 200, me.content)
        self.assertTrue(me.json()["can_review_orders"])
        self.assertFalse(me.json()["is_shop_admin"])

    def test_creating_a_client_or_a_duplicate_is_rejected(self):
        api = self.owner_api
        as_client = api.post("/api/admin/users/", {
            "email": "someone@example.com", "role": "client", "password": "strongpass123",
        }, format="json")
        self.assertEqual(as_client.status_code, 400, as_client.content)

        duplicate = api.post("/api/admin/users/", {
            "email": "owner@shop.local", "role": "approver", "password": "strongpass123",
        }, format="json")
        self.assertEqual(duplicate.status_code, 400, duplicate.content)

    def test_password_rules_apply_to_staff_accounts(self):
        api = self.owner_api
        missing = api.post("/api/admin/users/", {
            "email": "nopass@shop.local", "role": "approver",
        }, format="json")
        self.assertEqual(missing.status_code, 400, missing.content)
        self.assertIn("password", missing.json())

        weak = api.post("/api/admin/users/", {
            "email": "weak@shop.local", "role": "approver", "password": "123",
        }, format="json")
        self.assertEqual(weak.status_code, 400, weak.content)

    def test_only_the_owner_manages_staff_accounts(self):
        forbidden = self.approver_api.post("/api/admin/users/", {
            "email": "helper@shop.local", "role": "approver", "password": "strongpass123",
        }, format="json")
        self.assertEqual(forbidden.status_code, 403, forbidden.content)

        client_side = self.client_api.get("/api/admin/users/")
        self.assertEqual(client_side.status_code, 403, client_side.content)

    def test_owner_cannot_demote_or_deactivate_themselves(self):
        api = self.owner_api
        demote = api.patch(f"/api/admin/users/{self.owner.pk}/", {"role": "approver"},
                           format="json")
        self.assertEqual(demote.status_code, 400, demote.content)
        disable = api.delete(f"/api/admin/users/{self.owner.pk}/")
        self.assertEqual(disable.status_code, 400, disable.content)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.role, User.Role.ADMIN)
        self.assertTrue(self.owner.is_active)

    def test_the_last_active_admin_can_never_be_demoted(self):
        """Backstop behind the endpoint: a lone owner is protected.

        Through HTTP the self-guard fires first (an owner demoting themselves
        is refused), so the "last active admin" check is exercised directly —
        it is the safety net if the endpoint is ever exposed to a different
        caller, e.g. via an impersonation or bulk-roles path.
        """
        from apps.accounts.views import AdminStaffDetailView

        view = AdminStaffDetailView()
        # The owner is the only active admin: demoting them would lock the
        # shop out of its own configuration.
        self.assertTrue(view._would_remove_last_owner(self.owner, removing=True))
        # Approvers are not owners, so the guard never applies to them.
        self.assertFalse(view._would_remove_last_owner(self.approver, removing=True))
        # With a second active admin in the shop, demotion is safe.
        User.objects.create_user(
            username="second@shop.local", email="second@shop.local",
            password="strongpass123", role=User.Role.ADMIN,
        )
        self.assertFalse(view._would_remove_last_owner(self.owner, removing=True))

    def test_deactivating_an_approver_blocks_its_login(self):
        # Sign in first so we know the account works before it is disabled.
        self.assertEqual(self.approver_api.get("/api/auth/me/").status_code, 200)
        disabled = self.owner_api.delete(f"/api/admin/users/{self.approver.pk}/")
        self.assertEqual(disabled.status_code, 200, disabled.content)
        self.assertFalse(disabled.json()["is_active"])
        locked_out = APIClient().post("/api/auth/token/",
                                      {"email": "mara@shop.local",
                                       "password": "mara1234pass"}, format="json")
        self.assertEqual(locked_out.status_code, 401, locked_out.content)


class ApproverPermissionsTests(StaffManagementTestCase):
    """The approver works the print queue — and nothing else."""

    def test_approver_sees_the_queue_and_approves_an_order(self):
        order = self.submit_and_pay()
        api = self.approver_api

        queue = api.get("/api/admin/orders/", {"status": "pending_review"})
        self.assertEqual(queue.status_code, 200, queue.content)
        self.assertIn(order["id"], [entry["id"] for entry in queue.json()])

        detail = api.get(f"/api/admin/orders/{order['id']}/")
        self.assertEqual(detail.status_code, 200, detail.content)

        approve = api.post(f"/api/admin/orders/{order['id']}/actions/approve/", {},
                           format="json")
        self.assertEqual(approve.status_code, 200, approve.content)
        self.assertIn(approve.json()["status"],
                      ("approved_queued", "printing", "on_hold"))

    def test_approver_can_request_a_revision(self):
        order = self.submit_and_pay()
        response = self.approver_api.post(
            f"/api/admin/orders/{order['id']}/actions/request_revision/",
            {"note": "Page 2 is cut off, please re-upload."}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "revision_requested")

    def test_approver_cannot_handle_money_or_cancellation(self):
        order = self.submit_and_pay()
        api = self.approver_api
        for action in ("cancel", "record_payment"):
            response = api.post(
                f"/api/admin/orders/{order['id']}/actions/{action}/", {}, format="json")
            self.assertEqual(response.status_code, 403, f"{action}: {response.content}")

    def test_approver_cannot_touch_configuration(self):
        api = self.approver_api
        # Pricing, payment options and printer credentials are owner-only.
        # (GET on the settings singletons is public by design — quoting runs
        # for guests — so the guard is on the writes.)
        cases = [
            ("put", "/api/pricing/settings/", {"duplex_discount_factor": 0.5}),
            ("put", "/api/payments/settings/", {"allow_pay_on_pickup": True}),
            ("get", "/api/admin/epson/status/", None),
            ("get", "/api/admin/epson/auth-url/", None),
            ("get", "/api/admin/printer/", None),
            ("post", "/api/admin/paymongo/test-connection/", {}),
        ]
        for method, url, payload in cases:
            response = getattr(api, method)(url, payload, format="json") \
                if payload is not None else getattr(api, method)(url)
            self.assertEqual(response.status_code, 403,
                             f"{method.upper()} {url} -> {response.status_code}")

        # ...but the printer job queue is exactly what an approver needs.
        self.assertEqual(api.get("/api/admin/print-jobs/").status_code, 200)

    def test_clients_are_locked_out_of_the_review_queue(self):
        api = self.client_api
        self.assertEqual(api.get("/api/admin/orders/").status_code, 403)
        self.assertEqual(api.get("/api/admin/print-jobs/").status_code, 403)

        me = api.get("/api/auth/me/").json()
        self.assertFalse(me["can_review_orders"])
        self.assertFalse(me["is_approver"])
        self.assertFalse(me["is_shop_admin"])
