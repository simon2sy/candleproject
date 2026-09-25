"""Payment screenshot upload validation.

Stores the screenshot rules in one place and enforces them at both the
stored-file (model) level and the HTTP request level, so a user cannot
bypass content checks by sending a crafted POST.
"""
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

MAX_SCREENSHOT_MB = 5
MAX_SCREENSHOT_BYTES = MAX_SCREENSHOT_MB * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


@deconstructible
class PaymentScreenshotValidator:
    """DRF / model-level validator for payment_screenshot ImageFields."""

    code = "invalid_payment_screenshot"

    def __call__(self, file):
        if file.size > MAX_SCREENSHOT_BYTES:
            raise ValidationError(
                f"Screenshot too large. Maximum size is {MAX_SCREENSHOT_MB} MB "
                f"(your file is {file.size / 1024 / 1024:.2f} MB).",
                code=self.code,
            )
        content_type = getattr(file, "content_type", "").lower()
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationError(
                f"Screenshot must be a JPEG, PNG, or WebP image. "
                f"Detected type: {content_type}.",
                code=self.code,
            )
        # Best-effort content check: rewind + verify Pillow can open it.
        try:
            from PIL import Image

            file.seek(0)
            Image.open(file).verify()
            file.seek(0)
        except Exception:
            raise ValidationError(
                "Screenshot file is not a valid image.",
                code=self.code,
            )

    def __eq__(self, other):
        return isinstance(other, PaymentScreenshotValidator)


# Single instance used by the model field and the API view.
validate_payment_screenshot = PaymentScreenshotValidator()
