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


class CreateFavoritesListSerializer(serializers.Serializer):
    products = serializers.ListSerializer(allow_empty=True, child=serializers.IntegerField(), required=True)
    user_id = serializers.IntegerField(required=True)

    def create(self, validated_data, *args, **kwargs):
        favorites = Favorite.objects.filter(user_id=validated_data['user_id'], product_id__in=validated_data['products'])

        if len(validated_data['products']) == len(favorites):
            return {'error': 'Такие продукты уже существуют'}

        if len(validated_data['products']):
            objs = [
                Favorite(product_id=item, user_id=validated_data['user_id']) for item in validated_data['products']
            ]

            Favorite.objects.bulk_create(objs)

        return {'data': 'created'}
