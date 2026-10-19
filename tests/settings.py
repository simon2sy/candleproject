"""Test database setup and configuration.

Extends the real project settings so the suite exercises the same apps,
middleware, URLconf and DRF configuration as the running site, then applies
the test-only overrides: an in-memory database, relaxed upload limits and
disabled rate limiting.
"""
import os
from pathlib import Path

# ``config.settings`` refuses to boot when DEBUG=False without SECRET_KEY and a
# DATABASE_URL — exactly how the CI test job is configured.  No real database
# is ever opened (DATABASES is overridden below), so satisfy those guards with
# throwaway values before extending the real settings.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production")
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")

from config.settings import *  # noqa: E402,F401,F403

# CI runs the suite with DEBUG=False, which switches on the production
# hardening block.  The test client speaks plain HTTP, so never bounce its
# requests to HTTPS and never mark cookies secure-only.
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Fast, throwaway database — no server required, nothing to clean up.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Increase upload limits so validator tests can build oversized files while
# still exercising the validation logic (production caps uploads at 5 MB).
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Media uploads land in a throwaway directory, never in the real MEDIA_ROOT.
MEDIA_ROOT = Path(__file__).resolve().parent.parent / "test_media"

# Faster user creation; password strength is not what these tests check.
AUTH_PASSWORD_VALIDATORS = []

# The Django test client talks to the host "testserver".
ALLOWED_HOSTS = ["*"]

# Rate limiting must never make a test flaky: drop the global anon/user
# throttles, but keep every scoped rate the login/register views read straight
# from DEFAULT_THROTTLE_RATES — a missing scope rate makes DRF raise
# ImproperlyConfigured (500) instead of throttling.  The scoped rates are
# raised so a large suite can never trip them.
REST_FRAMEWORK = dict(REST_FRAMEWORK)  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    **REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
    "auth_register": "10000/minute",
    "auth_login": "10000/minute",
}

# CORS checks off during tests.
CORS_ALLOWED_ORIGINS = ["http://testserver"]
CORS_ALLOW_CREDENTIALS = False