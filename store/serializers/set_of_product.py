from rest_framework import serializers
from store.models import SetOfProduct
from store.serializers.products import ProductSerializer


class SetOfProductSerializer(serializers.ModelSerializer):
    products = ProductSerializer(many=True)

    class Meta:
        model = SetOfProduct
        fields = '__all__'


class SetOfProductsSerializerWithCount(serializers.ModelSerializer):
    products_count = serializers.IntegerField()

    class Meta:
        model = SetOfProduct
        fields = '__all__'
