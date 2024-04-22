from rest_framework import serializers

from store.models import Blog


class BlogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = ['id', 'name_uz', 'name_ru', 'description_uz', 'description_ru', 'photo', 'slug']
