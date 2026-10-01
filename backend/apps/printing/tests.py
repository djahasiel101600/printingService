"""Epson device-authorization tests. Network calls are mocked."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.printing.epson import EpsonClient, EpsonError
from apps.printing.models import EpsonCredential


class EpsonTokenPayloadTests(TestCase):
    """The rotating device token must always win over stale/legacy settings."""

    def test_stored_refresh_token_wins_over_environment(self):
        cred = EpsonCredential.load()
        cred.refresh_token = "db-refresh"
        cred.save()

        with override_settings(EPSON_DEVICE_REFRESH_TOKEN="env-refresh", EPSON_DEVICE_GRANT="password"):
            payload = EpsonClient(mock_mode=False)._token_payload()

        self.assertEqual(payload, {"grant_type": "refresh_token", "refresh_token": "db-refresh"})

    def test_environment_refresh_token_used_when_store_is_empty(self):
        with override_settings(EPSON_DEVICE_REFRESH_TOKEN="env-refresh"):
            payload = EpsonClient(mock_mode=False)._token_payload()

        self.assertEqual(payload["grant_type"], "refresh_token")
        self.assertEqual(payload["refresh_token"], "env-refresh")

    def test_authorization_code_grant_is_honoured(self):
        with override_settings(EPSON_DEVICE_GRANT="authorization_code", EPSON_AUTH_CODE="the-code"):
            payload = EpsonClient(mock_mode=False)._token_payload()

        self.assertEqual(payload["grant_type"], "authorization_code")
        self.assertEqual(payload["code"], "the-code")
        self.assertTrue(payload["redirect_uri"].endswith("/epson/callback"))

    def test_unconfigured_device_raises_actionable_error(self):
        with override_settings(EPSON_DEVICE_REFRESH_TOKEN="", EPSON_DEVICE_EMAIL="", EPSON_DEVICE_GRANT="password"):
            with self.assertRaises(EpsonError) as ctx:
                EpsonClient(mock_mode=False)._token_payload()

        self.assertIn("device authorization flow", str(ctx.exception))

    def test_password_grant_is_never_sent(self):
        """API v2 has no password grant: configured e-mail/password must NOT
        produce grant_type=password (that is the unsupported_grant_type bug) —
        the user has to run the device authorization flow instead."""
        with override_settings(
            EPSON_DEVICE_REFRESH_TOKEN="",
            EPSON_DEVICE_EMAIL="printer@demo.epsonconnect.com",
            EPSON_DEVICE_PASSWORD="hunter2",
            EPSON_DEVICE_GRANT="password",
        ):
            with self.assertRaises(EpsonError) as ctx:
                EpsonClient(mock_mode=False)._token_payload()

        self.assertIn("device authorization flow", str(ctx.exception))
        self.assertNotIn("password", str(ctx.exception).lower().replace("password grant", ""))


class EpsonDeviceFlowViewTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.admin = User.objects.create_user(
            username="admin@print.local", email="admin@print.local",
            password="s3cretpass!", role=User.Role.ADMIN,
        )
        self.api.force_authenticate(self.admin)

    def test_status_reports_not_connected_initially(self):
        with override_settings(EPSON_DEVICE_REFRESH_TOKEN=""):
            response = self.api.get("/api/admin/epson/status/")

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertFalse(body["device_connected"])
        self.assertEqual(body["refresh_token_source"], "none")

    @override_settings(FRONTEND_URL="https://print.example.com",
                       EPSON_REDIRECT_URI="",  # exercise the derived default
                       EPSON_CLIENT_ID="cid", EPSON_CLIENT_SECRET="secret")
    def test_auth_url_stores_state_and_encodes_redirect(self):
        with patch("apps.printing.epson.EpsonClient.get_application_token", return_value="tok"):
            response = self.api.get("/api/admin/epson/auth-url/")

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        query = parse_qs(urlparse(body["authorization_url"]).query)
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["client_id"], ["cid"])
        self.assertEqual(query["scope"], ["device"])
        self.assertEqual(query["redirect_uri"], ["https://print.example.com/epson/callback"])
        self.assertEqual(query["state"], [body["state"]])
        self.assertEqual(EpsonCredential.load().pending_state, body["state"])

    @override_settings(EPSON_REDIRECT_URI="https://registered.example.com/cb",
                       EPSON_CLIENT_ID="cid", EPSON_CLIENT_SECRET="secret")
    def test_registered_redirect_uri_overrides_the_default(self):
        """Tutorial §4.1: the value sent must be the URI registered in §3."""
        with patch("apps.printing.epson.EpsonClient.get_application_token", return_value="tok"):
            response = self.api.get("/api/admin/epson/auth-url/")

        body = response.json()
        self.assertEqual(body["redirect_uri"], "https://registered.example.com/cb")
        self.assertEqual(
            parse_qs(urlparse(body["authorization_url"]).query)["redirect_uri"],
            ["https://registered.example.com/cb"],
        )

    @override_settings(EPSON_CLIENT_ID="cid", EPSON_CLIENT_SECRET="secret")
    def test_auth_url_reports_bad_credentials_instead_of_a_dead_link(self):
        with patch("apps.printing.epson.EpsonClient.get_application_token",
                   side_effect=EpsonError("Application token request failed (401): invalid_client")):
            response = self.api.get("/api/admin/epson/auth-url/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("regenerate", response.json()["detail"].lower())

    def test_auth_url_requires_configured_credentials(self):
        with override_settings(EPSON_CLIENT_ID="", EPSON_CLIENT_SECRET=""):
            response = self.api.get("/api/admin/epson/auth-url/")

        self.assertEqual(response.status_code, 400)

    def test_exchange_persists_refresh_token_and_clears_state(self):
        cred = EpsonCredential.load()
        cred.pending_state = "state-123"
        cred.save()

        with patch("apps.printing.epson.EpsonClient.exchange_code") as exchange:
            exchange.return_value = {"access_token": "dev", "refresh_token": "rotated-refresh", "expires_in": 3600}
            response = self.api.post(
                "/api/admin/epson/exchange-code/", {"code": "abc", "state": "state-123"}, format="json")

        self.assertEqual(response.status_code, 200, response.content)
        stored = EpsonCredential.load()
        self.assertEqual(stored.refresh_token, "rotated-refresh")
        self.assertEqual(stored.pending_state, "")
        # The secret is never echoed back to the browser.
        self.assertNotIn("rotated-refresh", response.content.decode())

    def test_exchange_rejects_state_mismatch(self):
        cred = EpsonCredential.load()
        cred.pending_state = "expected"
        cred.save()

        with patch("apps.printing.epson.EpsonClient.exchange_code") as exchange:
            response = self.api.post(
                "/api/admin/epson/exchange-code/", {"code": "abc", "state": "wrong"}, format="json")

        self.assertEqual(response.status_code, 400)
        exchange.assert_not_called()

    def test_exchange_requires_a_code(self):
        response = self.api.post("/api/admin/epson/exchange-code/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_regular_client_cannot_reach_the_device_flow(self):
        client = User.objects.create_user(
            username="c@example.com", email="c@example.com", password="s3cretpass!")
        api = APIClient()
        api.force_authenticate(client)

        self.assertEqual(api.get("/api/admin/epson/auth-url/").status_code, 403)
        self.assertEqual(api.get("/api/admin/epson/status/").status_code, 403)