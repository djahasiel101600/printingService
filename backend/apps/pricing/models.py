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
