from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AdminCustomersView,
    AdminStaffDetailView,
    AdminStaffView,
    LoginView,
    MeView,
    RegisterView,
    SetupView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/setup/", SetupView.as_view(), name="auth-setup"),
    path("auth/token/", LoginView.as_view(), name="auth-token"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("admin/customers/", AdminCustomersView.as_view(), name="admin-customers"),
    # User management: admins + approvers (owner-only, see AdminStaffView).
    path("admin/users/", AdminStaffView.as_view(), name="admin-users"),
    path("admin/users/<int:pk>/", AdminStaffDetailView.as_view(), name="admin-user-detail"),
]
