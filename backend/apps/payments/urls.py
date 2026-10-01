from django.urls import path

from .views import CheckoutView, PayMongoTestConnectionView, SimulatePaymentView, WebhookView

urlpatterns = [
    path("payments/checkout/", CheckoutView.as_view(), name="payments-checkout"),
    path("payments/webhook/", WebhookView.as_view(), name="payments-webhook"),
    path("payments/webhook/simulate/", SimulatePaymentView.as_view(), name="payments-webhook-simulate"),
    path("admin/paymongo/test-connection/", PayMongoTestConnectionView.as_view(), name="admin-paymongo-test-connection"),
]
