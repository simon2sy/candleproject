"""Checkout and oversell protection tests (storefront)."""
from decimal import Decimal
from django.test import TestCase

from catalog.models import Category, Product
from orders.models import Order
from tests.helpers import make_seller, make_user
from tests.checkout import checkout_payload, valid_png, oversized_png, fake_png, add_to_cart


class CheckoutOversellTest(TestCase):
    """Oversell protection exercised through the storefront checkout."""

    def setUp(self):
        self.seller_user, self.seller_profile = make_seller("seller_oversell")
        self.customer = make_user("buyer_oversell")
        self.product = Product.objects.create(
            seller=self.seller_profile,
            category=Category.objects.create(name="Oversell Cat", slug="oversell-cat"),
            name="Limited Soy Wax",
            slug="limited-soy-wax",
            sku="LSO-001",
            price=Decimal("350.00"),
            stock_quantity=2,
        )
        self.client.force_login(self.customer)

    def test_checkout_success_decrements_stock(self):
        add_to_cart(self.client, self.product, quantity=1)
        resp = self.client.post("/checkout/", checkout_payload(), follow=False)
        self.assertEqual(resp.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 1)
        self.assertTrue(Order.objects.filter(customer=self.customer).exists())

    def test_checkout_fails_when_cart_exceeds_stock(self):
        add_to_cart(self.client, self.product, quantity=3)
        resp = self.client.post("/checkout/", checkout_payload())
        self.assertEqual(resp.status_code, 200)
        errors = [m.message for m in resp.context["messages"] if m.level_tag == "error"]
        self.assertTrue(any("stock" in e.lower() for e in errors))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())


class CheckoutScreenshotValidationTest(TestCase):
    def setUp(self):
        self.seller_user, self.seller_profile = make_seller("seller_ss")
        self.customer = make_user("buyer_ss")
        Category.objects.create(name="Screenshot Cat", slug="screenshot-cat")
        self.product = Product.objects.create(
            seller=self.seller_profile,
            category=Category.objects.get(slug="screenshot-cat"),
            name="Scented Wax",
            slug="scented-wax",
            sku="SCENT-001",
            price=Decimal("500.00"),
            stock_quantity=5,
        )
        self.client.force_login(self.customer)
        add_to_cart(self.client, self.product, quantity=1)

    def _checkout_with_screenshot(self, payload, screenshot):
        """Post checkout with a screenshot file (passed in data dict)."""
        payload = dict(payload)
        payload["payment_screenshot"] = screenshot
        return self.client.post("/checkout/", payload, follow=False)

    def test_checkout_accepts_valid_screenshot(self):
        resp = self._checkout_with_screenshot(
            checkout_payload({"full_name": "Sita Gurung"}), valid_png()
        )
        self.assertEqual(resp.status_code, 302)
        order = Order.objects.get(customer=self.customer)
        self.assertIsNotNone(order.payment_screenshot)

    def test_checkout_rejects_oversized_screenshot(self):
        resp = self._checkout_with_screenshot(
            checkout_payload({"full_name": "Sita Gurung"}), oversized_png()
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())
        errors = [m.message for m in resp.context["messages"] if m.level_tag == "error"]
        self.assertTrue(any("5 MB" in e or "screenshot" in e.lower() for e in errors))

    def test_checkout_rejects_invalid_screenshot(self):
        resp = self._checkout_with_screenshot(
            checkout_payload({"full_name": "Sita Gurung"}), fake_png()
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())
        errors = [m.message for m in resp.context["messages"] if m.level_tag == "error"]
        self.assertTrue(any("image" in e.lower() or "valid" in e.lower() for e in errors))
