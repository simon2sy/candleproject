"""Scoped DRF throttles for auth endpoints.

These are referenced by config.settings.REST_FRAMEWORK and are applied
globally.  Each view that needs a different scope can set
``throttle_scope`` on the view class.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AnonRateThrottle(AnonRateThrottle):
    """Default throttle for unauthenticated requests."""

    scope = "anon"


class UserRateThrottle(UserRateThrottle):
    """Default throttle for authenticated requests."""

    scope = "user"
