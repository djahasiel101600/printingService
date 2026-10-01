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
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "facebook_handle", "role", "is_shop_admin"]
        read_only_fields = ["id", "role", "is_shop_admin"]


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
