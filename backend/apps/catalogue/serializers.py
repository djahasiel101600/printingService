from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Product
from .services import unique_slug
from .validators import validate_default_spec


class ProductSerializer(serializers.ModelSerializer):
    price_peso = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "slug", "name", "description", "category", "price", "price_peso",
            "unit_label", "min_quantity", "max_quantity", "is_active", "is_featured",
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

    def create(self, validated_data):
        validated_data["slug"] = unique_slug(validated_data["name"])
        return super().create(validated_data)
