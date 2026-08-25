from rest_framework import serializers

from payments.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ('id', 'provider', 'provider_payment_id', 'amount', 'currency', 'status', 'created_at', 'paid_at')


class EmptyPaymentInputSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or data:
            raise serializers.ValidationError({'detail': 'Request body must be empty'})
        return {}
