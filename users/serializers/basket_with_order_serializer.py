from store.models import Basket
from store.serializers.products import ProductSerializer
from users.serializers.order import OrderCreateSerializer
from rest_framework import serializers


class BasketOrderSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    order = OrderCreateSerializer(read_only=True)

    class Meta:
        model = Basket
        fields = ['id', 'price', 'quantity', 'product', 'order']
