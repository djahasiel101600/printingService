from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "unit_label", "is_active", "is_featured", "display_order"]
    list_filter = ["is_active", "is_featured", "category"]
    search_fields = ["name", "description", "category"]
    readonly_fields = ["slug", "created_at", "updated_at"]
    actions = None

    def has_delete_permission(self, request, obj=None):
        return False
