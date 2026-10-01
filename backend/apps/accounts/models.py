from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Application user.

    Roles mirror PRD §3. Guests never materialise as users — guest orders keep
    a contact snapshot on the Order itself.
    """

    class Role(models.TextChoices):
        CLIENT = "client", "Client"
        ADMIN = "admin", "Admin / Staff"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True)
    facebook_handle = models.CharField(max_length=128, blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CLIENT)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.email} ({self.role})"

    @property
    def is_shop_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser
