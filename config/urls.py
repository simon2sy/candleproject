"""URL configuration for config project."""
import re

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse

from config.health import healthz, readyz
from storefront.sitemaps import CategorySitemap, ProductSitemap, StaticViewSitemap

SITEMAPS = {
    "pages": StaticViewSitemap,
    "products": ProductSitemap,
    "categories": CategorySitemap,
}


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /dashboard/",
        "Disallow: /cart/",
        "Disallow: /checkout/",
        "Disallow: /orders/",
        "Disallow: /wishlist/",
        "Disallow: /customer-preview/",
        "Disallow: /api/",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")

# Single-seller store: the admin is the supplier, so brand the admin as such.
admin.site.site_header = "Nismita Craft Studio — Supplier Admin"
admin.site.site_title = "Nismita Supplier Admin"
admin.site.index_title = "Manage catalogue, orders & customers"

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path("admin/", admin.site.urls),
    path("robots.txt", robots_txt, name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="django.contrib.sitemaps.views.sitemap"),
    path("api/v1/", include("config.api_v1")),
    path("", include("storefront.urls")),
]

# Serve uploaded files (product images, payment screenshots) in development.
# In production a web server (nginx/WhiteNoise-compatible storage) should do this.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


