"""Storage backends.

Product, category and seller images are meant to be public.  Customer payment
screenshots are not: they show bank/eSewa screens with names, amounts and
transaction ids.  Keeping everything in one ``MEDIA_ROOT`` meant anyone could
fetch ``/media/payment_screenshots/<file>`` (Django serves ``MEDIA_URL`` in
development) and every production web-server rule had to remember to block it.

Private files now live in ``PRIVATE_MEDIA_ROOT``, outside ``MEDIA_ROOT`` and
``STATIC_ROOT``, and are only readable through the authenticated views in
``storefront`` (``payment-screenshot`` / ``dashboard-payment-screenshot``).
"""
from __future__ import annotations

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateMediaStorage(FileSystemStorage):
    """FileSystemStorage rooted outside the publicly served media tree.

    ``base_url`` is deliberately a path that no URL pattern routes: it exists so
    ``FieldFile.url`` keeps working (the Django admin renders file fields as
    links) and always resolves to a 404.  Read the file through the
    authenticated views instead.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("location", settings.PRIVATE_MEDIA_ROOT)
        kwargs.setdefault("base_url", settings.PRIVATE_MEDIA_URL)
        # Owner-only permissions on POSIX: even a misconfigured web server that
        # happens to point at this directory cannot serve the files.
        kwargs.setdefault("file_permissions_mode", 0o600)
        kwargs.setdefault("directory_permissions_mode", 0o700)
        super().__init__(**kwargs)


private_media_storage = PrivateMediaStorage()
