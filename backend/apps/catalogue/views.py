from django.db.models import Q
from rest_framework import filters, generics, mixins, permissions, viewsets
from rest_framework.response import Response

from apps.activitylog.services import log_activity
from apps.pricing.views import IsShopAdmin

from .models import Product
from .serializers import ProductSerializer


class PublicProductQuerysetMixin:
    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True)
        search = self.request.query_params.get("search", "").strip()
        category = self.request.query_params.get("category", "").strip()
        featured = self.request.query_params.get("featured")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search) | Q(category__icontains=search)
            )
        if category:
            queryset = queryset.filter(category__iexact=category)
        if featured is not None:
            queryset = queryset.filter(is_featured=featured.lower() in {"1", "true", "yes"})
        return queryset


class PublicProductListView(PublicProductQuerysetMixin, generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["display_order", "name", "price"]
    ordering = ["display_order", "name", "id"]


class PublicProductDetailView(PublicProductQuerysetMixin, generics.RetrieveAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"


class AdminProductViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                          mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                          mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "category"]
    ordering_fields = ["display_order", "name", "price", "updated_at"]
    ordering = ["display_order", "name", "id"]

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get("category", "").strip()
        active = self.request.query_params.get("is_active")
        status = self.request.query_params.get("status", "").strip().lower()
        if category:
            queryset = queryset.filter(category__iexact=category)
        if status in {"active", "archived"}:
            queryset = queryset.filter(is_active=status == "active")
        if active is not None:
            queryset = queryset.filter(is_active=active.lower() in {"1", "true", "yes"})
        return queryset

    def perform_create(self, serializer):
        product = serializer.save()
        log_activity(
            self.request.user, "catalogue.product.create", object_type="catalogue_product",
            object_repr=product.name, object_id=product.pk,
            detail=f"Price {product.price / 100:.2f} PHP/{product.unit_label}."
                   + (" Cover image uploaded." if product.cover_image else ""),
        )

    def perform_update(self, serializer):
        old_price = serializer.instance.price
        old_active = serializer.instance.is_active
        old_cover = serializer.instance.cover_image.name if serializer.instance.cover_image else None
        product = serializer.save()
        new_cover = product.cover_image.name if product.cover_image else None
        cover_change = ""
        if old_cover != new_cover:
            cover_change = " Cover image removed." if not new_cover else " Cover image replaced."
        log_activity(
            self.request.user, "catalogue.product.update", object_type="catalogue_product",
            object_repr=product.name, object_id=product.pk,
            detail=f"Price {old_price / 100:.2f} -> {product.price / 100:.2f} PHP; "
                   f"active {old_active} -> {product.is_active}." + cover_change,
        )

    def perform_destroy(self, instance):
        if instance.is_active:
            instance.is_active = False
            instance.save(update_fields=["is_active", "updated_at"])
            log_activity(
                self.request.user, "catalogue.product.archive", object_type="catalogue_product",
                object_repr=instance.name, object_id=instance.pk,
            )

    def destroy(self, request, *args, **kwargs):
        self.perform_destroy(self.get_object())
        return Response(status=204)
