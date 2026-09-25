"""Catalog serializers."""
from rest_framework import serializers

from .models import Category, Product, ProductAttribute, ProductImage, ProductVariant, Tag


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "image", "parent", "is_active", "children")

    def get_children(self, obj):
        children = obj.children.filter(is_active=True)
        return CategorySerializer(children, many=True, context=self.context).data


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "slug")


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image", "alt_text", "is_primary", "display_order")


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ("id", "product", "name", "sku", "price", "compare_at_price", "stock_quantity", "is_active")
        read_only_fields = ("product",)


class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = ("id", "product", "name", "value")
        read_only_fields = ("product",)


class ProductListSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    seller = serializers.CharField(source="seller.business_name", read_only=True)
    primary_image = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "seller", "category", "tags", "name", "slug", "sku", "short_description",
            "price", "compare_at_price", "stock_quantity", "is_active", "is_featured",
            "is_available", "primary_image", "created_at",
        )

    def get_primary_image(self, obj):
        img = getattr(obj, "_primary_image", None)
        if img is None:
            img = next((i for i in obj.images.all() if i.is_primary), None) or (obj.images.first() if hasattr(obj, "images") else None)
        if not img:
            return None
        request = self.context.get("request")
        url = img.image.url if hasattr(img.image, "url") else None
        return request.build_absolute_uri(url) if request and url else url


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    category_detail = CategorySerializer(source="category", read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ("description", "images", "variants", "attributes", "category_detail")


class ProductWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            "category", "tags", "name", "slug", "sku", "short_description", "description",
            "price", "compare_at_price", "stock_quantity", "low_stock_threshold",
            "is_active", "is_featured", "is_available",
        )

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        seller = self.context["seller"]
        product = Product.objects.create(seller=seller, **validated_data)
        if tags:
            product.tags.set(tags)
        return product
