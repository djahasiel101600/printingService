"""Epson Connect API v2 client implementing the endpoints in openapi.spec:
auth token, devices/info, capability/{printMode}, capability/default,
POST /printing/jobs, file upload to uploadUri, jobs/{id}/print,
jobs/{id}/cancel, and GET jobs/{id} status. Bearer device token + x-api-key
on every call. EPSON_MOCK_MODE swaps in an in-memory simulator so the full
order lifecycle works without real Epson credentials.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from io import BytesIO

import requests
from django.conf import settings
from django.core.cache import cache
from PIL import Image

log = logging.getLogger(__name__)

TOKEN_CACHE_KEY = "epson:device-token"
APP_TOKEN_CACHE_KEY = "epson:application-token"


class EpsonError(Exception):
    """Raised when the Epson Connect API returns an error."""


@dataclass
class EpsonJobResult:
    job_id: str
    upload_uri: str


@dataclass
class EpsonJobStatus:
    status: str
    job_name: str = ""
    total_pages: int = 0
    start_date: str = ""
    update_date: str = ""


@dataclass
class _MockState:
    jobs: dict = field(default_factory=dict)

    def advance(self, job_id: str) -> str:
        """Move a mock job one step further along a realistic lifecycle."""
        path = ["created", "pending", "processing", "completed"]
        job = self.jobs.get(job_id)
        if not job:
            return "created"
        current = job["status"]
        if current in path:
            idx = min(path.index(current) + 1, len(path) - 1)
            job["status"] = path[idx]
        return job["status"]


_mock_state = _MockState()


def get_mock_state() -> _MockState:
    return _mock_state


class EpsonClient:
    """Thin HTTP wrapper around Epson Connect API v2."""

    # Content types the upload endpoint accepts (openapi.spec components
    # requestBodies ``File``), keyed by the extension from Appendix G
    # ("Printable file"). Anything outside this set is answered with an error,
    # and a request with *no* Content-Type at all is answered with a bodyless
    # ``400 Bad Request``.
    UPLOAD_CONTENT_TYPES = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
    }

    def __init__(self, mock_mode: bool | None = None):
        self.mock_mode = settings.EPSON_MOCK_MODE if mock_mode is None else mock_mode
        self.api_base = settings.EPSON_API_BASE
        self.upload_base = settings.EPSON_UPLOAD_BASE
        self.auth_base = settings.EPSON_AUTH_BASE
        self.session = requests.Session()

    # ------------------------------------------------------------------ auth
    @property
    def redirect_uri(self) -> str:
        """OAuth redirect target.

        Per tutorial §3 the "Redirect URI" is registered on the Epson app, and
        §4.1 says the value passed here must be that registered URI — so
        ``EPSON_REDIRECT_URI`` takes precedence over the derived default.
        """
        configured = (getattr(settings, "EPSON_REDIRECT_URI", "") or "").strip()
        if configured:
            return configured
        return f"{settings.FRONTEND_URL.rstrip('/')}/epson/callback"

    def get_authorization_url(self, state: str = "") -> str:
        """Build the Epson OAuth authorization URL for the device authorization
        code flow. The user opens this URL, signs in with the Epson account that
        owns the printer, and Epson redirects back with a ``code``.

        NOTE: Epson Connect API v2 has no password grant — the device token can
        only be obtained this way (see openapi.spec ``components.securitySchemes``).
        """
        params = {
            "response_type": "code",
            "client_id": settings.EPSON_CLIENT_ID,
            "redirect_uri": self.redirect_uri,
            "scope": "device",
        }
        if state:
            params["state"] = state
        query = "&".join(f"{k}={requests.utils.quote(v)}" for k, v in params.items())
        return f"{self.auth_base}/auth/authorize?{query}"

    def exchange_code(self, code: str) -> dict:
        """Exchange an authorization code for access + refresh tokens."""
        if self.mock_mode:
            return {"access_token": "mock-device-token", "refresh_token": "mock-refresh-token", "expires_in": 3600}
        response = self.session.post(
            f"{self.auth_base}/auth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                # Tutorial §4.1 puts client_id in the body; HTTP Basic is also
                # accepted by Epson, so send both.
                "client_id": settings.EPSON_CLIENT_ID,
            },
            auth=(settings.EPSON_CLIENT_ID, settings.EPSON_CLIENT_SECRET),
            headers={"x-api-key": settings.EPSON_API_KEY} if settings.EPSON_API_KEY else {},
            timeout=30,
        )
        if response.status_code != 200:
            raise EpsonError(f"Code exchange failed ({response.status_code}): {response.text[:300]}")
        return response.json()

    # -------------------------------------------------- device-token storage
    def stored_refresh_token(self) -> str:
        """Refresh token captured by the authorization-code flow (may be empty)."""
        from .models import EpsonCredential

        try:
            return EpsonCredential.load().refresh_token or ""
        except Exception:  # noqa: BLE001 - DB may be unmigrated during setup
            log.warning("Could not read the stored Epson refresh token", exc_info=True)
            return ""

    def save_refresh_token(self, refresh_token: str) -> None:
        """Persist the (rotating) refresh token so restarts keep working."""
        from .models import EpsonCredential

        cred = EpsonCredential.load()
        cred.refresh_token = refresh_token
        cred.save(update_fields=["refresh_token", "updated_at"])

    def _token_payload(self) -> dict:
        """Build the token request payload based on available credentials."""
        grant = settings.EPSON_DEVICE_GRANT

        # Explicit one-off: exchange an authorization code supplied via env.
        if grant == "authorization_code" and settings.EPSON_AUTH_CODE:
            return {
                "grant_type": "authorization_code",
                "code": settings.EPSON_AUTH_CODE,
                "redirect_uri": self.redirect_uri,
            }

        # Normal operation: redeem the device refresh token. A token captured by
        # the authorization-code flow wins over the env value because Epson
        # issues a fresh refresh token every time one is redeemed.
        refresh = self.stored_refresh_token() or settings.EPSON_DEVICE_REFRESH_TOKEN
        if refresh:
            return {"grant_type": "refresh_token", "refresh_token": refresh}

        # Epson Connect API v2 implements ONLY the authorization-code flow for
        # device tokens (openapi.spec securitySchemes.deviceToken): there is no
        # resource-owner password grant. EPSON_DEVICE_EMAIL / EPSON_DEVICE_PASSWORD
        # must never become a grant_type=password request - that is always
        # answered with "unsupported_grant_type". Fail with instructions instead
        # of sending a request the API can only reject.
        raise EpsonError(
            "Epson device not connected (no device refresh token). Complete the "
            "device authorization flow in Admin -> API Settings (Epson device "
            "authorization -> Get authorization URL -> sign in to Epson), or set "
            "EPSON_MOCK_MODE=True to simulate printing."
        )

    def get_device_token(self, force_refresh: bool = False) -> str:
        """Fetch (and cache) a device access token from the auth server."""
        if self.mock_mode:
            return "mock-device-token"
        cached = cache.get(TOKEN_CACHE_KEY)
        if cached and not force_refresh:
            return cached
        auth = (settings.EPSON_CLIENT_ID, settings.EPSON_CLIENT_SECRET) if settings.EPSON_CLIENT_ID else None
        response = self.session.post(
            f"{self.auth_base}/auth/token",
            data=self._token_payload(),
            auth=auth,
            headers={"x-api-key": settings.EPSON_API_KEY} if settings.EPSON_API_KEY else {},
            timeout=30,
        )
        if response.status_code != 200:
            raise EpsonError(f"Device token request failed ({response.status_code}): {response.text[:300]}")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise EpsonError("Device token response missing access_token")
        expires_in = int(payload.get("expires_in", 3600))
        cache.set(TOKEN_CACHE_KEY, token, timeout=max(60, expires_in - 300))
        if payload.get("refresh_token"):
            # Epson rotates the refresh token on every redemption; persist it so a
            # restart never falls back to a stale value in the environment.
            try:
                self.save_refresh_token(payload["refresh_token"])
            except Exception:  # noqa: BLE001 - never lose a working token over this
                log.warning("Could not persist the rotated Epson refresh token", exc_info=True)
            cache.set(f"{TOKEN_CACHE_KEY}:refresh", payload["refresh_token"], timeout=60 * 60 * 24 * 29)
        return token

    def get_application_token(self, force_refresh: bool = False) -> str:
        """Application token via the client-credentials grant (non-device APIs)."""
        if self.mock_mode:
            return "mock-application-token"
        cached = cache.get(APP_TOKEN_CACHE_KEY)
        if cached and not force_refresh:
            return cached
        response = self.session.post(
            f"{self.auth_base}/auth/token",
            data={"grant_type": "client_credentials"},
            auth=(settings.EPSON_CLIENT_ID, settings.EPSON_CLIENT_SECRET),
            headers={"x-api-key": settings.EPSON_API_KEY} if settings.EPSON_API_KEY else {},
            timeout=30,
        )
        if response.status_code != 200:
            raise EpsonError(f"Application token request failed ({response.status_code}): {response.text[:300]}")
        payload = response.json()
        token = payload["access_token"]
        cache.set(APP_TOKEN_CACHE_KEY, token, timeout=max(60, int(payload.get("expires_in", 3600)) - 300))
        return token

    # -------------------------------------------------------------- plumbing
    def _headers(self, token: str, content_type: str | None = None) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        if settings.EPSON_API_KEY:
            headers["x-api-key"] = settings.EPSON_API_KEY
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _request(self, method: str, path: str, json_body=None) -> dict:
        url = f"{self.api_base}{path}"
        token = self.get_device_token()
        response = self.session.request(
            method, url, headers=self._headers(token, "application/json" if json_body else None),
            json=json_body, timeout=60,
        )
        if response.status_code == 401:
            # Token revoked/expired mid-flight -> force refresh once and retry.
            token = self.get_device_token(force_refresh=True)
            response = self.session.request(
                method, url, headers=self._headers(token, "application/json" if json_body else None),
                json=json_body, timeout=60,
            )
        if response.status_code >= 400:
            raise EpsonError(f"{method} {path} failed ({response.status_code}): {response.text[:300]}")
        return response.json() if response.content else {}

    # ------------------------------------------------------------- endpoints
    def get_device_info(self) -> dict:
        if self.mock_mode:
            return {
                "productName": settings.EPSON_PRINTER_NAME,
                "serialNumber": "MOCK-12345678",
                "multiByteDisplay": False,
                "connected": True,
            }
        return self._request("GET", "/printing/devices/info")

    def get_capabilities(self, print_mode: str) -> dict:
        """GET /printing/capability/{printMode} — drives the guided form."""
        if self.mock_mode:
            return _mock_capabilities()
        return self._request("GET", f"/printing/capability/{print_mode}")

    def get_default_settings(self) -> dict:
        if self.mock_mode:
            return {"printSettings": {
                "paperSize": "ps_a4", "paperType": "pt_plainpaper", "borderless": False,
                "printQuality": "normal", "paperSource": "auto", "colorMode": "mono",
                "doubleSided": "none", "reverseOrder": False, "copies": 1, "collate": True,
            }}
        return self._request("GET", "/printing/capability/default")

    def create_job(self, job_name: str, print_mode: str, print_settings: dict) -> EpsonJobResult:
        """POST /printing/jobs -> {jobId, uploadUri} (job expires after 3 days)."""
        body = {"jobName": job_name[:256], "printMode": print_mode, "printSettings": print_settings}
        if self.mock_mode:
            job_id = uuid.uuid4().hex
            _mock_state.jobs[job_id] = {"status": "created", "name": job_name}
            return EpsonJobResult(job_id=job_id, upload_uri=f"{self.upload_base}/data?Key=mock-{job_id}")
        data = self._request("POST", "/printing/jobs", json_body=body)
        return EpsonJobResult(job_id=data["jobId"], upload_uri=data["uploadUri"])

    @staticmethod
    def _sniff_extension(content: bytes) -> str:
        """Identify the payload from its magic bytes.

        The customer's file name is not evidence: it can claim an extension the
        bytes do not have, and Epson validates the *data* — a mismatch surfaces
        as ``invalid_print_data`` when the job is released.
        """
        if content[:4] == b"%PDF":
            return "pdf"
        if content[:3] == b"\xff\xd8\xff":
            return "jpg"
        if content[:8] == b"\x89PNG\r\n\x1a\n":
            return "png"
        if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return "webp"
        if content[:6] in (b"GIF87a", b"GIF89a"):
            return "gif"
        return ""

    @staticmethod
    def _transcode_to_jpeg(content: bytes, file_name: str) -> bytes:
        """Re-encode an image Epson cannot print (WebP, GIF, …) as JPEG.

        Returns ``b""`` when the payload is not an image, so the caller can
        report a useful error instead of uploading bytes the printer rejects.
        """
        try:
            with Image.open(BytesIO(content)) as opened:
                # JPEG has no alpha channel: flatten transparency onto white
                # instead of the black it would otherwise print as.
                if opened.mode in ("RGBA", "LA", "PA") or (
                    opened.mode == "P" and "transparency" in opened.info
                ):
                    rgba = opened.convert("RGBA")
                    image = Image.new("RGB", rgba.size, (255, 255, 255))
                    image.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    image = opened.convert("RGB")
                buffer = BytesIO()
                image.save(buffer, format="JPEG", quality=95)
        except Exception:  # noqa: BLE001 - best effort; the caller reports it
            log.warning("Could not transcode '%s' for the printer", file_name, exc_info=True)
            return b""
        log.info("Transcoded '%s' to JPEG for the printer", file_name)
        return buffer.getvalue()

    def _prepare_payload(self, file_name: str, content: bytes) -> tuple[bytes, str]:
        """Return the bytes and Appendix G extension to send to ``/data``.

        WebP is offered by the upload form but is missing from Appendix G, so
        it is transcoded rather than pushed at a printer that would answer
        ``400 invalid_print_data``.
        """
        if not content:
            raise EpsonError(f"Refusing to upload '{file_name}': the file is empty.")
        extension = self._sniff_extension(content)
        if not extension:
            extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if extension == "jpeg":
            extension = "jpg"
        if extension in self.UPLOAD_CONTENT_TYPES:
            return content, extension
        converted = self._transcode_to_jpeg(content, file_name)
        if not converted:
            raise EpsonError(
                f"'{file_name}' is not a printable file. The printer accepts PDF, "
                "JPG and PNG (Epson Appendix G) — convert it and replace the file "
                "before releasing the order."
            )
        return converted, "jpg"

    def upload_file(self, upload_uri: str, file_name: str, content: bytes) -> None:
        """POST the binary to the job's uploadUri with ``&File=1.<ext>``.

        Three things matter here and all three were wrong before: the ``File``
        query value must be exactly ``1.(extension)`` (openapi.spec
        ``components.parameters.file``) and never the customer's own file name,
        which carries spaces and non-ASCII characters and can claim an
        extension the payload does not have — Epson stores it regardless and
        then rejects the job with ``invalid_print_data`` ("The uploaded file is
        incorrect") when ``/print`` is called. The payload also needs an
        explicit ``Content-Type`` from Epson's accepted set, because a request
        with none is answered with a bodyless ``400 Bad Request``.
        """
        if self.mock_mode:
            return
        prepared, extension = self._prepare_payload(file_name, content)
        separator = "&" if "?" in upload_uri else "?"
        url = f"{upload_uri}{separator}File=1.{extension}"
        headers = {"Content-Type": self.UPLOAD_CONTENT_TYPES[extension]}
        response = self.session.post(url, data=prepared, headers=headers, timeout=300)
        if response.status_code >= 400:
            raise EpsonError(f"File upload failed ({response.status_code}): {response.text[:300]}")

    def execute_job(self, job_id: str) -> None:
        """POST /printing/jobs/{jobId}/print — release the job to the printer."""
        if self.mock_mode:
            _mock_state.advance(job_id)
            return
        try:
            self._request("POST", f"/printing/jobs/{job_id}/print")
        except EpsonError as exc:
            if "invalid_print_data" in str(exc):
                # Surface the spec's plain-language meaning instead of the raw
                # error string in the order's status history.
                raise EpsonError(
                    f"{exc} — the printer rejected the uploaded file "
                    '(Epson: "The uploaded file is incorrect"). Check the file '
                    "format (PDF, JPG or PNG) and reprint."
                ) from exc
            raise

    def cancel_job(self, job_id: str) -> None:
        if self.mock_mode:
            if job_id in _mock_state.jobs:
                _mock_state.jobs[job_id]["status"] = "canceled"
            return
        self._request("POST", f"/printing/jobs/{job_id}/cancel")

    def get_job_status(self, job_id: str) -> EpsonJobStatus:
        """GET /printing/jobs/{jobId} — poll the job lifecycle."""
        if self.mock_mode:
            job = _mock_state.jobs.get(job_id)
            if not job:
                raise EpsonError("job_not_found")
            status = job["status"]
            if status in ("created", "pending", "processing"):
                status = _mock_state.advance(job_id)
            return EpsonJobStatus(status=status, job_name=job.get("name", ""), total_pages=0)
        data = self._request("GET", f"/printing/jobs/{job_id}")
        return EpsonJobStatus(
            status=data.get("status", "pending"),
            job_name=data.get("jobName", ""),
            total_pages=data.get("totalPages", 0),
            start_date=data.get("startDate", ""),
            update_date=data.get("updateDate", ""),
        )


def _mock_capabilities() -> dict:
    """Plausible capability payload mirroring the documented response shape."""
    return {
        "colorModes": ["color", "mono"],
        "resolutions": [300, 600],
        "paperSizes": [
            {
                "paperSize": "ps_a4",
                "paperTypes": [
                    {"paperType": "pt_plainpaper", "borderless": False,
                     "paperSources": ["auto", "front1", "front2"],
                     "printQualities": ["draft", "normal", "high"], "doubleSided": True},
                    {"paperType": "pt_photopaper", "borderless": True,
                     "paperSources": ["rear"], "printQualities": ["high"], "doubleSided": False},
                ],
            },
            {
                "paperSize": "ps_letter",
                "paperTypes": [
                    {"paperType": "pt_plainpaper", "borderless": False,
                     "paperSources": ["auto", "front1"],
                     "printQualities": ["draft", "normal", "high"], "doubleSided": True},
                ],
            },
            {
                "paperSize": "ps_a3",
                "paperTypes": [
                    {"paperType": "pt_plainpaper", "borderless": False,
                     "paperSources": ["auto"], "printQualities": ["normal", "high"],
                     "doubleSided": False},
                ],
            },
            {
                "paperSize": "ps_2l",
                "paperTypes": [
                    {"paperType": "pt_photopaper", "borderless": True,
                     "paperSources": ["rear"], "printQualities": ["high"], "doubleSided": False},
                ],
            },
        ],
    }

