from rest_framework import serializers

from nutrition.models import Allergen, DeliveryMethod, NutritionProfile


def language_from_request(request):
    value = request.headers.get('Accept-Language', 'ru').lower()
    return 'uz' if value.startswith('uz') else 'ru'


class LocalizedSerializer(serializers.Serializer):
    def localized(self, instance, field, language):
        return getattr(instance, '{}_{}'.format(field, language))


class NutritionProfileSerializer(serializers.ModelSerializer):
    storage = serializers.SerializerMethodField()
    serving = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    allergens = serializers.SerializerMethodField()
    delivery_methods = serializers.SerializerMethodField()

    class Meta:
        model = NutritionProfile
        fields = (
            'kind', 'portion_weight_grams', 'servings', 'calories_kcal',
            'protein_grams', 'fat_grams', 'carbohydrate_grams',
            'shelf_life_hours', 'requires_cooling', 'is_available',
            'storage', 'serving', 'tags', 'allergens', 'delivery_methods',
        )

    def _language(self):
        return self.context.get('language', 'ru')

    def get_storage(self, instance):
        return getattr(instance, 'storage_{}'.format(self._language()))

    def get_serving(self, instance):
        return getattr(instance, 'serving_{}'.format(self._language()))

    def get_tags(self, instance):
        language = self._language()
        return [getattr(tag, 'name_{}'.format(language)) for tag in instance.tags.all()]

    def get_allergens(self, instance):
        language = self._language()
        return [getattr(item, 'name_{}'.format(language)) for item in instance.allergens.all()]

    def get_delivery_methods(self, instance):
        language = self._language()
        return [
            {
                'code': method.code,
                'name': getattr(method, 'name_{}'.format(language)),
                'kind': method.kind,
            }
            for method in instance.allowed_delivery_methods.filter(is_active=True)
        ]


class DeliveryMethodSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryMethod
        fields = ('code', 'name', 'kind', 'base_fee', 'minimum_order', 'free_from')

    def get_name(self, instance):
        language = self.context.get('language', 'ru')
        return getattr(instance, 'name_{}'.format(language))


class DeliveryZoneSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    fee = serializers.IntegerField()


class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = ('slug', 'name_ru', 'name_uz')
