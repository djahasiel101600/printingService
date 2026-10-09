from django.urls import path

from .views import (
    CheckoutView,
    PayMongoTestConnectionView,
    PaymentSettingsView,
    SalesDashboardView,
    SimulatePaymentView,
    WebhookView,
)

urlpatterns = [
    path("payments/checkout/", CheckoutView.as_view(), name="payments-checkout"),
    path("payments/settings/", PaymentSettingsView.as_view(), name="payments-settings"),
    path("payments/webhook/", WebhookView.as_view(), name="payments-webhook"),
    path("payments/webhook/simulate/", SimulatePaymentView.as_view(), name="payments-webhook-simulate"),
    path("admin/paymongo/test-connection/", PayMongoTestConnectionView.as_view(), name="admin-paymongo-test-connection"),
    # Sales dashboard: owner-only, computed from the append-only SalesEntry ledger.
    path("admin/sales/dashboard/", SalesDashboardView.as_view(), name="admin-sales-dashboard"),
]
