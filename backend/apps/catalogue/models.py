from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from .validators import validate_cover_image, validate_default_spec


def catalogue_cover_upload_to(instance, filename) -> str:
    """Store cover photos under a stable product path with collision-safe names."""
    slug = instance.slug or f"product-{instance.pk or 'new'}"
    extension = Path(str(filename)).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".jpg"
    return f"catalogue/products/{slug}/{uuid4().hex}{extension}"


class Product(models.Model):
    """An admin-managed, fixed-price printing service."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, editable=False)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(
        upload_to=catalogue_cover_upload_to,
        validators=[validate_cover_image],
        blank=True,
        null=True,
        max_length=255,
        help_text="Optional JPEG, PNG, or WebP cover photo (maximum 5 MB).",
    )
    category = models.CharField(max_length=80)
    price = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Fixed unit price in centavos.",
    )
    unit_label = models.CharField(max_length=60, default="piece")
    min_quantity = models.PositiveSmallIntegerField(default=1)
    max_quantity = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    default_spec = models.JSONField(default=dict, blank=True, validators=[validate_default_spec])
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name", "id"]
        constraints = [
            models.CheckConstraint(check=models.Q(price__gte=1), name="catalogue_price_positive"),
            models.CheckConstraint(check=models.Q(min_quantity__gte=1), name="catalogue_min_quantity_positive"),
            models.CheckConstraint(
                check=models.Q(max_quantity__isnull=True) | models.Q(max_quantity__gte=models.F("min_quantity")),
                name="catalogue_quantity_bounds_ordered",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active", "display_order", "name"], name="catalogue_active_order_idx"),
            models.Index(fields=["is_active", "category"], name="catalogue_active_category_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} — {self.price / 100:.2f} PHP/{self.unit_label}"

    def clean(self):
        super().clean()
        if self.max_quantity is not None and self.max_quantity < self.min_quantity:
            raise ValidationError({"max_quantity": "Must be greater than or equal to the minimum quantity."})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:120] or "product"
            candidate = base
            suffix = 2
            while Product.objects.filter(slug=candidate).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def price_peso(self) -> float:
        return self.price / 100
