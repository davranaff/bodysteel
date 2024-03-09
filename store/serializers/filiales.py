from rest_framework import serializers

from store.models import Filial


class FilialSerializer(serializers.ModelSerializer):

    class Meta:
        model = Filial
        fields = '__all__'
