import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Product
from .services import unique_slug
from .validators import validate_cover_image, validate_default_spec


logger = logging.getLogger(__name__)


class ProductSerializer(serializers.ModelSerializer):
    price_peso = serializers.FloatField(read_only=True)
    cover_image = serializers.ImageField(required=False, allow_null=True, write_only=True)
    cover_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "slug", "name", "description", "cover_image", "cover_image_url",
            "category", "price", "price_peso", "unit_label", "min_quantity", "max_quantity",
            "is_active", "is_featured",
            "display_order", "default_spec", "instructions", "created_at", "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def validate_category(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Category is required.")
        return value

    def validate_unit_label(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Unit label is required.")
        return value

    def validate_cover_image(self, value):
        try:
            return validate_cover_image(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_default_spec(self, value):
        try:
            return validate_default_spec(value)
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict) from exc
            raise serializers.ValidationError(exc.messages) from exc

    def validate(self, attrs):
        instance = self.instance
        minimum = attrs.get("min_quantity", instance.min_quantity if instance else 1)
        maximum = attrs.get("max_quantity", instance.max_quantity if instance else None)
        if minimum < 1:
            raise serializers.ValidationError({"min_quantity": "Must be at least 1."})
        if maximum is not None and maximum < minimum:
            raise serializers.ValidationError({"max_quantity": "Must be greater than or equal to the minimum quantity."})
        return attrs

    def get_cover_image_url(self, product) -> str | None:
        if not product.cover_image:
            return None
        url = product.cover_image.url
        if not url.startswith(("/", "http://", "https://")):
            url = f"/{url}"
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    @staticmethod
    def _delete_cover_image(storage, name):
        try:
            storage.delete(name)
        except Exception:
            logger.exception("Could not remove replaced catalogue cover image %s", name)

    def update(self, instance, validated_data):
        old_cover = instance.cover_image
        old_name = old_cover.name if old_cover else None
        storage = old_cover.storage if old_cover else None
        product = super().update(instance, validated_data)
        new_name = product.cover_image.name if product.cover_image else None
        if old_name and old_name != new_name:
            transaction.on_commit(lambda: self._delete_cover_image(storage, old_name))
        return product

    def create(self, validated_data):
        validated_data["slug"] = unique_slug(validated_data["name"])
        return super().create(validated_data)
