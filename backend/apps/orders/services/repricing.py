"""Keep analysis, itemised quote lines and the order subtotal in sync."""
import logging

from apps.pricing.quotation import compute_quote, line_quote_data

from .color_analysis import ensure_order_file_analysis

log = logging.getLogger(__name__)


def reprice_order(order, *, force_analysis: bool = False):
    """Analyze current sources, recalculate the quote, and persist both.

    Every operation that can change pages, selected page modes, copies or print
    options calls this single service so an old color split can never leave a
    stale price behind.
    """
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
