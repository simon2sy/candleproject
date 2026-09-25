"""Orders serializers: wishlist + cart + orders."""
from rest_framework import serializers

from catalog.models import Product
from .models import Cart, CartItem, Order, OrderItem, Wishlist, WishlistItem


class WishlistItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    price = serializers.DecimalField(source="product.price", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = WishlistItem
        fields = ("id", "product", "product_name", "price", "created_at")
        read_only_fields = ("id", "created_at")


class WishlistSerializer(serializers.ModelSerializer):
    items = WishlistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Wishlist
        fields = ("id", "items", "created_at", "updated_at")


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ("id", "product", "variant", "quantity", "product_name", "product_slug", "unit_price", "line_total")
        read_only_fields = ("id",)


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ("id", "items", "subtotal", "count", "updated_at")


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id", "product", "variant", "seller", "product_name", "sku",
            "quantity", "unit_price", "total_price",
        )
        read_only_fields = ("id", "seller", "product_name", "sku", "total_price")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id", "order_number", "status", "subtotal", "shipping_cost",
            "discount", "total", "shipping_address", "items", "created_at", "updated_at",
            # delivery + payment (read-only via API for Phase 1)
            "full_name", "phone", "province", "district", "city", "address_line", "landmark",
            "payment_method", "payment_status", "payment_reference",
        )
        read_only_fields = (
            "id", "order_number", "subtotal", "total", "created_at", "updated_at",
            "full_name", "phone", "province", "district", "city", "address_line", "landmark",
            "payment_method", "payment_status", "payment_reference",
        )
