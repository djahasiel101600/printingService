from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PriceRule, PricingSettings
from .serializers import PriceRuleSerializer


class IsShopAdmin(permissions.BasePermission):
    """Allows access only to shop admin/staff users."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_shop_admin)


class PriceRuleViewSet(viewsets.ModelViewSet):
    queryset = PriceRule.objects.all()
    serializer_class = PriceRuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]


class PricingSettingsView(APIView):
    """Public read / admin-only write for the shop's global pricing knobs.

    Mirrors payments.PaymentSettingsView: quoting runs for guests (no auth),
    so GET is public; writes require a shop admin. Values live in the DB
    (PricingSettings, seeded from the legacy env vars by migration 0002) so
    the shop can edit them at runtime from the admin Pricing page.
    """

    permission_classes = [permissions.AllowAny]

    @staticmethod
    def _payload(knob: PricingSettings) -> dict:
        return {
            "duplex_discount_factor": knob.duplex_discount_factor,
            "min_partial_percent": knob.min_partial_percent,
            "fallback_price_per_side": knob.fallback_price_per_side,
            "fallback_price_per_side_peso": knob.fallback_price_per_side / 100,
            "updated_at": knob.updated_at,
        }

    def get(self, request):
        return Response(self._payload(PricingSettings.get_solo()))

    def put(self, request):
        if not (request.user and request.user.is_authenticated and request.user.is_shop_admin):
            return Response({"detail": "Admin access required."}, status=403)

        knob = PricingSettings.get_solo()
        data = request.data

        if "duplex_discount_factor" in data:
            try:
                factor = float(data["duplex_discount_factor"])
            except (TypeError, ValueError):
                return Response({"duplex_discount_factor": "Must be a number between 0.0 and 1.0."}, status=400)
            if not 0.0 <= factor <= 1.0:
                return Response({"duplex_discount_factor": "Must be between 0.0 and 1.0."}, status=400)
            knob.duplex_discount_factor = factor

        if "min_partial_percent" in data:
            try:
                percent = int(data["min_partial_percent"])
            except (TypeError, ValueError):
                return Response({"min_partial_percent": "Must be a whole number between 0 and 100."}, status=400)
            if not 0 <= percent <= 100:
                return Response({"min_partial_percent": "Must be between 0 and 100."}, status=400)
            knob.min_partial_percent = percent

        if "fallback_price_per_side" in data:
            try:
                price = int(data["fallback_price_per_side"])
            except (TypeError, ValueError):
                return Response({"fallback_price_per_side": "Must be a whole number of centavos (≥ 1)."}, status=400)
            if price < 1:
                return Response({"fallback_price_per_side": "Must be at least 1 centavo."}, status=400)
            knob.fallback_price_per_side = price

        knob.save()
        return Response(self._payload(knob))
