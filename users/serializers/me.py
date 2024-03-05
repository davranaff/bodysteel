from rest_framework import serializers

from store.models import Favorite
from store.serializers.products import ProductSerializer
from users.models import User


class UserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False)

    def update(self, instance, validated_data):
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.username = validated_data.get("username", instance.username)
        instance.save()
        return {
            'username': instance.username,
            'email': instance.email,
            'phone': instance.phone,
            'first_name': instance.first_name,
            'last_name': instance.last_name,
            'id': instance.id
        }

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone']


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
