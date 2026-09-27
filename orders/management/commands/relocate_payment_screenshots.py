"""Move legacy payment screenshots out of the public media tree.

Screenshots used to be uploaded to ``MEDIA_ROOT/payment_screenshots/`` and were
therefore downloadable by anyone who requested
``/media/payment_screenshots/<file>``.  ``Order.payment_screenshot`` now uses the
private storage (``config.storage``, rooted at ``PRIVATE_MEDIA_ROOT``), so files
that were written before that change must be moved once.

    python manage.py relocate_payment_screenshots --dry-run
    python manage.py relocate_payment_screenshots

Safe to re-run: files that are already in the private root are skipped, and the
database never has to change (the stored name is relative to the storage root).
"""
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from orders.models import Order


class Command(BaseCommand):
    help = "Move legacy media/payment_screenshots files into PRIVATE_MEDIA_ROOT."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Report what would be moved without touching any file."
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        storage = Order._meta.get_field("payment_screenshot").storage
        legacy_root = Path(settings.MEDIA_ROOT)
        orders = (
            Order.objects.exclude(payment_screenshot="")
            .exclude(payment_screenshot__isnull=True)
            .only("pk", "order_number", "payment_screenshot")
        )

        moved, present, missing = [], [], []
        for order in orders.iterator():
            name = order.payment_screenshot.name
            source = legacy_root / name
            target = Path(storage.path(name))
            if target.exists():
                present.append(name)
                continue
            if not source.exists():
                missing.append(f"{order.order_number}: {name}")
                continue
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
            moved.append(f"{order.order_number}: {name}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no files were moved."))
        for line in moved:
            self.stdout.write(f"{'would move' if dry_run else 'moved'}: {line}")
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Would move' if dry_run else 'Moved'} {len(moved)} file(s); "
                f"{len(present)} already private."
            )
        )
        if missing:
            self.stdout.write(
                self.style.ERROR(f"{len(missing)} screenshot(s) referenced in the DB but not found on disk:")
            )
            for line in missing:
                self.stdout.write(f"  missing: {line}")
            self.stdout.write(
                f"Private media root: {settings.PRIVATE_MEDIA_ROOT} (legacy root: {legacy_root})"
            )
