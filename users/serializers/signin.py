from rest_framework import serializers
from django.contrib.auth import authenticate, login
from users.models import User
from users.validators.phone import validate_phone


class SigninSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=13, validators=[validate_phone])
    password = serializers.CharField(min_length=8)

    def check(self, attrs):
        try:
            user = User.objects.prefetch_related('auth_token').get(phone=attrs.get('phone'))
            if not user.check_password(attrs.get('password')):
                return {'error': 'Wrong password'}

            return {'data': {
                'id': user.id,
                'phone': user.phone,
                'username': user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                'token': user.auth_token.key,
            }}
        except User.DoesNotExist:
            return {'error': 'User not found'}
