from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PriceRuleViewSet, PricingSettingsView

router = DefaultRouter()
router.register("admin/pricing-rules", PriceRuleViewSet, basename="pricing-rules")

urlpatterns = [
    # Singleton pricing knobs: public GET / admin-only PUT. Declared before the
    # router so it can never be shadowed by a future "<pk>/" detail route.
    path("pricing/settings/", PricingSettingsView.as_view(), name="pricing-settings"),
    path("", include(router.urls)),
]
