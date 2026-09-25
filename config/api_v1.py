"""API v1 router: /api/v1/..."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.views import AddressViewSet, MeView, RegisterView, SellerProfileViewSet
from catalog.views import CategoryViewSet, ProductVariantViewSet, ProductViewSet
from orders.views import CartViewSet, OrderViewSet, WishlistViewSet

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"variants", ProductVariantViewSet, basename="variant")
router.register(r"addresses", AddressViewSet, basename="address")
router.register(r"sellers", SellerProfileViewSet, basename="seller")
router.register(r"wishlist", WishlistViewSet, basename="wishlist")
router.register(r"cart", CartViewSet, basename="cart")
router.register(r"orders", OrderViewSet, basename="order")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("", include(router.urls)),
]
