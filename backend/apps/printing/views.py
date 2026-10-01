from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pricing.views import IsShopAdmin

from .epson import EpsonClient, EpsonError
from .serializers import PrintJobSerializer
from .services import sync_print_jobs


class CapabilitiesView(APIView):
    """Printer capabilities per print mode — drives the guided order form.

    The PRD (§7.1) requires that clients only ever see sizes/types/qualities
    the connected printer actually supports.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        print_mode = request.query_params.get("print_mode", "document")
        if print_mode not in ("document", "photo"):
            print_mode = "document"
        client = EpsonClient()
        try:
            payload = client.get_capabilities(print_mode)
        except Exception as exc:  # noqa: BLE001 - surfaced as a clean API error
            return Response({"detail": f"Printer capabilities unavailable: {exc}"}, status=503)
        return Response({"printMode": print_mode, **payload})


class DeviceInfoView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get(self, request):
        client = EpsonClient()
        try:
            return Response(client.get_device_info())
        except Exception as exc:  # noqa: BLE001
            return Response({"detail": f"Printer unavailable: {exc}"}, status=503)


class EpsonAuthUrlView(APIView):
    """Get the Epson OAuth authorization URL for device setup."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get(self, request):
        client = EpsonClient()
        try:
            url = client.get_authorization_url()
            return Response({"authorization_url": url})
        except Exception as exc:
            return Response({"detail": str(exc)}, status=400)


class EpsonExchangeCodeView(APIView):
    """Exchange an authorization code for access + refresh tokens."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def post(self, request):
        code = request.data.get("code", "").strip()
        if not code:
            return Response({"detail": "Authorization code is required."}, status=400)
        client = EpsonClient()
        try:
            tokens = client.exchange_code(code)
            return Response({
                "detail": "Authorization successful!",
                "access_token": tokens.get("access_token", ""),
                "refresh_token": tokens.get("refresh_token", ""),
                "expires_in": tokens.get("expires_in", 0),
            })
        except EpsonError as exc:
            return Response({"detail": str(exc)}, status=400)


class EpsonTestConnectionView(APIView):
    """Test the Epson API connection with current credentials."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def post(self, request):
        mock_mode = request.data.get("mock_mode")
        client = EpsonClient(mock_mode=mock_mode if mock_mode is not None else None)
        result = {"mock_mode": client.mock_mode, "tests": {}}

        # Test 1: Application token
        try:
            app_token = client.get_application_token()
            result["tests"]["application_token"] = {"status": "success", "token_prefix": app_token[:20] + "..." if len(app_token) > 20 else app_token}
        except Exception as exc:
            result["tests"]["application_token"] = {"status": "failed", "error": str(exc)[:200]}

        # Test 2: Device token
        try:
            device_token = client.get_device_token()
            result["tests"]["device_token"] = {"status": "success", "token_prefix": device_token[:20] + "..." if len(device_token) > 20 else device_token}
        except Exception as exc:
            result["tests"]["device_token"] = {"status": "failed", "error": str(exc)[:200]}

        # Test 3: Device info
        try:
            info = client.get_device_info()
            result["tests"]["device_info"] = {"status": "success", "data": info}
        except Exception as exc:
            result["tests"]["device_info"] = {"status": "failed", "error": str(exc)[:200]}

        # Test 4: Capabilities
        try:
            caps = client.get_capabilities("document")
            result["tests"]["capabilities"] = {"status": "success", "color_modes": caps.get("colorModes"), "paper_sizes": [p["paperSize"] for p in caps.get("paperSizes", [])]}
        except Exception as exc:
            result["tests"]["capabilities"] = {"status": "failed", "error": str(exc)[:200]}

        all_passed = all(t["status"] == "success" for t in result["tests"].values())
        result["overall"] = "success" if all_passed else "failed"
        return Response(result)


class PrintJobViewSet(APIView):
    """Admin: list print jobs and sync their status from Epson."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get(self, request):
        from .models import PrintJob

        jobs = PrintJob.objects.select_related("order", "order_file").all()
        order_id = request.query_params.get("order")
        if order_id:
            jobs = jobs.filter(order_id=order_id)
        return Response(PrintJobSerializer(jobs[:200], many=True).data)

    def post(self, request):
        """Trigger a status sync (optionally scoped to ?order=<id>)."""
        from apps.orders.models import Order

        order = None
        order_id = request.query_params.get("order")
        if order_id:
            order = Order.objects.filter(id=order_id).first()
            if not order:
                return Response({"detail": "Order not found"}, status=404)
        sync_print_jobs(order)
        return Response({"detail": "Print job statuses synced."})
