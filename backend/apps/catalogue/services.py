from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils.text import slugify

from apps.pricing.quotation import LineQuote, Quote

from .models import Product
from .validators import validate_quantity


def active_product_or_404(product_id) -> Product:
    try:
        product_id = int(product_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("A valid product is required.") from exc
    return get_object_or_404(Product, pk=product_id, is_active=True)


def product_quote(
    *,
    name: str,
    unit_price: int,
    unit_label: str,
    quantity: int,
    product_id: int | None = None,
) -> Quote:
    quantity = int(quantity)
    amount = unit_price * quantity
    line = LineQuote(
        label=name,
        pages=None,
        copies=None,
        unit_price=unit_price,
        sides=None,
        amount=amount,
        color_mode=None,
        kind="catalogue",
        quantity=quantity,
        unit_label=unit_label,
        product_id=product_id,
    )
    return Quote(lines=[line], subtotal=amount)


def quote_active_product(product_id, quantity) -> Quote:
    product = active_product_or_404(product_id)
    try:
        quantity = validate_quantity(product, quantity)
    except ValidationError as exc:
        raise ValidationError({"product_quantity": exc.messages}) from exc
    return product_quote(
        name=product.name,
        unit_price=product.price,
        unit_label=product.unit_label,
        quantity=quantity,
        product_id=product.pk,
    )


def effective_product_spec(product: Product, submitted: dict) -> dict:
    spec = {**product.default_spec, **submitted}
    spec["copies"] = 1
    return spec


def combined_instructions(product: Product, submitted: str) -> str:
    submitted = (submitted or "").strip()
    if product.instructions and product.instructions not in submitted:
        return f"{submitted}\n\n{product.instructions}".strip()
    return submitted


def unique_slug(name: str) -> str:
    base = slugify(name)[:120] or "product"
    candidate = base
    suffix = 2
    while Product.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
