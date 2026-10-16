from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers

from store.models import Product, ProductImage, Product360Image, Category
from store.serializers.brand import BrandSerializer
from store.serializers.category import CategorySerializer
from store.serializers.review import ReviewSerializer, published_reviews
from store.serializers.sanitized_model import SanitizedModelSerializer
from nutrition.serializers import NutritionProfileSerializer


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['photo']


class Product360ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product360Image
        fields = ['id', 'photo', 'sort_order']


class ProductSerializer(SanitizedModelSerializer):
    product_images = ProductImageSerializer(many=True, read_only=True)
    product_360_images = Product360ImageSerializer(many=True, read_only=True)
    rating = serializers.IntegerField(read_only=True)
    liked = serializers.BooleanField(read_only=True)
    is_leader_count = serializers.IntegerField(read_only=True)
    reviews = serializers.SerializerMethodField()
    category = serializers.PrimaryKeyRelatedField(many=True, queryset=Category.objects.all())
    brand = BrandSerializer()
    nutrition_profile = serializers.SerializerMethodField()

    @swagger_serializer_method(serializer_or_field=ReviewSerializer(many=True))
    def get_reviews(self, instance):
        # Unmoderated or hidden reviews never leave the backend.
        return ReviewSerializer(published_reviews(instance), many=True).data

    def get_nutrition_profile(self, instance):
        profile = getattr(instance, 'nutrition_profile', None)
        if not profile:
            return None
        language = self.context.get('request').headers.get('Accept-Language', 'ru') if self.context.get('request') else 'ru'
        language = 'uz' if language.lower().startswith('uz') else 'ru'
        return NutritionProfileSerializer(profile, context={'language': language}).data

    class Meta:
        model = Product
        fields = '__all__'
