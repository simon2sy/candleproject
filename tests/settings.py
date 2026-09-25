"""Test database setup and configuration."""
import os
from pathlib import Path

# Use SQLite in-memory for tests (faster than PostgreSQL)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Increase upload limits for testing so we can test validators properly.
# Production uses 5MB via settings.py; tests use 10MB to allow oversized
# test files while still testing the validation logic.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Allow media uploads during tests
MEDIA_ROOT = Path(__file__).resolve().parent.parent / "test_media"

# Disable password validators for faster test creation
AUTH_PASSWORD_VALIDATORS = []

# Allow all hosts during tests
ALLOWED_HOSTS = ["*"]

# Disable rate limiting during test runs
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}

# Disable CORS checks during tests
CORS_ALLOWED_ORIGINS = ["http://testserver"]
CORS_ALLOW_CREDENTIALS = False

# Allow media uploads during tests
MEDIA_ROOT = Path(__file__).resolve().parent.parent / "test_media"

# Disable password validators for faster test creation
AUTH_PASSWORD_VALIDATORS = []

# Allow all hosts during tests
ALLOWED_HOSTS = ["*"]

# Disable rate limiting during test runs
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}

# Disable CORS checks during tests
CORS_ALLOWED_ORIGINS = ["http://testserver"]
CORS_ALLOW_CREDENTIALS = False