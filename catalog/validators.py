"""Security validation for uploaded catalog images."""
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


@deconstructible
class ProductImageValidator:
    """Validate bytes and decoded image content, not just the filename or MIME type."""

    def __call__(self, uploaded_file):
        if uploaded_file.size > MAX_IMAGE_BYTES:
            raise ValidationError("Product images must be 5 MB or smaller.")
        if not uploaded_file.name:
            raise ValidationError("The uploaded image has no filename.")
        # Avoid extension-based trust and normalize user-controlled names.
        if Path(uploaded_file.name).name != uploaded_file.name:
            raise ValidationError("Invalid image filename.")
        try:
            uploaded_file.seek(0)
            with Image.open(uploaded_file) as image:
                if image.format not in ALLOWED_IMAGE_FORMATS:
                    raise ValidationError("Only JPG, PNG and WebP images are allowed.")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValidationError("Product image dimensions are too large.")
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise ValidationError("Upload a valid JPG, PNG or WebP image.")
        finally:
            uploaded_file.seek(0)
