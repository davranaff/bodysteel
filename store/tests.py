from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from store.models import Filial, FilialPhoto, Product


class FilialApiTests(APITestCase):
    @staticmethod
    def _image_file(name='photo.gif'):
        return SimpleUploadedFile(
            name,
            b'GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;',
            content_type='image/gif'
        )

    @staticmethod
    def _filial_payload():
        return {
            'name_uz': 'Bukhara 1',
            'name_ru': 'Бухара 1',
            'address_uz': 'Республика Узбекистан, г. Бухара',
            'address_ru': 'Республика Узбекистан, г. Бухара',
            'work_time_start': '09:00',
            'work_time_end': '20:00',
            'day_off': 'Воскресенье',
            'phone': '+998901112233',
            'address_url': 'https://maps.google.com',
            'address_location': 'https://maps.google.com/?q=bukhara',
        }

    def test_filiales_list_returns_gallery(self):
        filial = Filial.objects.create(**self._filial_payload(), photo=self._image_file('cover.gif'))
        FilialPhoto.objects.create(filial=filial, photo=self._image_file('extra.gif'))

        response = self.client.get(reverse('store:filiales'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertIn('photos', response.data['data'][0])
        self.assertEqual(len(response.data['data'][0]['photos']), 1)

    def test_create_filial_with_multiple_photos(self):
        admin_user = get_user_model().objects.create_superuser(
            username='admin_filial',
            email='admin@example.com',
            phone='+998900000001',
            password='test-pass-123',
            first_name='Admin',
            last_name='User',
        )
        self.client.force_authenticate(user=admin_user)

        payload = self._filial_payload()
        payload['new_photos'] = [self._image_file('photo-1.gif'), self._image_file('photo-2.gif')]

        response = self.client.post(reverse('store:filiales'), payload, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Filial.objects.count(), 1)
        filial = Filial.objects.first()
        self.assertEqual(FilialPhoto.objects.filter(filial=filial).count(), 2)
        self.assertEqual(len(response.data['data']['photos']), 2)

    def test_create_filial_requires_admin(self):
        payload = self._filial_payload()
        payload['new_photos'] = [self._image_file('photo.gif')]

        response = self.client.post(reverse('store:filiales'), payload, format='multipart')

        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class StorefrontChannelApiTests(APITestCase):
    def setUp(self):
        self.supplement = Product.objects.create(
            name_ru='Тестовый протеин для каталога',
            name_uz='Katalog uchun sinov proteini',
            slug='test-supplement-channel',
            description_ru='<p>Спортивное питание</p>',
            description_uz='<p>Sport ovqatlanishi</p>',
            price=100000,
            country_ru='Uzbekistan',
            country_uz='O‘zbekiston',
            product_type=Product.TYPE_SUPPLEMENT,
            quantity=5,
        )
        self.meal = Product.objects.create(
            name_ru='Тестовый обед ПП для каталога',
            name_uz='Katalog uchun sinov PP taomi',
            slug='test-meal-channel',
            description_ru='<p>Правильное питание</p>',
            description_uz='<p>To‘g‘ri ovqatlanish</p>',
            price=65000,
            country_ru='Uzbekistan',
            country_uz='O‘zbekiston',
            product_type=Product.TYPE_MEAL,
            quantity=5,
        )

    def test_sports_storefront_does_not_include_pp_products(self):
        response = self.client.get('/api/v1/store/products/?all=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product_ids = [item['id'] for item in response.data['data']]
        self.assertIn(self.supplement.pk, product_ids)
        self.assertNotIn(self.meal.pk, product_ids)

    def test_pp_has_a_separate_catalog_endpoint(self):
        response = self.client.get('/api/v1/nutrition/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product_ids = [item['id'] for item in response.data['data']]
        self.assertIn(self.meal.pk, product_ids)
        self.assertNotIn(self.supplement.pk, product_ids)
