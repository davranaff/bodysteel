from rest_framework import serializers

from store.models import Favorite

from store.serializers.products import ProductSerializer


class GetFavoritesSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = Favorite
        fields = ['id', 'user', 'product', ]


class CreateFavoritesSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=True)
    user_id = serializers.IntegerField(required=True)

    def create(self, validated_data, *args, **kwargs):
        try:
            favorite = Favorite.objects.get(**validated_data)
            favorite.delete()
            return {'data': 'deleted'}
        except Favorite.DoesNotExist:
            Favorite.objects.create(**validated_data)
            return {'data': 'created'}
