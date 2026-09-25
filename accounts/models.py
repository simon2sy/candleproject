"""Custom user, seller profile and customer address models."""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils import timezone


class User(AbstractUser):
    """Custom user with roles and seller-approval tracking."""

    class Roles(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        SELLER = "SELLER", "Seller"
        ADMIN = "ADMIN", "Admin"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=10, choices=Roles.choices, default=Roles.CUSTOMER)
    is_seller_approved = models.BooleanField(default=False)
    seller_approved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["email"], name="user_email_idx"),
            models.Index(fields=["role"], name="user_role_idx"),
        ]

    def __str__(self):  # pragma: no cover
        return f"{self.username} ({self.role})"

    @property
    def is_seller(self) -> bool:
        return self.role == self.Roles.SELLER

    @property
    def is_approved_seller(self) -> bool:
        return self.is_seller and self.is_seller_approved

    def approve_seller(self):
        self.is_seller_approved = True
        self.seller_approved_at = timezone.now()
        self.save(update_fields=["is_seller_approved", "seller_approved_at", "updated_at"])


class SellerProfile(models.Model):
    """One seller storefront per seller user. Owns many products."""

    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="seller_profile")
    business_name = models.CharField(max_length=255)
    business_description = models.TextField(blank=True)
    business_phone = models.CharField(max_length=20, blank=True)
    business_email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    tax_number = models.CharField(max_length=50, blank=True)
    logo = models.ImageField(upload_to="sellers/logos/", null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["business_name"], name="seller_name_idx"),
            models.Index(fields=["is_verified"], name="seller_verified_idx"),
        ]

    def __str__(self):  # pragma: no cover
        return self.business_name


class Address(models.Model):
    """Customer shipping/billing address. A user may have many."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="addresses")
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        indexes = [
            models.Index(fields=["user", "is_default"], name="addr_user_default_idx"),
        ]
        constraints = [
            # Only one default address per user (partial unique index).
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_default=True),
                name="unique_default_address_per_user",
            ),
        ]

    def __str__(self):  # pragma: no cover
        return f"{self.full_name} — {self.address_line_1}, {self.city}"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Unset other defaults for this user (keeps invariant on DBs
            # where partial unique constraint is not enforced, e.g. dev).
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        elif not Address.objects.filter(user=self.user).exclude(pk=self.pk).exists():
            # First address for a user becomes default automatically.
            if not self.pk:
                self.is_default = True
        super().save(*args, **kwargs)

