from store.models import Category
from store.serializers.sanitized_model import SanitizedModelSerializer


class CategorySerializer(SanitizedModelSerializer):

    class Meta:
        model = Category
        fields = '__all__'

