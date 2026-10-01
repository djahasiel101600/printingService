from django.contrib import admin

from .models import EpsonCredential, PrintJob


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ["epson_job_id", "order", "status", "epson_status", "print_mode", "submitted_at"]
    list_filter = ["status", "print_mode"]
    search_fields = ["epson_job_id", "order__tracking_id"]
    readonly_fields = ["print_settings_snapshot"]


@admin.register(EpsonCredential)
class EpsonCredentialAdmin(admin.ModelAdmin):
    """The rotating device refresh token lives here — treat it as a secret."""

    list_display = ["__str__", "updated_at"]
    readonly_fields = ["refresh_token", "pending_state", "updated_at"]
