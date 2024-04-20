from rest_framework import serializers

from store.models import Product, ProductImage
from store.serializers.brand import BrandSerializer
from store.serializers.category import CategorySerializer
from store.serializers.review import ReviewSerializer


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['photo']


class ProductSerializer(serializers.ModelSerializer):
    product_images = ProductImageSerializer(many=True, read_only=True)
    rating = serializers.IntegerField(read_only=True)
    liked = serializers.BooleanField(read_only=True)
    is_leader_count = serializers.IntegerField(read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    category = CategorySerializer()
    brand = BrandSerializer()

    class Meta:
        model = Product
        fields = '__all__'
