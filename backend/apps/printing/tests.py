"""Epson device-authorization tests. Network calls are mocked."""

from io import BytesIO
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from django.test import TestCase, override_settings
from PIL import Image
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


class EpsonUploadFileTests(TestCase):
    """The upload POST must match what openapi.spec documents for ``/data``.

    Regression: ``File=`` used to carry the customer's own file name (spaces,
    non-ASCII, an extension the bytes may not even have) while the spec
    requires the literal ``1.(extension)``. Epson accepted the upload anyway
    and only complained later, at ``/print``, with ``400 invalid_print_data`` —
    surfaced as "All print jobs failed to submit". The body also needs an
    explicit ``Content-Type`` from Epson's accepted set, because a request
    with none gets a bodyless ``400``.
    """

    def setUp(self):
        self.client = EpsonClient(mock_mode=False)
        self.content = b"%PDF-1.4 fake payload"

    def _post(self, upload_uri, file_name, content=None):
        with patch.object(self.client.session, "post") as post:
            post.return_value = Mock(status_code=200, text="")
            self.client.upload_file(upload_uri, file_name,
                                    self.content if content is None else content)
        return post.call_args

    def test_upload_sets_a_pdf_content_type(self):
        args, kwargs = self._post("https://x/data?Key=k", "science activity.pdf")

        self.assertEqual(kwargs["headers"], {"Content-Type": "application/pdf"})

    def test_file_query_is_the_documented_one_based_name(self):
        """openapi.spec ``components.parameters.file``: format "1.(extension)".

        The customer's file name must never reach the query string.
        """
        args, _ = self._post("https://x/data?Key=k", "science activity.pdf")

        self.assertEqual(args[0], "https://x/data?Key=k&File=1.pdf")

    def test_file_query_drops_spaces_and_non_ascii_from_the_file_name(self):
        args, _ = self._post("https://x/data?Key=k", "Pang-ulong Noli ½.pdf")

        self.assertEqual(args[0], "https://x/data?Key=k&File=1.pdf")

    def test_upload_uses_ampersand_when_uri_already_has_a_query(self):
        args, _ = self._post("https://x/data?Key=k&Other=1", "1.pdf")

        self.assertEqual(args[0], "https://x/data?Key=k&Other=1&File=1.pdf")

    def test_content_type_and_file_query_follow_the_payload(self):
        # ``jpeg`` is normalised to ``jpg`` — Appendix G accepts both.
        cases = {
            "a.pdf": (b"%PDF-1.4 payload", "application/pdf", "File=1.pdf"),
            "a.jpg": (b"\xff\xd8\xff\xe0payload", "image/jpeg", "File=1.jpg"),
            "a.jpeg": (b"\xff\xd8\xff\xe0payload", "image/jpeg", "File=1.jpg"),
            "a.png": (b"\x89PNG\r\n\x1a\npayload", "image/png", "File=1.png"),
        }

        for name, (content, expected_type, expected_query) in cases.items():
            with self.subTest(name=name):
                args, kwargs = self._post("https://x/data?Key=k", name, content=content)
                self.assertEqual(kwargs["headers"], {"Content-Type": expected_type})
                self.assertEqual(args[0].rsplit("&", 1)[-1], expected_query)

    def test_content_type_follows_the_bytes_when_the_file_name_lies(self):
        """A JPEG named ".pdf" must still be declared (and named) as a JPEG."""
        args, kwargs = self._post("https://x/data?Key=k", "scan.pdf",
                                  content=b"\xff\xd8\xff\xe0payload")

        self.assertEqual(kwargs["headers"], {"Content-Type": "image/jpeg"})
        self.assertEqual(args[0], "https://x/data?Key=k&File=1.jpg")

    def test_unknown_extension_falls_back_to_sniffing_the_payload(self):
        _, kwargs = self._post("https://x/data?Key=k", "scan", content=b"\x89PNG\r\n\x1a\nrest")

        self.assertEqual(kwargs["headers"], {"Content-Type": "image/png"})

    def test_upload_never_sends_an_empty_content_type(self):
        for name in ("noextension", "weird.xyz"):
            with self.subTest(name=name):
                _, kwargs = self._post("https://x/data?Key=k", name)
                self.assertTrue(kwargs["headers"]["Content-Type"])

    def test_webp_is_transcoded_to_jpeg(self):
        """Appendix G has no WebP, so it is re-encoded instead of uploaded.

        Sending it as-is made Epson answer ``400 invalid_print_data`` ("The
        uploaded file is incorrect") the moment the order was approved.
        """
        buffer = BytesIO()
        Image.new("RGBA", (8, 8), (255, 0, 0, 128)).save(buffer, "WEBP")

        args, kwargs = self._post("https://x/data?Key=k", "screenshot.webp",
                                  content=buffer.getvalue())

        self.assertEqual(args[0], "https://x/data?Key=k&File=1.jpg")
        self.assertEqual(kwargs["headers"], {"Content-Type": "image/jpeg"})
        self.assertTrue(kwargs["data"].startswith(b"\xff\xd8\xff"), "not re-encoded to JPEG")

    def test_unprintable_payload_raises_before_wasting_a_job(self):
        with self.assertRaises(EpsonError) as ctx:
            self._post("https://x/data?Key=k", "notes.txt", content=b"just some text")

        self.assertIn("PDF, JPG and PNG", str(ctx.exception))

    def test_empty_payload_is_rejected_locally(self):
        with self.assertRaises(EpsonError) as ctx:
            self._post("https://x/data?Key=k", "blank.pdf", content=b"")

        self.assertIn("empty", str(ctx.exception))

    def test_invalid_print_data_is_explained_in_the_job_error(self):
        """The raw Epson code is unreadable in the order's status history."""
        client = EpsonClient(mock_mode=False)
        with patch.object(client, "_request",
                          side_effect=EpsonError("POST /printing/jobs/x/print failed (400): "
                                                 '{"error":"invalid_print_data"}')):
            with self.assertRaises(EpsonError) as ctx:
                client.execute_job("x")

        self.assertIn("The uploaded file is incorrect", str(ctx.exception))

    def test_error_response_raises_with_status(self):
        with patch.object(self.client.session, "post") as post:
            post.return_value = Mock(status_code=400, text="")
            with self.assertRaises(EpsonError) as ctx:
                self.client.upload_file("https://x/data?Key=k", "a.pdf", self.content)

        self.assertIn("400", str(ctx.exception))

    def test_mock_mode_performs_no_request(self):
        with patch.object(EpsonClient(mock_mode=True).session, "post") as post:
            EpsonClient(mock_mode=True).upload_file("https://x/data?Key=k", "a.pdf", self.content)

        post.assert_not_called()


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