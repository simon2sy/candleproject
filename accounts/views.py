"""Accounts API: register, me, addresses, seller profiles."""
from rest_framework import generics, permissions, viewsets

from .models import Address, SellerProfile
from .serializers import AddressSerializer, RegisterSerializer, SellerProfileSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer


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
    serializer_class = SellerProfileSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser or getattr(user, "role", "") == "ADMIN":
            return SellerProfile.objects.select_related("user").all()
        if getattr(user, "role", "") == "SELLER":
            return SellerProfile.objects.select_related("user").filter(user=user)
        return SellerProfile.objects.select_related("user").filter(is_verified=True)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

