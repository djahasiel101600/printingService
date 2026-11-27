from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminProductViewSet, PublicProductDetailView, PublicProductListView

router = DefaultRouter()
router.register("admin/catalogue/products", AdminProductViewSet, basename="admin-catalogue-products")

urlpatterns = [
    path("catalogue/products/", PublicProductListView.as_view(), name="catalogue-product-list"),
    path("catalogue/products/<slug:slug>/", PublicProductDetailView.as_view(), name="catalogue-product-detail"),
    path("", include(router.urls)),
]
