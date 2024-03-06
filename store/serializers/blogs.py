from rest_framework import serializers

from store.models import Blog


class BlogSerializer(serializers.ModelSerializer):

    class Meta:
        model = Blog
        fields = ['name', 'name_en', 'photo']
