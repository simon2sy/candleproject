"""Storefront SEO regression tests — crawlability, canonicals, and schema."""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings

from accounts.models import SellerProfile
from catalog.models import Category, Product


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
        self.assertIn('name="description"', html)
        # Exact required homepage description.
        self.assertIn(
            "Nismita Craft Studio offers candle moulds, wax, wicks, colours "
            "and craft supplies in Nepal. Shop candle-making materials online "
            "with delivery across Nepal.",
            html,
        )
        # The misspelled brand must never appear anywhere in the output.
        self.assertNotIn("Nisha", html)

    def test_homepage_explains_business_and_links_categories(self):
        html = self.client.get("/").content.decode()
        self.assertIn("Kathmandu-based candle-making supplies business", html)
        self.assertIn("/category/candle-molds/", html)
        self.assertIn("/about/", html)
        self.assertIn("/contact/", html)

    def test_site_schema_is_emitted_exactly_once(self):
        """No duplicate or conflicting Organization/WebSite entities."""
        for url in ("/", "/shop/", "/category/candle-molds/", "/about/", "/contact/"):
            html = self.client.get(url).content.decode()
            self.assertEqual(html.count('"@type":"Organization"'), 1, url)
            self.assertEqual(html.count('"@type":"WebSite"'), 1, url)
            # Every JSON-LD block must be valid JSON.
            blocks = html.split('<script type="application/ld+json">')[1:]
            self.assertTrue(blocks, url)
            for raw in (b.split("</script>")[0] for b in blocks):
                json.loads(raw)

    def test_canonical_is_never_localhost_or_http(self):
        for url in ("/", "/shop/", "/about/", "/contact/", "/category/candle-molds/",
                    "/product/blueberry-mould/"):
            html = self.client.get(url).content.decode()
            head = html.split("</head>")[0]
            self.assertIn('rel="canonical" href="https://nismitacraftstudio.com', html, url)
            self.assertNotIn('href="http://', head, url)
            self.assertNotIn("testserver", head, url)
            self.assertNotIn("127.0.0.1", head, url)
            self.assertNotIn("Nisha", html, url)

    def test_www_redirects_to_canonical_host(self):
        res = self.client.get("/", headers={"host": "www.nismitacraftstudio.com"})
        self.assertEqual(res.status_code, 301)
        self.assertEqual(res["Location"], "https://nismitacraftstudio.com/")

    def test_organization_website_and_localbusiness_content(self):
        html = self.client.get("/").content.decode()
        payload = html.split('<script type="application/ld+json">')[1].split("</script>")[0]
        data = json.loads(payload)
        nodes = {n["@type"]: n for n in data["@graph"]}
        org = nodes["Organization"]
        self.assertEqual(org["@id"], "https://nismitacraftstudio.com/#organization")
        self.assertEqual(org["name"], "Nismita Craft Studio")
        self.assertEqual(org["url"], "https://nismitacraftstudio.com/")
        self.assertIn("https://www.instagram.com/nismita_craft_studio/", org["sameAs"])
        site = nodes["WebSite"]
        self.assertEqual(site["@id"], "https://nismitacraftstudio.com/#website")
        self.assertEqual(
            site["publisher"], {"@id": "https://nismitacraftstudio.com/#organization"}
        )

        # Contact page carries the local business entity with real NAP data.
        contact = self.client.get("/contact/").content.decode()
        self.assertIn('"@type":["LocalBusiness","Store"]', contact)
        self.assertIn("Narephate - 32", contact)
        self.assertIn("+977 970-8909514", contact)
        self.assertIn("Kathmandu", contact)
        # No invented opening hours / ratings anywhere.
        self.assertNotIn("openingHours", contact)
        self.assertNotIn("aggregateRating", contact)
        self.assertNotIn('"@type":"Review"', contact)

    def test_website_searchaction_matches_real_search_url(self):
        html = self.client.get("/").content.decode()
        payload = html.split('<script type="application/ld+json">')[1].split("</script>")[0]
        data = json.loads(payload)
        site = {n["@type"]: n for n in data["@graph"]}["WebSite"]
        action = site["potentialAction"]
        self.assertEqual(action["@type"], "SearchAction")
        self.assertEqual(
            action["target"]["urlTemplate"],
            "https://nismitacraftstudio.com/shop/?search={search_term_string}",
        )
        self.assertEqual(action["query-input"], "required name=search_term_string")

    def test_product_seo_unique_title_schema(self):
        res = self.client.get("/product/blueberry-mould/")
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn(
            "<title>Blueberry Silicone Candle Mould | Nismita Craft Studio Nepal</title>",
            html,
        )
        self.assertIn('rel="canonical" href="https://nismitacraftstudio.com/product/blueberry-mould/"', html)
        self.assertIn('property="og:type" content="product"', html)
        self.assertIn("Blueberry Silicone Candle Mould</h1>", html)
        # JSON-LD is valid and uses DB fields only (no invented ratings).
        payload = html.split('<script type="application/ld+json">')[2].split("</script>")[0]
        data = json.loads(payload)
        nodes = data["@graph"]
        product = next(n for n in nodes if n["@type"] == "Product")
        self.assertEqual(product["name"], "Blueberry Silicone Candle Mould")
        self.assertEqual(product["sku"], "NCS-0001")
        self.assertEqual(product["brand"], {"@type": "Brand", "name": "Nismita Craft Studio"})
        self.assertEqual(product["offers"]["priceCurrency"], "NPR")
        self.assertEqual(product["offers"]["price"], "450.00")
        self.assertIn(
            product["offers"]["availability"],
            ("https://schema.org/InStock", "https://schema.org/OutOfStock"),
        )
        self.assertNotIn("review", product)
        self.assertNotIn("aggregateRating", product)
        self.assertEqual(
            next(n for n in nodes if n["@type"] == "BreadcrumbList")["@id"],
            "https://nismitacraftstudio.com/product/blueberry-mould/#breadcrumb",
        )

    def test_category_seo_and_shop_seo_and_pagination_noindex(self):
        res = self.client.get("/category/candle-molds/")
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn("<title>Candle Moulds in Nepal | Nismita Craft Studio</title>", html)
        self.assertIn("<h1>Candle Moulds in Nepal</h1>", html)
        self.assertIn('rel="canonical" href="https://nismitacraftstudio.com/category/candle-molds/"', html)
        # Useful, original copy rather than a keyword shell.
        self.assertIn("Why silicone moulds are the most forgiving choice", html)
        self.assertIn("How to choose a mould that suits your wax", html)
        self.assertIn('"@type":"ItemList"', html)

        shop = self.client.get("/shop/").content.decode()
        self.assertIn(
            "<title>Shop Candle Making Supplies in Nepal | Nismita Craft Studio</title>",
            shop,
        )
        self.assertIn("<h1>Candle Making Supplies in Nepal</h1>", shop)

        filtered = self.client.get("/shop/?search=wax")
        self.assertIn("noindex,follow", filtered.content.decode())
        paged = self.client.get("/shop/?page=3")
        self.assertIn("noindex,follow", paged.content.decode())

    def test_every_category_gets_unique_title_and_h1(self):
        active = list(Category.objects.filter(is_active=True))
        titles, h1s = set(), set()
        for c in active:
            html = self.client.get(f"/category/{c.slug}/").content.decode()
            titles.add(html.split("<title>")[1].split("</title>")[0])
            h1s.add(html.split("<h1>")[1].split("</h1>")[0])
            self.assertIn("Nismita Craft Studio", html)
            self.assertNotIn("Nisha", html)
        self.assertEqual(len(titles), len(active))
        self.assertEqual(len(h1s), len(active))

    def test_no_unsupported_best_claims_in_seo_copy(self):
        banned = ["best candle mould", "best in nepal", "no.1 in nepal", "number one in nepal"]
        for url in ("/", "/shop/", "/about/", "/contact/", "/category/candle-molds/"):
            html = self.client.get(url).content.decode().lower()
            for phrase in banned:
                self.assertNotIn(phrase, html, f"{url} -> {phrase}")

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
