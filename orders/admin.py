"""Orders admin: wishlists, carts, orders and items."""
from django.contrib import admin

from .models import Cart, CartItem, Order, OrderItem, Wishlist, WishlistItem


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user",)
    inlines = [WishlistItemInline]


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("wishlist", "product", "created_at")
    search_fields = ("product__name", "product__sku", "wishlist__user__username")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("wishlist", "product")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("total_price",)
    autocomplete_fields = ("product", "variant", "seller")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer", "status", "payment_method", "payment_status", "total", "province", "district", "created_at")
    list_filter = ("status", "payment_method", "payment_status", "province", "created_at")
    search_fields = ("order_number", "customer__username", "customer__email", "phone", "full_name")
    readonly_fields = ("created_at", "updated_at", "subtotal", "total", "confirmed_at", "confirmed_by")
    autocomplete_fields = ("customer",)
    inlines = [OrderItemInline]
    fieldsets = (
        ("Order", {"fields": ("order_number", "customer", "status", "subtotal", "shipping_cost", "discount", "total")}),
        ("Delivery (Nepal)", {"fields": ("full_name", "phone", "province", "district", "city", "address_line", "landmark", "shipping_address")}),
        ("Payment", {"fields": ("payment_method", "payment_status", "payment_reference", "payment_screenshot", "whatsapp_number", "confirmed_at", "confirmed_by")}),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_name", "sku", "quantity", "unit_price", "total_price")
    search_fields = ("order__order_number", "product_name", "sku")
    readonly_fields = ("total_price",)
    autocomplete_fields = ("order", "product", "variant", "seller")


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ("product", "variant")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "count", "subtotal", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user",)
    inlines = [CartItemInline]

