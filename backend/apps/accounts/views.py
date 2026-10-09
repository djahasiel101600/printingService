from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.pricing.views import IsShopAdmin

from .serializers import (
    EmailTokenObtainPairSerializer,
    MeSerializer,
    RegisterSerializer,
    SetupSerializer,
    StaffMemberSerializer,
    StaffMemberWriteSerializer,
)

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(MeSerializer(user).data, status=201)


class SetupView(APIView):
    """First-run bootstrap: create the shop's first admin account.

    GET  /api/auth/setup/  -> {"needs_setup": bool}
    POST /api/auth/setup/  -> creates the admin, returns JWT tokens + user

    Public by necessity (nobody can log in yet), but self-disabling: as soon as
    any admin exists it answers 403, so it can never mint extra admins later.
    """

    permission_classes = [permissions.AllowAny]

    @staticmethod
    def _admin_exists() -> bool:
        return User.objects.filter(role=User.Role.ADMIN).exists()

    def get(self, request):
        return Response({"needs_setup": not self._admin_exists()})

    def post(self, request):
        serializer = SetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Re-check inside the transaction so two racing requests can't both win.
        with transaction.atomic():
            if self._admin_exists():
                return Response({"detail": "Setup has already been completed."}, status=403)
            user = serializer.save()

        refresh = EmailTokenObtainPairSerializer.get_token(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": MeSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)

    def patch(self, request):
        serializer = MeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AdminCustomersView(APIView):
    """Admin typeahead: registered customers an order can be linked to when
    creating an order on the customer's behalf."""

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get(self, request):
        search = request.query_params.get("search", "").strip()
        customers = User.objects.filter(role=User.Role.CLIENT)
        if search:
            customers = customers.filter(
                Q(email__icontains=search) | Q(first_name__icontains=search)
                | Q(last_name__icontains=search) | Q(phone__icontains=search)
            )
        return Response([
            {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
            }
            for user in customers[:20]
        ])


class AdminStaffView(APIView):
    """User management (owner-only): list and create shop-side accounts.

    GET  /api/admin/users/           -> every admin + approver account
    POST /api/admin/users/           -> create an approver or a second admin

    Added so a shop can hand the approval queue to another person: an
    ``approver`` may work the review queue but cannot open pricing, printer
    credentials, payment settings or this list (see ``IsShopStaff``).
    """

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get(self, request):
        search = request.query_params.get("search", "").strip()
        staff = User.objects.filter(role__in=[User.Role.ADMIN, User.Role.APPROVER]).order_by("email")
        if search:
            staff = staff.filter(
                Q(email__icontains=search) | Q(first_name__icontains=search)
                | Q(last_name__icontains=search) | Q(phone__icontains=search)
            )
        return Response(StaffMemberSerializer(staff, many=True).data)

    def post(self, request):
        serializer = StaffMemberWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(StaffMemberSerializer(user).data, status=status.HTTP_201_CREATED)


class AdminStaffDetailView(APIView):
    """User management (owner-only): edit, re-role or deactivate one account.

    PATCH  -> names, phone, role, password, active flag
    DELETE -> deactivate (soft): the account keeps its order history

    Guards: an owner may never demote or deactivate themselves, and the last
    active owner can never be removed — that would lock the shop out of its own
    configuration.
    """

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def _staff_or_404(self, pk: int) -> User:
        user = get_object_or_404(
            User.objects.filter(role__in=[User.Role.ADMIN, User.Role.APPROVER]), pk=pk,
        )
        return user

    def _would_remove_last_owner(self, target: User, *, removing: bool) -> bool:
        if not removing or not target.is_shop_admin:
            return False
        owners = User.objects.filter(
            Q(role=User.Role.ADMIN) | Q(is_superuser=True), is_active=True,
        ).exclude(pk=target.pk)
        return not owners.exists()

    def get(self, request, pk):
        return Response(StaffMemberSerializer(self._staff_or_404(pk)).data)

    def patch(self, request, pk):
        target = self._staff_or_404(pk)
        demoting = "role" in request.data and request.data["role"] != User.Role.ADMIN
        deactivating = request.data.get("is_active") in (False, "false", "False", 0)
        if target.pk == request.user.pk and (demoting or deactivating):
            return Response(
                {"detail": "You cannot change your own role or deactivate your own account."},
                status=400,
            )
        if target.is_shop_admin and (demoting or deactivating) and self._would_remove_last_owner(target, removing=True):
            return Response({"detail": "At least one active admin account is required."}, status=400)

        serializer = StaffMemberWriteSerializer(target, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        action = "staff.demote" if demoting else "staff.deactivate"
        log_activity(
            request.user, action, object_type="user",
            object_repr=user.email, object_id=user.pk,
            detail=(f"Role changed {target.role} to {user.role}."
                    if demoting else "Account deactivated."),
        )
        return Response(StaffMemberSerializer(user).data)

    def delete(self, request, pk):
        target = self._staff_or_404(pk)
        if target.pk == request.user.pk:
            return Response({"detail": "You cannot deactivate your own account."}, status=400)
        if self._would_remove_last_owner(target, removing=True):
            return Response({"detail": "At least one active admin account is required."}, status=400)
        target.is_active = False
        target.save(update_fields=["is_active"])
        log_activity(
            request.user, "staff.deactivate", object_type="user",
            object_repr=target.email, object_id=target.pk,
            detail="Account deactivated (order history kept).",
        )
        return Response(StaffMemberSerializer(target).data)
