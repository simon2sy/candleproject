"""Shared SEO context for every storefront template.

Provides ``canonical_url`` (HTTPS + preferred domain, no query strings),
``seo_robots_extra`` (used to keep paginated/filtered duplicates out of the
index) and Open Graph helpers without touching business logic.
"""
from __future__ import annotations

from .seo import DEFAULT_OG_IMAGE, absolute_url, canonical_domain, canonical_url


def _robots_extra(request) -> str:
    params = request.GET
    if not params:
        return ""
    # Only page=1 is canonical-adjacent; deeper pages and filtered/sorted
    # views are duplicates of page 1 and should not be indexed separately.
    page = (params.get("page") or "").strip()
    filter_keys = {"search", "min_price", "max_price", "ordering"}
    if any((params.get(k) or "").strip() for k in filter_keys):
        return "noindex,follow"
    if page and page != "1":
        return "noindex,follow"
    return ""


def seo(request):
    path = request.path or "/"
    return {
        "canonical_url": canonical_url(request, path),
        "canonical_domain": canonical_domain(),
        "seo_robots_extra": _robots_extra(request),
        "og_image_default": absolute_url(request, DEFAULT_OG_IMAGE),
    }
