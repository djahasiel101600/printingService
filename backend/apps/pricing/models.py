from django.core.validators import MinValueValidator
from django.db import models


class PriceRule(models.Model):
    """Price per printed side (page face) for a parameter combination.

    Prices are stored in centavos (PHP) to avoid float rounding issues.
    Lookup order: exact match on (media_size, media_type, color_mode,
    print_quality), then progressively relaxed matches (drop quality, then
    type, then size) so a missing row never breaks quoting.
    """

    media_size = models.CharField(max_length=32)      # Epson ps_* code or "any"
    media_type = models.CharField(max_length=32)      # Epson pt_* code or "any"
    color_mode = models.CharField(max_length=16)      # color | mono | any
    print_quality = models.CharField(max_length=16)   # high | normal | draft | any
    price_per_page = models.IntegerField(validators=[MinValueValidator(1)], help_text="Centavos per printed side")
    effective_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-effective_date", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["media_size", "media_type", "color_mode", "print_quality"],
                name="unique_price_rule_combination",
            )
        ]

    def __str__(self) -> str:
        return f"{self.media_size}/{self.media_type}/{self.color_mode}/{self.print_quality} = {self.price_per_page / 100:.2f} PHP"

    @property
    def price_per_page_peso(self) -> float:
        return self.price_per_page / 100


class PricingSettings(models.Model):
    """Shop-wide pricing knobs (singleton row, always pk=1).

    Mirrors apps.payments.PaymentSettings: GET is public so quoting and
    checkout UIs can show the rules; writes are restricted to shop admins
    (see PricingSettingsView).

    These values were previously env vars (DUPLEX_DISCOUNT_FACTOR,
    MIN_PARTIAL_PERCENT) plus the hardcoded 500-centavo fallback in
    quotation.compute_quote. Migration 0002 seeds this row from the same env
    vars so quoting is byte-for-byte identical on deploy; after that the DB
    is the single source of truth — changing the env vars has no effect.
    """

    duplex_discount_factor = models.FloatField(
        default=0.90,
        help_text="Multiplier applied to the per-side price of double-sided jobs (0.0-1.0).",
    )
    min_partial_percent = models.PositiveSmallIntegerField(
        default=50,
        help_text="Smallest allowed down payment, as a percentage of the subtotal.",
    )
    fallback_price_per_side = models.PositiveIntegerField(
        default=500,
        help_text="Centavos per printed side when no price rule matches.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return (
            f"Pricing settings (duplex ×{self.duplex_discount_factor}, "
            f"min partial {self.min_partial_percent}%, "
            f"fallback ₱{self.fallback_price_per_side / 100:.2f})"
        )

    @classmethod
    def get_solo(cls) -> "PricingSettings":
        settings_obj, _ = cls.objects.get_or_create(pk=1)
        return settings_obj
