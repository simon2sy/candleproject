"""Wishlist + cart + order models."""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from orders.validators import validate_payment_screenshot


class Wishlist(models.Model):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="wishlist")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wishlist of {self.user.username}"


class WishlistItem(models.Model):
    wishlist = models.ForeignKey("orders.Wishlist", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="wishlisted_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["wishlist", "product"], name="unique_wishlist_product"),
        ]

    def __str__(self):
        return f"{self.product.name} in {self.wishlist}"


class Cart(models.Model):
    """One persistent cart per user (session cart merges into this on login)."""

    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart of {self.user.username}"

    @property
    def subtotal(self):
        return sum((i.line_total for i in self.items.all()), Decimal("0.00"))

    @property
    def count(self):
        return sum((i.quantity for i in self.items.all()), 0)


class CartItem(models.Model):
    cart = models.ForeignKey("orders.Cart", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="cart_items")
    variant = models.ForeignKey(
        "catalog.ProductVariant", null=True, blank=True, on_delete=models.CASCADE, related_name="cart_items"
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "product", "variant"], name="unique_cart_product_variant"),
        ]
        indexes = [models.Index(fields=["cart"], name="cartitem_cart_idx")]

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def unit_price(self):
        if self.variant_id and self.variant:
            return self.variant.price
        return self.product.price

    @property
    def line_total(self):
        return self.unit_price * self.quantity



class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PROCESSING = "PROCESSING", "Processing"
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentMethod(models.TextChoices):
        QR = "QR", "QR Payment"
        ESEWA = "ESEWA", "eSewa"
        KHALTI = "KHALTI", "Khalti"
        FONEPAY = "FONEPAY", "FonePay"
        IMEPAY = "IMEPAY", "IME Pay"
        BANK = "BANK", "Bank Transfer"
        COD = "COD", "Cash on Delivery"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending verification"
        VERIFIED = "VERIFIED", "Payment verified"
        REJECTED = "REJECTED", "Payment rejected"

    customer = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="orders")
    order_number = models.CharField(max_length=32, unique=True, db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    shipping_address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- Delivery location (all Nepal: 7 provinces / 77 districts) ---
    full_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    province = models.CharField(max_length=40, blank=True, db_index=True)
    district = models.CharField(max_length=40, blank=True, db_index=True)
    city = models.CharField(max_length=80, blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=255, blank=True)

    # --- Manual payment (screenshot sent via WhatsApp, verified by admin) ---
    payment_method = models.CharField(
        max_length=12, choices=PaymentMethod.choices, default=PaymentMethod.ESEWA, db_index=True
    )
    payment_status = models.CharField(
        max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True
    )
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_screenshot = models.ImageField(
        upload_to="payment_screenshots/", blank=True, null=True, validators=[validate_payment_screenshot]
    )
    whatsapp_number = models.CharField(max_length=20, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="confirmed_orders"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "status"], name="order_cust_status_idx"),
            models.Index(fields=["status", "created_at"], name="order_status_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(total__gte=0), name="order_total_non_negative"),
        ]

    def __str__(self):
        return self.order_number

    def recalculate(self):
        items = self.items.all()
        self.subtotal = sum((i.total_price for i in items), Decimal("0.00"))
        self.total = self.subtotal + self.shipping_cost - self.discount
        if self.total < 0:
            self.total = Decimal("0.00")


class OrderItem(models.Model):
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="order_items")
    variant = models.ForeignKey(
        "catalog.ProductVariant", null=True, blank=True, on_delete=models.PROTECT, related_name="order_items"
    )
    seller = models.ForeignKey("accounts.SellerProfile", on_delete=models.PROTECT, related_name="order_items")
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=["order"], name="oitem_order_idx"),
            models.Index(fields=["seller"], name="oitem_seller_idx"),
            models.Index(fields=["product"], name="oitem_product_idx"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)

