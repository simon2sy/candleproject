"""Orders API: wishlist + cart (login required) + orders (customer sees own; admin all)."""
import uuid

from django.conf import settings
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from catalog.models import Product, ProductVariant
from .models import Cart, CartItem, Order, OrderItem, Wishlist, WishlistItem
from .serializers import CartSerializer, OrderSerializer, WishlistItemSerializer, WishlistSerializer
from .services import InsufficientStock, place_order_from_cart


class WishlistViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WishlistSerializer

    def get_object(self):
        wishlist, _ = Wishlist.objects.prefetch_related("items__product").get_or_create(user=self.request.user)
        return wishlist

    def list(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=False, methods=["post"], url_path="add")
    def add(self, request):
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        product_id = request.data.get("product")
        try:
            product = Product.objects.get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        item, created = WishlistItem.objects.get_or_create(wishlist=wishlist, product=product)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(WishlistItemSerializer(item).data, status=code)

    @action(detail=False, methods=["post"], url_path="remove")
    def remove(self, request):
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        WishlistItem.objects.filter(wishlist=wishlist, product_id=request.data.get("product")).delete()
        return Response({"detail": "Removed."})


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("status",)
    search_fields = ("order_number",)
    ordering = ("-created_at",)

    def get_queryset(self):
        user = self.request.user
        qs = Order.objects.prefetch_related("items__product", "items__seller").all()
        if user.is_staff or user.is_superuser or getattr(user, "role", "") == "ADMIN":
            return qs
        return qs.filter(customer=user)

    def perform_create(self, serializer):
        # Create an order from the user's cart (checkout). Requires login.
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        items = list(cart.items.select_related("product", "product__seller", "variant"))
        if not items:
            raise ValidationError("Your cart is empty.")

        order_num = f"ORD-{uuid.uuid4().hex[:10].upper()}"
        try:
            order = place_order_from_cart(
                cart=cart,
                cart_items=items,
                customer=self.request.user,
                order_num=order_num,
                shipping_cost=settings.SHIPPING_FLAT,
                payment_method=serializer.validated_data.get("payment_method", Order.PaymentMethod.ESEWA),
                payment_reference=serializer.validated_data.get("payment_reference", ""),
                whatsapp_number=serializer.validated_data.get("whatsapp_number", ""),
                full_name=serializer.validated_data.get("full_name", ""),
                phone=serializer.validated_data.get("phone", ""),
                province=serializer.validated_data.get("province", ""),
                district=serializer.validated_data.get("district", ""),
                city=serializer.validated_data.get("city", ""),
                address_line=serializer.validated_data.get("address_line", ""),
                landmark=serializer.validated_data.get("landmark", ""),
            )
        except InsufficientStock as exc:
            raise ValidationError(str(exc))

        serializer.instance = order

    def perform_update(self, serializer):
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, "role", "") == "ADMIN"
        if not is_admin and serializer.instance.customer != user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You cannot modify another customer's order.")
        if not is_admin:
            # Customers may not change status in Phase 1.
            serializer.save(status=serializer.instance.status)
        else:
            serializer.save()


class CartViewSet(viewsets.GenericViewSet):
    """Login-required cart: GET /cart/, POST /cart/add/, /cart/update/, /cart/remove/, /cart/clear/."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CartSerializer

    def get_cart(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart

    def list(self, request, *args, **kwargs):
        cart = self.get_cart()
        cart.items.select_related("product", "variant")
        return Response(self.get_serializer(cart).data)

    def _resolve(self, product_id, variant_id=None):
        try:
            product = Product.objects.select_related("seller").get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            return None, Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(pk=variant_id, product=product, is_active=True)
            except ProductVariant.DoesNotExist:
                return None, Response({"detail": "Variant not found."}, status=status.HTTP_404_NOT_FOUND)
        return (product, variant), None

    @action(detail=False, methods=["post"], url_path="add")
    def add(self, request):
        qty = max(1, int(request.data.get("quantity", 1)))
        resolved, err = self._resolve(request.data.get("product"), request.data.get("variant"))
        if err:
            return err
        product, variant = resolved
        cart = self.get_cart()
        item, created = CartItem.objects.get_or_create(cart=cart, product=product, variant=variant, defaults={"quantity": qty})
        if not created:
            item.quantity += qty
            item.save(update_fields=["quantity", "updated_at"])
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="update")
    def update_qty(self, request):
        qty = int(request.data.get("quantity", 1))
        cart = self.get_cart()
        try:
            item = CartItem.objects.get(cart=cart, pk=request.data.get("item"))
        except CartItem.DoesNotExist:
            return Response({"detail": "Item not found."}, status=status.HTTP_404_NOT_FOUND)
        if qty <= 0:
            item.delete()
        else:
            item.quantity = qty
            item.save(update_fields=["quantity", "updated_at"])
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=["post"], url_path="remove")
    def remove(self, request):
        cart = self.get_cart()
        CartItem.objects.filter(cart=cart, pk=request.data.get("item")).delete()
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=["post"], url_path="clear")
    def clear(self, request):
        cart = self.get_cart()
        cart.items.all().delete()
        return Response(CartSerializer(cart).data)


