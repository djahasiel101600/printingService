import json

from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pricing.quotation import compute_quote
from apps.pricing.views import IsShopAdmin
from apps.printing.services import submit_order_to_printer, sync_print_jobs

from .models import Order, OrderFile, PrintSpecification
from .serializers import AdminOrderSerializer, GuestContactSerializer, OrderSerializer, PrintSpecificationSerializer
from .services.file_edits import FileEditError, apply_edit, count_pages

EDITABLE_STATUSES = (
    Order.Status.DRAFT, Order.Status.AWAITING_PAYMENT, Order.Status.REVISION_REQUESTED,
)


def _quote_lines(quote) -> list[dict]:
    return [
        {
            "label": line.label, "pages": line.pages, "copies": line.copies,
            "unit_price": line.unit_price, "unit_price_peso": line.unit_price / 100,
            "sides": line.sides, "amount": line.amount, "amount_peso": line.amount / 100,
        }
        for line in quote.lines
    ]


def _quote_response(quote) -> dict:
    return {
        "lines": _quote_lines(quote),
        "subtotal": quote.subtotal,
        "subtotal_peso": quote.subtotal_peso,
        "min_partial_peso": quote.subtotal * settings.MIN_PARTIAL_PERCENT / 100,
    }


def _parse_spec(data, key: str = "spec") -> dict:
    raw = data.get(key)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid {key} JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{key} must be an object")
    return parsed


