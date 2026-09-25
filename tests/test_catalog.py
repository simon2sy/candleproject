"""Catalog isolation, filtering, privacy, wishlist, order tests."""
from decimal import Decimal

from accounts.models import Address
from catalog.models import Category
from django.test import TestCase
from orders.models import Order, OrderItem, Wishlist, WishlistItem
from rest_framework.test import APIClient

from .helpers import login, make_product, make_seller, make_user


class CatalogIsolationTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Molds", slug="molds")
        self.u_a, self.p_a = make_seller("seller_a")
        self.u_b, self.p_b = make_seller("seller_b")
        self.prod_a = make_product(self.p_a, self.cat, name="Mold A", sku="MOLD-A")
        self.ca = login(APIClient(), "seller_a")
        self.cb = login(APIClient(), "seller_b")

    def test_category_creation_requires_admin(self):
        res = self.ca.post("/api/v1/categories/", {"name": "X", "slug": "x"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_seller_a_cannot_edit_seller_b_product(self):
        res = self.cb.patch(f"/api/v1/products/{self.prod_a.slug}/", {"price": "999.00"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_product_filtering_search_ordering(self):
        make_product(self.p_a, self.cat, name="Soy Wax 500g", sku="SOY-500", price="350.00")
        make_product(self.p_a, self.cat, name="Soy Wax 1kg", sku="SOY-1000", price="650.00")
        res = self.ca.get("/api/v1/products/?search=Soy&ordering=price")
        self.assertEqual(res.status_code, 200)
        prices = [float(r["price"]) for r in res.data["results"]]
        self.assertEqual(prices, sorted(prices))
        res2 = self.ca.get("/api/v1/products/?min_price=400&max_price=700")
        self.assertTrue(all(400 <= float(r["price"]) <= 700 for r in res2.data["results"]))


class PrivacyTests(TestCase):
    def test_customer_a_cannot_view_customer_b_addresses(self):
        make_user("cust_a")
        b = make_user("cust_b")
        Address.objects.create(user=b, full_name="B", phone="1", address_line_1="St",
                               city="C", country="X", postal_code="1")
        c = login(APIClient(), "cust_a")
        res = c.get("/api/v1/addresses/")
        self.assertEqual(res.status_code, 200)
        rows = res.data["results"] if isinstance(res.data, dict) else res.data
        self.assertEqual(rows, [])

    def test_single_default_address(self):
        u = make_user("cust_c")
        Address.objects.create(user=u, full_name="C", phone="1", address_line_1="S1",
                               city="C", country="X", postal_code="1", is_default=True)
        Address.objects.create(user=u, full_name="C", phone="1", address_line_1="S2",
                               city="C", country="X", postal_code="1", is_default=True)
        self.assertEqual(Address.objects.filter(user=u, is_default=True).count(), 1)


class WishlistOrderTests(TestCase):
    def test_wishlist_no_duplicates(self):
        u = make_user("w1")
        _, prof = make_seller("ws")
        cat = Category.objects.create(name="Wax", slug="wax")
        prod = make_product(prof, cat)
        wl, _ = Wishlist.objects.get_or_create(user=u)
        WishlistItem.objects.get_or_create(wishlist=wl, product=prod)
        _, created = WishlistItem.objects.get_or_create(wishlist=wl, product=prod)
        self.assertFalse(created)
        self.assertEqual(wl.items.count(), 1)

    def test_order_snapshot_totals(self):
        cust = make_user("buyer2")
        _, prof = make_seller("os")
        cat = Category.objects.create(name="Wicks", slug="wicks")
        prod = make_product(prof, cat, name="Wick", sku="WICK-1", price="100.00")
        order = Order.objects.create(customer=cust, order_number="ORD-TEST-1")
        OrderItem.objects.create(order=order, product=prod, seller=prof, product_name=prod.name,
                                 sku=prod.sku, quantity=2, unit_price=prod.price)
        order.recalculate()
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.subtotal, Decimal("200.00"))
        self.assertEqual(order.total, Decimal("200.00"))
        prod.price = Decimal("999.00")
        prod.save()
        self.assertEqual(order.items.get().unit_price, Decimal("100.00"))
