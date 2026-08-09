from store.models import Menu
from store.serializers.sanitized_model import SanitizedModelSerializer


class MenuSerializer(SanitizedModelSerializer):

    class Meta:
        model = Menu
        fields = '__all__'
