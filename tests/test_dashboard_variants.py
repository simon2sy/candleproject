"""Dashboard: adding a product can also add its variants (price + quantity).

Covers the repeated variant rows on the dashboard add-product form, the plain
per-row validation messages, and that what the seller types there is sellable
on the customer-facing product page.
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Category, Product
from orders.models import CartItem

from .helpers import make_user


class DashboardVariantTests(TestCase):
    """The add-product form posts repeated name / price / quantity rows."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="variant_admin", email="variant_admin@example.com",
            password="Testpass123!", is_staff=True,
        )
        self.category = Category.objects.create(name="Candles", slug="candles")
        self.client.force_login(self.staff)
        self.url = reverse("storefront:dashboard-add-product")

    def _post(self, **extra):
        data = {"name": "Soy Wax Blend", "category": self.category.pk, "price": "500.00", "stock": "10"}
        data.update(extra)
        return self.client.post(self.url, data)

    # ------------------------------------------------------------------ page
    def test_add_page_offers_a_variant_row(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn("id='ap-variants'", html)
        self.assertIn("name='variant_name'", html)
        self.assertIn("name='variant_price'", html)
        self.assertIn("name='variant_stock'", html)
        self.assertIn("id='ap-variant-add'", html)

    # ------------------------------------------------------------------ happy path
    def test_variants_are_saved_with_their_price_and_quantity(self):
        res = self._post(
            variant_name=["Small", "Large"],
            variant_price=["450.00", "600.00"],
            variant_stock=["3", "7"],
        )
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        product = Product.objects.get(name="Soy Wax Blend")
        self.assertEqual(product.price, Decimal("500.00"))  # base price untouched
        variants = list(product.variants.order_by("price"))
        self.assertEqual([v.name for v in variants], ["Small", "Large"])
        self.assertEqual([v.price for v in variants], [Decimal("450.00"), Decimal("600.00")])
        self.assertEqual([v.stock_quantity for v in variants], [3, 7])
        self.assertTrue(all(v.is_active for v in variants))

    def test_every_variant_gets_its_own_sku(self):
        self._post(variant_name=["Small", "Large"], variant_price=["450.00", "600.00"], variant_stock=["1", "2"])
        product = Product.objects.get(name="Soy Wax Blend")
        skus = list(product.variants.values_list("sku", flat=True))
        self.assertEqual(len(skus), 2)
        self.assertEqual(len(set(skus)), 2)
        self.assertTrue(all(sku.startswith(product.sku) for sku in skus))

    def test_quantity_defaults_to_zero_when_left_empty(self):
        res = self._post(variant_name=["Large"], variant_price=["600.00"], variant_stock=[""])
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        self.assertEqual(Product.objects.get(name="Soy Wax Blend").variants.get().stock_quantity, 0)

    def test_untouched_rows_are_ignored(self):
        res = self._post(variant_name=["Large", ""], variant_price=["600.00", ""], variant_stock=["4", ""])
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        product = Product.objects.get(name="Soy Wax Blend")
        self.assertEqual(list(product.variants.values_list("name", flat=True)), ["Large"])

    def test_product_without_variants_still_works(self):
        res = self._post(variant_name=[""], variant_price=[""], variant_stock=[""])
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        self.assertEqual(Product.objects.get(name="Soy Wax Blend").variants.count(), 0)

    # ------------------------------------------------------------------ validation
    def test_missing_variant_price_stops_the_product(self):
        res = self._post(variant_name=["Large"], variant_price=[""], variant_stock=["5"])
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Variant 1: enter a price.")
        self.assertFalse(Product.objects.filter(name="Soy Wax Blend").exists())

    def test_variant_without_a_name_is_rejected(self):
        res = self._post(variant_name=[""], variant_price=["450.00"], variant_stock=["2"])
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Variant 1: enter a variant name.")
        self.assertFalse(Product.objects.filter(name="Soy Wax Blend").exists())

    def test_bad_variant_price_and_quantity_are_reported_per_row(self):
        res = self._post(
            variant_name=["Large", "Small"], variant_price=["abc", "400.00"], variant_stock=["5", "-2"],
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Variant 1: price must be a number like 999 or 999.50.")
        self.assertContains(res, "Variant 2: quantity must be a whole number of units (0 or more).")
        self.assertFalse(Product.objects.filter(name="Soy Wax Blend").exists())

    def test_duplicate_variant_names_are_rejected(self):
        res = self._post(
            variant_name=["Large", "large"], variant_price=["600.00", "650.00"], variant_stock=["2", "2"],
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Variant 2: “large” is already used — give every variant its own name.")
        self.assertFalse(Product.objects.filter(name="Soy Wax Blend").exists())

    def test_over_long_variant_name_is_rejected(self):
        res = self._post(variant_name=["L" * 256], variant_price=["600.00"], variant_stock=["1"])
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Variant 1: name is too long (255 characters max).")
        self.assertFalse(Product.objects.filter(name="Soy Wax Blend").exists())

    def test_huge_variant_price_is_rejected(self):
        res = self._post(variant_name=["Large"], variant_price=["999999999999"], variant_stock=["1"])
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Variant 1: price is too large.")
        self.assertFalse(Product.objects.filter(name="Soy Wax Blend").exists())

    def test_typed_variant_values_survive_an_error(self):
        res = self._post(variant_name=["Large"], variant_price=["abc"], variant_stock=["5"])
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "value='Large'")
        self.assertContains(res, "value='abc'")

    # ------------------------------------------------------------------ shop side
    def test_dashboard_variants_are_sellable_on_the_product_page(self):
        self._post(variant_name=["Small", "Large"], variant_price=["450.00", "600.00"], variant_stock=["3", "7"])
        product = Product.objects.get(name="Soy Wax Blend")
        large = product.variants.get(name="Large")

        session = self.client.session
        session["customer_preview"] = True
        session.save()
        html = self.client.get(reverse("storefront:detail", args=[product.slug])).content.decode()
        self.assertIn("Large — Rs 600.00", html)
        self.assertIn("Base price — Rs 500.00", html)

        buyer = make_user("variant_buyer")
        self.client.force_login(buyer)
        self.client.post(reverse("storefront:cart-add", args=[product.id]), {"quantity": "1", "variant": str(large.id)})
        item = CartItem.objects.get(cart__user=buyer)
        self.assertEqual(item.variant, large)
        self.assertEqual(item.unit_price, Decimal("600.00"))

    def test_new_product_is_listed_in_the_dashboard(self):
        self._post(variant_name=["Large"], variant_price=["600.00"], variant_stock=["4"])
        res = self.client.get(reverse("storefront:dashboard-products"))
        self.assertContains(res, "Soy Wax Blend")

    def test_product_list_shows_each_variant_with_price_and_stock(self):
        self._post(variant_name=["Small", "Large"], variant_price=["450.00", "600.00"], variant_stock=["3", "7"])
        res = self.client.get(reverse("storefront:dashboard-products"))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn(">Small<", html)
        self.assertIn(">Large<", html)
        self.assertIn("Rs 450.00", html)
        self.assertIn("Rs 600.00", html)
        self.assertIn("3 left", html)
        self.assertIn("7 left", html)

    def test_product_list_says_when_there_are_no_variants(self):
        self._post()
        res = self.client.get(reverse("storefront:dashboard-products"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Base price only")
