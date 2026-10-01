from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
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
