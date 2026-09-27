from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalog.models import Category, Product
from storefront.seo import canonical_domain


class _CanonicalSitemap(Sitemap):
    """Sitemap base pinned to the canonical HTTPS production domain.

    Django's default derives ``<loc>`` hosts from Sites/requests, which can
    leak ``testserver`` or dev hosts.  Overriding ``get_domain`` keeps every
    URL on the preferred production domain.
    """

    protocol = "https"

    def get_domain(self, site=None):
        return canonical_domain()


class StaticViewSitemap(_CanonicalSitemap):
    changefreq = "weekly"

    def items(self):
        return [
            ("storefront:home", 1.0),
            ("storefront:shop", 0.8),
            ("storefront:about", 0.7),
            ("storefront:contact", 0.7),
        ]

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]

    


class ProductSitemap(_CanonicalSitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        # Only indexable products: active AND available. Disabled /
        # unavailable products stay out of the sitemap (their pages still
        # render with an accurate OutOfStock Offer when visited directly).
        return (
            Product.objects.filter(is_active=True, is_available=True)
            .order_by("slug")
            .only("slug", "updated_at")
        )

    def location(self, item):
        return reverse("storefront:detail", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated_at


class CategorySitemap(_CanonicalSitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        # Every active category is an indexable /category/<slug>/ page
        # (top-level and children all render through the shop view).
        return (
            Category.objects.filter(is_active=True)
            .order_by("slug")
            .only("slug", "updated_at")
        )

    def location(self, item):
        return reverse("storefront:category", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated_at
