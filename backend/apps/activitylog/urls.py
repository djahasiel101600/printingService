from django.urls import path

from .views import ActivityLogView

urlpatterns = [
    # Owner-only audit feed. Declared in its own app so every admin surface
    # (orders, pricing, staff) can import apps.activitylog.services freely.
    path("admin/activity-logs/", ActivityLogView.as_view(), name="admin-activity-logs"),
]
