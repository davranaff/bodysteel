from rest_framework import serializers
from store.models import Coupon


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['id', 'code', 'discount_percent', 'max_uses', 'used_count', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at', 'used_count']


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField(required=True)

    def validate_code(self, value):
        try:
            coupon = Coupon.objects.get(code=value, is_active=True)
            if not coupon.can_use():
                raise serializers.ValidationError("Купон больше не может быть использован")
            return value
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Купон не найден или неактивен") 