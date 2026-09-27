"""Cache-backed rate limiting for the plain (non-DRF) HTML form views.

``config.throttles`` covers the JSON API; the template forms (``/login/``,
``/register/``) are not DRF views and had no protection at all, so the HTML
login could be used to guess passwords forever.  ``AttemptLimiter`` is the small
piece of machinery those views need: count failures per identity and lock the
identity out for a while.

It uses Django's cache framework.  The default local-memory cache counts per
process, which is fine for a single-worker deployment; point ``CACHES`` at a
shared cache (Redis/Memcached) when running several workers.
"""
from __future__ import annotations

from django.conf import settings
from django.core.cache import cache


def client_ip(request) -> str:
    """Best-effort client IP used as part of the throttle key.

    ``X-Forwarded-For`` is only trusted when ``TRUST_PROXY_HEADERS`` is on,
    otherwise a client could rotate the header on every request and escape the
    counter entirely.
    """
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "unknown").strip() or "unknown"


class AttemptLimiter:
    """Count failed attempts for a key and lock it out past a threshold.

    >>> limiter = AttemptLimiter("login", max_attempts=3, window=600)
    >>> limiter.is_locked("127.0.0.1:bob@example.com")
    False
    """

    def __init__(self, namespace: str, max_attempts: int, window: int, lockout: int | None = None):
        self.namespace = namespace
        self.max_attempts = max(1, int(max_attempts))
        self.window = max(1, int(window))
        self.lockout = max(1, int(lockout if lockout is not None else window))

    # -- keys ---------------------------------------------------------------
    def _keys(self, identifier: str) -> tuple[str, str]:
        base = f"ratelimit:{self.namespace}:{identifier}"
        return f"{base}:count", f"{base}:locked"

    # -- queries ------------------------------------------------------------
    def is_locked(self, identifier: str) -> bool:
        _, locked_key = self._keys(identifier)
        return bool(cache.get(locked_key))

    def attempts(self, identifier: str) -> int:
        count_key, _ = self._keys(identifier)
        return int(cache.get(count_key, 0) or 0)

    def remaining_attempts(self, identifier: str) -> int:
        return max(0, self.max_attempts - self.attempts(identifier))

    # -- mutations ----------------------------------------------------------
    def register_failure(self, identifier: str) -> None:
        """Record one failure; locks the identifier out at the threshold."""
        count_key, locked_key = self._keys(identifier)
        try:
            count = cache.incr(count_key)
        except ValueError:  # key absent (or expired) -> start a fresh window
            cache.set(count_key, 1, self.window)
            count = 1
        if count >= self.max_attempts:
            cache.set(locked_key, 1, self.lockout)
            cache.delete(count_key)

    def clear(self, identifier: str) -> None:
        """Forget a key — call this after a successful login."""
        for key in self._keys(identifier):
            cache.delete(key)
