from django.conf import settings
from rest_framework import serializers

from apps.printing.constants import (
    EPSON_COLOR_MODES, EPSON_DOUBLE_SIDED, EPSON_PAPER_QUALITIES,
    EPSON_PAPER_SIZES, EPSON_PAPER_SOURCES, EPSON_PAPER_TYPES,
)
from apps.printing.models import PrintJob
from apps.payments.models import Payment

from .models import Order, OrderFile, OrderStatusHistory, PrintSpecification


class PrintSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrintSpecification
        fields = ["id", "order_file", "media_size", "media_type", "color_mode", "sides",
                  "print_quality", "copies", "borderless", "source", "reverse_order",
                  "collate", "free_text_instructions"]

    def validate_copies(self, value):
        if not 1 <= value <= 99:
            raise serializers.ValidationError("Epson supports 1-99 copies.")
        return value

    def validate(self, attrs):
        valid_sizes = {code for code, _ in EPSON_PAPER_SIZES}
        valid_types = {code for code, _ in EPSON_PAPER_TYPES}
        valid_colors = {code for code, _ in EPSON_COLOR_MODES}
        valid_sides = {code for code, _ in EPSON_DOUBLE_SIDED}
        valid_quality = {code for code, _ in EPSON_PAPER_QUALITIES}
        valid_sources = {code for code, _ in EPSON_PAPER_SOURCES}
        for field, allowed in (
            ("media_size", valid_sizes), ("media_type", valid_types),
            ("color_mode", valid_colors), ("sides", valid_sides),
            ("print_quality", valid_quality), ("source", valid_sources),
        ):
            if attrs.get(field) and attrs[field] not in allowed:
                raise serializers.ValidationError({field: f"Must be one of: {', '.join(sorted(allowed))}"})
        return attrs


class OrderFileSerializer(serializers.ModelSerializer):
    specification = PrintSpecificationSerializer(read_only=True)
    has_edits = serializers.SerializerMethodField()
    has_final_file = serializers.SerializerMethodField()
    # Page selection: what the shop decided to actually put in the printer.
    # These are model *properties*, so they are declared explicitly — DRF will
    # not infer a field type for them on its own.
    selected_pages = serializers.ListField(child=serializers.IntegerField(), read_only=True)
    selected_page_count = serializers.IntegerField(read_only=True)
    page_selection_label = serializers.CharField(read_only=True)
    page_selection_active = serializers.BooleanField(read_only=True)
    print_ready = serializers.BooleanField(read_only=True)

    class Meta:
        model = OrderFile
        fields = ["id", "file_name", "file_type", "content_type", "size", "page_count",
                  "edit_actions", "has_edits", "file", "edited_file", "final_file",
                  "has_final_file", "replaced_by_admin", "specification",
                  "page_selection", "selected_pages", "selected_page_count",
                  "page_selection_label", "page_selection_active", "print_ready",
                  "uploaded_at"]
        read_only_fields = fields

    def get_has_edits(self, obj) -> bool:
        return bool(obj.edited_file)

    def get_has_final_file(self, obj) -> bool:
        return bool(obj.final_file)


class StatusHistorySerializer(serializers.ModelSerializer):
    to_status_display = serializers.SerializerMethodField()

    class Meta:
        model = OrderStatusHistory
        fields = ["id", "from_status", "to_status", "to_status_display", "note", "created_at"]

    def get_to_status_display(self, obj) -> str:
        try:
            return Order.Status(obj.to_status).label
        except ValueError:
            return obj.to_status


class OrderPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "amount", "method", "status", "paid_at", "refund_status", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    files = OrderFileSerializer(many=True, read_only=True)
    history = StatusHistorySerializer(many=True, read_only=True)
    payments = OrderPaymentSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    client_name = serializers.CharField(source="client_display_name", read_only=True)
    # NOTE: must be a SerializerMethodField — a plain read-only FloatField would
    # look up `Order.subtotal_peso`, which does not exist, and DRF would then
    # silently omit the key from the response (breaking the frontend).
    subtotal_peso = serializers.SerializerMethodField()
    min_partial_peso = serializers.SerializerMethodField()
    amount_paid_peso = serializers.SerializerMethodField()
    balance_due_peso = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ["id", "tracking_id", "status", "status_display", "payment_type",
                  "payment_method", "client_name", "guest_name", "guest_contact_method",
                  "guest_contact_value", "subtotal", "subtotal_peso", "min_partial_peso",
                  "amount_paid", "amount_paid_peso",
                  "balance_due", "balance_due_peso", "admin_notes", "revision_note",
                  "reprint_count",
                  "files", "history", "payments", "created_at", "approved_at", "completed_at"]
        read_only_fields = fields

    def get_subtotal_peso(self, obj) -> float:
        return obj.subtotal / 100

    def get_min_partial_peso(self, obj) -> float:
        """Smallest allowed down payment (matches payments.services.create_checkout)."""
        return (obj.subtotal * settings.MIN_PARTIAL_PERCENT // 100) / 100

    def get_amount_paid_peso(self, obj) -> float:
        return obj.amount_paid / 100

    def get_balance_due_peso(self, obj) -> float:
        return obj.balance_due / 100


class AdminOrderSerializer(OrderSerializer):
    print_jobs = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ["print_jobs"]

    def get_print_jobs(self, obj):
        return PrintJobSerializerLite(obj.print_jobs.all(), many=True).data


class PrintJobSerializerLite(serializers.ModelSerializer):
    file_name = serializers.CharField(source="order_file.file_name", read_only=True, default=None)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_printer_cancelled = serializers.BooleanField(read_only=True)
    pages_label = serializers.CharField(read_only=True)
    pages_snapshot = serializers.ListField(child=serializers.IntegerField(), read_only=True)

    class Meta:
        model = PrintJob
        fields = ["id", "epson_job_id", "file_name", "order_file", "printer_name",
                  "print_mode", "status", "status_display", "epson_status",
                  "pages_printed", "pages_snapshot", "pages_label", "is_reprint",
                  "is_printer_cancelled", "error_message",
                  "submitted_at", "completed_at", "created_at"]


class GuestContactSerializer(serializers.Serializer):
    """Required when an unauthenticated client submits an order (PRD §4.1)."""

    guest_name = serializers.CharField(max_length=128)
    guest_contact_method = serializers.ChoiceField(choices=Order.ContactMethod.choices)
    guest_contact_value = serializers.CharField(max_length=254)
