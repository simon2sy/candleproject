from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalog.models import Category, Product


class StaticViewSitemap(Sitemap):
    protocol = "https"
    priority = 0.8
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

    


class ProductSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Product.objects.filter(is_active=True, is_available=True).only("slug", "updated_at")

    def location(self, item):
        return reverse("storefront:detail", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated_at


class CategorySitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Category.objects.filter(is_active=True, parent__isnull=True).only("slug", "updated_at")

    def location(self, item):
        return reverse("storefront:category", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated_at
