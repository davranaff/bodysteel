from rest_framework import serializers

from store.models import Blog


class BlogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = ['id', 'name', 'name_en', 'description', 'description_en', 'photo']
