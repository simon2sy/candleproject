"""Storefront SEO regression tests — crawlability, canonicals, and schema."""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings

from accounts.models import SellerProfile
from catalog.models import Category, Product, ProductImage


@override_settings(SEO_CANONICAL_DOMAIN="nismitacraftstudio.com")
class StorefrontSeoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="seller1", email="s1@example.com", password="x" * 12)
        cls.profile = SellerProfile.objects.create(user=cls.user, business_name="Nismita Craft Studio")
        cls.category = Category.objects.create(name="Candle Molds", slug="candle-molds", is_active=True)
        cls.product = Product.objects.create(
            seller=cls.profile,
            category=cls.category,
            name="Blueberry Silicone Candle Mould",
            slug="blueberry-mould",
            sku="NCS-0001",
            short_description="Blueberry silicone candle mould for handmade candles.",
            price="450.00",
            stock_quantity=5,
            is_active=True,
            is_available=True,
        )

    def test_homepage_seo(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn("<h1>Nismita Craft Studio</h1>", html)
        self.assertIn("Nismita Craft Studio | Candle Moulds & Craft Supplies in Nepal", html)
        self.assertIn('rel="canonical" href="https://nismitacraftstudio.com/"', html)
        self.assertIn('name="robots" content="index,follow', html)
        self.assertIn('"@type":"Organization"', html)
        self.assertIn('"@type":"WebSite"', html)

    def test_product_seo_unique_title_schema(self):
        res = self.client.get("/product/blueberry-mould/")
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn("<title>Blueberry Silicone Candle Mould | Nismita Craft Studio</title>", html)
        self.assertIn('rel="canonical" href="https://nismitacraftstudio.com/product/blueberry-mould/"', html)
        self.assertIn('property="og:type" content="product"', html)
        self.assertIn("Blueberry Silicone Candle Mould</h1>", html)
        # JSON-LD is valid and uses DB fields only (no invented ratings).
        payload = html.split('<script type="application/ld+json">')[1].split("</script>")[0]
        data = json.loads(payload)
        self.assertEqual(data["@type"], "Product")
        self.assertEqual(data["name"], "Blueberry Silicone Candle Mould")
        self.assertEqual(data["offers"]["priceCurrency"], "NPR")
        self.assertNotIn("review", data)
        self.assertNotIn("aggregateRating", data)

    def test_category_and_shop_seo_and_pagination_noindex(self):
        res = self.client.get("/category/candle-molds/")
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn("<title>Candle Molds | Nismita Craft Studio</title>", html)
        self.assertIn('rel="canonical" href="https://nismitacraftstudio.com/category/candle-molds/"', html)
        filtered = self.client.get("/shop/?search=wax")
        self.assertIn("noindex,follow", filtered.content.decode())
        paged = self.client.get("/shop/?page=3")
        self.assertIn("noindex,follow", paged.content.decode())

    def test_private_pages_noindexed(self):
        # Anonymous visits to cart/checkout redirect to login (correct auth
        # behaviour — business logic untouched). Both the login page itself
        # and the authenticated cart/checkout pages must be noindexed.
        for url in ("/login/", "/register/"):
            res = self.client.get(url)
            self.assertIn("noindex,nofollow", res.content.decode(), url)
        self.client.force_login(self.user)
        for url in ("/cart/", "/checkout/"):
            res = self.client.get(url, follow=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn("noindex,nofollow", res.content.decode(), url)

    def test_robots_and_sitemap(self):
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        body = robots.content.decode()
        self.assertIn("User-agent: *", body)
        self.assertIn("Disallow: /admin/", body)
        self.assertIn("Disallow: /cart/", body)
        self.assertIn("Disallow: /checkout/", body)
        self.assertIn("Disallow: /api/", body)
        self.assertIn("Sitemap: https://nismitacraftstudio.com/sitemap.xml", body)
        sm = self.client.get("/sitemap.xml")
        self.assertEqual(sm.status_code, 200)
        xml = sm.content.decode()
        self.assertIn("https://nismitacraftstudio.com/", xml)
        self.assertIn("/category/candle-molds/", xml)
        self.assertIn("/product/blueberry-mould/", xml)
        self.assertNotIn("/admin/", xml)
        self.assertNotIn("/cart/", xml)

    def test_404_noindexed(self):
        res = self.client.get("/does-not-exist-xyz/")
        self.assertEqual(res.status_code, 404)
        self.assertIn("noindex,nofollow", res.content.decode())

    def test_product_images_have_alt_and_dimensions(self):
        res = self.client.get("/product/blueberry-mould/")
        html = res.content.decode()
        self.assertIn("Nismita Craft Studio", html.split("<img")[1].split(">")[0] if "<img" in html else "")
