from django.contrib import admin

from .models import PrintJob


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ["epson_job_id", "order", "status", "epson_status", "print_mode", "submitted_at"]
    list_filter = ["status", "print_mode"]
    search_fields = ["epson_job_id", "order__tracking_id"]
    readonly_fields = ["print_settings_snapshot"]
