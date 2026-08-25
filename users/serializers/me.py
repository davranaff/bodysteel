from rest_framework import serializers

from users.models import User


class UserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=False, max_length=100)
    email = serializers.EmailField(read_only=True)
    phone = serializers.CharField(read_only=True)

    def update(self, instance, validated_data):
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.username = validated_data.get("username", instance.username)
        instance.save()
        return instance

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone']