class OrderCreateView(APIView):
    """Create an order: upload files + print spec (+ guest contact snapshot)."""

    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        files = request.FILES.getlist("files")
        if not files:
            return Response({"detail": "At least one file is required."}, status=400)

        user = request.user if request.user.is_authenticated else None
        guest = GuestContactSerializer(data=request.data)
        if user is None:
            guest.is_valid(raise_exception=True)

        try:
            spec_data = _parse_spec(request.data)
            per_file = json.loads(request.data.get("per_file_specs", "[]"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        spec_serializer = PrintSpecificationSerializer(data=spec_data)
        spec_serializer.is_valid(raise_exception=True)
        spec_defaults = spec_serializer.validated_data

        order = Order.objects.create(
            user=user,
            status=Order.Status.DRAFT,
            **({} if user else {
                "guest_name": guest.validated_data["guest_name"],
                "guest_contact_method": guest.validated_data["guest_contact_method"],
                "guest_contact_value": guest.validated_data["guest_contact_value"],
            }),
        )

        errors = []
        for index, uploaded in enumerate(files):
            content_type = uploaded.content_type or ""
            is_pdf = content_type == "application/pdf" or uploaded.name.lower().endswith(".pdf")
            file_type = OrderFile.FileType.PDF if is_pdf else OrderFile.FileType.IMAGE
            if uploaded.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
                errors.append(f"{uploaded.name} exceeds the {settings.MAX_UPLOAD_MB}MB limit.")
                continue
            order_file = OrderFile(
                order=order, file=uploaded, file_name=uploaded.name,
                file_type=file_type, content_type=content_type, size=uploaded.size,
            )
            order_file.file.save(uploaded.name, uploaded, save=False)
            order_file.file.open("rb")
            content = order_file.file.read()
            order_file.file.close()
            try:
                order_file.page_count = count_pages(file_type, content)
            except FileEditError as exc:
                errors.append(f"{uploaded.name}: {exc}")
                continue
            order_file.save()

            file_spec = dict(spec_defaults)
            if index < len(per_file) and isinstance(per_file[index], dict):
                file_spec_serializer = PrintSpecificationSerializer(data=per_file[index])
                if file_spec_serializer.is_valid():
                    file_spec = {**file_spec, **file_spec_serializer.validated_data}
            PrintSpecification.objects.create(
                order=order, order_file=order_file,
                free_text_instructions=file_spec.get("free_text_instructions", ""),
                **{k: v for k, v in file_spec.items() if k != "free_text_instructions"},
            )

        if errors or not order.files.exists():
            order.delete()
            return Response({"detail": "; ".join(errors) or "No valid files uploaded."}, status=400)

        order.subtotal = compute_quote(order.quote_specs()).subtotal
        order.set_status(Order.Status.AWAITING_PAYMENT, note="Order submitted, awaiting payment")
        return Response(
            {"order": OrderSerializer(order).data, "quote": _quote_response(compute_quote(order.quote_specs()))},
            status=status.HTTP_201_CREATED,
        )


class QuoteView(APIView):
    """Live quotation preview without creating an order."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        specs = body.get("files") or [{
            "page_count": body.get("page_count", 1),
            **{k: body.get(k) for k in ("media_size", "media_type", "color_mode",
                                        "print_quality", "sides", "copies")},
        }]
        try:
            quote = compute_quote(specs)
        except (TypeError, ValueError) as exc:
            return Response({"detail": f"Invalid quote payload: {exc}"}, status=400)
        return Response(_quote_response(quote))


class OrderListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user)
        return Response(OrderSerializer(orders, many=True).data)


class OrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        if order.user != request.user and not request.user.is_shop_admin:
            return Response({"detail": "Not allowed."}, status=403)
        return Response(OrderSerializer(order).data)


class OrderFileEditView(APIView):
    """Apply crop / split / resize / center edits to an uploaded file.

    Authenticated owners (or admins) can edit while the order is editable.
    Guests edit without an account by presenting the order's tracking_id.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, order_pk, file_pk):
        order = get_object_or_404(Order, pk=order_pk)
        order_file = get_object_or_404(OrderFile, pk=file_pk, order=order)
        user = request.user if request.user.is_authenticated else None

        if user:
            if order.user != user and not user.is_shop_admin:
                return Response({"detail": "Not allowed."}, status=403)
        elif order.user or request.data.get("tracking_id") != order.tracking_id:
            # Guests must prove ownership of the order via its tracking ID.
            return Response({"detail": "Not allowed."}, status=403)

        if order.status not in EDITABLE_STATUSES and not (user and user.is_shop_admin):
            return Response({"detail": "Files can no longer be edited for this order."}, status=409)

        action = request.data.get("action")
        params = request.data.get("params") or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                return Response({"detail": "Invalid params JSON."}, status=400)
        try:
            apply_edit(order_file, action, params)
        except FileEditError as exc:
            return Response({"detail": str(exc)}, status=400)

        # Re-price the order while payment has not started.
        if order.status != Order.Status.PENDING_REVIEW:
            order.subtotal = compute_quote(order.quote_specs()).subtotal
            order.save(update_fields=["subtotal"])
        return Response(OrderSerializer(order).data)


class OrderFilePreviewView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, order_pk, file_pk):
        """Inline preview; guests must present the tracking ID as a query param."""
        order = get_object_or_404(Order, pk=order_pk)
        order_file = get_object_or_404(OrderFile, pk=file_pk, order=order)
        user = request.user if request.user.is_authenticated else None
        if order.user:
            if user != order.user and not (user and user.is_shop_admin):
                return Response({"detail": "Not allowed."}, status=403)
        elif request.query_params.get("tracking_id") != order.tracking_id:
            return Response({"detail": "Not allowed."}, status=403)
        variant = request.query_params.get("variant", "edited")
        field = order_file.edited_file if variant == "edited" and order_file.edited_file else order_file.file
        field.open("rb")
        response = FileResponse(field, content_type=order_file.content_type or "application/octet-stream")
        response["Content-Disposition"] = f'inline; filename="{order_file.file_name}"'
        return response


def _status_label(status_value: str) -> str:
    try:
        return Order.Status(status_value).label
    except ValueError:
        return status_value


class TrackOrderView(APIView):
    """Guest-safe status tracking: tracking ID + contact match (PRD §4.1 #9)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, tracking_id: str):
        order = Order.objects.filter(tracking_id=tracking_id.upper()).first()
        contact = request.query_params.get("contact", "")
        if not order or not order.contact_matches(contact):
            return Response({"detail": "No order found for that tracking ID and contact."}, status=404)
        return Response({
            "tracking_id": order.tracking_id,
            "status": order.status,
            "status_display": order.get_status_display(),
            "client_name": order.client_display_name,
            "subtotal_peso": order.subtotal / 100,
            "amount_paid_peso": order.amount_paid / 100,
            "balance_due_peso": order.balance_due / 100,
            "files": [{"id": f.id, "file_name": f.file_name, "page_count": f.page_count,
                       "file_type": f.file_type} for f in order.files.all()],
            "history": [
                {"to_status": h.to_status,
                 "to_status_display": _status_label(h.to_status),
                 "note": h.note, "created_at": h.created_at}
                for h in order.history.all()
            ],
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        })


# ===================================================================== admin
class AdminOrderListView(APIView):
    """Review queue sorted by submission time (PRD §4.2 #1)."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get(self, request):
        orders = Order.objects.all()
        status_filter = request.query_params.get("status")
        if status_filter:
            orders = orders.filter(status=status_filter)
        search = request.query_params.get("search", "").strip()
        if search:
            from django.db.models import Q

            orders = orders.filter(
                Q(tracking_id__icontains=search) | Q(guest_name__icontains=search)
                | Q(user__email__icontains=search) | Q(guest_contact_value__icontains=search)
            )
        return Response(AdminOrderSerializer(orders[:200], many=True).data)


class AdminOrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        sync_print_jobs(order)  # refresh Epson state before showing
        return Response(AdminOrderSerializer(order).data)


class AdminOrderActionView(APIView):
    """Approve / Reject / Request Revision / Hold / Ready / Complete / Cancel."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    ALLOWED = {
        "approve": {Order.Status.PENDING_REVIEW},
        "reject": {Order.Status.PENDING_REVIEW, Order.Status.AWAITING_PAYMENT, Order.Status.ON_HOLD},
        "request_revision": {Order.Status.PENDING_REVIEW},
        "hold": {Order.Status.PRINTING, Order.Status.APPROVED_QUEUED},
        "resolve_hold": {Order.Status.ON_HOLD},
        "ready": {Order.Status.PRINTING, Order.Status.ON_HOLD, Order.Status.APPROVED_QUEUED},
        "complete": {Order.Status.PRINTED_READY},
        "cancel": {Order.Status.DRAFT, Order.Status.AWAITING_PAYMENT, Order.Status.PENDING_REVIEW,
                   Order.Status.APPROVED_QUEUED, Order.Status.ON_HOLD, Order.Status.REVISION_REQUESTED},
    }

    def post(self, request, pk, action: str):
        order = get_object_or_404(Order, pk=pk)
        allowed = self.ALLOWED.get(action)
        if not allowed:
            return Response({"detail": f"Unknown action '{action}'."}, status=400)
        if order.status not in allowed:
            return Response({"detail": f"Cannot {action.replace('_', ' ')} an order in status '{order.status}'."},
                            status=409)

        note = request.data.get("note", "") or request.data.get("reason", "")
        from apps.payments.services import refund_order

        if action == "approve":
            order.set_status(Order.Status.APPROVED_QUEUED, note=note, actor=request.user)
            submit_order_to_printer(order)
            order.refresh_from_db()
            failed = [j for j in order.print_jobs.all() if j.status == "failed"]
            if failed and len(failed) == order.print_jobs.count():
                order.set_status(Order.Status.ON_HOLD,
                                 note=f"All print jobs failed to submit: {failed[0].error_message}",
                                 actor=request.user)
        elif action == "reject":
            order.set_status(Order.Status.REJECTED, note=note, actor=request.user)
            refund_order(order, reason="rejected_by_shop")
        elif action == "request_revision":
            order.revision_note = note
            order.save(update_fields=["revision_note"])
            order.set_status(Order.Status.REVISION_REQUESTED, note=note, actor=request.user)
        elif action == "hold":
            order.set_status(Order.Status.ON_HOLD, note=note, actor=request.user)
        elif action == "resolve_hold":
            order.set_status(Order.Status.APPROVED_QUEUED, note=note or "Printer issue resolved",
                             actor=request.user)
            sync_print_jobs(order)
        elif action == "ready":
            order.set_status(Order.Status.PRINTED_READY, note=note or "Ready for pickup", actor=request.user)
        elif action == "complete":
            order.set_status(Order.Status.COMPLETED, note=note or "Picked up and settled", actor=request.user)
        elif action == "cancel":
            order.set_status(Order.Status.CANCELLED, note=note, actor=request.user)
            refund_order(order, reason="cancelled")
        return Response(AdminOrderSerializer(order).data)


class AdminOrderSpecView(APIView):
    """Admin correction of ambiguous print parameters (PRD §4.2 #3)."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def patch(self, request, order_pk, spec_pk):
        order = get_object_or_404(Order, pk=order_pk)
        spec = get_object_or_404(PrintSpecification, pk=spec_pk, order=order)
        serializer = PrintSpecificationSerializer(spec, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        order.subtotal = compute_quote(order.quote_specs()).subtotal
        order.save(update_fields=["subtotal"])
        return Response(AdminOrderSerializer(order).data)


class AdminResubmitView(APIView):
    """Re-submit failed print jobs to the printer."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        failed = order.print_jobs.filter(status__in=["failed", "canceled"])
        if not failed.exists():
            return Response({"detail": "No failed print jobs to resubmit."}, status=409)
        failed.delete()
        submit_order_to_printer(order)
        return Response(AdminOrderSerializer(order).data)
