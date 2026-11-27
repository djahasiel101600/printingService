"""Quotation engine.

Given print specifications and page counts, computes an itemised quote in
centavos. Pricing model:

* a PriceRule supplies the price per printed side for the
  (media_size, media_type, color_mode, print_quality) combination;
* total sides = pages * copies;
* double-sided printing earns the configured discount factor
  (PricingSettings.duplex_discount_factor, default 0.90) because it saves
  paper;
* rules use ``"any"`` as a wildcard on any field; the most specific match
  (most exact fields) wins, falling back to the most recently effective
  rule, so quoting never fails outright.
"""
from dataclasses import dataclass

from django.db import models

from .models import PriceRule, PricingSettings


@dataclass
class LineQuote:
    label: str
    pages: int | None
    copies: int | None
    unit_price: int          # centavos per printed side or catalogue unit
    sides: int | None       # total printed sides; catalogue quantity is separate
    amount: int              # centavos
    color_mode: str | None = "mono"  # concrete mode; ``auto`` is expanded below
    kind: str = "custom"
    quantity: int | None = None
    unit_label: str | None = None
    product_id: int | None = None


@dataclass
class Quote:
    lines: list[LineQuote]
    subtotal: int            # centavos

    @property
    def subtotal_peso(self) -> float:
        return self.subtotal / 100


def find_rule(media_size: str, media_type: str, color_mode: str, print_quality: str) -> PriceRule | None:
    """Find the most specific matching price rule.

    Each field matches either exactly or via the ``"any"`` wildcard, so a rule
    like ``media_size="any"`` with ``print_quality="normal"`` is found when
    looking up a mono/normal job on any paper size. More specific matches
    (more exact fields) take precedence over wildcard matches; among equally
    specific matches the most recently effective rule wins.
    """
    rules = PriceRule.objects.filter(
        models.Q(media_size=media_size) | models.Q(media_size="any"),
        models.Q(media_type=media_type) | models.Q(media_type="any"),
        models.Q(color_mode=color_mode) | models.Q(color_mode="any"),
        models.Q(print_quality=print_quality) | models.Q(print_quality="any"),
        is_active=True,
    )

    rules = rules.annotate(
        specificity=(
            models.Case(
                models.When(media_size=media_size, then=1),
                default=0,
                output_field=models.IntegerField(),
            )
            + models.Case(
                models.When(media_type=media_type, then=1),
                default=0,
                output_field=models.IntegerField(),
            )
            + models.Case(
                models.When(color_mode=color_mode, then=1),
                default=0,
                output_field=models.IntegerField(),
            )
            + models.Case(
                models.When(print_quality=print_quality, then=1),
                default=0,
                output_field=models.IntegerField(),
            )
        )
    ).order_by("-specificity", "-effective_date", "id")

    return rules.first()



def _page_modes(spec: dict, page_count: int) -> list[str]:
    """Normalise per-page modes; absent or invalid entries are safely color."""
    raw = spec.get("page_modes")
    if raw is None:
        analysis = spec.get("color_analysis") or {}
        raw = [entry.get("mode") for entry in analysis.get("pages") or []]
    if isinstance(raw, dict):
        raw = [raw.get(str(number), raw.get(number)) for number in range(1, page_count + 1)]
    if not isinstance(raw, (list, tuple)):
        raw = []
    return [
        mode if mode in ("color", "mono") else "color"
        for mode in list(raw[:page_count]) + ["color"] * max(0, page_count - len(raw))
    ]


def compute_quote(specs: list[dict]) -> Quote:
    """Compute concrete per-side lines, expanding ``auto`` into color/mono.

    ``page_modes`` is either a list in page order or a mapping of page numbers
    to modes. Missing analysis is deliberately charged as color. Global knobs
    (duplex factor, fallback price) come from PricingSettings.
    """
    knobs = PricingSettings.get_solo()
    lines: list[LineQuote] = []
    for spec in specs:
        page_count = max(1, int(spec.get("page_count") or 1))
        copies = min(99, max(1, int(spec.get("copies") or 1)))
        requested = spec.get("color_mode") or "mono"
        media_size = spec.get("media_size") or "any"
        media_type = spec.get("media_type") or "any"
        print_quality = spec.get("print_quality") or "any"
        double_sided = spec.get("sides") in ("long", "short")
        label = spec.get("label") or "Print job"

        if requested == "auto":
            modes = _page_modes(spec, page_count)
            groups = []
            for mode in ("mono", "color"):
                count = modes.count(mode)
                if count:
                    groups.append((mode, count))
        else:
            mode = requested if requested in ("color", "mono") else "color"
            groups = [(mode, page_count)]

        for mode, count in groups:
            rule = find_rule(media_size, media_type, mode, print_quality)
            unit_price = rule.price_per_page if rule else knobs.fallback_price_per_side
            if double_sided:
                unit_price = round(unit_price * knobs.duplex_discount_factor)
            sides = count * copies
            line_label = label
            if requested == "auto" and len(groups) > 1:
                line_label += " — Color" if mode == "color" else " — Black & white"
            lines.append(LineQuote(
                label=line_label, pages=count, copies=copies,
                unit_price=unit_price, sides=sides, amount=sides * unit_price,
                color_mode=mode,
            ))
    return Quote(lines=lines, subtotal=sum(line.amount for line in lines))


def line_quote_data(line: LineQuote) -> dict:
    return {
        "label": line.label, "pages": line.pages, "copies": line.copies,
        "color_mode": line.color_mode,
        "unit_price": line.unit_price, "unit_price_peso": line.unit_price / 100,
        "sides": line.sides, "amount": line.amount, "amount_peso": line.amount / 100,
        "kind": line.kind, "quantity": line.quantity,
        "unit_label": line.unit_label, "product_id": line.product_id,
    }
