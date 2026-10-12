from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError('Unknown or invalid fields')
        return super().to_internal_value(data)


class AudienceSerializer(StrictSerializer):
    platforms = serializers.ListField(child=serializers.ChoiceField(choices=('android', 'ios')), required=False, max_length=2)
    languages = serializers.ListField(child=serializers.ChoiceField(choices=('ru', 'uz')), required=False, max_length=2)
    device_models = serializers.ListField(child=serializers.CharField(max_length=100), required=False, max_length=50)
    app_version = serializers.CharField(max_length=40, required=False)
    os_version_prefix = serializers.CharField(max_length=40, required=False)
    device_seen_after = serializers.DateTimeField(required=False)
    device_seen_before = serializers.DateTimeField(required=False)
    include_staff = serializers.BooleanField(default=False)
    one_device_per_user = serializers.BooleanField(default=False)
    user_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=200)
    group_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=100)
    joined_after = serializers.DateTimeField(required=False)
    joined_before = serializers.DateTimeField(required=False)
    login_after = serializers.DateTimeField(required=False)
    login_before = serializers.DateTimeField(required=False)
    phone_verified = serializers.BooleanField(required=False)
    email_verified = serializers.BooleanField(required=False)
    bonus_used = serializers.BooleanField(required=False)
    telegram_connected = serializers.BooleanField(required=False)
    order_scope = serializers.ChoiceField(choices=('purchases', 'paid', 'delivered', 'all'), default='purchases')
    order_count_min = serializers.IntegerField(min_value=0, required=False)
    order_count_max = serializers.IntegerField(min_value=0, required=False)
    spend_min = serializers.IntegerField(min_value=0, required=False)
    spend_max = serializers.IntegerField(min_value=0, required=False)
    last_purchase_after = serializers.DateTimeField(required=False)
    last_purchase_before = serializers.DateTimeField(required=False)
    fulfillment_statuses = serializers.ListField(child=serializers.ChoiceField(choices=(
        'new', 'confirmed', 'preparing', 'ready', 'delivering', 'delivered', 'cancelled')), required=False, max_length=7)
    payment_statuses = serializers.ListField(child=serializers.ChoiceField(choices=(
        'unpaid', 'pending', 'paid', 'failed', 'refunded')), required=False, max_length=5)
    delivery_methods = serializers.ListField(child=serializers.CharField(max_length=50), required=False, max_length=50)
    delivery_zones = serializers.ListField(child=serializers.CharField(max_length=100), required=False, max_length=100)
    used_coupon = serializers.BooleanField(required=False)
    has_cart = serializers.BooleanField(required=False)
    has_favorites = serializers.BooleanField(required=False)
    has_course_access = serializers.BooleanField(required=False)
    course_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=100)

    def get_fields(self):
        fields = super().get_fields()
        for prefix in ('purchased', 'last_purchase', 'cart', 'favorite'):
            for kind in ('product', 'category', 'brand'):
                fields[prefix + '_' + kind + '_ids'] = serializers.ListField(
                    child=serializers.IntegerField(min_value=1), required=False, max_length=200)
        return fields

    def validate(self, attrs):
        pairs = [('order_count_min', 'order_count_max'), ('spend_min', 'spend_max')]
        pairs += [(prefix + '_after', prefix + '_before') for prefix in ('device_seen', 'joined', 'login', 'last_purchase')]
        for lower, upper in pairs:
            if lower in attrs and upper in attrs and attrs[lower] > attrs[upper]:
                raise serializers.ValidationError({upper: 'Upper boundary must not precede lower boundary'})
        return attrs
