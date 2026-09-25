"""Django settings for candle ecommerce (Phase 1)."""
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _parse_database_url(url: str):
    """Parse DATABASE_URL into Django DATABASES settings.

    Local development may use SQLite when DATABASE_URL is empty. Production must
    provide PostgreSQL explicitly so a production process cannot silently fall
    back to an untracked local database file.
    """
    if not url:
        if not DEBUG:
            raise ImproperlyConfigured("DATABASE_URL is required when DEBUG=False.")
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    parsed = urlparse(url)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL must use postgres:// or postgresql://.")
    if not parsed.hostname or not parsed.path.lstrip("/"):
        raise ImproperlyConfigured("DATABASE_URL must include a host and database name.")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "CONN_MAX_AGE": int(os.getenv("DATABASE_CONN_MAX_AGE", "60")),
        "OPTIONS": {"connect_timeout": int(os.getenv("DATABASE_CONNECT_TIMEOUT", "5"))},
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username,
        "PASSWORD": parsed.password,
        "HOST": parsed.hostname,
        "PORT": parsed.port or "5432",
    }


# Dev-friendly default; production (DEBUG=False) must supply a real key.
DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")

# Fail loudly when production runs without a real secret key instead of
# silently falling back to a publicly-known dev value.
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-dev-only-change-me"
    else:
        raise RuntimeError(
            "SECRET_KEY is not set. Add it to your .env or environment before "
            "running with DEBUG=False."
        )

# Only keep dev hosts when DEBUG is on; production must explicitly list hosts.
_DEV_HOSTS = {"localhost", "127.0.0.1", "[::1]", "testserver"}
if DEBUG:
    _raw = os.getenv("ALLOWED_HOSTS", "")
    _hosts = {h.strip() for h in _raw.split(",") if h.strip()}
    _hosts |= _DEV_HOSTS
    ALLOWED_HOSTS = sorted(_hosts)
else:
    _raw = os.getenv("ALLOWED_HOSTS", "")
    _hosts = {h.strip() for h in _raw.split(",") if h.strip()}
    _deploy = os.getenv("DEPLOY_HOST", "").strip()
    if _deploy:
        _hosts.add(_deploy)
    if not _hosts:
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS is empty in production. Set ALLOWED_HOSTS in .env "
            "(or DEPLOY_HOST)."
        )
    ALLOWED_HOSTS = sorted(_hosts)

INSTALLED_APPS = [
"django.contrib.admin",
"django.contrib.auth",
"django.contrib.contenttypes",
"django.contrib.sessions",
"django.contrib.messages",
"django.contrib.staticfiles",
# Third-party
"rest_framework",
"django_filters",
"corsheaders",
    # WhiteNoise must come after staticfiles (and as early as possible in middleware).
    "whitenoise.runserver_nostatic",
# Local
"accounts",
"catalog",
"orders",
"storefront",
]

