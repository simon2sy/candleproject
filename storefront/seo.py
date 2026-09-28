"""SEO helpers: canonical URLs, absolute URLs, brand constants and schema.

Every public canonical URL is built from ``settings.SEO_CANONICAL_DOMAIN``
(production default ``nismitacraftstudio.com``) so Google only ever indexes
one HTTPS URL per page — never ``localhost``, ``127.0.0.1`` or ``testserver``.

Only facts that are actually true for the business are stored here (brand
name, the real Instagram/TikTok profiles, the Kathmandu address and the
WhatsApp/phone number that already appear on the site).  Nothing about
ratings, reviews, opening hours, prices or awards is invented.
"""
from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings

PRODUCTION_DOMAIN = "nismitacraftstudio.com"
PRODUCTION_BASE = f"https://{PRODUCTION_DOMAIN}"
BRAND_NAME = "Nismita Craft Studio"
DEFAULT_OG_IMAGE = "/static/img/logo.png"

# --- Real, publicly listed business facts (keep in sync with the site) -------
BUSINESS_PHONE = "+977-970-8909514"
BUSINESS_PHONE_E164 = "+9779708909514"
BUSINESS_WHATSAPP = "https://wa.me/9779708909514"
BUSINESS_STREET = "Narephate - 32"
BUSINESS_CITY = "Kathmandu"
BUSINESS_REGION = "Bagmati"
BUSINESS_COUNTRY = "Nepal"
BUSINESS_COUNTRY_CODE = "NP"
# Real official profiles of the business (used in `sameAs`).
SOCIAL_PROFILES = [
    "https://www.instagram.com/nismita_craft_studio/",
    "https://www.tiktok.com/@nismita_craft_studio",
]
# The founder is credited on the homepage/About page; only used where the
# project already states this publicly.
FOUNDER_NAME = "Sumita Basel"


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


def _dev_host_fallback_allowed() -> bool:
    """Opt-in only (SEO_ALLOW_DEV_HOSTS=true) — never on by default.

    Off by default so canonical, Open Graph, sitemap and JSON-LD URLs can
    never be generated from a request host, even by mistake in staging.
    """
    return str(
        getattr(settings, "SEO_ALLOW_DEV_HOSTS", "false") or "false"
    ).strip().lower() in ("1", "true", "yes")


def absolute_url(request, path: str) -> str:
    """Absolute HTTPS URL on the canonical domain (never testserver/dev)."""
    if not path.startswith("/"):
        path = f"/{path}"
    if request is not None and settings.DEBUG and _dev_host_fallback_allowed():
        try:
            current = (request.get_host() or "").split(":")[0].lower()
        except Exception:  # pragma: no cover - defensive
            current = ""
        # Only an explicit local preview host may be echoed back.
        if current in {"localhost", "127.0.0.1", "[::1]", "testserver"}:
            scheme = request.scheme if request.scheme in ("http", "https") else "http"
            return f"{scheme}://{request.get_host()}{path}"
    return f"{canonical_base()}{path}"


def canonical_url(request, path: str | None = None) -> str:
    return absolute_url(request, path if path is not None else request.path)


# ---------------------------------------------------------------------------
# Structured data (JSON-LD) — built from constants above so every page emits
# the same, single Organization + WebSite entity graph.
# ---------------------------------------------------------------------------
def _id(fragment: str) -> str:
    return f"{canonical_base()}/#{fragment}"


def postal_address() -> dict:
    return {
        "@type": "PostalAddress",
        "streetAddress": BUSINESS_STREET,
        "addressLocality": BUSINESS_CITY,
        "addressRegion": BUSINESS_REGION,
        "addressCountry": BUSINESS_COUNTRY_CODE,
    }


def organization_node() -> dict:
    """The single Organization entity for Nismita Craft Studio."""
    return {
        "@type": "Organization",
        "@id": _id("organization"),
        "name": BRAND_NAME,
        "url": f"{canonical_base()}/",
        "logo": {
            "@type": "ImageObject",
            "url": f"{canonical_base()}{DEFAULT_OG_IMAGE}",
        },
        "image": f"{canonical_base()}{DEFAULT_OG_IMAGE}",
        "description": (
            "Nismita Craft Studio is a Kathmandu-based business supplying "
            "candle moulds, candle wax, candle wicks, mica colours, glitters "
            "and related craft supplies to candle makers across Nepal."
        ),
        "telephone": BUSINESS_PHONE,
        "address": postal_address(),
        "founder": {
            "@type": "Person",
            "name": FOUNDER_NAME,
            "jobTitle": "Founder",
            "worksFor": {"@id": _id("organization")},
        },
        "contactPoint": [
            {
                "@type": "ContactPoint",
                "contactType": "customer support",
                "telephone": BUSINESS_PHONE,
                "url": BUSINESS_WHATSAPP,
                "availableLanguage": ["ne", "en"],
            }
        ],
        "sameAs": list(SOCIAL_PROFILES),
    }


def website_node() -> dict:
    """The single WebSite entity, with a SearchAction that matches /shop/."""
    return {
        "@type": "WebSite",
        "@id": _id("website"),
        "url": f"{canonical_base()}/",
        "name": BRAND_NAME,
        "description": (
            f"{BRAND_NAME} — candle moulds, wax, wicks, colours and craft "
            "supplies in Nepal, delivered nationwide from Kathmandu."
        ),
        "inLanguage": "en-NP",
        "publisher": {"@id": _id("organization")},
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{canonical_base()}/shop/?search={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        },
    }


def local_business_node() -> dict:
    """Storefront node for the physical Kathmandu business.

    `Store` is a valid schema.org subtype of LocalBusiness for a retail
    supply shop.  Deliberately omits opening hours, ratings and review
    counts because the project does not publish verifiable values.
    """
    return {
        "@type": ["LocalBusiness", "Store"],
        "@id": _id("localbusiness"),
        "name": BRAND_NAME,
        "url": f"{canonical_base()}/",
        "image": f"{canonical_base()}{DEFAULT_OG_IMAGE}",
        "logo": f"{canonical_base()}{DEFAULT_OG_IMAGE}",
        "telephone": BUSINESS_PHONE,
        "address": postal_address(),
        "areaServed": [
            {"@type": "Country", "name": "Nepal"},
            {"@type": "City", "name": "Kathmandu"},
        ],
        "currenciesAccepted": "NPR",
        "paymentAccepted": "Cash on Delivery, QR payment (eSewa, Khalti, Fonepay, IME Pay)",
        "parentOrganization": {"@id": _id("organization")},
        "sameAs": list(SOCIAL_PROFILES),
    }


def site_schema() -> dict:
    """Site-wide @graph rendered once per page from ``base.html``."""
    return {
        "@context": "https://schema.org",
        "@graph": [organization_node(), website_node()],
    }
