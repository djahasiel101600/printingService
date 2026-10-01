from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PriceRuleViewSet

router = DefaultRouter()
router.register("admin/pricing-rules", PriceRuleViewSet, basename="pricing-rules")

urlpatterns = [
    path("", include(router.urls)),
]
