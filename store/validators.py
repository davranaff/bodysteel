from django.core.exceptions import ValidationError


CATALOG_IMAGE_MAX_BYTES = 3 * 1024 * 1024


def validate_catalog_image_size(file):
    if file.size > CATALOG_IMAGE_MAX_BYTES:
        raise ValidationError(
            'Изображение должно быть не больше 3 МБ (сейчас %(size).1f МБ).',
            code='image_too_large',
            params={'size': file.size / (1024 * 1024)},
        )
