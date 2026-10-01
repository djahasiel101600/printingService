from rest_framework import serializers

from .models import PriceRule


class PriceRuleSerializer(serializers.ModelSerializer):
    price_per_page_peso = serializers.FloatField(read_only=True)

    class Meta:
        model = PriceRule
        fields = ["id", "media_size", "media_type", "color_mode", "print_quality",
                  "price_per_page", "price_per_page_peso", "effective_date", "is_active"]

    def validate_price_per_page(self, value):
        if value < 1:
            raise serializers.ValidationError("price_per_page must be at least 1 centavo.")
        return value
