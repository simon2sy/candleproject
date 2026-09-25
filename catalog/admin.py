"""Catalog admin: categories, products, variants, images, attributes, tags, inventory."""
from django.contrib import admin

from .models import Category, InventoryLog, Product, ProductAttribute, ProductImage, ProductVariant, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active", "created_at")
    list_filter = ("is_active", "parent", "created_at")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("parent",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Single-seller store: the seller is always the Nismita profile, so the
    picker is hidden and auto-assigned on save (the admin is the supplier)."""

    list_display = ("name", "sku", "category", "price", "stock_quantity", "is_active", "is_featured")
    list_filter = ("is_active", "is_featured", "is_available", "category", "created_at")
    search_fields = ("name", "slug", "sku", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("category", "tags")
    inlines = [ProductVariantInline, ProductImageInline, ProductAttributeInline]
    fieldsets = (
        (None, {"fields": ("category", "tags", "name", "slug", "sku")}),
        ("Content", {"fields": ("short_description", "description")}),
        ("Pricing & stock", {"fields": ("price", "compare_at_price", "stock_quantity", "low_stock_threshold")}),
        ("Visibility", {"fields": ("is_active", "is_featured", "is_available")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.seller_id:
            from accounts.models import SellerProfile

            profile = SellerProfile.objects.filter(user=request.user).first() or SellerProfile.objects.first()
            if profile is None:
                profile = SellerProfile.objects.create(
                    user=request.user,
                    business_name="Nismita Craft Studio",
                    business_phone="+977 970-8909514",
                    address="Narephate - 32",
                    city="Kathmandu",
                    country="Nepal",
                    is_verified=True,
                )
            obj.seller = profile
        super().save_model(request, obj, form, change)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "product", "price", "stock_quantity", "is_active")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "sku", "product__name")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("product",)


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "is_primary", "display_order", "created_at")
    list_filter = ("is_primary", "created_at")
    search_fields = ("product__name", "alt_text")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("product",)


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ("product", "name", "value")
    list_filter = ("name",)
    search_fields = ("product__name", "name", "value")
    autocomplete_fields = ("product",)


@admin.register(InventoryLog)
class InventoryLogAdmin(admin.ModelAdmin):
    list_display = ("product", "variant", "change_type", "quantity", "new_quantity", "created_by", "created_at")
    list_filter = ("change_type", "created_at")
    search_fields = ("product__sku", "product__name", "variant__sku", "note")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("product", "variant", "created_by")

