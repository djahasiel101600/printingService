"""Epson Connect API v2 constants.

Every enum below is taken verbatim from the official OpenAPI specification
(openapi.spec, components.schemas) so our model choices can never drift from
what the printer cloud accepts.
"""

EPSON_PRINT_MODES = [
    ("document", "document"),
    ("photo", "photo"),
]

EPSON_PAPER_SIZES = [
    ("ps_a3", "A3"),
    ("ps_a4", "A4"),
    ("ps_a5", "A5"),
    ("ps_a6", "A6"),
    ("ps_b5", "B5"),
    ("ps_tabloid", "Tabloid"),
    ("ps_letter", "Letter"),
    ("ps_legal", "Legal"),
    ("ps_halfletter", "Half Letter"),
    ("ps_kg", "KG"),
    ("ps_l", "L"),
    ("ps_2l", "2L"),
    ("ps_10x12", "10x12"),
    ("ps_8x10", "8x10"),
    ("ps_hivision", "Hi-Vision"),
    ("ps_5x8", "5x8"),
    ("ps_postcard", "Postcard"),
]

EPSON_PAPER_TYPES = [
    ("pt_plainpaper", "Plain paper"),
    ("pt_photopaper", "Photo paper"),
    ("pt_hagaki", "Hagaki"),
    ("pt_hagakiphoto", "Hagaki photo"),
    ("pt_hagakiinkjet", "Hagaki inkjet"),
    ("pt_roll", "Roll"),
]

EPSON_PAPER_SOURCES = [
    ("auto", "Auto"),
    ("rear", "Rear"),
    ("front1", "Front 1"),
    ("front2", "Front 2"),
    ("front3", "Front 3"),
    ("front4", "Front 4"),
    ("roll", "Roll"),
]

EPSON_PAPER_QUALITIES = [
    ("high", "High"),
    ("normal", "Normal"),
    ("draft", "Draft"),
]

# Epson doubleSided: none | long | short (duplex long/short edge binding)
EPSON_DOUBLE_SIDED = [
    ("none", "Single-sided"),
    ("long", "Double-sided (flip long edge)"),
    ("short", "Double-sided (flip short edge)"),
]

EPSON_COLOR_MODES = [
    ("color", "Color"),
    ("mono", "Black & white"),
]

# Epson print job status enum (schema `status`)
EPSON_JOB_STATUSES = [
    "preparing", "reserved", "pending", "processing",
    "media_empty", "media_jam", "marker_supply_empty", "stopped_other",
    "canceled", "error_occurred", "completed", "expired",
]

# Map Epson job status -> local order status (PRD §8)
EPSON_STATUS_TO_ORDER_STATUS = {
    "preparing": "printing",
    "reserved": "approved_queued",
    "pending": "printing",
    "processing": "printing",
    "media_empty": "on_hold",
    "media_jam": "on_hold",
    "marker_supply_empty": "on_hold",
    "stopped_other": "on_hold",
    # The printer cancelled the job itself (cancelled in the Epson queue,
    # expired, or stopped locally). This is NOT an order cancellation — the
    # shop reprints it, so it maps to its own recoverable status.
    "canceled": "print_cancelled",
    "error_occurred": "on_hold",
    "completed": "printed_ready",
    "expired": "print_cancelled",
}

# Friendly client-facing descriptions for Epson job statuses
EPSON_STATUS_LABELS = {
    "preparing": "Preparing",
    "reserved": "Reserved",
    "pending": "Pending",
    "processing": "Processing",
    "media_empty": "Out of paper",
    "media_jam": "Paper jam",
    "marker_supply_empty": "Ink low/empty",
    "stopped_other": "Stopped",
    "canceled": "Cancelled",
    "error_occurred": "Printer error",
    "completed": "Completed",
    "expired": "Expired",
}
