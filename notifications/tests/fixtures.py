import uuid
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth.models import Permission
from django.utils import timezone
from rest_framework.authtoken.models import Token

from notifications.clients.firebase import SendResult
from notifications.models import PushCampaign
from notifications.services.devices import register_device
from store.models import Basket, Category, Order, Product
from users.models import User

PUSH_SETTINGS = {'PUSH_ENABLED': True, 'PUSH_FIREBASE_PROJECT_ID': 'synthetic-test-project',
                 'PUSH_TOKEN_ENCRYPTION_KEYS': (Fernet.generate_key().decode(),),
                 'BODYSTEEL_STOREFRONT_PROXY_TOKEN': 'synthetic-storefront-proxy-with-40-characters'}


def shopper(index=1, **kwargs):
    return User.objects.create_user(username='push-shopper-{}'.format(index), email='push{}@example.test'.format(index),
                                   phone='+99890{:07d}'.format(index), **kwargs)


def operator(index=99):
    user = shopper(index, is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label='notifications'))
    return user


def device_values(token='synthetic-fcm-token-000000000001', **kwargs):
    return {'token': token, 'platform': 'android', 'model': 'Pixel 8', 'os_version': '16',
            'app_version': '1.0.0', 'app_build': '1', 'permission': 'authorized', 'marketing_opt_in': True, **kwargs}


def device(user, **kwargs):
    credential, _ = Token.objects.get_or_create(user=user)
    installation = uuid.uuid4()
    values = device_values(token='synthetic-fcm-' + uuid.uuid4().hex, **kwargs)
    register_device(user, credential, installation, values, kwargs.get('language', 'ru'))
    from notifications.models import PushDevice
    return PushDevice.objects.get(installation_id=installation)


def campaign(actor, **kwargs):
    return PushCampaign.objects.create(created_by=actor, name='Synthetic campaign', title_ru='RU title',
        title_uz='UZ title', body_ru='RU text', body_uz='UZ text', target_url='https://bodysteel.uz/app/catalog', **kwargs)


def product(index=1, category=None, brand=None):
    item = Product.objects.create(name_ru='Push product {}'.format(index), name_uz='Push product UZ {}'.format(index),
        slug='push-product-{}'.format(index), price=100000, quantity=100,
        country_ru='Test', country_uz='Test', brand=brand)
    if category:
        item.category.add(category)
    return item


def category(index=1):
    return Category.objects.create(name_ru='Push category {}'.format(index), name_uz='Push category UZ {}'.format(index),
                                   photo='synthetic.jpg', description='Test', sort=index)


def purchase(user, item=None, **kwargs):
    order = Order.objects.create(user=user, type='pickup', full_name='Synthetic shopper', phone=user.phone,
        subtotal_price=100000, total_price=kwargs.pop('total_price', 100000), status='purchased', **kwargs)
    if item:
        Basket.objects.create(user=user, order=order, product=item, quantity=1)
    return order


class FakeSender:
    def __init__(self, results=None, callback=None):
        self.results = list(results or [SendResult('accepted', message_id='synthetic-message')])
        self.calls = []
        self.callback = callback

    def send(self, token, delivery):
        self.calls.append((token, delivery.pk))
        if self.callback:
            self.callback(delivery)
        return self.results.pop(0) if self.results else SendResult('accepted')
