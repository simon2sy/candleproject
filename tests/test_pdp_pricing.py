"""Product-detail pricing: every product shows its BASE price until a variant is chosen.

Regression guard for the bug where the first variant was auto-selected on page
load, which silently replaced ``product.price`` with the cheapest variant price
in the main price, the quantity totals and the sticky bar.
"""
import re
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Category, ProductVariant
from orders.models import CartItem
from orders.services import _display_price

from .helpers import make_product, make_seller


def _class_span(html, cls):
    m = re.search(r'<span class="%s"[^>]*>(.*?)</span>' % re.escape(cls), html, re.S)
    return m.group(1).strip() if m else None


def _elem_text(html, elem_id):
    m = re.search(r'<[^>]*id="%s"[^>]*>(.*?)</' % re.escape(elem_id), html, re.S)
    return m.group(1).strip() if m else None


def _attr_of(html, marker, attr):
    m = re.search(r"<[^>]*%s[^>]*>" % re.escape(marker), html, re.S)
    if not m:
        return None
    a = re.search(r'%s="([^"]*)"' % re.escape(attr), m.group(0))
    return a.group(1) if a else None


def _between(html, start, end):
    i = html.find(start)
    if i == -1:
        return ""
    j = html.find(end, i + len(start))
    return html[i:] if j == -1 else html[i:j]


def _inline_product_price(html):
    m = re.search(r"var productPrice = ([0-9.]+);", html)
    return m.group(1) if m else None


class ProductDetailBasePriceTests(TestCase):
    """Base price stands, and the variant prices stay optional."""

    def setUp(self):
        self.cat = Category.objects.create(name="Molds", slug="molds")
        _user, self.seller = make_seller("seller_pdp")
        # Base 500.00 with variants 450.00 / 500.00 / 600.00 — the cheapest one
        # (450.00) is exactly what the old auto-select logic used to show.
        self.product = make_product(self.seller, self.cat, name="Soy Wax Blend", sku="SOY-VAR", price="500.00")
        self.small = self._variant("Small", "SOY-VAR-S", "450.00")
        self.medium = self._variant("Medium", "SOY-VAR-M", "500.00")
        self.large = self._variant("Large", "SOY-VAR-L", "600.00")
        self.plain = make_product(self.seller, self.cat, name="Cotton Wick", sku="WICK-100", price="350.00")
        self.url = reverse("storefront:detail", args=[self.product.slug])

    def _variant(self, name, sku, price):
        return ProductVariant.objects.create(
            product=self.product, name=name, sku=sku, price=Decimal(price), stock_quantity=5
        )

    def _html(self, slug=None):
        res = self.client.get(reverse("storefront:detail", args=[slug or self.product.slug]))
        self.assertEqual(res.status_code, 200)
        return res.content.decode()

    # ------------------------------------------------------------------ detail page
    def test_detail_shows_base_price_before_any_variant_is_picked(self):
        html = self._html()
        self.assertEqual(_class_span(html, "pdp-price"), "Rs 500.00")
        self.assertEqual(_elem_text(html, "desktopTotal"), "Rs 500.00")
        self.assertEqual(_elem_text(html, "barTotal"), "Rs 500.00")
        self.assertEqual(_attr_of(html, 'class="pdp-sticky-bar"', "data-unit-price"), "500.00")
        self.assertEqual(_attr_of(html, 'id="desktopTotal"', "data-price"), "500.00")
        self.assertEqual(_inline_product_price(html), "500.00")
        self.assertNotIn("Rs 450.00", _class_span(html, "pdp-price") or "")

    def test_no_variant_is_preselected_on_load(self):
        variants = _between(self._html(), "<!-- Variants -->", "<!-- Offers -->")
        self.assertNotEqual(variants, "")
        self.assertNotIn("checked", variants)
        self.assertNotIn('class="pdp-variant-btn active', variants)

    def test_variant_prices_are_still_offered(self):
        variants = _between(self._html(), "<!-- Variants -->", "<!-- Offers -->")
        self.assertIn('data-price="450.00"', variants)
        self.assertIn("Small — Rs 450.00", variants)
        self.assertIn("Large — Rs 600.00", variants)

    def test_hidden_variant_selects_default_to_empty(self):
        html = self._html()
        for marker in ('id="desktopVariant"', 'id="mobileVariant"'):
            block = _between(html, marker, "</select>")
            self.assertIn('<option value=""></option>', block)
        self.assertIn(
            '<option value="%d">Small</option>' % self.small.id,
            _between(html, 'id="desktopVariant"', "</select>"),
        )
        self.assertIn(
            '<option value="%d">Large</option>' % self.large.id,
            _between(html, 'id="mobileVariant"', "</select>"),
        )

    def test_detail_without_variants_keeps_base_price(self):
        html = self._html(self.plain.slug)
        self.assertEqual(_class_span(html, "pdp-price"), "Rs 350.00")
        self.assertEqual(_elem_text(html, "desktopTotal"), "Rs 350.00")
        self.assertEqual(_attr_of(html, 'class="pdp-sticky-bar"', "data-unit-price"), "350.00")
        self.assertEqual(_inline_product_price(html), "350.00")
        self.assertNotIn('id="desktopVariant"', html)
        self.assertNotIn('id="mobileVariant"', html)

    # ------------------------------------------------------------------ product cards
    def test_card_shows_base_price_not_a_variant_price(self):
        res = self.client.get(reverse("storefront:home"))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn('<div class="price">Rs 500.00</div>', html)
        self.assertNotIn("Rs 450.00", html)
        self.assertNotIn("Rs 600.00", html)


