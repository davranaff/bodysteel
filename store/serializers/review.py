from rest_framework import serializers

from django.core.validators import MinValueValidator, MaxValueValidator

from store.models import Review
from users.serializers.me import UserSerializer


class ReviewSerializer(serializers.ModelSerializer):
    rating = serializers.IntegerField(required=True, validators=[MinValueValidator(0), MaxValueValidator(5)])
    user = UserSerializer(read_only=True, required=False)
    full_name = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = Review
        fields = '__all__'
