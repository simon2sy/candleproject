"""Shared DRF permissions for Phase 1."""
from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_staff or u.is_superuser or getattr(u, "role", "") == "ADMIN"))


class IsSeller(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "role", "") == "SELLER")


class IsApprovedSeller(IsSeller):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and bool(getattr(request.user, "is_seller_approved", False))


class IsSupplier(IsAdmin):
    """Single-seller store: the admin/staff IS the supplier, and the one
    approved seller profile may also create products.

    Composed with plain boolean logic because DRF's ``|`` only combines
    permission *classes*, not instances.
    """

    def has_permission(self, request, view):
        return super().has_permission(request, view) or IsApprovedSeller().has_permission(request, view)


class IsOwner(permissions.BasePermission):
    """Object-level: user owns the object (user attr) or seller owns product."""

    def has_object_permission(self, request, view, obj):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if getattr(obj, "user", None) == u:
            return True
        # Product owned via seller profile
        seller = getattr(obj, "seller", None)
        if seller is not None and getattr(seller, "user", None) == u:
            return True
        # Address / wishlist item nested ownership
        owner = getattr(getattr(obj, "wishlist", None), "user", None)
        if owner == u:
            return True
        return False
