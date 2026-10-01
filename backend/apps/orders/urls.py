from django.urls import path

from .views import (
    AdminOrderActionView,
    AdminOrderDetailView,
    AdminOrderListView,
    AdminOrderSpecView,
    AdminResubmitView,
    OrderCreateView,
    OrderDetailView,
    OrderFileEditView,
    OrderFilePreviewView,
    OrderListView,
    QuoteView,
    TrackOrderView,
)

urlpatterns = [
    path("orders/", OrderCreateView.as_view(), name="order-create"),
    path("orders/quote/", QuoteView.as_view(), name="order-quote"),
    path("orders/mine/", OrderListView.as_view(), name="order-list"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("orders/<int:order_pk>/files/<int:file_pk>/edit/", OrderFileEditView.as_view(), name="order-file-edit"),
    path("orders/<int:order_pk>/files/<int:file_pk>/preview/", OrderFilePreviewView.as_view(), name="order-file-preview"),
    path("track/<str:tracking_id>/", TrackOrderView.as_view(), name="order-track"),
    # admin
    path("admin/orders/", AdminOrderListView.as_view(), name="admin-order-list"),
    path("admin/orders/<int:pk>/", AdminOrderDetailView.as_view(), name="admin-order-detail"),
    path("admin/orders/<int:pk>/actions/<str:action>/", AdminOrderActionView.as_view(), name="admin-order-action"),
    path("admin/orders/<int:order_pk>/specs/<int:spec_pk>/", AdminOrderSpecView.as_view(), name="admin-order-spec"),
    path("admin/orders/<int:pk>/resubmit/", AdminResubmitView.as_view(), name="admin-order-resubmit"),
]
