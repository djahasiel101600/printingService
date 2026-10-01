from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class ShopUserAdmin(UserAdmin):
    list_display = ["email", "first_name", "last_name", "phone", "role", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name", "phone"]
    ordering = ["email"]
    fieldsets = UserAdmin.fieldsets + (
        ("Print shop", {"fields": ("phone", "facebook_handle", "role")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Print shop", {"fields": ("email", "phone", "facebook_handle", "role")}),
    )
