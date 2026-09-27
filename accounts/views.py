"""Accounts API: register, me, addresses, seller profiles."""
import logging

from django.db.models import ProtectedError
from rest_framework import generics, permissions, throttling, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView

from config.permissions import IsAdmin
from .models import Address, SellerProfile
from .serializers import AddressSerializer, RegisterSerializer, SellerProfileSerializer, UserSerializer

logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer
    # Sign-up abuse guard.  Without ``throttle_scope`` the ``auth_register``
    # rate in DEFAULT_THROTTLE_RATES was configured but never enforced.
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "auth_register"


class LoginView(TokenObtainPairView):
    """Password login with a brute-force guard.

    The ``auth_login`` rate in ``DEFAULT_THROTTLE_RATES`` was configured but
    never applied to this view, so credential stuffing was unlimited.
    """

    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "auth_login"


class LogoutView(TokenBlacklistView):
    """Blacklist the caller's refresh token so it cannot be replayed."""

    permission_classes = [permissions.IsAuthenticated]


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SellerProfileViewSet(viewsets.ModelViewSet):
    """Seller profiles: public read, admin-only write.

    This viewset used to rely on ``get_queryset()`` alone for access control,
    so *any* authenticated customer fell through to the verified-profile branch,
    could ``PATCH`` the store's own profile (address, phone, bank details) and —
    because ``Product.seller`` cascaded — a single ``DELETE`` wiped the whole
    catalogue.
    """

    serializer_class = SellerProfileSerializer

    def get_permissions(self):
        """Reads stay public; every write requires staff/ADMIN."""
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [IsAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and (
            user.is_staff or user.is_superuser or getattr(user, "role", "") == "ADMIN"
        ):
            return SellerProfile.objects.select_related("user").all()
        if user.is_authenticated and getattr(user, "role", "") == "SELLER":
            return SellerProfile.objects.select_related("user").filter(user=user)
        return SellerProfile.objects.select_related("user").filter(is_verified=True)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        # Deleting a profile detaches products from their seller, so treat it as
        # a deliberate admin action and keep a trace of who did it.
        logger.warning(
            "SellerProfile %s (pk=%s) deleted by %s",
            instance, instance.pk, self.request.user,
        )
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                {
                    "detail": "This seller still has products. Re-assign or delete "
                    "those products before deleting the profile."
                }
            )

