import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pricing.quotation import compute_quote
from apps.pricing.views import IsShopAdmin
from apps.printing.services import (
    printable_files, submit_order_to_printer, sync_print_jobs, unprintable_files,
)

from .models import (
    PRINTABLE_EXTENSIONS, Order, OrderFile, OrderStatusHistory, PrintSpecification,
    format_page_selection,
)
from .serializers import AdminOrderSerializer, GuestContactSerializer, OrderSerializer, PrintSpecificationSerializer
from .services.document_preview import PreviewError, build_preview
from .services.file_edits import FileEditError, apply_edit, count_pages, select_pages

User = get_user_model()

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
        is_admin = bool(user and user.is_shop_admin)
        customer_user_id = request.data.get("customer_user_id")

        # An admin may place an order on a customer's behalf — either linked to
        # a registered account (customer_user_id) or with guest contact details
        # (walk-in customer). In both cases the order is NOT owned by the admin.
        proxy_guest = is_admin and not customer_user_id and bool(request.data.get("guest_name"))

        order_user = user
        guest_data = {}
        if is_admin and customer_user_id:
            try:
                target = User.objects.filter(pk=customer_user_id).first()
            except (TypeError, ValueError):
                target = None
            if not target:
                return Response({"detail": "Customer account not found."}, status=400)
            order_user = target
        elif user is None or proxy_guest:
            guest = GuestContactSerializer(data=request.data)
            guest.is_valid(raise_exception=True)
            guest_data = guest.validated_data
            order_user = None

        try:
            spec_data = _parse_spec(request.data)
            per_file = json.loads(request.data.get("per_file_specs", "[]"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        spec_serializer = PrintSpecificationSerializer(data=spec_data)
        spec_serializer.is_valid(raise_exception=True)
        spec_defaults = spec_serializer.validated_data

        order = Order.objects.create(
            user=order_user,
            status=Order.Status.DRAFT,
            **guest_data,
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
    """Owners and staff read the full order.

    Guests (anonymous orders) prove ownership by presenting the tracking ID —
    the same proof used by the file preview/edit endpoints — so a customer who
    just placed an order without an account can still open their confirmation
    page and pay.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        user = request.user if request.user.is_authenticated else None
        if user and (order.user_id == user.id or user.is_shop_admin):
            return Response(OrderSerializer(order).data)
        if order.user_id is None and request.query_params.get("tracking_id") == order.tracking_id:
            return Response(OrderSerializer(order).data)
        return Response({"detail": "Not allowed."}, status=403)


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


def _file_read(field) -> bytes:
    field.open("rb")
    try:
        return field.read()
    finally:
        field.close()


class OrderFilePreviewView(APIView):
    """Stream an uploaded file back for preview or download.

    ``?variant=`` picks which revision to serve — ``original`` (what the client
    uploaded), ``edited`` (after the client's crop/split/resize) or ``final``
    (after the admin's page selection). Documents are served as-is here and
    rendered through ``OrderFileTextPreviewView`` instead.
    """

    permission_classes = [permissions.AllowAny]

    VARIANTS = ("edited", "original", "final")

    def get(self, request, order_pk, file_pk):
        order = get_object_or_404(Order, pk=order_pk)
        order_file = get_object_or_404(OrderFile, pk=file_pk, order=order)
        user = request.user if request.user.is_authenticated else None
        if order.user:
            if user != order.user and not (user and user.is_shop_admin):
                return Response({"detail": "Not allowed."}, status=403)
        elif request.query_params.get("tracking_id") != order.tracking_id:
            return Response({"detail": "Not allowed."}, status=403)

        variant = request.query_params.get("variant", "edited")
        if variant not in self.VARIANTS:
            return Response({"detail": f"Unknown variant '{variant}'."}, status=400)
        if variant == "original":
            field, content_type, name = order_file.file, order_file.content_type, order_file.file_name
        elif variant == "final":
            field = order_file.final_file or order_file.print_file
            content_type = order_file.print_content_type
            name = order_file.print_file_name
        else:
            field = order_file.edited_file or order_file.file
            content_type = order_file.print_content_type
            name = order_file.print_file_name

        if not field:
            return Response({"detail": "That version of the file does not exist."}, status=404)

        disposition = "attachment" if request.query_params.get("download") == "1" else "inline"
        response = FileResponse(
            field, content_type=content_type or "application/octet-stream",
            filename=name if disposition == "attachment" else None,
            as_attachment=disposition == "attachment",
        )
        if disposition == "inline":
            response["Content-Disposition"] = f'inline; filename="{name}"'
        return response


class OrderFileTextPreviewView(APIView):
    """Extracted contents of a Word/Excel/PowerPoint/text upload.

    Browsers cannot render these formats natively, so the server pulls the text
    out of the container and returns a structured payload the UI displays.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, order_pk, file_pk):
        order = get_object_or_404(Order, pk=order_pk)
        order_file = get_object_or_404(OrderFile, pk=file_pk, order=order)
        user = request.user if request.user.is_authenticated else None
        if order.user:
            if user != order.user and not (user and user.is_shop_admin):
                return Response({"detail": "Not allowed."}, status=403)
        elif request.query_params.get("tracking_id") != order.tracking_id:
            return Response({"detail": "Not allowed."}, status=403)

        try:
            preview = build_preview(order_file.file_name, _file_read(order_file.file))
        except PreviewError as exc:
            return Response({"detail": str(exc)}, status=415)
        return Response({
            **preview.as_dict(),
            "file_name": order_file.file_name,
            "page_count": order_file.page_count,
        })


def _status_label(status_value: str) -> str:
    try:
        return Order.Status(status_value).label
    except ValueError:
        return status_value


class TrackOrderView(APIView):
    """Guest-safe status tracking: tracking ID + contact match (PRD §4.1 #9).

    The tracking ID alone is not enough — anybody who guesses or copies it must
    not be able to read someone else's order, so a guest also has to present the
    email/phone/Facebook handle used when the order was placed. Signed-in owners
    and staff skip that second step because the JWT already proves ownership.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, tracking_id: str):
        code = tracking_id.strip().upper().replace(" ", "")
        if not code:
            return Response({"detail": "Enter a tracking ID."}, status=400)
        order = Order.objects.filter(tracking_id=code).first()
        if not order:
            return Response({"detail": f"No order found with tracking ID {code}."}, status=404)

        user = request.user if request.user.is_authenticated else None
        owned = bool(user) and (order.user_id == user.id or user.is_shop_admin)
        if not owned and not order.contact_matches(request.query_params.get("contact", "")):
            return Response(
                {"detail": (
                    "That contact does not match this order. Enter the exact email, "
                    "phone number or Facebook name used when you placed it, or "
                    "sign in to the account that owns the order."
                )},
                status=403,
            )

        return Response({
            "id": order.id,
            "tracking_id": order.tracking_id,
            "status": order.status,
            "status_display": order.get_status_display(),
            "client_name": order.client_display_name,
            "subtotal_peso": order.subtotal / 100,
            "amount_paid_peso": order.amount_paid / 100,
            "balance_due_peso": order.balance_due / 100,
            "reprint_count": order.reprint_count,
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
                | Q(user__email__icontains=search) | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search) | Q(guest_contact_value__icontains=search)
            )
        return Response(AdminOrderSerializer(orders[:200], many=True).data)


class AdminOrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        sync_print_jobs(order)  # refresh Epson state before showing
        return Response(AdminOrderSerializer(order).data)


class AdminOrderActionView(APIView):
    """Approve / Reject / Request Revision / Hold / Reprint / Ready / Complete / Cancel."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    ALLOWED = {
        "approve": {Order.Status.PENDING_REVIEW},
        "reject": {Order.Status.PENDING_REVIEW, Order.Status.AWAITING_PAYMENT, Order.Status.ON_HOLD,
                   Order.Status.PRINT_CANCELLED},
        "request_revision": {Order.Status.PENDING_REVIEW},
        "hold": {Order.Status.PRINTING, Order.Status.APPROVED_QUEUED},
        "resolve_hold": {Order.Status.ON_HOLD},
        "ready": {Order.Status.PRINTING, Order.Status.ON_HOLD, Order.Status.APPROVED_QUEUED,
                  Order.Status.PRINT_CANCELLED},
        "complete": {Order.Status.PRINTED_READY},
        # Reprint is the recovery path for anything that already reached the
        # printer — bad output, a jam, or a job the printer cancelled itself.
        "reprint": {Order.Status.ON_HOLD, Order.Status.APPROVED_QUEUED, Order.Status.PRINTING,
                    Order.Status.PRINTED_READY, Order.Status.PRINT_CANCELLED,
                    Order.Status.COMPLETED},
        "cancel": {Order.Status.DRAFT, Order.Status.AWAITING_PAYMENT, Order.Status.PENDING_REVIEW,
                   Order.Status.APPROVED_QUEUED, Order.Status.ON_HOLD, Order.Status.REVISION_REQUESTED},
        "record_payment": {Order.Status.AWAITING_PAYMENT, Order.Status.PENDING_REVIEW,
                           Order.Status.APPROVED_QUEUED, Order.Status.PRINTING, Order.Status.ON_HOLD,
                           Order.Status.PRINTED_READY, Order.Status.COMPLETED},
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
            blocked = unprintable_files(order)
            if blocked:
                return Response({"detail": (
                    "Convert these to PDF (or replace them) before approving: "
                    + ", ".join(f.file_name for f in blocked)
                    + ". The printer only accepts PDF and image files."
                )}, status=409)
            order.set_status(Order.Status.APPROVED_QUEUED, note=note, actor=request.user)
            submit_order_to_printer(order)
            order.refresh_from_db()
            failed = [j for j in order.print_jobs.all() if j.status == "failed"]
            if failed and len(failed) == order.print_jobs.count():
                order.set_status(Order.Status.ON_HOLD,
                                 note=f"All print jobs failed to submit: {failed[0].error_message}",
                                 actor=request.user)
        elif action == "reprint":
            response = self._reprint(request, order, note)
            if response is not None:
                return response
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
        elif action == "record_payment":
            from apps.payments.services import record_manual_payment

            amount = record_manual_payment(order, actor=request.user)
            if amount == 0:
                return Response({"detail": "This order has no balance due."}, status=409)
            order.refresh_from_db()
        return Response(AdminOrderSerializer(order).data)

    def _reprint(self, request, order: Order, note: str):
        """Send the order to the printer again.

        The previous run is kept intact (jobs, history, reprint count) so the
        admin can still see what went wrong; a fresh set of Epson jobs is
        created and tagged as a reprint. Optionally scoped to a single file via
        ``file_id`` — that is how you recover just the sheet the printer
        cancelled without wasting paper on the ones that printed fine.
        """
        blocked = unprintable_files(order)
        if blocked:
            return Response({"detail": (
                "Convert these to PDF (or replace them) before reprinting: "
                + ", ".join(f.file_name for f in blocked)
            )}, status=409)

        order_file_ids = request.data.get("file_ids") or []
        if isinstance(order_file_ids, str):
            order_file_ids = [order_file_ids]
        if not order_file_ids:
            single = request.data.get("file_id")
            order_file_ids = [single] if single else []
        if not printable_files(order):
            return Response({"detail": "This order has no printable files."}, status=409)

        targets = None
        if order_file_ids:
            targets = list(order.files.filter(pk__in=order_file_ids))
            if not targets:
                return Response({"detail": "No matching files on this order."}, status=404)
        jobs = submit_order_to_printer(order, reprint=True, order_files=targets)
        order.refresh_from_db()

        order.reprint_count += 1
        order.save(update_fields=["reprint_count"])
        failed = [j for j in jobs if j.status == "failed"]
        summary = note or f"Reprint #{order.reprint_count} sent to the printer"
        if failed:
            summary += f" — {len(failed)} job(s) failed to submit"

        # A reprint always puts the order back into the flow; if every job
        # failed to submit it lands on hold instead.
        order.set_status(
            Order.Status.ON_HOLD if failed and len(failed) == len(jobs)
            else Order.Status.APPROVED_QUEUED,
            note=summary,
            actor=request.user,
        )
        return None


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


class AdminOrderNotesView(APIView):
    """Save the order's internal notes (never shown to the client)."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def patch(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        order.admin_notes = request.data.get("admin_notes", "")
        order.save(update_fields=["admin_notes"])
        return Response(AdminOrderSerializer(order).data)


class AdminOrderFilePagesView(APIView):
    """Admin page selection — "which pages of this file should be printed?".

    Epson Connect has no page-range parameter, so the chosen pages are written
    into a trimmed ``final_file`` that is uploaded to the printer instead of the
    original. The order is re-quoted from the surviving pages so the customer is
    only charged for what actually comes out of the printer.
    """

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def patch(self, request, order_pk, file_pk):
        order = get_object_or_404(Order, pk=order_pk)
        order_file = get_object_or_404(OrderFile, pk=file_pk, order=order)

        if order_file.file_type != OrderFile.FileType.PDF:
            return Response({"detail": "Page selection only applies to PDF files."}, status=400)

        raw = request.data.get("pages", request.data.get("page_selection"))
        if raw is None:
            return Response({"detail": "Send a 'pages' array of page numbers."}, status=400)
        try:
            pages = [int(page) for page in raw]
        except (TypeError, ValueError):
            return Response({"detail": "Pages must be numbers."}, status=400)

        try:
            selected = select_pages(order_file, pages)
        except FileEditError as exc:
            return Response({"detail": str(exc)}, status=400)

        order.refresh_from_db()
        order.subtotal = compute_quote(order.quote_specs()).subtotal
        order.save(update_fields=["subtotal"])
        return Response({
            "order": AdminOrderSerializer(order).data,
            "selected_pages": selected,
            "label": order_file.page_selection_label,
        })


class AdminOrderFileReplaceView(APIView):
    """Swap an un-printable upload (e.g. a .docx) for a converted PDF.

    The original is kept for the audit trail; ``final_file`` becomes the new
    print-ready version, so the admin can convert the document in Word (or
    Google Docs) and release the order without asking the customer again.
    """

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, order_pk, file_pk):
        order = get_object_or_404(Order, pk=order_pk)
        order_file = get_object_or_404(OrderFile, pk=file_pk, order=order)
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "Attach a file under the 'file' field."}, status=400)
        extension = upload.name.rsplit(".", 1)[-1].lower()
        if extension not in PRINTABLE_EXTENSIONS:
            return Response({"detail": (
                f"'{upload.name}' cannot be sent to the printer. Upload a PDF or an image."
            )}, status=400)
        if upload.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
            return Response({"detail": f"File exceeds the {settings.MAX_UPLOAD_MB}MB limit."}, status=400)

        order_file.file_type = (OrderFile.FileType.PDF if extension == "pdf"
                                else OrderFile.FileType.IMAGE)
        order_file.content_type = upload.content_type or ""
        order_file.size = upload.size
        order_file.replaced_by_admin = True
        # The conversion replaces the document, so drop the stale page selection
        # and rebuild the page count from the new file.
        order_file.page_selection = []
        if order_file.edited_file:
            order_file.edited_file.delete(save=False)
            order_file.edited_file = None
        if order_file.final_file:
            order_file.final_file.delete(save=False)
        order_file.final_file.save(upload.name, upload, save=False)
        order_file.save()

        content = _file_read(order_file.final_file)
        try:
            order_file.page_count = count_pages(order_file.file_type, content)
        except FileEditError as exc:
            return Response({"detail": str(exc)}, status=400)
        order_file.save(update_fields=["page_count"])

        order.refresh_from_db()
        order.subtotal = compute_quote(order.quote_specs()).subtotal
        order.save(update_fields=["subtotal"])
        OrderStatusHistory.objects.create(
            order=order, from_status=order.status, to_status=order.status,
            note=f"Shop replaced '{order_file.file_name}' with a converted PDF",
            actor=request.user,
        )
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
