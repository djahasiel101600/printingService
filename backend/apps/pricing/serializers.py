"""Serializer for PriceRule CRUD."""
from rest_framework import serializers

from apps.printing.constants import (
    EPSON_COLOR_MODES, EPSON_PAPER_QUALITIES, EPSON_PAPER_SIZES, EPSON_PAPER_TYPES,
)

from .models import PriceRule

# The Epson codes the frontend derives from /printing/capabilities/. A rule
# keyed on anything else could never match a real quotation spec.
COLOR_MODE_CODES = {code for code, _ in EPSON_COLOR_MODES}
QUALITY_CODES = {code for code, _ in EPSON_PAPER_QUALITIES}
SIZE_CODES = {code for code, _ in EPSON_PAPER_SIZES}
TYPE_CODES = {code for code, _ in EPSON_PAPER_TYPES}


class PriceRuleSerializer(serializers.ModelSerializer):
    # Read-only peso view of price_per_page (an int of centavos) for the UI.
    price_per_page_peso = serializers.FloatField(read_only=True)

    class Meta:
        model = PriceRule
        fields = ["id", "media_size", "media_type", "color_mode", "print_quality",
                  "price_per_page", "price_per_page_peso", "effective_date", "is_active"]

    def validate_price_per_page(self, value):
        if value < 1:
            raise serializers.ValidationError("price_per_page must be at least 1 centavo.")
        return value

    def validate(self, attrs):
        """Reject values that would save fine but silently never match.

        Quotation lookups compare Epson codes exactly, so a rule with
        media_size="A4" could never match a "ps_a4" spec. Each field accepts
        its `any` wildcard (the documented catch-all behaviour) or a known
        code. Also guard the model's unique combination constraint so a
        duplicate comes back as a clean 400 instead of an IntegrityError 500.
        """
        instance = self.instance
        media_size = attrs.get("media_size", instance.media_size if instance else None)
        media_type = attrs.get("media_type", instance.media_type if instance else None)
        color_mode = attrs.get("color_mode", instance.color_mode if instance else None)
        print_quality = attrs.get("print_quality", instance.print_quality if instance else None)

        if media_size != "any" and media_size not in SIZE_CODES:
            raise serializers.ValidationError({
                "media_size": f"Unknown paper size {media_size!r} — use an Epson code (ps_a4, ps_letter, …) or 'any'."})
        if media_type != "any" and media_type not in TYPE_CODES:
            raise serializers.ValidationError({
                "media_type": f"Unknown paper type {media_type!r} — use an Epson code (pt_plainpaper, …) or 'any'."})
        if color_mode != "any" and color_mode not in COLOR_MODE_CODES:
            raise serializers.ValidationError({
                "color_mode": f"Must be one of: {', '.join(sorted(COLOR_MODE_CODES | {'any'}))}."})
        if print_quality != "any" and print_quality not in QUALITY_CODES:
            raise serializers.ValidationError({
                "print_quality": f"Must be one of: {', '.join(sorted(QUALITY_CODES | {'any'}))}."})

        conflicts = PriceRule.objects.filter(
            media_size=media_size, media_type=media_type,
            color_mode=color_mode, print_quality=print_quality,
        )
        if instance is not None:
            conflicts = conflicts.exclude(pk=instance.pk)
        if conflicts.exists():
            raise serializers.ValidationError(
                "A price rule for this paper size / type / color / quality combination already exists."
            )
        return attrs
