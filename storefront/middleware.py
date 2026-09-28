"""Search-engine canonicalisation middleware.

Redirects the ``www`` host to the bare production domain so Google only
ever indexes ``https://nismitacraftstudio.com/``.  Plain ``http`` is left
to ``SECURE_SSL_REDIRECT`` (production) and ``APPEND_SLASH`` trailing-slash
handling stays in ``CommonMiddleware`` — this middleware only collapses the
single www/non-www duplicate, never anything else.
"""
from __future__ import annotations

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


def _canonical_host() -> str:
    return str(getattr(settings, "SEO_CANONICAL_DOMAIN", "") or "nismitacraftstudio.com").strip().lower()


class CanonicalDomainMiddleware:
    """301 ``www.<canonical>`` -> ``<canonical>`` (preserves path + query)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = (request.get_host() or "").split(":")[0].strip().lower()
        canonical = _canonical_host()
        if host == f"www.{canonical}":
            path = request.get_full_path() or "/"
            return HttpResponsePermanentRedirect(f"https://{canonical}{path}")
        return self.get_response(request)
