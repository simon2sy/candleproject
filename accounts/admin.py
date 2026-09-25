"""Accounts admin: users, seller profiles, addresses."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone

from .models import Address, SellerProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "is_seller_approved", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_seller_approved", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name", "phone")
    readonly_fields = ("date_joined", "last_login", "updated_at", "seller_approved_at")
    actions = ("approve_sellers", "unapprove_sellers")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Ecommerce", {"fields": ("phone", "role", "is_seller_approved", "seller_approved_at", "updated_at")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Ecommerce", {"fields": ("email", "phone", "role")}),
    )

    @admin.action(description="Approve selected sellers")
    def approve_sellers(self, request, queryset):
        queryset.filter(role=User.Roles.SELLER).update(is_seller_approved=True, seller_approved_at=timezone.now())

    @admin.action(description="Reject/deactivate selected sellers")
    def unapprove_sellers(self, request, queryset):
        queryset.update(is_seller_approved=False, seller_approved_at=None)


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ("business_name", "user", "city", "country", "is_verified", "created_at")
    list_filter = ("is_verified", "country", "created_at")
    search_fields = ("business_name", "user__username", "user__email", "tax_number")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user",)
    actions = ("verify_sellers", "unverify_sellers")

    @admin.action(description="Verify selected sellers")
    def verify_sellers(self, request, queryset):
        queryset.update(is_verified=True)

    @admin.action(description="Unverify selected sellers")
    def unverify_sellers(self, request, queryset):
        queryset.update(is_verified=False)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "city", "country", "postal_code", "is_default", "created_at")
    list_filter = ("country", "is_default", "created_at")
    search_fields = ("full_name", "user__username", "user__email", "city", "postal_code")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user",)

