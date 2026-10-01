from rest_framework import permissions, viewsets

from .models import PriceRule
from .serializers import PriceRuleSerializer


class IsShopAdmin(permissions.BasePermission):
    """Allows access only to shop admin/staff users."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_shop_admin)


class PriceRuleViewSet(viewsets.ModelViewSet):
    queryset = PriceRule.objects.all()
    serializer_class = PriceRuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]
