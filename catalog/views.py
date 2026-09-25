"""Catalog API: categories, products, variants with seller isolation."""
from django.db.models import Prefetch
from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from accounts.models import SellerProfile
from config.permissions import IsAdmin
from .filters import ProductFilter
from .models import Category, Product, ProductImage, ProductVariant
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    ProductVariantSerializer,
    ProductWriteSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True).prefetch_related("children")
    serializer_class = CategorySerializer
    lookup_field = "slug"

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [IsAdmin()]


class ProductViewSet(viewsets.ModelViewSet):
    filterset_class = ProductFilter
    search_fields = ("name", "slug", "sku", "description", "short_description")
    ordering_fields = ("price", "created_at", "name")
    ordering = ("-created_at",)
    lookup_field = "slug"

    def get_queryset(self):
        qs = (
            Product.objects.select_related("seller", "category")
            .prefetch_related("tags", "images", "variants", "attributes")
            .all()
        )
        if self.action in ("list", "retrieve"):
            return qs.filter(is_active=True)
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductWriteSerializer
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductListSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action == "create":
            from config.permissions import IsSupplier

            # Single-seller store: the admin/staff IS the supplier, so allow
            # either the store admin or the (single) approved seller profile.
            return [IsSupplier()]
        return [permissions.IsAuthenticated()]

    def _seller_profile(self):
        user = self.request.user
        try:
            return user.seller_profile
        except SellerProfile.DoesNotExist:
            # Single-seller fallback: reuse the one store profile, or bind it
            # to this (admin) user when the store profile doesn't exist yet.
            profile = SellerProfile.objects.first()
            if profile is not None:
                return profile
            return SellerProfile.objects.create(
                user=user,
                business_name="Nismita Craft Studio",
                business_phone="+977 970-8909514",
                address="Narephate - 32",
                city="Kathmandu",
                country="Nepal",
                is_verified=True,
            )

    def perform_create(self, serializer):
        tags = serializer.validated_data.pop("tags", [])
        product = Product.objects.create(seller=self._seller_profile(), **serializer.validated_data)
        if tags:
            product.tags.set(tags)
        serializer.instance = product

    def perform_update(self, serializer):
        product = self.get_object()
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, "role", "") == "ADMIN"
        if not is_admin and product.seller.user != user:
            raise PermissionDenied("You cannot edit another seller's product.")
        serializer.save()

    def perform_destroy(self, serializer_instance=None):
        product = self.get_object()
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, "role", "") == "ADMIN"
        if not is_admin and product.seller.user != user:
            raise PermissionDenied("You cannot delete another seller's product.")
        product.is_active = False  # soft-deactivate instead of hard delete
        product.save(update_fields=["is_active", "updated_at"])


class ProductVariantViewSet(viewsets.ModelViewSet):
    serializer_class = ProductVariantSerializer

    def get_queryset(self):
        qs = ProductVariant.objects.select_related("product", "product__seller").all()
        if self.action in ("list", "retrieve"):
            return qs.filter(is_active=True, product__is_active=True)
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        product_id = self.request.data.get("product")
        try:
            product = Product.objects.select_related("seller").get(pk=product_id)
        except Product.DoesNotExist:
            raise PermissionDenied("Product not found.")
        is_admin = user.is_staff or user.is_superuser or getattr(user, "role", "") == "ADMIN"
        if not is_admin:
            if getattr(user, "role", "") != "SELLER" or not user.is_seller_approved:
                raise PermissionDenied("Only approved sellers can add variants.")
            if product.seller.user != user:
                raise PermissionDenied("You cannot add variants to another seller's product.")
        serializer.save(product=product)

    def _check_owner(self, obj):
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, "role", "") == "ADMIN"
        if not is_admin and obj.product.seller.user != user:
            raise PermissionDenied("You cannot modify another seller's variant.")

    def perform_update(self, serializer):
        self._check_owner(self.get_object())
        serializer.save()

    def perform_destroy(self, instance):
        self._check_owner(instance)
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


