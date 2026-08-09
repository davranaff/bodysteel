from store.models import Blog
from store.serializers.sanitized_model import SanitizedModelSerializer


class BlogSerializer(SanitizedModelSerializer):
    class Meta:
        model = Blog
        fields = ['id', 'name_uz', 'name_ru', 'description_uz', 'description_ru', 'photo', 'slug']
