from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer as BaseTokenObtainPairSerializer

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "facebook_handle", "password"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.role = User.Role.CLIENT
        user.username = validated_data.get("email")  # AbstractUser requires a username
        user.save()
        return user


class SetupSerializer(serializers.ModelSerializer):
    """Creates the shop's first admin. Guarded by SetupView (only runs once)."""

    # Uses Django's configured AUTH_PASSWORD_VALIDATORS (min length + common).
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "password"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.username = validated_data.get("email")  # AbstractUser requires a username
        user.set_password(password)
        user.role = User.Role.ADMIN
        # The first admin is the full owner: API admin AND Django admin.
        user.is_staff = True
        user.is_superuser = True
        user.save()
        return user


class MeSerializer(serializers.ModelSerializer):
    is_approver = serializers.BooleanField(read_only=True)
    can_review_orders = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "facebook_handle", "role",
                  "is_shop_admin", "is_approver", "can_review_orders"]
        read_only_fields = ["id", "role", "is_shop_admin", "is_approver", "can_review_orders"]


# Roles the shop owner may hand out from user management. Clients self-register
# through /auth/register/, so they are never created here.
STAFF_ROLES = (User.Role.APPROVER, User.Role.ADMIN)


class StaffMemberSerializer(serializers.ModelSerializer):
    """A shop-side account as it appears in the owner's user management list."""

    is_approver = serializers.BooleanField(read_only=True)
    is_shop_admin = serializers.BooleanField(read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "role", "role_display",
                  "is_active", "is_staff", "is_superuser", "is_approver", "is_shop_admin",
                  "date_joined", "last_login"]
        read_only_fields = fields


class StaffMemberWriteSerializer(serializers.ModelSerializer):
    """Create / edit an admin or approver account (owner-only endpoints)."""

    role = serializers.ChoiceField(choices=STAFF_ROLES)
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=False, validators=[validate_password],
    )

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "role",
                  "password", "is_active"]

    def validate_email(self, value: str) -> str:
        email = value.strip().lower()
        queryset = User.objects.filter(email__iexact=email)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    def validate(self, attrs):
        # A new staff account needs a password; on edit it is optional
        # ("leave blank to keep the current one").
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "A password is required for a new account."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.username = validated_data["email"]  # AbstractUser requires a username
        user.set_password(password)
        # Django-admin access follows the owner role; approvers are API-only.
        user.is_staff = user.role == User.Role.ADMIN
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.username = instance.email
        instance.is_staff = instance.role == User.Role.ADMIN or instance.is_superuser
        instance.save()
        return instance


class EmailTokenObtainPairSerializer(BaseTokenObtainPairSerializer):
    """Email/password login (email is the USERNAME_FIELD)."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = MeSerializer(self.user).data
        return data
