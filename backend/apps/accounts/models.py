from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Application user.

    Roles mirror PRD §3. Guests never materialise as users — guest orders keep
    a contact snapshot on the Order itself.
    """

    class Role(models.TextChoices):
        CLIENT = "client", "Client"
        # Works the review queue (approve / reject / request revision / release
        # to the printer) but cannot touch shop configuration: pricing, printer
        # credentials, payment settings or other staff accounts.
        APPROVER = "approver", "Approver (print orders)"
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
        """Owner-level access: shop configuration, staff accounts, money."""
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_approver(self) -> bool:
        return self.role == self.Role.APPROVER

    @property
    def can_review_orders(self) -> bool:
        """Everyone who may work the review queue (PRD §4.2).

        Approvers were added beside admins so a shop can hand the print
        approval queue to a second person without giving them the pricing
        table, the PayMongo/Epson credentials or the staff list.
        """
        return self.is_shop_admin or self.is_approver

    @property
    def is_staff_member(self) -> bool:
        """Any shop-side account (admins + approvers), clients excluded."""
        return self.role in {self.Role.ADMIN, self.Role.APPROVER} or self.is_superuser
