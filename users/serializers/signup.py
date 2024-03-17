from rest_framework import serializers
from rest_framework.authtoken.models import Token
from django.contrib.auth.hashers import make_password

from users.models import User
from users.validators.phone import validate_phone


class PhoneVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=13, required=True, validators=[validate_phone])

    def create(self, validated_data):
        if User.objects.filter(phone=validated_data['phone'], email=validated_data['email']).exists():
            return {'error': 'Phone number or email is exists'}
        User.objects.create(**validated_data)
        return {'error': None}


class SignUpSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=13, required=True, validators=[validate_phone])
    password = serializers.CharField(min_length=8)
    password_confirm = serializers.CharField(min_length=8)
    # code = serializers.CharField(max_length=6, required=True)

    def check(self, attrs):
        try:
            user = User.objects.get(phone=attrs.get('phone'))

            if user:

                if attrs.get('password') == attrs.get('password_confirm'):
                    user.password = make_password(attrs.get('password'))
                    user.verification = True
                    user.code = None
                    user.save(with_code=False)

                    token = Token.objects.create(user=user)

                    return {'data': {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "phone": user.phone,
                        'token': token.key
                    }}
                return {'error': 'Password mismatch'}

            return {'error': 'phone or code invalid!'}

        except User.DoesNotExist:
            return {'error': 'user does not exist!'}
