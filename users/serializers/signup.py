from rest_framework import serializers

from users.models import User
from users.validators.phone import validate_phone
from users.utils.random_username import random_username


class PhoneVerificationSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=13, required=True, validators=[validate_phone])

    def create(self, validated_data):
        return User.objects.create(**validated_data, username=random_username())


class CodeVerificationSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=13, required=True)

    def check(self, attrs):
        ...
