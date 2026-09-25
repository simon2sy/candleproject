from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalog.models import Category, Product


class StaticViewSitemap(Sitemap):
    protocol = "https"
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return ["storefront:home", "storefront:shop", "storefront:about", "storefront:contact"]

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Product.objects.filter(is_active=True, is_available=True).only("slug", "updated_at")

    def location(self, item):
        return reverse("storefront:detail", kwargs={"slug": item.slug})


class CategorySitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Category.objects.filter(is_active=True, parent__isnull=True).only("slug", "updated_at")

    def location(self, item):
        return reverse("storefront:category", kwargs={"slug": item.slug})
