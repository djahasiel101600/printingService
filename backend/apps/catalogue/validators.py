from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from apps.printing.constants import (
    EPSON_COLOR_MODES,
    EPSON_DOUBLE_SIDED,
    EPSON_PAPER_QUALITIES,
    EPSON_PAPER_SIZES,
    EPSON_PAPER_SOURCES,
    EPSON_PAPER_TYPES,
)

ALLOWED_SPEC_KEYS = {
    "media_size", "media_type", "color_mode", "sides", "print_quality",
    "copies", "borderless", "orientation", "source", "reverse_order", "collate",
}
CHOICES = {
    "media_size": {value for value, _ in EPSON_PAPER_SIZES},
    "media_type": {value for value, _ in EPSON_PAPER_TYPES},
    "color_mode": {value for value, _ in EPSON_COLOR_MODES} | {"auto"},
    "sides": {value for value, _ in EPSON_DOUBLE_SIDED},
    "print_quality": {value for value, _ in EPSON_PAPER_QUALITIES},
    "orientation": {"portrait", "landscape"},
    "source": {value for value, _ in EPSON_PAPER_SOURCES},
}
BOOLEAN_SPEC_KEYS = {"borderless", "reverse_order", "collate"}

COVER_IMAGE_MAX_BYTES = 5 * 1024 * 1024
COVER_IMAGE_MAX_PIXELS = 20_000_000
COVER_IMAGE_EXTENSIONS = {
    "JPEG": {".jpg", ".jpeg"},
    "PNG": {".png"},
    "WEBP": {".webp"},
}


def validate_cover_image(value):
    """Accept only reasonably sized, genuinely decoded raster cover photos."""
    if not value:
        return value
    if getattr(value, "size", None) and value.size > COVER_IMAGE_MAX_BYTES:
        raise ValidationError("Cover photo must be 5 MB or smaller.")

    try:
        value.seek(0)
        with Image.open(value) as image:
            image_format = image.format
            if image_format not in COVER_IMAGE_EXTENSIONS:
                raise ValidationError("Cover photo must be a JPEG, PNG, or WebP image.")
            if image.width * image.height > COVER_IMAGE_MAX_PIXELS:
                raise ValidationError("Cover photo dimensions are too large.")
            image.verify()
    except ValidationError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError) as exc:
        raise ValidationError("Upload a valid JPEG, PNG, or WebP image.") from exc
    finally:
        try:
            value.seek(0)
        except (AttributeError, OSError):
            pass

    extension = Path(str(getattr(value, "name", ""))).suffix.lower()
    if extension not in COVER_IMAGE_EXTENSIONS[image_format]:
        raise ValidationError("The cover photo file extension must match its image format.")
    return value


def validate_default_spec(value):
    if not isinstance(value, dict):
        raise ValidationError("default_spec must be an object.")

    unknown = sorted(set(value) - ALLOWED_SPEC_KEYS)
    if unknown:
        raise ValidationError(f"Unknown default_spec fields: {', '.join(unknown)}.")

    for field, allowed in CHOICES.items():
        if field in value and value[field] not in allowed:
            raise ValidationError({field: f"Must be one of: {', '.join(sorted(allowed))}."})

    for field in BOOLEAN_SPEC_KEYS:
        if field in value and not isinstance(value[field], bool):
            raise ValidationError({field: "Must be true or false."})

    if "copies" in value:
        copies = value["copies"]
        if isinstance(copies, bool) or not isinstance(copies, int) or copies != 1:
            raise ValidationError({"copies": "Catalogue products always use one Epson copy; quantity is managed separately."})

    return value


def validate_quantity(product, value) -> int:
    if isinstance(value, bool):
        raise ValidationError("Quantity must be a whole number.")
    try:
        quantity = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Quantity must be a whole number.") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValidationError("Quantity must be a whole number.")
    if quantity < product.min_quantity:
        raise ValidationError(f"Quantity must be at least {product.min_quantity}.")
    if product.max_quantity is not None and quantity > product.max_quantity:
        raise ValidationError(f"Quantity must be at most {product.max_quantity}.")
    return quantity
