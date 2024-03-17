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


class CreateBasketsListSerializer(serializers.Serializer):
    baskets = serializers.ListSerializer(allow_empty=True, required=True, child=serializers.DictField())

    def create(self, validated_data):
        products_ids = [item.get('product_id') for item in validated_data['baskets']]

        baskets = Basket.objects.filter(user=validated_data.get('user'), product_id__in=products_ids)

        if len(baskets) == len(validated_data.get('baskets')):
            return {'error': 'Такие корзины уже существуют'}

        if len(validated_data.get('baskets')):
            objs = [
                Basket(user_id=validated_data.get('user'),
                       product_id=item.get('product_id'),
                       quantity=item.get('quantity'),
                       ) for item in validated_data['baskets']
            ]

            Basket.objects.bulk_create(objs)

        return {'data': 'created'}
