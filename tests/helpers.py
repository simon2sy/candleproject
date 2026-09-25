"""Shared fixtures for Phase 1 tests."""
from decimal import Decimal

from accounts.models import SellerProfile, User
from catalog.models import Category, Product


def make_user(username, role=User.Roles.CUSTOMER, approved=False, **kw):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password="Testpass123!",
        role=role, is_seller_approved=approved, **kw,
    )


def make_seller(username, approved=True):
    user = make_user(username, role=User.Roles.SELLER, approved=approved)
    profile, _ = SellerProfile.objects.get_or_create(user=user, defaults={"business_name": f"{username} store"})
    return user, profile


def make_product(seller, category, name="Soy Wax", sku="SOY-500", price="350.00"):
    slug = name.lower().replace(" ", "-") + f"-{sku.lower()}"
    return Product.objects.create(
        seller=seller, category=category, name=name, slug=slug,
        sku=sku, price=Decimal(price), stock_quantity=10,
    )


def login(client, username):
    tok = client.post("/api/v1/auth/login/", {"username": username, "password": "Testpass123!"}, format="json").data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tok}")
    return client
