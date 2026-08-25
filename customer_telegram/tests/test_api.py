from urllib.parse import parse_qs, urlsplit

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from customer_telegram.models import CustomerTelegramChat, CustomerTelegramLink
from customer_telegram.tests.base import TELEGRAM_SETTINGS
from users.models import User


@override_settings(**TELEGRAM_SETTINGS)
class CustomerTelegramApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.headers = {
            'HTTP_X_STOREFRONT_PROXY_TOKEN': TELEGRAM_SETTINGS['BODYSTEEL_STOREFRONT_PROXY_TOKEN'],
            'HTTP_ACCEPT_LANGUAGE': 'ru',
        }

    def test_registration_start_has_strict_boundary_and_safe_receipt(self):
        url = '/api/v1/users/telegram/registration/start/'
        identity = {
            'email': 'new@example.test', 'phone': '+998901234581', 'username': 'new-shopper',
            'first_name': 'New', 'last_name': 'Shopper',
        }
        self.assertEqual(self.client.post(url, identity, format='json').status_code, 403)
        bad_language = {**self.headers, 'HTTP_ACCEPT_LANGUAGE': 'en'}
        self.assertEqual(self.client.post(url, identity, format='json', **bad_language).status_code, 406)
        self.assertEqual(self.client.post(
            url, {**identity, 'is_staff': True}, format='json', **self.headers,
        ).status_code, 400)

        response = self.client.post(url, identity, format='json', **self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['Content-Language'], 'ru')
        self.assertEqual(set(response.data['data']), {
            'challenge_id', 'expires_in', 'resend_after', 'telegram_url',
        })
        deep_link = response.data['data']['telegram_url']
        self.assertEqual(urlsplit(deep_link).netloc, 't.me')
        token = parse_qs(urlsplit(deep_link).query)['start'][0]
        self.assertLessEqual(len(token), 64)
        self.assertNotIn(identity['phone'], deep_link)
        self.assertNotIn(token, CustomerTelegramLink.objects.get().token_digest)

    def test_password_reset_is_neutral_for_missing_account(self):
        response = self.client.post(
            '/api/v1/users/telegram/password/forgot/',
            {'identifier': 'missing@example.test'},
            format='json',
            **{**self.headers, 'HTTP_ACCEPT_LANGUAGE': 'uz'},
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.headers['Content-Language'], 'uz')
        self.assertEqual(set(response.data['data']), {
            'challenge_id', 'expires_in', 'resend_after', 'telegram_url',
        })

    def test_account_link_requires_authentication_and_unlink_clears_marketing(self):
        status_url = '/api/v1/users/telegram/account/'
        link_url = '/api/v1/users/telegram/account/link/start/'
        unlink_url = '/api/v1/users/telegram/account/unlink/'
        self.assertEqual(self.client.get(status_url).status_code, 401)
        self.assertEqual(self.client.post(link_url, {}, format='json').status_code, 401)
        self.assertEqual(self.client.post(unlink_url, {}, format='json').status_code, 401)

        user = User.objects.create_user(
            username='account-link', email='account-link@example.test',
            phone='+998901234582', password='safe-password',
        )
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(status_url).data, {
            'data': {'connected': False, 'notifications': False},
        })
        response = self.client.post(
            link_url, {}, format='json', HTTP_ACCEPT_LANGUAGE='uz',
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['data']['telegram_url'].startswith(
            'https://t.me/BodySteelClientBot?start=a_',
        ))
        chat = CustomerTelegramChat.objects.create(
            user=user, telegram_user_id=9101, chat_id=9101, language='uz',
            marketing_opt_in=True,
        )
        self.assertEqual(self.client.get(status_url).data['data'], {
            'connected': True, 'notifications': True,
        })
        self.assertEqual(self.client.post(unlink_url, {}, format='json').status_code, 204)
        chat.refresh_from_db()
        self.assertIsNone(chat.user_id)
        self.assertFalse(chat.marketing_opt_in)
        self.assertFalse(CustomerTelegramLink.objects.filter(
            user=user, state=CustomerTelegramLink.AWAITING_START,
        ).exists())

    def test_account_soft_delete_unlinks_chat_and_disables_marketing(self):
        user = User.objects.create_user(
            username='delete-link', email='delete-link@example.test',
            phone='+998901234583', password='safe-password',
        )
        chat = CustomerTelegramChat.objects.create(
            user=user, telegram_user_id=9102, chat_id=9102, language='ru',
            marketing_opt_in=True,
        )
        self.client.force_authenticate(user)
        self.assertEqual(self.client.delete('/api/v1/users/me/').status_code, 204)
        user.refresh_from_db()
        chat.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.deleted_at)
        self.assertIsNone(chat.user_id)
        self.assertFalse(chat.marketing_opt_in)
