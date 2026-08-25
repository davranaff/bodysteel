from rest_framework import serializers


class CheckoutItemSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=100)


class CheckoutQuoteSerializer(serializers.Serializer):
    baskets = CheckoutItemSerializer(many=True, allow_empty=False, min_length=1, max_length=20)
    type = serializers.ChoiceField(choices=('dcb', 'dtu', 'pickup'))
    delivery_method_code = serializers.RegexField(r'^[a-z0-9_-]{1,50}$', required=False, allow_blank=True)
    delivery_zone_code = serializers.RegexField(r'^[a-z0-9_-]{1,100}$', required=False, allow_blank=True)
    delivery_slot_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    coupon_code = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError({'detail': 'Invalid checkout quote'})
        allowed = set(self.fields)
        if set(data) - allowed:
            raise serializers.ValidationError({'detail': 'Unknown checkout quote field'})
        return super().to_internal_value(data)
