from rest_framework import serializers

from django.core.validators import MinValueValidator

from store.models import Basket, Product
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


class CreateBasketsListSerializer(serializers.Serializer):
    baskets = serializers.ListSerializer(allow_empty=True, required=True, child=serializers.DictField())

    def create(self, validated_data):

        if len(validated_data.get('baskets')):
            baskets = []

            for item in validated_data['baskets']:
                basket = Basket.objects.create(
                    product_id=item.get('product'),
                    quantity=item.get('quantity'),
                )
                product = Product.objects.get(id=item.get('product'))
                product.quantity -= int(item.get('quantity'))
                product.save()
                baskets.append(basket.id)

            return {'data': baskets}

