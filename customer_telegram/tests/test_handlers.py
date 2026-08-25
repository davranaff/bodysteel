from django.test import TestCase, override_settings
from urllib.parse import parse_qs, urlsplit

from customer_telegram.handlers import handle_update
from customer_telegram.i18n import catalogs_match, message
from customer_telegram.keyboards import main_menu
from customer_telegram.models import CustomerTelegramChat
from customer_telegram.links import start_account_link
from customer_telegram.tests.base import FakeTelegramApi, TELEGRAM_SETTINGS
from users.models import User


@override_settings(**TELEGRAM_SETTINGS)
class CustomerTelegramHandlerTests(TestCase):
    def test_first_start_requires_explicit_language_selection(self):
        api = FakeTelegramApi()
        result = handle_update(self.message('/start', language_code='uz'), api)
        self.assertEqual(result, 'language')
        chat = CustomerTelegramChat.objects.get(chat_id=5001)
        self.assertEqual(chat.language, '')
        self.assertEqual(api.messages[0][1], message('ru', 'choose_language'))

        result = handle_update(self.callback('lang:uz'), api)
        self.assertEqual(result, 'language')
        chat.refresh_from_db()
        self.assertEqual(chat.language, 'uz')
        self.assertEqual(api.callbacks, [('callback-1', None)])

    def test_callback_sender_must_own_private_chat(self):
        CustomerTelegramChat.objects.create(
            telegram_user_id=5001, chat_id=5001, language='ru',
        )
        api = FakeTelegramApi()
        payload = self.callback('notify:on')
        payload['callback_query']['from']['id'] = 5002
        self.assertEqual(handle_update(payload, api), 'denied')
        self.assertFalse(CustomerTelegramChat.objects.get(chat_id=5001).marketing_opt_in)
        self.assertEqual(api.callbacks, [('callback-1', None)])

    def test_stop_only_disables_marketing_and_unlink_is_visible(self):
        chat = CustomerTelegramChat.objects.create(
            telegram_user_id=5001, chat_id=5001, language='ru', marketing_opt_in=True,
        )
        api = FakeTelegramApi()
        self.assertEqual(handle_update(self.message('/stop'), api), 'notifications_off')
        chat.refresh_from_db()
        self.assertFalse(chat.marketing_opt_in)
        self.assertTrue(chat.is_active)
        labels = [button['text'] for row in main_menu('ru')['keyboard'] for button in row]
        self.assertIn(message('ru', 'menu_unlink'), labels)

    def test_ru_and_uz_catalogs_have_exact_parity(self):
        self.assertTrue(catalogs_match())

    def test_notification_consent_requires_explicit_valid_callback(self):
        chat = CustomerTelegramChat.objects.create(
            telegram_user_id=5001, chat_id=5001, language='uz',
        )
        self.assertFalse(chat.marketing_opt_in)
        api = FakeTelegramApi()
        self.assertEqual(handle_update(self.callback('notify:on'), api), 'notifications')
        chat.refresh_from_db()
        self.assertTrue(chat.marketing_opt_in)
        self.assertEqual(chat.marketing_consent_source, 'bot_callback')
        self.assertIsNotNone(chat.marketing_opted_in_at)
        self.assertEqual(handle_update(self.callback('notify:off'), api), 'notifications')
        chat.refresh_from_db()
        self.assertFalse(chat.marketing_opt_in)
        self.assertIsNotNone(chat.marketing_opted_out_at)
        invalid = self.callback('lang:en')
        self.assertEqual(handle_update(invalid, api), 'ignored')
        chat.refresh_from_db()
        self.assertEqual(chat.language, 'uz')

    def test_deep_link_language_is_honored_before_chat_language(self):
        user = User.objects.create_user(
            username='language-link', email='language-link@example.test',
            phone='+998901234599', password='safe-password',
        )
        receipt = start_account_link(user, 'uz')
        token = parse_qs(urlsplit(receipt.telegram_url).query)['start'][0]
        api = FakeTelegramApi()
        self.assertEqual(handle_update(self.message('/start {}'.format(token)), api), 'contact_requested')
        self.assertEqual(api.messages[0][1], message('uz', 'request_contact'))

    @staticmethod
    def message(text, language_code='ru'):
        return {'message': {
            'message_id': 1,
            'from': {'id': 5001, 'is_bot': False, 'language_code': language_code},
            'chat': {'id': 5001, 'type': 'private'},
            'text': text,
        }}

    @staticmethod
    def callback(data):
        return {'callback_query': {
            'id': 'callback-1',
            'from': {'id': 5001, 'is_bot': False},
            'data': data,
            'message': {
                'message_id': 2,
                'from': {'id': 7001, 'is_bot': True},
                'chat': {'id': 5001, 'type': 'private'},
            },
        }}
