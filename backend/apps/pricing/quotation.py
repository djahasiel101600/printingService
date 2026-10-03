"""Quotation engine.

Given print specifications and page counts, computes an itemised quote in
centavos. Pricing model:

* a PriceRule supplies the price per printed side for the
  (media_size, media_type, color_mode, print_quality) combination;
* total sides = pages * copies;
* double-sided printing earns the configured discount factor
  (PricingSettings.duplex_discount_factor, default 0.90) because it saves
  paper;
* rules are matched exactly first, then relaxed (quality -> type -> size)
  with "any" wildcards, so quoting never fails outright.
"""
from dataclasses import dataclass

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


def _rule_queryset(**match):
    kwargs = {field: value for field, value in match.items() if value != "any"}
    kwargs.update({field: "any" for field, value in match.items() if value == "any"})
    return PriceRule.objects.filter(is_active=True, **kwargs).order_by("-effective_date")


def find_rule(media_size: str, media_type: str, color_mode: str, print_quality: str) -> PriceRule | None:
    """Exact match first, then relaxed lookups (quality -> type -> size)."""
    matches = [
        {"media_size": media_size, "media_type": media_type,
         "color_mode": color_mode, "print_quality": print_quality},
        {"media_size": media_size, "media_type": media_type,
         "color_mode": color_mode, "print_quality": "any"},
        {"media_size": media_size, "media_type": "any",
         "color_mode": color_mode, "print_quality": "any"},
        {"media_size": "any", "media_type": "any",
         "color_mode": color_mode, "print_quality": "any"},
        {"media_size": "any", "media_type": "any",
         "color_mode": "any", "print_quality": "any"},
    ]
    for match in matches:
        rule = _rule_queryset(**match).first()
        if rule:
            return rule
    return None



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
