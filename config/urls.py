"""URL configuration for config project."""
import re

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.shortcuts import render

from config.health import healthz, readyz
from storefront.seo import canonical_base
from storefront.sitemaps import CategorySitemap, ProductSitemap, StaticViewSitemap

SITEMAPS = {
    "pages": StaticViewSitemap,
    "products": ProductSitemap,
    "categories": CategorySitemap,
}


def robots_txt(request):
    # Public pages are fully crawlable. Private / transactional / internal
    # areas are disallowed so Google never indexes cart, checkout, accounts,
    # orders, staff tools, APIs or auth flows. The sitemap URL is absolute
    # on the canonical HTTPS domain (never the request/dev host).
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
        "Disallow: /login/",
        "Disallow: /register/",
        "Disallow: /logout/",
        "Disallow: /payment/",
        "Disallow: /api/",
        "",
        f"Sitemap: {canonical_base()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")

# Single-seller store: the admin is the supplier, so brand the admin as such.
admin.site.site_header = "Nismita Craft Studio — Supplier Admin"
admin.site.site_title = "Nismita Supplier Admin"
admin.site.index_title = "Manage catalogue, orders & customers"


def handler404_view(request, exception):
    response = render(request, "storefront/404.html", status=404)
    # Keep error pages out of the index without touching security settings.
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def handler500_view(request):
    response = render(request, "storefront/500.html", status=500)
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


handler404 = handler404_view
handler500 = handler500_view

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path("admin/", admin.site.urls),
    path("robots.txt", robots_txt, name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="django.contrib.sitemaps.views.sitemap"),
    path("api/v1/", include("config.api_v1")),
    path("", include("storefront.urls")),
]

# Serve public uploads (product, category and seller images) in development.
# Payment screenshots are NOT here: they live in PRIVATE_MEDIA_ROOT, outside
# MEDIA_ROOT, and are streamed only by the authenticated views in storefront.
# In production a web server should serve MEDIA_URL instead (and never expose
# PRIVATE_MEDIA_ROOT).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


