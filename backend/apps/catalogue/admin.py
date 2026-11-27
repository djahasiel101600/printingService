from django.contrib import admin
from django.utils.html import format_html

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "unit_label", "is_active", "is_featured", "display_order"]
    list_filter = ["is_active", "is_featured", "category"]
    search_fields = ["name", "description", "category"]
    readonly_fields = ["slug", "cover_preview", "created_at", "updated_at"]
    actions = None

    @admin.display(description="Cover preview")
    def cover_preview(self, obj):
        if not obj or not obj.cover_image:
            return "No cover photo"
        url = obj.cover_image.url
        if not url.startswith(("/", "http://", "https://")):
            url = f"/{url}"
        return format_html(
            '<img src="{}" alt="Cover preview" style="max-width:240px;max-height:160px;border-radius:0.5rem;" />',
            url,
        )

    def has_delete_permission(self, request, obj=None):
        return False
