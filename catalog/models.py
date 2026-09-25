"""Catalog models: categories, products, variants, images, attributes, tags, inventory."""

from django.core.validators import MinValueValidator, validate_image_file_extension
from django.db import models

from .validators import ProductImageValidator


class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", null=True, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"], name="cat_slug_idx"),
            models.Index(fields=["parent", "is_active"], name="cat_parent_active_idx"),
        ]

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    seller = models.ForeignKey("accounts.SellerProfile", on_delete=models.CASCADE, related_name="products")
    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT, related_name="products")
    tags = models.ManyToManyField("catalog.Tag", blank=True, related_name="products")
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    short_description = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    compare_at_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_available = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["seller"], name="prod_seller_idx"),
            models.Index(fields=["category"], name="prod_category_idx"),
            models.Index(fields=["is_active", "is_available"], name="prod_active_avail_idx"),
            models.Index(fields=["is_featured"], name="prod_featured_idx"),
            models.Index(fields=["price"], name="prod_price_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name="product_price_non_negative"),
            models.CheckConstraint(condition=models.Q(stock_quantity__gte=0), name="product_stock_non_negative"),
        ]

    def __str__(self):
        return self.name

    @property
    def primary_image(self):
        """Best image to show for this product: the flagged primary one, else the first.

        Returns ``None`` when the product has no image yet, so templates can fall
        back to the placeholder artwork instead of rendering a broken <img>.
        """
        images = list(self.images.all())
        for image in images:
            if image.is_primary:
                return image
        return images[0] if images else None

    @property
    def discount_percent(self):
        """Whole-number saving vs. the compare-at price (0 when there is no deal)."""
        if self.compare_at_price and self.compare_at_price > self.price:
            return int(
                round((self.compare_at_price - self.price) / self.compare_at_price * 100)
            )
        return 0


class ProductVariant(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    compare_at_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price"]
        indexes = [models.Index(fields=["product", "is_active"], name="variant_prod_active_idx")]
        constraints = [models.CheckConstraint(condition=models.Q(price__gte=0), name="variant_price_non_negative")]

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class ProductImage(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(
        upload_to="products/%Y/%m/",
        validators=[validate_image_file_extension, ProductImageValidator()],
    )
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "id"]
        indexes = [models.Index(fields=["product", "display_order"], name="img_prod_order_idx")]

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductAttribute(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="attributes")
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["product", "name"], name="attr_prod_name_idx")]
        constraints = [models.UniqueConstraint(fields=["product", "name", "value"], name="unique_product_attribute")]

    def __str__(self):
        return f"{self.product.name}: {self.name}={self.value}"


class InventoryLog(models.Model):
    """Append-only stock movement ledger for product / variant."""

    class ChangeType(models.TextChoices):
        STOCK_IN = "STOCK_IN", "Stock in"
        STOCK_OUT = "STOCK_OUT", "Stock out"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        ORDER = "ORDER", "Order"
        RETURN = "RETURN", "Return"

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="inventory_logs")
    variant = models.ForeignKey(
        "catalog.ProductVariant", null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_logs"
    )
    change_type = models.CharField(max_length=12, choices=ChangeType.choices, db_index=True)
    quantity = models.IntegerField()
    previous_quantity = models.PositiveIntegerField()
    new_quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_logs"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "created_at"], name="inv_prod_created_idx"),
            models.Index(fields=["variant"], name="inv_variant_idx"),
        ]

    def __str__(self):
        return f"{self.change_type} {self.quantity} for {self.product.sku}"


