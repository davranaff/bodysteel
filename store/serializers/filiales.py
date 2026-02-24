from rest_framework import serializers

from store.models import Filial, FilialPhoto


class FilialPhotoSerializer(serializers.ModelSerializer):

    class Meta:
        model = FilialPhoto
        fields = ['id', 'photo', 'created_at']
        read_only_fields = ['id', 'created_at']


class FilialSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    new_photos = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )
    delete_photo_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        is_create = self.instance is None
        has_legacy_photo = bool(attrs.get('photo'))
        has_new_photos = bool(attrs.get('new_photos'))

        if is_create and not has_legacy_photo and not has_new_photos:
            raise serializers.ValidationError({
                'new_photos': 'Добавьте минимум одно фото филиала.'
            })
        return attrs

    def get_photos(self, obj):
        photos = list(obj.photos.all())
        if photos:
            return FilialPhotoSerializer(photos, many=True, context=self.context).data

        if obj.photo:
            return [{
                'id': None,
                'photo': serializers.ImageField().to_representation(obj.photo),
                'created_at': obj.created_at,
            }]

        return []

    @staticmethod
    def _create_filial_photo_if_not_exists(instance, image_file):
        file_name = str(image_file)
        exists = instance.photos.filter(photo=file_name).exists()
        if not exists:
            FilialPhoto.objects.create(filial=instance, photo=image_file)

    def create(self, validated_data):
        new_photos = validated_data.pop('new_photos', [])
        validated_data.pop('delete_photo_ids', None)

        filial = super().create(validated_data)

        if filial.photo:
            self._create_filial_photo_if_not_exists(filial, filial.photo)

        for image in new_photos:
            FilialPhoto.objects.create(filial=filial, photo=image)

        return filial

    def update(self, instance, validated_data):
        new_photos = validated_data.pop('new_photos', [])
        delete_photo_ids = validated_data.pop('delete_photo_ids', [])
        old_photo_name = str(instance.photo) if instance.photo else ''

        filial = super().update(instance, validated_data)

        if delete_photo_ids:
            filial.photos.filter(id__in=delete_photo_ids).delete()

        if filial.photo and str(filial.photo) != old_photo_name:
            self._create_filial_photo_if_not_exists(filial, filial.photo)

        for image in new_photos:
            FilialPhoto.objects.create(filial=filial, photo=image)

        return filial

    class Meta:
        model = Filial
        fields = [
            'id',
            'name_uz',
            'name_ru',
            'address_uz',
            'address_ru',
            'work_time_start',
            'work_time_end',
            'day_off',
            'phone',
            'address_url',
            'address_location',
            'photo',
            'photos',
            'new_photos',
            'delete_photo_ids',
            'created_at',
        ]
