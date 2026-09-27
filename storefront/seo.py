"""SEO helpers: canonical URLs, absolute URLs, and shared constants.

All public canonical URLs use HTTPS + the preferred production domain so
Google indexes one URL per page regardless of proxy scheme or dev hosts.
"""
from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings

PRODUCTION_DOMAIN = "nismitacraftstudio.com"
PRODUCTION_BASE = f"https://{PRODUCTION_DOMAIN}"
BRAND_NAME = "Nismita Craft Studio"
DEFAULT_OG_IMAGE = "/static/img/logo.png"


def canonical_domain() -> str:
    configured = str(getattr(settings, "SEO_CANONICAL_DOMAIN", "") or "").strip()
    if configured:
        return configured.lower()
    site_url = str(getattr(settings, "SEO_SITE_URL", "") or "").strip()
    if site_url:
        try:
            host = urlparse(site_url).hostname or ""
            if host:
                return host.lower()
        except ValueError:
            pass
    return PRODUCTION_DOMAIN


def canonical_base() -> str:
    return f"https://{canonical_domain()}"


def absolute_url(request, path: str) -> str:
    """Absolute HTTPS URL on the canonical domain (never testserver/dev)."""
    if not path.startswith("/"):
        path = f"/{path}"
    if request is not None:
        try:
            current = (request.get_host() or "").split(":")[0].lower()
        except Exception:  # pragma: no cover - defensive
            current = ""
        # In local development keep the local host so previews/tests work.
        if settings.DEBUG and current in {"localhost", "127.0.0.1", "[::1]", "testserver"}:
            scheme = request.scheme if request.scheme in ("http", "https") else "http"
            return f"{scheme}://{request.get_host()}{path}"
    return f"{canonical_base()}{path}"


def canonical_url(request, path: str | None = None) -> str:
    return absolute_url(request, path if path is not None else request.path)
