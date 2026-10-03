"""Configurable pricing: PricingSettings singleton + PriceRule CRUD validation."""
import os

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import PriceRule, PricingSettings
from .quotation import compute_quote

User = get_user_model()

# The same defaults the 0002 migration seeds from, so tests stay valid
# whether or not a dev .env overrides them.
ENV_DUPLEX = float(os.getenv("DUPLEX_DISCOUNT_FACTOR", "0.90"))
ENV_MIN_PARTIAL = int(os.getenv("MIN_PARTIAL_PERCENT", "50"))

SPEC = {"page_count": 4, "copies": 1, "media_size": "ps_a4",
        "media_type": "pt_plainpaper", "color_mode": "mono",
        "print_quality": "normal", "sides": "none"}


def make_admin() -> User:
    return User.objects.create_user(
        username="admin@print.local", email="admin@print.local",
        password="admin1234", role=User.Role.ADMIN,
    )


def make_client_user() -> User:
    return User.objects.create_user(
        username="client@example.com", email="client@example.com",
        password="s3cretpass!", role=User.Role.CLIENT,
    )


class PricingSettingsEndpointTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.admin_api = APIClient()
        self.admin_api.force_authenticate(make_admin())

    def test_get_is_public_and_matches_seeded_row(self):
        response = self.api.get("/api/pricing/settings/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        knob = PricingSettings.get_solo()
        self.assertEqual(body["duplex_discount_factor"], knob.duplex_discount_factor)
        self.assertEqual(body["min_partial_percent"], knob.min_partial_percent)
        self.assertEqual(body["fallback_price_per_side"], knob.fallback_price_per_side)
        self.assertEqual(body["fallback_price_per_side_peso"],
                         knob.fallback_price_per_side / 100)
        # Migration seeds from the legacy env vars (defaults 0.90 / 50 / 500).
        self.assertEqual(knob.duplex_discount_factor, ENV_DUPLEX)
        self.assertEqual(knob.min_partial_percent, ENV_MIN_PARTIAL)
        self.assertEqual(knob.fallback_price_per_side, 500)

    def test_put_requires_admin(self):
        anon = APIClient()
        response = anon.put("/api/pricing/settings/",
                            {"duplex_discount_factor": 0.8}, format="json")
        self.assertEqual(response.status_code, 403)

        client_api = APIClient()
        client_api.force_authenticate(make_client_user())
        response = client_api.put("/api/pricing/settings/",
                                  {"duplex_discount_factor": 0.8}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(PricingSettings.get_solo().duplex_discount_factor, ENV_DUPLEX)

    def test_admin_can_update_knobs(self):
        response = self.admin_api.put("/api/pricing/settings/", {
            "duplex_discount_factor": 0.85,
            "min_partial_percent": 30,
            "fallback_price_per_side": 750,
        }, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        knob = PricingSettings.get_solo()
        self.assertEqual(knob.duplex_discount_factor, 0.85)
        self.assertEqual(knob.min_partial_percent, 30)
        self.assertEqual(knob.fallback_price_per_side, 750)

    def test_put_updates_only_provided_keys(self):
        response = self.admin_api.put("/api/pricing/settings/",
                                      {"min_partial_percent": 40}, format="json")
        self.assertEqual(response.status_code, 200)
        knob = PricingSettings.get_solo()
        self.assertEqual(knob.min_partial_percent, 40)
        self.assertEqual(knob.duplex_discount_factor, ENV_DUPLEX)
        self.assertEqual(knob.fallback_price_per_side, 500)

    def test_put_rejects_out_of_range_values(self):
        for payload in ({"duplex_discount_factor": 1.5},
                        {"duplex_discount_factor": -0.1},
                        {"duplex_discount_factor": "abc"},
                        {"min_partial_percent": 120},
                        {"min_partial_percent": "high"},
                        {"fallback_price_per_side": 0},
                        {"fallback_price_per_side": -5}):
            response = self.admin_api.put("/api/pricing/settings/", payload, format="json")
            self.assertEqual(response.status_code, 400, payload)
        knob = PricingSettings.get_solo()
        self.assertEqual(knob.duplex_discount_factor, ENV_DUPLEX)
        self.assertEqual(knob.min_partial_percent, ENV_MIN_PARTIAL)
        self.assertEqual(knob.fallback_price_per_side, 500)

    def test_quote_uses_db_duplex_factor(self):
        knob = PricingSettings.get_solo()
        knob.duplex_discount_factor = 0.5
        knob.save()
        PriceRule.objects.create(media_size="ps_a4", media_type="pt_plainpaper",
                                 color_mode="mono", print_quality="normal",
                                 price_per_page=300)
        quote = compute_quote([{**SPEC, "page_count": 10, "sides": "long"}])
        self.assertEqual(quote.subtotal, round(300 * 0.5) * 10)

    def test_fallback_price_from_db_when_no_rule_matches(self):
        knob = PricingSettings.get_solo()
        knob.fallback_price_per_side = 250
        knob.save()
        quote = compute_quote([{**SPEC, "copies": 2}])
        self.assertEqual(quote.subtotal, 4 * 2 * 250)

    def test_quote_endpoint_min_partial_is_pesos_from_db(self):
        knob = PricingSettings.get_solo()
        knob.min_partial_percent = 25
        knob.save()
        response = self.api.post("/api/orders/quote/", {"files": [SPEC]}, format="json")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        # No rules → fallback 500c × 4 pages = 2000c; 25% = 500c = ₱5.00.
        self.assertEqual(body["subtotal"], 4 * 500)
        self.assertEqual(body["min_partial_peso"], 5.0)


class PriceRuleCrudTests(TestCase):
    def setUp(self):
        self.admin_api = APIClient()
        self.admin_api.force_authenticate(make_admin())
        self.client_api = APIClient()
        self.client_api.force_authenticate(make_client_user())
        PriceRule.objects.create(media_size="ps_a4", media_type="pt_plainpaper",
                                 color_mode="mono", print_quality="normal",
                                 price_per_page=300)

    @staticmethod
    def payload(**overrides) -> dict:
        body = {"media_size": "ps_a5", "media_type": "pt_plainpaper",
                "color_mode": "color", "print_quality": "normal",
                "price_per_page": 600, "is_active": True}
        body.update(overrides)
        return body

    def test_anonymous_cannot_list(self):
        response = APIClient().get("/api/admin/pricing-rules/")
        self.assertIn(response.status_code, (401, 403))

    def test_client_user_cannot_list(self):
        response = self.client_api.get("/api/admin/pricing-rules/")
        self.assertEqual(response.status_code, 403)

    def test_admin_crud_round_trip(self):
        response = self.admin_api.post("/api/admin/pricing-rules/",
                                       self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.content)
        rule_id = response.json()["id"]
        self.assertEqual(response.json()["price_per_page_peso"], 6.0)

        response = self.admin_api.get("/api/admin/pricing-rules/")
        self.assertEqual(response.status_code, 200)
        # DefaultRouter + PageNumberPagination → {count, next, previous, results}.
        self.assertEqual(response.json()["count"], 2)

        response = self.admin_api.patch(f"/api/admin/pricing-rules/{rule_id}/",
                                        {"price_per_page": 700}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["price_per_page"], 700)

        response = self.admin_api.delete(f"/api/admin/pricing-rules/{rule_id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(PriceRule.objects.count(), 1)

    def test_duplicate_create_is_client_error_not_500(self):
        response = self.admin_api.post("/api/admin/pricing-rules/", {
            "media_size": "ps_a4", "media_type": "pt_plainpaper",
            "color_mode": "mono", "print_quality": "normal", "price_per_page": 400,
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PriceRule.objects.count(), 1)

    def test_duplicate_update_is_client_error_not_500(self):
        other = PriceRule.objects.create(media_size="ps_a5", media_type="pt_plainpaper",
                                         color_mode="mono", print_quality="normal",
                                         price_per_page=350)
        response = self.admin_api.patch(f"/api/admin/pricing-rules/{other.id}/",
                                        {"media_size": "ps_a4"}, format="json")
        self.assertEqual(response.status_code, 400)
        other.refresh_from_db()
        self.assertEqual(other.media_size, "ps_a5")

    def test_update_keeping_own_combination_is_allowed(self):
        rule = PriceRule.objects.get(media_size="ps_a4")
        response = self.admin_api.patch(f"/api/admin/pricing-rules/{rule.id}/",
                                        {"price_per_page": 320}, format="json")
        self.assertEqual(response.status_code, 200)
        rule.refresh_from_db()
        self.assertEqual(rule.price_per_page, 320)

    def test_unknown_vocabulary_rejected(self):
        for field, value in (("media_size", "A4"), ("media_type", "plain"),
                             ("color_mode", "grey"), ("print_quality", "ultra")):
            response = self.admin_api.post("/api/admin/pricing-rules/",
                                           self.payload(**{field: value}), format="json")
            self.assertEqual(response.status_code, 400, field)

    def test_any_wildcards_allowed(self):
        response = self.admin_api.post("/api/admin/pricing-rules/", self.payload(
            media_size="any", media_type="any", color_mode="any", print_quality="any",
        ), format="json")
        self.assertEqual(response.status_code, 201, response.content)

    def test_price_must_be_at_least_one_centavo(self):
        response = self.admin_api.post("/api/admin/pricing-rules/",
                                       self.payload(price_per_page=0), format="json")
        self.assertEqual(response.status_code, 400)

    def test_deactivating_rule_falls_back_to_fallback_price(self):
        rule = PriceRule.objects.get(media_size="ps_a4")
        response = self.admin_api.patch(f"/api/admin/pricing-rules/{rule.id}/",
                                        {"is_active": False}, format="json")
        self.assertEqual(response.status_code, 200)
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)
        # ps_a4/mono/normal now has no active rule → DB fallback price applies.
        quote = compute_quote([SPEC])
        self.assertEqual(quote.subtotal,
                         4 * PricingSettings.get_solo().fallback_price_per_side)