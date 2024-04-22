from rest_framework import serializers

from store.models import Order
from users.serializers.basket import BasketSerializer


class OrderSerializer(serializers.ModelSerializer):
    baskets = BasketSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = '__all__'


class OrderCreateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(required=True)
    phone = serializers.CharField(required=True)
    email = serializers.EmailField(required=False)
    address = serializers.CharField(required=True)
    fix_check = serializers.FileField(required=True)
    order_code = serializers.CharField(required=False)

    def create(self, validated_data):
        order = Order.objects.create(**validated_data)
        return order

    class Meta:
        model = Order
        fields = '__all__'
