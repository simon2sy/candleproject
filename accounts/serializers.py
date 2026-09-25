"""Accounts serializers: registration, profile, addresses, seller profiles."""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Address, SellerProfile, User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    role = serializers.ChoiceField(choices=[User.Roles.CUSTOMER, User.Roles.SELLER], default=User.Roles.CUSTOMER)

    class Meta:
        model = User
        fields = ("username", "email", "password", "first_name", "last_name", "phone", "role")

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        # ADMIN can never be self-registered; serializer choices already exclude it.
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if user.role == User.Roles.SELLER:
            SellerProfile.objects.get_or_create(user=user, defaults={"business_name": user.username})
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id", "username", "email", "first_name", "last_name", "phone",
            "role", "is_seller_approved", "seller_approved_at", "date_joined",
        )
        read_only_fields = ("id", "role", "is_seller_approved", "seller_approved_at", "date_joined")


class SellerProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    is_approved = serializers.BooleanField(source="user.is_seller_approved", read_only=True)

    class Meta:
        model = SellerProfile
        fields = (
            "id", "user", "username", "business_name", "business_description", "business_phone",
            "business_email", "address", "city", "state", "country", "postal_code",
            "tax_number", "logo", "is_verified", "is_approved", "created_at", "updated_at",
        )
        read_only_fields = ("id", "user", "is_verified", "created_at", "updated_at")


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id", "full_name", "phone", "address_line_1", "address_line_2",
            "city", "state", "country", "postal_code", "is_default", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
