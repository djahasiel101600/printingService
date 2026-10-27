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
    pages: int
    copies: int
    unit_price: int          # centavos per printed side
    sides: int               # total printed sides
    amount: int              # centavos


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



def compute_quote(specs: list[dict]) -> Quote:
    """specs: [{'media_size','media_type','color_mode','print_quality',
    'sides','copies','page_count','label'}...] — sides uses Epson values
    (none|long|short). Global knobs (duplex factor, fallback price) come from
    the admin-editable PricingSettings singleton (DB), not env vars."""
    knobs = PricingSettings.get_solo()
    lines: list[LineQuote] = []
    for spec in specs:
        page_count = max(1, int(spec.get("page_count") or 1))
        copies = min(99, max(1, int(spec.get("copies") or 1)))
        color_mode = spec.get("color_mode") or "mono"
        media_size = spec.get("media_size") or "any"
        media_type = spec.get("media_type") or "any"
        print_quality = spec.get("print_quality") or "any"
        double_sided = spec.get("sides") in ("long", "short")

        rule = find_rule(media_size, media_type, color_mode, print_quality)
        unit_price = rule.price_per_page if rule else knobs.fallback_price_per_side
        if double_sided:
            unit_price = round(unit_price * knobs.duplex_discount_factor)
        sides = page_count * copies
        amount = sides * unit_price
        lines.append(LineQuote(
            label=spec.get("label") or "Print job",
            pages=page_count, copies=copies,
            unit_price=unit_price, sides=sides, amount=amount,
        ))
    return Quote(lines=lines, subtotal=sum(line.amount for line in lines))
