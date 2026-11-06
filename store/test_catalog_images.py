from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from store.models import Category, Product360Image, ProductImage
from store.validators import CATALOG_IMAGE_MAX_BYTES, validate_catalog_image_size


class CatalogImageSizeTests(SimpleTestCase):
    def test_accepts_image_of_exactly_three_megabytes(self):
        validate_catalog_image_size(SimpleUploadedFile('ok.jpg', b'0' * CATALOG_IMAGE_MAX_BYTES))

    def test_rejects_image_over_three_megabytes(self):
        with self.assertRaises(ValidationError) as caught:
            validate_catalog_image_size(SimpleUploadedFile('big.jpg', b'0' * (CATALOG_IMAGE_MAX_BYTES + 1)))

        self.assertEqual(caught.exception.code, 'image_too_large')
        self.assertIn('3 МБ', caught.exception.messages[0])

    def test_catalog_photo_fields_use_the_limit(self):
        for model in (Category, ProductImage, Product360Image):
            with self.subTest(model=model.__name__):
                field = model._meta.get_field('photo')
                self.assertIn(validate_catalog_image_size, field.validators)
