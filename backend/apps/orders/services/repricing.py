"""Keep analysis, itemised quote lines and the order subtotal in sync."""
import logging

from apps.catalogue.services import product_quote
from apps.pricing.quotation import compute_quote, line_quote_data

from .color_analysis import ensure_order_file_analysis

log = logging.getLogger(__name__)


def reprice_order(order, *, force_analysis: bool = False):
    """Analyze current sources, recalculate the quote, and persist both.

    Every operation that can change pages, selected page modes, copies or print
    options calls this single service so an old color split can never leave a
    stale price behind.
    """
    if order.catalogue_product_id:
        required = (
            order.product_name_snapshot, order.product_unit_price_snapshot,
            order.product_unit_label_snapshot, order.product_quantity,
            order.product_min_quantity_snapshot,
        )
        if any(value is None for value in required) or not order.product_name_snapshot:
            raise ValueError("Catalogue order is missing its pricing snapshot.")
        if order.product_quantity < order.product_min_quantity_snapshot:
            raise ValueError("Catalogue order quantity is below its snapshotted minimum.")
        if (order.product_max_quantity_snapshot is not None
                and order.product_quantity > order.product_max_quantity_snapshot):
            raise ValueError("Catalogue order quantity exceeds its snapshotted maximum.")
        quote = product_quote(
            name=order.product_name_snapshot,
            unit_price=order.product_unit_price_snapshot,
            unit_label=order.product_unit_label_snapshot,
            quantity=order.product_quantity,
            product_id=order.catalogue_product_id,
        )
        order.subtotal = quote.subtotal
        order.quote_breakdown = [line_quote_data(line) for line in quote.lines]
        order.save(update_fields=["subtotal", "quote_breakdown", "updated_at"])
        return quote

    for order_file in order.files.all():
        try:
            ensure_order_file_analysis(order_file, force=force_analysis)
        except Exception as exc:  # noqa: BLE001 - quoting must remain available
            log.warning(
                "Could not analyse '%s' of order %s for repricing: %s",
                order_file.file_name, order.tracking_id, exc, exc_info=True,
            )
            # effective_page_modes() conservatively treats missing analysis as
            # color in Auto mode, so the customer is never undercharged.

    quote = compute_quote(order.quote_specs())
    order.subtotal = quote.subtotal
    order.quote_breakdown = [line_quote_data(line) for line in quote.lines]
    order.save(update_fields=["subtotal", "quote_breakdown", "updated_at"])
    return quote
