from rest_framework import serializers
from rest_framework.authtoken.models import Token

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

        token = Token.objects.get(user=instance)

        return {
            'username': instance.username,
            'email': instance.email,
            'phone': instance.phone,
            'first_name': instance.first_name,
            'last_name': instance.last_name,
            'id': instance.id,
            "token": token.key,
        }

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone']