MIDDLEWARE = [
"corsheaders.middleware.CorsMiddleware",
"django.middleware.security.SecurityMiddleware",
"whitenoise.middleware.WhiteNoiseMiddleware",
"django.contrib.sessions.middleware.SessionMiddleware",
"django.middleware.common.CommonMiddleware",
"django.middleware.csrf.CsrfViewMiddleware",
"django.contrib.auth.middleware.AuthenticationMiddleware",
"django.contrib.messages.middleware.MessageMiddleware",
"django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": _parse_database_url(os.getenv("DATABASE_URL", "").strip())}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
{"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
{"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
{"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# WhiteNoise: serve static files from the WSGI layer without a separate web server.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # Use the non-manifest variant during tests (no collectstatic required);
        # in production, collectstatic creates the hashed manifest, so this is safe.
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# --- File upload limits (protect against huge uploads). ---
# Screenshots capped at 5 MB; forms get 10 MB headroom.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # Allow larger files to reach the validator
FILE_UPLOAD_MAX_SIZE = 10 * 1024 * 1024  # Allow larger files to reach the validator

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# --- Production security hardening (enabled whenever DEBUG=False). ---
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
else:
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_HTTPONLY = True
    X_FRAME_OPTIONS = "DENY"

# Trust proxy headers only when the deployment is behind a trusted HTTPS proxy.
# Do not enable this when Django is directly reachable from the public internet.
if os.getenv("TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# CSRF trusted origins: env override + every allowed host + Cloudflare
# quick-tunnel demo URLs, so login/register/checkout POSTs never 403 behind an
# HTTPS edge. Bare hosts in the env var get https:// prepended; ".domain"
# allowed-host entries become "*.domain" origin patterns.
_csrf_origins = []
for _o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(","):
    _o = _o.strip()
    if _o:
        _csrf_origins.append(_o if "://" in _o else f"https://{_o}")
for _h in ALLOWED_HOSTS:
    _origin = f"https://*{_h}" if _h.startswith(".") else f"https://{_h}"
    if _origin not in _csrf_origins:
        _csrf_origins.append(_origin)
if DEBUG and "https://*.trycloudflare.com" not in _csrf_origins:
    _csrf_origins.append("https://*.trycloudflare.com")
CSRF_TRUSTED_ORIGINS = _csrf_origins

# --- WhatsApp order confirmation (customer sends payment screenshot here) ---
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "9779708909514")  # format: 977XXXXXXXXXX

# --- Shipping (Nepal delivery): a single flat charge; no free-delivery threshold ---
SHIPPING_FLAT = Decimal(os.getenv("SHIPPING_FLAT", "150"))

# --- Manual payment accounts shown to customers at checkout ---
PAYMENT_ACCOUNTS = {
    "ESEWA": os.getenv("ESEWA_NUMBER", "9800000000 — Nismita Craft Studio"),
    "KHALTI": os.getenv("KHALTI_NUMBER", "9800000000 — Nismita Craft Studio"),
    "FONEPAY": os.getenv("FONEPAY_ID", "nismita@fonepay"),
    "IMEPAY": os.getenv("IMEPAY_NUMBER", "9800000000 — Nismita Craft Studio"),
    "BANK": os.getenv("BANK_DETAILS", "NIC Asia Bank — A/C 1234567890123 — Nismita Craft Studio Pvt. Ltd."),
    "COD": "Pay cash when the courier delivers.",
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # Rate-limit auth endpoints.  Scoped rates are defined in config/throttles.py.
    "DEFAULT_THROTTLE_CLASSES": [
        "config.throttles.UserRateThrottle",
        "config.throttles.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": os.getenv("THROTTLE_USER", "1000/hour"),
        "anon": os.getenv("THROTTLE_ANON", "60/minute"),
        "auth_register": os.getenv("THROTTLE_AUTH_REGISTER", "5/minute"),
        "auth_login": os.getenv("THROTTLE_AUTH_LOGIN", "10/minute"),
    },
}

SIMPLE_JWT = {
"ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
"REFRESH_TOKEN_LIFETIME": timedelta(days=7),
"AUTH_HEADER_TYPES": ("Bearer",),
}

# --- CORS (open for local React dev; tighten in production) ---
# CORS is disabled unless explicitly configured. Never expose credentialed APIs
# to arbitrary browser origins in production.
_CORS_ORIGINS_ENV = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000" if DEBUG else "")
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in _CORS_ORIGINS_ENV.split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True
if not DEBUG and not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = []

# --- Logging: structured console output for production; file in debug. ---
_LOG_DIR = BASE_DIR / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": _LOG_DIR / "django.log",
            "maxBytes": 5_000_000,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"] + (["file"] if DEBUG else []),
        "level": "DEBUG" if DEBUG else "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"] + (["file"] if DEBUG else []),
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"] + (["file"] if DEBUG else []),
            "level": "ERROR",
            "propagate": False,
        },
        "orders": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "catalog": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "storefront": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "accounts": {"level": "INFO", "handlers": ["console"], "propagate": False},
    },
}

# --- Sentry (optional; add SENTRY_DSN to .env to activate). ---
try:
    import sentry_sdk  # noqa: F401
except ImportError:
    sentry_sdk = None  # type: ignore

if sentry_sdk is not None:
    SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
    if SENTRY_DSN:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment="production" if not DEBUG else "development",
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=DEBUG,
        )