from django.core.validators import MaxValueValidator, MinValueValidator
from rest_framework import serializers

from store.catalog.reviews.privacy import author_key
from store.models import Review


class ReviewCreateSerializer(serializers.ModelSerializer):
    """Customer input for a new review; moderation fields are never writable."""

    rating = serializers.IntegerField(required=True, validators=[MinValueValidator(1), MaxValueValidator(5)])

    class Meta:
        model = Review
        fields = ('rating', 'comment', 'product')


class ReviewAuthorSerializer(serializers.Serializer):
    # Only the public display handle; never email, phone, names or the account id.
    username = serializers.CharField(read_only=True)


class ReviewSerializer(serializers.ModelSerializer):
    """Public, PII-free representation of a published review."""

    user = ReviewAuthorSerializer(read_only=True, allow_null=True)
    author_id = serializers.SerializerMethodField()

    def get_author_id(self, instance):
        return author_key(instance.user_id)

    class Meta:
        model = Review
        fields = ('id', 'user', 'author_id', 'full_name', 'rating', 'comment', 'product', 'created_at')
        read_only_fields = fields


def published_reviews(product):
    """Published reviews of a product, reusing ``with_storefront_relations`` prefetches."""
    prefetched = getattr(product, 'published_reviews', None)
    if prefetched is not None:
        return prefetched
    return product.reviews.published().select_related('user')
