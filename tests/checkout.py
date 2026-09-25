"""Checkout, oversell, screenshot and pagination test helpers."""
from base64 import b64decode
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import SellerProfile, User
from catalog.models import Category, Product
from orders.models import Order

_VALID_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDw"
    "ADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def valid_png():
    return SimpleUploadedFile(
        "screenshot.png", b64decode(_VALID_PNG_B64), content_type="image/png"
    )


def oversized_png():
    return SimpleUploadedFile(
        "big.png", b"x" * (6 * 1024 * 1024), content_type="image/png"
    )


def fake_png():
    return SimpleUploadedFile(
        "fake.png", b"not a real png at all", content_type="image/png"
    )


def checkout_payload(overrides=None):
    payload = {
        "full_name": "Ram Shrestha",
        "phone": "9800000000",
        "province": "Bagmati",
        "district": "Kathmandu",
        "city": "Kathmandu",
        "address_line": "Mg Road",
        "landmark": "",
        "payment_method": "ESEWA",
        "payment_reference": "",
        "whatsapp_number": "",
    }
    if overrides:
        payload.update(overrides)
    return payload


def add_to_cart(client, product, quantity=1):
    return client.post(f"/cart/add/{product.pk}/", {"quantity": quantity})


def clear_cart(cart):
    cart.items.all().delete()


def create_seller_user(username):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="Sellerpass123!",
        is_staff=False,
        is_active=True,
        is_seller=True,
    )
    SellerProfile.objects.create(user=user)
    return user, user.sellerprofile


def create_product(seller, category, stock=5, price=Decimal("300.00"), sku="TST-001"):
    return Product.objects.create(
        seller=seller,
        category=category,
        name=f"Test Product {sku}",
        slug=f"test-{sku.lower()}",
        sku=sku,
        price=price,
        stock_quantity=stock,
    )


def create_pending_order(customer, number="ORD-001", total=Decimal("100.00")):
    return Order.objects.create(
        customer=customer,
        order_number=number,
        status=Order.Status.PENDING,
        total=total,
        shipping_cost=Decimal("0.00"),
    )
