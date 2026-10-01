from django.contrib import admin

from .models import Order, OrderFile, OrderStatusHistory, PrintSpecification


class OrderFileInline(admin.TabularInline):
    model = OrderFile
    extra = 0


class PrintSpecificationInline(admin.TabularInline):
    model = PrintSpecification
    extra = 0


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ["from_status", "to_status", "note", "actor", "created_at"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["tracking_id", "status", "client_display_name", "payment_type",
                    "subtotal", "amount_paid", "created_at"]
    list_filter = ["status", "payment_type"]
    search_fields = ["tracking_id", "guest_name", "guest_contact_value", "user__email"]
    inlines = [OrderFileInline, PrintSpecificationInline, OrderStatusHistoryInline]
    readonly_fields = ["tracking_id"]


@admin.register(OrderFile)
class OrderFileAdmin(admin.ModelAdmin):
    list_display = ["file_name", "order", "file_type", "page_count", "size"]
    search_fields = ["file_name", "order__tracking_id"]


@admin.register(PrintSpecification)
class PrintSpecificationAdmin(admin.ModelAdmin):
    list_display = ["order", "order_file", "media_size", "media_type", "color_mode",
                    "sides", "print_quality", "copies"]
    list_filter = ["color_mode", "sides", "print_quality"]
