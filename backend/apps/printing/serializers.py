from rest_framework import serializers

from .models import PrintJob


class PrintJobSerializer(serializers.ModelSerializer):
    file_name = serializers.CharField(source="order_file.file_name", read_only=True, default=None)

    class Meta:
        model = PrintJob
        fields = ["id", "order", "order_file", "file_name", "epson_job_id", "printer_name",
                  "print_mode", "print_settings_snapshot", "status", "epson_status",
                  "pages_printed", "error_message", "submitted_at", "completed_at", "created_at"]
