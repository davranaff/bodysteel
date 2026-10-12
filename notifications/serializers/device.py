from rest_framework import serializers

from notifications.models import PushDevice
from .audience import StrictSerializer


class DeviceSerializer(StrictSerializer):
    token = serializers.RegexField(r'^[A-Za-z0-9_:\-]{16,4096}$', required=False, write_only=True)
    platform = serializers.ChoiceField(choices=PushDevice.Platform.values)
    model = serializers.CharField(max_length=100, allow_blank=True, default='')
    os_version = serializers.CharField(max_length=40, allow_blank=True, default='')
    app_version = serializers.CharField(max_length=40, allow_blank=True, default='')
    app_build = serializers.CharField(max_length=40, allow_blank=True, default='')
    permission = serializers.ChoiceField(choices=PushDevice.Permission.values)
    marketing_opt_in = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if attrs['permission'] in ('authorized', 'provisional') and not attrs.get('token'):
            raise serializers.ValidationError('An authorized installation needs its FCM token')
        return attrs
