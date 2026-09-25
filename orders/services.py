"""Order placement service: oversell-safe checkout + stock reservation.

Consumed by both the storefront checkout and the DRF OrderViewSet so the
oversell protection is the same code path in both places.
"""
from decimal import Decimal
from typing import List, Tuple

from django.db import models, transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from catalog.models import Product, ProductVariant
from orders.models import Cart, CartItem, Order, OrderItem


class InsufficientStock(DjangoValidationError):
    code = "insufficient_stock"
    product = None
    requested = 0
    available = 0

    def __init__(self, msg: str, product, requested: int, available: int):
        super().__init__(msg, code="insufficient_stock")
        self.product = product
        self.requested = requested
        self.available = available


def _display_price(item: CartItem) -> Decimal:
    if item.variant_id:
        return item.variant.price
    return item.product.price


def _reserve_stock(items: List[Tuple[Product, CartItem]], order_num: str):
    """Lock + validate + decrement stock for every cart item inside an atomic block.

    Uses select_for_update on the row being decremented so two concurrent
    checkouts for the same stock can't both pass the availability check.
    Raises InsufficientStock on the first item that can't be fulfilled.
    """
    # Order items by (product, variant) to keep reserve deterministic.
    items_sorted = sorted(items, key=lambda p_ci: (p_ci[0].pk, p_ci[1].variant_id or 0))

    for product, cart_item in items_sorted:
        qty = cart_item.quantity
        variant = cart_item.variant

        if variant:
            # variant-level stock (variant.stock_quantity)
            row = (
                ProductVariant.objects
                .select_for_update()
                .filter(pk=variant.pk, stock_quantity__gte=qty)
                .first()
            )
            if row is None:
                raise InsufficientStock(
                    f"Not enough stock for '{product.name}' (variant '{variant.name}'). Requested {qty}, only {variant.stock_quantity} left.",
                    product, qty, variant.stock_quantity,
                )
            ProductVariant.objects.filter(pk=variant.pk).update(
                stock_quantity=models.F("stock_quantity") - qty
            )
        else:
            # product-level stock (product.stock_quantity)
            row = list(
                Product.objects
                .select_for_update()
                .filter(pk=product.pk, stock_quantity__gte=qty)
                .values_list("stock_quantity", flat=True)
            )
            cur = row[0] if row else 0
            if cur < qty:
                raise InsufficientStock(
                    f"Not enough stock for '{product.name}'. Requested {qty}, only {cur} left.",
                    product, qty, cur,
                )
            Product.objects.filter(pk=product.pk).update(
                stock_quantity=models.F("stock_quantity") - qty
            )


def place_order_from_cart(cart: Cart, cart_items: List[CartItem], customer, order_num: str,
                          shipping_cost: Decimal = Decimal("0"), discount: Decimal = Decimal("0"),
                          payment_method: str = "", payment_reference: str = "",
                          whatsapp_number: str = "",
                          full_name: str = "", phone: str = "",
                          province: str = "", district: str = "", city: str = "",
                          address_line: str = "", landmark: str = ""):
    """Create an order from a cart inside one transaction with oversell protection.

    Returns the created Order.  Raises InsufficientStock if stock can't cover
    all cart items.
    """
    with transaction.atomic():
        # 1. Reserve stock (locks, validates, decrements).
        _reserve_stock(
            [(ci.product, ci) for ci in cart_items],
            order_num=order_num,
        )

        subtotal = Decimal("0.00")
        order = Order.objects.create(
            customer=customer,
            order_number=order_num,
            status=Order.Status.PENDING,
            shipping_cost=shipping_cost,
            discount=discount,
            full_name=full_name,
            phone=phone,
            province=province,
            district=district,
            city=city,
            address_line=address_line,
            landmark=landmark,
            payment_method=payment_method,
            payment_reference=payment_reference,
            whatsapp_number=whatsapp_number,
            shipping_address=(
                f"{full_name} — {phone} — {address_line}, {city}, "
                f"{district}, {province}, Nepal"
            ),
        )

        for ci in cart_items:
            unit_price = _display_price(ci)
            OrderItem.objects.create(
                order=order,
                product=ci.product,
                variant=ci.variant,
                seller=ci.product.seller,
                product_name=ci.product.name,
                sku=ci.variant.sku if ci.variant_id else ci.product.sku,
                quantity=ci.quantity,
                unit_price=unit_price,
            )
            subtotal += unit_price * ci.quantity

        order.subtotal = subtotal
        order.total = subtotal + shipping_cost - discount
        if order.total < 0:
            order.total = Decimal("0.00")
        order.save(update_fields=["subtotal", "total", "updated_at"])

        # Clear the cart after a successful order.
        cart.items.all().delete()

        return order