class CartVariantPricingTests(TestCase):
    """Cart and order charge the base price until a variant is actually sent."""

    def setUp(self):
        self.cat = Category.objects.create(name="Molds", slug="molds")
        _user, self.seller = make_seller("seller_cart")
        self.product = make_product(self.seller, self.cat, name="Soy Wax Blend", sku="SOY-VAR", price="500.00")
        self.large = ProductVariant.objects.create(
            product=self.product, name="Large", sku="SOY-VAR-L", price=Decimal("600.00"), stock_quantity=5
        )
        self.buyer = User.objects.create_user(
            username="pdp_buyer", email="pdp_buyer@example.com",
            password="Testpass123!", role=User.Roles.CUSTOMER,
        )
        self.client.force_login(self.buyer)

    def _add(self, **data):
        return self.client.post(reverse("storefront:cart-add", args=[self.product.id]), data)

    def test_empty_variant_charges_base_price(self):
        res = self._add(quantity="1", variant="")
        self.assertEqual(res.status_code, 302)
        item = CartItem.objects.get(cart__user=self.buyer, product=self.product, variant__isnull=True)
        self.assertEqual(item.unit_price, Decimal("500.00"))
        self.assertEqual(item.line_total, Decimal("500.00"))
        self.assertEqual(_display_price(item), Decimal("500.00"))

        html = self.client.get(reverse("storefront:cart")).content.decode()
        self.assertIn("Rs 500.00", html)

    def test_selected_variant_charges_its_own_price(self):
        res = self._add(quantity="1", variant=str(self.large.id))
        self.assertEqual(res.status_code, 302)
        item = CartItem.objects.get(cart__user=self.buyer, product=self.product, variant=self.large)
        self.assertEqual(item.unit_price, Decimal("600.00"))
        self.assertEqual(item.line_total, Decimal("600.00"))
        self.assertEqual(_display_price(item), Decimal("600.00"))


class BasePriceOptionTests(TestCase):
    """The base price is a selectable option, so a picked variant can be undone.

    Without it a customer had to leave the page to get back to the base price
    after clicking any variant.
    """

    def setUp(self):
        self.cat = Category.objects.create(name="Molds", slug="molds")
        _user, self.seller = make_seller("seller_base")
        self.product = make_product(self.seller, self.cat, name="Soy Wax Blend", sku="SOY-BASE", price="500.00")
        self.large = ProductVariant.objects.create(
            product=self.product, name="Large", sku="SOY-BASE-L", price=Decimal("600.00"), stock_quantity=5
        )
        self.plain = make_product(self.seller, self.cat, name="Cotton Wick", sku="WICK-BASE", price="350.00")

    def _options(self, slug):
        res = self.client.get(reverse("storefront:detail", args=[slug]))
        self.assertEqual(res.status_code, 200)
        return _between(res.content.decode(), '<div class="pdp-variant-options">', "</div>")

    def _base_input(self, options):
        m = re.search(r'<input type="radio" name="variant" value=""[^>]*>', options)
        self.assertIsNotNone(m, "the base-price option is missing from the variant picker")
        return m.group(0)

    def test_base_price_is_a_choice_in_the_variant_picker(self):
        options = self._options(self.product.slug)
        self.assertIn("Base price — Rs 500.00", options)
        self.assertIn('data-price="500.00"', self._base_input(options))
        # Empty value -> cart_add treats it as the base price (no variant).
        self.assertIn('value=""', self._base_input(options))

    def test_base_price_choice_is_not_preselected(self):
        options = self._options(self.product.slug)
        self.assertNotIn("checked", options)
        self.assertNotIn("pdp-variant-btn active", options)

    def test_base_price_choice_comes_before_the_variants(self):
        options = self._options(self.product.slug)
        self.assertLess(options.index("Base price"), options.index("Large"))

    def test_base_price_choice_is_disabled_only_when_the_base_is_out_of_stock(self):
        self.product.stock_quantity = 0
        self.product.save(update_fields=["stock_quantity"])
        options = self._options(self.product.slug)
        self.assertIn("disabled", self._base_input(options))
        large = re.search(r'<input type="radio" name="variant" value="%d"[^>]*>' % self.large.id, options)
        self.assertNotIn("disabled", large.group(0))

    def test_no_base_price_choice_without_variants(self):
        html = self.client.get(reverse("storefront:detail", args=[self.plain.slug])).content.decode()
        # The class name also lives in the page's <style> block, so match the markup.
        self.assertNotIn('<div class="pdp-variant-options">', html)
        self.assertNotIn("Base price —", html)
        self.assertEqual(_class_span(html, "pdp-price"), "Rs 350.00")

    def test_choosing_the_base_price_again_charges_the_base_price(self):
        self.assertIn('value=""', self._base_input(self._options(self.product.slug)))
        buyer = User.objects.create_user(
            username="base_buyer", email="base_buyer@example.com",
            password="Testpass123!", role=User.Roles.CUSTOMER,
        )
        self.client.force_login(buyer)
        self.client.post(reverse("storefront:cart-add", args=[self.product.id]), {"quantity": "1", "variant": ""})
        item = CartItem.objects.get(cart__user=buyer)
        self.assertIsNone(item.variant)
        self.assertEqual(_display_price(item), Decimal("500.00"))

