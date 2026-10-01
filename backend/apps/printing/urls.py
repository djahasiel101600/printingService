from django.urls import path

from .views import (
    CapabilitiesView,
    DeviceInfoView,
    EpsonAuthUrlView,
    EpsonExchangeCodeView,
    EpsonStatusView,
    EpsonTestConnectionView,
    PrintJobViewSet,
)

urlpatterns = [
    path("printing/capabilities/", CapabilitiesView.as_view(), name="printing-capabilities"),
    path("admin/printer/", DeviceInfoView.as_view(), name="admin-printer-info"),
    path("admin/epson/status/", EpsonStatusView.as_view(), name="admin-epson-status"),
    path("admin/epson/auth-url/", EpsonAuthUrlView.as_view(), name="admin-epson-auth-url"),
    path("admin/epson/exchange-code/", EpsonExchangeCodeView.as_view(), name="admin-epson-exchange-code"),
    path("admin/epson/test-connection/", EpsonTestConnectionView.as_view(), name="admin-epson-test-connection"),
    path("admin/print-jobs/", PrintJobViewSet.as_view(), name="admin-print-jobs"),
]
