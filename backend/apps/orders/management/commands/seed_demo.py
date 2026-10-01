"""Seed pricing rules, an admin account, and a demo client.

Run:  python manage.py seed_demo
"""
from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.pricing.models import PriceRule

User = get_user_model()

DEFAULT_RULES = [
    # media_size, media_type, color_mode, print_quality, price_per_page (centavos)
    ("ps_a4", "pt_plainpaper", "mono", "normal", 300),
    ("ps_a4", "pt_plainpaper", "mono", "draft", 250),
    ("ps_a4", "pt_plainpaper", "mono", "high", 500),
    ("ps_a4", "pt_plainpaper", "color", "normal", 1000),
    ("ps_a4", "pt_plainpaper", "color", "draft", 800),
    ("ps_a4", "pt_plainpaper", "color", "high", 1500),
    ("ps_letter", "pt_plainpaper", "mono", "normal", 300),
    ("ps_letter", "pt_plainpaper", "color", "normal", 1000),
    ("ps_a3", "pt_plainpaper", "mono", "normal", 600),
    ("ps_a3", "pt_plainpaper", "color", "normal", 2000),
    ("any", "pt_photopaper", "color", "high", 3500),
    ("ps_2l", "pt_photopaper", "color", "high", 3500),
    ("ps_a4", "any", "any", "any", 400),
    ("any", "any", "any", "any", 500),
]


class Command(BaseCommand):
    help = "Seed pricing rules, an admin account, and a demo client."

    def handle(self, *args, **options):
        created_rules = 0
        for media_size, media_type, color_mode, print_quality, price in DEFAULT_RULES:
            _, created = PriceRule.objects.get_or_create(
                media_size=media_size, media_type=media_type,
                color_mode=color_mode, print_quality=print_quality,
                defaults={"price_per_page": price},
            )
            created_rules += int(created)
        self.stdout.write(f"Pricing rules: {created_rules} created, {PriceRule.objects.count()} total.")

        admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@print.local")
        if not User.objects.filter(email=admin_email).exists():
            User.objects.create_user(
                username=admin_email, email=admin_email,
                password=os.getenv("SEED_ADMIN_PASSWORD", "admin1234"),
                first_name="Shop", last_name="Admin", role=User.Role.ADMIN,
            )
            self.stdout.write(self.style.SUCCESS(f"Admin created: {admin_email} / admin1234"))

        client_email = os.getenv("SEED_CLIENT_EMAIL", "client@example.com")
        if not User.objects.filter(email=client_email).exists():
            User.objects.create_user(
                username=client_email, email=client_email,
                password=os.getenv("SEED_CLIENT_PASSWORD", "client1234"),
                first_name="Demo", last_name="Client", phone="09171234567",
                role=User.Role.CLIENT,
            )
            self.stdout.write(self.style.SUCCESS(f"Demo client created: {client_email} / client1234"))
