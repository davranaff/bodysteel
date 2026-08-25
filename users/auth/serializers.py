from rest_framework import serializers
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError as DjangoValidationError

from users.validators.phone import validate_phone


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != set(self.fields):
            raise serializers.ValidationError('Unexpected or missing fields')
        return super().to_internal_value(data)


class StartRegistrationSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=254, trim_whitespace=False)
    phone = serializers.CharField(max_length=13, trim_whitespace=False, validators=[validate_phone])
    username = serializers.CharField(max_length=100, required=False, allow_blank=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, trim_whitespace=False)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, trim_whitespace=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError('Unexpected or missing fields')
        allowed = {'email', 'phone'}
        extended = allowed | {'username', 'first_name', 'last_name'}
        if set(data) not in (allowed, extended):
            raise serializers.ValidationError('Unexpected or missing fields')
        values = serializers.Serializer.to_internal_value(self, data)
        if set(data) == extended:
            for field in ('username', 'first_name', 'last_name'):
                values[field] = values[field].strip()
                if not values[field]:
                    raise serializers.ValidationError(f'{field} is required')
        return values


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
    identifier = serializers.CharField(max_length=254, required=False, trim_whitespace=False)
    phone = serializers.CharField(max_length=13, required=False, trim_whitespace=False, validators=[validate_phone])
    password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) not in ({'identifier', 'password'}, {'phone', 'password'}):
            raise serializers.ValidationError('Unexpected or missing fields')
        values = serializers.Serializer.to_internal_value(self, data)
        identifier = values.get('identifier') or values.get('phone')
        if identifier.startswith('+'):
            try:
                validate_phone(identifier)
            except DjangoValidationError:
                raise serializers.ValidationError('Invalid identifier') from None
        else:
            try:
                EmailValidator()(identifier)
            except DjangoValidationError:
                raise serializers.ValidationError('Invalid identifier') from None
        values['identifier'] = identifier.lower() if '@' in identifier else identifier
        values.pop('phone', None)
        return values

class PasswordResetRequestSerializer(StrictSerializer):
    identifier = serializers.CharField(max_length=254, trim_whitespace=False)

    def validate_identifier(self, value):
        if value.startswith('+'):
            try:
                validate_phone(value)
            except DjangoValidationError:
                raise serializers.ValidationError('Invalid identifier') from None
            return value
        try:
            EmailValidator()(value)
        except DjangoValidationError:
            raise serializers.ValidationError('Invalid identifier') from None
        return value.lower()


class PasswordResetCompleteSerializer(StrictSerializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r'^\d{6}$', trim_whitespace=False)
    password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)
    password_confirm = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError('Passwords do not match')
        return attrs
class ChangePasswordSerializer(StrictSerializer):
    current_password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)
    new_password_confirm = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError('Passwords do not match')
        return attrs


class DeleteAccountSerializer(StrictSerializer):
    password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)
    confirmation = serializers.RegexField(r'^DELETE$', trim_whitespace=False)


class EmailChangeStartSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=254, trim_whitespace=False)


class PhoneChangeStartSerializer(StrictSerializer):
    phone = serializers.CharField(max_length=13, trim_whitespace=False, validators=[validate_phone])


class ContactVerificationCompleteSerializer(StrictSerializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r'^\d{6}$', trim_whitespace=False)
