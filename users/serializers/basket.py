from rest_framework import serializers

from django.core.validators import MinValueValidator

from store.models import Basket
from store.serializers.products import ProductSerializer


class BasketSerializer(serializers.ModelSerializer):
    quantity = serializers.IntegerField(validators=[MinValueValidator(1)])
    product = ProductSerializer(read_only=True)

    def update(self, instance, validated_data):
        instance.quantity = validated_data.get("quantity", instance.quantity)
        return super(BasketSerializer, self).update(instance, validated_data)

    class Meta:
        model = Basket
        fields = ['id', 'price', 'quantity', 'product', ]
