"""Users, registration, seller approval tests."""
from accounts.models import SellerProfile, User
from catalog.models import Category
from django.test import TestCase
from rest_framework.test import APIClient

from .helpers import login, make_seller


class UserTests(TestCase):
    def test_customer_registration_defaults_to_customer(self):
        c = APIClient()
        res = c.post("/api/v1/auth/register/", {
            "username": "buyer1", "email": "buyer1@example.com", "password": "Testpass123!",
        }, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(User.objects.get(username="buyer1").role, User.Roles.CUSTOMER)

    def test_cannot_self_register_as_admin(self):
        c = APIClient()
        res = c.post("/api/v1/auth/register/", {
            "username": "hacker", "email": "h@example.com", "password": "Testpass123!", "role": "ADMIN",
        }, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(User.objects.filter(username="hacker", role="ADMIN").exists())

    def test_seller_registration_creates_profile_unapproved(self):
        c = APIClient()
        res = c.post("/api/v1/auth/register/", {
            "username": "sellerx", "email": "sx@example.com", "password": "Testpass123!", "role": "SELLER",
        }, format="json")
        self.assertEqual(res.status_code, 201)
        u = User.objects.get(username="sellerx")
        self.assertFalse(u.is_seller_approved)
        self.assertTrue(SellerProfile.objects.filter(user=u).exists())


class SellerApprovalTests(TestCase):
    def _product_payload(self, cat):
        return {"category": cat.id, "name": "Wax", "slug": "wax-1", "sku": "WAX-1",
                "price": "10.00", "stock_quantity": 5}

    def test_unapproved_seller_cannot_create_product(self):
        make_seller("s1", approved=False)
        c = login(APIClient(), "s1")
        cat = Category.objects.create(name="Wax", slug="wax")
        res = c.post("/api/v1/products/", self._product_payload(cat), format="json")
        self.assertEqual(res.status_code, 403)

    def test_seller_approval_allows_create(self):
        make_seller("s2", approved=True)
        c = login(APIClient(), "s2")
        cat = Category.objects.create(name="Wax", slug="wax")
        res = c.post("/api/v1/products/", self._product_payload(cat), format="json")
        self.assertEqual(res.status_code, 201)
