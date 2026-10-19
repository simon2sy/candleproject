"""Dashboard: editing an existing product (fields, variants, photos, visibility).

Covers the edit page being staff-only and prefilled, the shared validation
messages, syncing variant rows (update / add / remove — with order history
protecting bought variants), photo removal, and the visibility toggles.
"""
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import User
from catalog.models import Category, Product, ProductImage, ProductVariant
from orders.models import Order, OrderItem

from .helpers import make_seller, make_user


class DashboardEditProductTests(TestCase):
    """The edit page reuses the add form and syncs whatever comes back."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="edit_admin", email="edit_admin@example.com",
            password="Testpass123!", is_staff=True,
        )
        self.category = Category.objects.create(name="Candles", slug="candles")
        self.extra = Category.objects.create(name="Wax", slug="wax")
        _, self.seller = make_seller("edit_seller")
        self.product = Product.objects.create(
            seller=self.seller, category=self.category, name="Soy Wax", slug="soy-wax",
            sku="SOY-WAX", short_description="Original short", description="Original description",
            price=Decimal("500.00"), stock_quantity=10,
        )
        self.large = ProductVariant.objects.create(
            product=self.product, name="Large", sku="SOY-WAX-V01",
            price=Decimal("700.00"), stock_quantity=4,
        )
        self.small = ProductVariant.objects.create(
            product=self.product, name="Small", sku="SOY-WAX-V02",
            price=Decimal("300.00"), stock_quantity=2,
        )
        self.client.force_login(self.staff)
        self.url = reverse("storefront:dashboard-edit-product", args=[self.product.pk])

    def _file(self, name="photo.png", image_format="PNG"):
        image = Image.new("RGB", (20, 20), "red")
        output = BytesIO()
        image.save(output, format=image_format)
        return SimpleUploadedFile(name, output.getvalue(), content_type=f"image/{image_format.lower()}")

    def _post(self, **extra):
        data = {
            "name": "Soy Wax",
            "category": str(self.category.pk),
            "price": "500.00",
            "stock": "10",
            "description": "Original description",
            "is_active": "1",
        }
        data.update(extra)
        return self.client.post(self.url, data)

    # ---------------------------------------------------------------- access
    def test_anonymous_visitors_are_sent_to_the_admin_login(self):
        self.client.logout()
        res = self.client.get(self.url)
        self.assertRedirects(res, f"/admin/login/?next={self.url}")

    def test_customers_cannot_open_the_edit_page(self):
        self.client.force_login(make_user("edit_buyer"))
        res = self.client.get(self.url)
        self.assertRedirects(res, f"/admin/login/?next={self.url}")

    def test_unknown_product_is_a_404(self):
        res = self.client.get(reverse("storefront:dashboard-edit-product", args=[999999]))
        self.assertEqual(res.status_code, 404)

    # ------------------------------------------------------------------ page
    def test_form_is_prefilled_with_the_stored_values(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn("value='Soy Wax'", html)
        self.assertIn(f"value='{self.category.pk}' selected", html)
        self.assertIn("value='500.00'", html)
        self.assertIn("value='10'", html)
        self.assertIn("Original description", html)
        self.assertIn("value='Large'", html)
        self.assertIn("value='700.00'", html)
        self.assertIn("name='variant_id'", html)
        self.assertIn("name='variant_sync'", html)
        self.assertIn("name='is_active'", html)

    def test_product_list_links_to_the_edit_page(self):
        res = self.client.get(reverse("storefront:dashboard-products"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, f"/dashboard/product/{self.product.pk}/edit/")

    # ---------------------------------------------------------- core fields
    def test_saving_updates_the_product(self):
        res = self._post(
            name="Soy Wax XL", category=str(self.extra.pk), price="650.50",
            stock="25", description="Updated description", is_featured="1",
        )
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Soy Wax XL")
        self.assertEqual(self.product.category, self.extra)
        self.assertEqual(self.product.price, Decimal("650.50"))
        self.assertEqual(self.product.stock_quantity, 25)
        self.assertEqual(self.product.description, "Updated description")
        self.assertEqual(self.product.short_description, "Updated description")
        self.assertTrue(self.product.is_active)
        self.assertTrue(self.product.is_featured)
        # The shop URL and order history stay valid.
        self.assertEqual(self.product.slug, "soy-wax")
        self.assertEqual(self.product.sku, "SOY-WAX")
        # No variant_sync marker → the stored variants are left alone.
        self.assertEqual(self.product.variants.count(), 2)

    def test_errors_keep_typed_values_and_change_nothing(self):
        res = self._post(name="", category="", price="abc", stock="-1", description="Typed in")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Enter a product name.")
        self.assertContains(res, "Choose a category.")
        self.assertContains(res, "Price must be a number like 999 or 999.50.")
        self.assertContains(res, "Stock must be a whole number of units (0 or more).")
        self.assertContains(res, "value='abc'")
        self.assertContains(res, "Typed in")
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Soy Wax")
        self.assertEqual(self.product.price, Decimal("500.00"))
        self.assertEqual(self.product.stock_quantity, 10)

    def test_huge_price_is_rejected(self):
        res = self._post(price="100000000")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Price is too large.")
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("500.00"))

    def test_the_products_own_deactivated_category_can_be_kept(self):
        self.category.is_active = False
        self.category.save(update_fields=["is_active"])
        res = self._post()
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.category, self.category)

    # ------------------------------------------------------------- variants
    def test_variant_rows_are_synced(self):
        res = self._post(
            variant_sync="1",
            variant_id=[str(self.large.pk), ""],
            variant_name=["Large", "Medium"],
            variant_price=["750.00", "500.00"],
            variant_stock=["6", "3"],
        )
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        self.assertEqual(set(self.product.variants.values_list("name", flat=True)), {"Large", "Medium"})
        large = self.product.variants.get(name="Large")
        self.assertEqual(large.price, Decimal("750.00"))
        self.assertEqual(large.stock_quantity, 6)
        medium = self.product.variants.get(name="Medium")
        self.assertEqual(medium.price, Decimal("500.00"))
        self.assertEqual(medium.sku, "SOY-WAX-V03")

    def test_clearing_a_variant_row_removes_it(self):
        res = self._post(
            variant_sync="1",
            variant_id=[str(self.small.pk), str(self.large.pk)],
            variant_name=["", "Large"],
            variant_price=["", "700.00"],
            variant_stock=["", "4"],
        )
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        self.assertEqual(list(self.product.variants.values_list("name", flat=True)), ["Large"])

    def test_a_variant_bought_by_a_customer_cannot_be_removed(self):
        buyer = make_user("edit_buyer")
        order = Order.objects.create(customer=buyer, order_number="ORD-EDIT-1")
        OrderItem.objects.create(
            order=order, product=self.product, variant=self.small, seller=self.seller,
            product_name=self.product.name, sku=self.small.sku,
            quantity=1, unit_price=self.small.price,
        )
        res = self._post(
            variant_sync="1",
            variant_id=[str(self.large.pk)],
            variant_name=["Large"],
            variant_price=["700.00"],
            variant_stock=["4"],
            name="Renamed product",
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "already appear in past orders")
        self.assertContains(res, "Small")
        self.assertTrue(self.product.variants.filter(pk=self.small.pk).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Soy Wax")  # nothing was saved

    def test_a_variant_row_from_another_product_is_rejected(self):
        other = Product.objects.create(
            seller=self.seller, category=self.category, name="Other", slug="other-x",
            sku="OTHER-1", price=Decimal("100.00"),
        )
        intruder = ProductVariant.objects.create(
            product=other, name="Ghost", sku="OTHER-1-V01", price=Decimal("10.00"),
        )
        res = self._post(
            variant_sync="1",
            variant_id=[str(intruder.pk)],
            variant_name=["Ghost"],
            variant_price=["10.00"],
            variant_stock=["1"],
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "not part of this product")
        self.assertEqual(self.product.variants.count(), 2)

    # --------------------------------------------------------------- photos
    def test_ticked_photos_are_deleted_on_save(self):
        img = ProductImage.objects.create(
            product=self.product, image=self._file("old.png"),
            alt_text="Soy Wax", is_primary=True, display_order=0,
        )
        res = self._post(remove_image=[str(img.pk)])
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        self.assertFalse(ProductImage.objects.filter(pk=img.pk).exists())

    def test_new_photos_are_appended_and_a_cover_is_kept(self):
        old = ProductImage.objects.create(
            product=self.product, image=self._file("old.png"),
            alt_text="Soy Wax", is_primary=True, display_order=0,
        )
        res = self._post(images=[self._file("new.png"), self._file("extra.jpg", "JPEG")])
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        self.assertEqual(self.product.images.count(), 3)
        self.assertEqual(list(self.product.images.values_list("display_order", flat=True)), [0, 1, 2])
        self.assertEqual(self.product.images.filter(is_primary=True).count(), 1)
        self.assertTrue(self.product.images.get(pk=old.pk).is_primary)

    def test_the_first_remaining_photo_becomes_the_cover(self):
        old = ProductImage.objects.create(
            product=self.product, image=self._file("old.png"),
            alt_text="Soy Wax", is_primary=True, display_order=0,
        )
        kept = ProductImage.objects.create(
            product=self.product, image=self._file("kept.png"),
            alt_text="Soy Wax", is_primary=False, display_order=1,
        )
        res = self._post(remove_image=[str(old.pk)])
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        kept.refresh_from_db()
        self.assertTrue(kept.is_primary)
        self.assertEqual(self.product.images.count(), 1)

    def test_the_edit_page_lists_current_photos_with_delete_ticks(self):
        img = ProductImage.objects.create(
            product=self.product, image=self._file("old.png"),
            alt_text="Soy Wax", is_primary=True, display_order=0,
        )
        res = self.client.get(self.url)
        self.assertContains(res, "name='remove_image'")
        self.assertContains(res, f"value='{img.pk}'")
        self.assertContains(res, "Cover")

    # ----------------------------------------------------------- visibility
    def test_unchecking_live_hides_the_product_and_featured_flags_it(self):
        res = self._post(is_active="", is_featured="1")
        self.assertRedirects(res, reverse("storefront:dashboard-products"))
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)
        self.assertTrue(self.product.is_featured)
