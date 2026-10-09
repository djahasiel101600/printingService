from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor_email", "action", "object_type", "object_repr"]
    list_filter = ["object_type", "action"]
    search_fields = ["object_repr", "actor_email", "detail"]
