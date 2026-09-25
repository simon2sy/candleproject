"""Catalog isolation, filtering, privacy, wishlist, order tests."""
from decimal import Decimal

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import Address, User
from catalog.models import Category, Product
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


class DashboardProductPhotoTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="photo_admin", email="photo_admin@example.com",
            password="Testpass123!", is_staff=True,
        )
        self.category = Category.objects.create(name="Photos", slug="photos")
        self.client.force_login(self.staff)

    def _file(self, name, image_format="PNG"):
        image = Image.new("RGB", (20, 20), "red")
        output = BytesIO()
        image.save(output, format=image_format)
        return SimpleUploadedFile(name, output.getvalue(), content_type=f"image/{image_format.lower()}")

    def test_dashboard_stores_multiple_photos_and_renders_thumbnails(self):
        response = self.client.post(reverse("storefront:dashboard-add-product"), {
            "name": "Photo set", "category": self.category.pk, "price": "12.50", "stock": "2",
            "images": [self._file("one.png"), self._file("two.jpg", "JPEG")],
        })
        self.assertRedirects(response, reverse("storefront:dashboard-products"))
        product = Product.objects.get(name="Photo set")
        self.assertEqual(product.images.count(), 2)
        self.assertEqual(list(product.images.values_list("display_order", flat=True)), [0, 1])
        self.assertEqual(list(product.images.values_list("is_primary", flat=True)), [True, False])
        session = self.client.session
        session["customer_preview"] = True
        session.save()
        detail = self.client.get(reverse("storefront:detail", kwargs={"slug": product.slug}))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "data-image-src=", count=2)

    def test_dashboard_rejects_invalid_image(self):
        response = self.client.post(reverse("storefront:dashboard-add-product"), {
            "name": "Bad photo", "category": self.category.pk, "price": "12.50", "stock": "2",
            "images": SimpleUploadedFile("payload.svg", b"<svg onload=alert(1)>", content_type="image/svg+xml"),
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload a valid JPG, PNG or WebP image.")
        self.assertFalse(Product.objects.filter(name="Bad photo").exists())

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse("storefront:logout")).status_code, 405)
        response = self.client.post(reverse("storefront:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


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
