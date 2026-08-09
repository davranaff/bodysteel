from rest_framework import serializers

from store.content.html import sanitize_html
from store.fields import SanitizedHtmlField


class SanitizedModelSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        for field in instance._meta.concrete_fields:
            if isinstance(field, SanitizedHtmlField) and field.name in representation:
                representation[field.name] = sanitize_html(representation[field.name])
        return representation
