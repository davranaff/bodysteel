from rest_framework import serializers

from store.models import Order
from store.utils.format_phone import format_phone_number
from users.serializers.basket import BasketSerializer


class OrderSerializer(serializers.ModelSerializer):
    baskets = BasketSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'id',
            'created_at',
            'total_price',
            'type',
            'full_name',
            'phone',
            'fix_check',
            'address',
            'status',
            'order_code',
            'coupon',
            'baskets',
        )


class StrictInputSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({
                'non_field_errors': ['Unknown order request field'],
            })
        return super().to_internal_value(data)


class OrderItemInputSerializer(StrictInputSerializer):
    product = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=100)


class OrderCreateSerializer(StrictInputSerializer):
    full_name = serializers.CharField(min_length=5, max_length=255, trim_whitespace=True)
    phone = serializers.CharField(min_length=12, max_length=32, trim_whitespace=True)
    address = serializers.CharField(min_length=1, max_length=255, trim_whitespace=True)
    type = serializers.ChoiceField(choices=Order.DELIVERY_CHOICES)
    baskets = OrderItemInputSerializer(many=True, allow_empty=False, min_length=1, max_length=20)
    coupon_code = serializers.CharField(
        min_length=1,
        max_length=20,
        allow_null=True,
        required=False,
        trim_whitespace=True,
    )
    integration_cart_token = serializers.RegexField(
        r'^[A-Za-z0-9_-]{32,64}$',
        allow_null=True,
        required=False,
    )

    def validate_phone(self, value):
        formatted = format_phone_number(value)
        if len(formatted) != 13 or not formatted.startswith('+998') or not formatted[1:].isdigit():
            raise serializers.ValidationError('Phone number is invalid')
        return formatted

    def validate(self, attrs):
        if attrs['type'] != 'pickup' and len(attrs['address']) < 2:
            raise serializers.ValidationError({'address': 'Delivery address is required'})
        return attrs
