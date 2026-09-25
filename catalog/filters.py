"""Catalog filters."""
import django_filters

from .models import Product


class ProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category__slug", lookup_expr="iexact")
    seller = django_filters.NumberFilter(field_name="seller__id")
    seller_name = django_filters.CharFilter(field_name="seller__business_name", lookup_expr="icontains")
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    tag = django_filters.CharFilter(field_name="tags__slug", lookup_expr="iexact")

    class Meta:
        model = Product
        fields = ["category", "seller", "seller_name", "min_price", "max_price", "is_featured", "is_available", "tag"]
