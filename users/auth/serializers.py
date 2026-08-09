from rest_framework import serializers

from users.validators.phone import validate_phone


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != set(self.fields):
            raise serializers.ValidationError('Unexpected or missing fields')
        return super().to_internal_value(data)


class StartRegistrationSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=254, trim_whitespace=False)
    phone = serializers.CharField(max_length=13, trim_whitespace=False, validators=[validate_phone])


class CompleteRegistrationSerializer(StrictSerializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r'^\d{6}$', trim_whitespace=False)
    password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)
    password_confirm = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError('Passwords do not match')
        return attrs


class SignInSerializer(StrictSerializer):
    phone = serializers.CharField(max_length=13, trim_whitespace=False, validators=[validate_phone])
    password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)
