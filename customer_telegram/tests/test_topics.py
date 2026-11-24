"""Topics in private chats with the customer bot (Bot API 10.5 sidebar)."""
import json
from io import StringIO
from unittest.mock import patch

import httpx
from django.core.management import call_command
from django.test import TestCase, override_settings

from customer_telegram.bot_api import CustomerTelegramApi, DeliveryStatus
from customer_telegram.handlers import handle_update
from customer_telegram.models import CustomerTelegramChat
from customer_telegram.tests.base import TELEGRAM_SETTINGS
from customer_telegram.topics import ORDERS, PROMO, replying_in, topic_thread

SETTINGS = {**TELEGRAM_SETTINGS, 'TELEGRAM_WIDGETS_ROLLOUT': ''}


class Telegram:
    """A Bot API double that records every call; ``refuse_threads`` fails sends into a topic."""

    def __init__(self, refuse_threads=False):
        self.calls = []
        self.refuse_threads = refuse_threads
        self.next_thread = 40

    def api(self):
        return CustomerTelegramApi(client=httpx.Client(transport=httpx.MockTransport(self.handle)))

    def handle(self, request):
        method = request.url.path.rsplit('/', 1)[-1]
        payload = json.loads(request.content)
        self.calls.append((method, payload))
        if method == 'createForumTopic':
            self.next_thread += 1
            return httpx.Response(200, json={'ok': True, 'result': {'message_thread_id': self.next_thread, 'name': payload['name']}})
        if self.refuse_threads and 'message_thread_id' in payload:
            return httpx.Response(400, json={'ok': False, 'description': 'Bad Request: message thread not found'})
        return httpx.Response(200, json={'ok': True, 'result': {'message_id': len(self.calls)}})

    def sends(self):
        return [payload for method, payload in self.calls if method.startswith('send')]


def chat(**extra):
    return CustomerTelegramChat.objects.create(**{'telegram_user_id': 5001, 'chat_id': 5001, 'language': 'ru', **extra})


@override_settings(**SETTINGS)
class TopicRoutingTests(TestCase):
    def test_messages_inside_a_topic_block_carry_its_thread(self):
        telegram = Telegram()
        api = telegram.api()
        with replying_in(5001, 7):
            api.send_message(5001, 'в теме')
            api.send_message(5002, 'другой чат')
        api.send_message(5001, 'вне темы')
        threads = [payload.get('message_thread_id') for payload in telegram.sends()]
        self.assertEqual(threads, [7, None, None])

    def test_a_reply_goes_to_the_topic_the_shopper_wrote_in(self):
        telegram = Telegram()
        update = {'message': {
            'message_id': 1, 'message_thread_id': 9, 'from': {'id': 5001, 'is_bot': False, 'language_code': 'ru'},
            'chat': {'id': 5001, 'type': 'private'}, 'text': '/help',
        }}
        chat()
        handle_update(update, telegram.api())
        self.assertTrue(telegram.sends())
        self.assertTrue(all(payload.get('message_thread_id') == 9 for payload in telegram.sends()))

    def test_a_lost_topic_falls_back_to_the_chat_and_is_forgotten(self):
        record = chat(orders_topic_id=12)
        telegram = Telegram(refuse_threads=True)
        with replying_in(5001, 12):
            result = telegram.api().send_message(5001, 'оплачено')
        self.assertEqual(result.status, DeliveryStatus.SENT)
        self.assertEqual([payload.get('message_thread_id') for payload in telegram.sends()], [12, None])
        record.refresh_from_db()
        self.assertIsNone(record.orders_topic_id)


@override_settings(**SETTINGS, CUSTOMER_TELEGRAM_TOPICS=True)
class TopicCreationTests(TestCase):
    def test_topic_is_created_once_with_an_intro_in_the_chat_language(self):
        record = chat(language='uz')
        telegram = Telegram()
        api = telegram.api()
        thread = topic_thread(record, ORDERS, api)
        self.assertEqual(topic_thread(record, ORDERS, api), thread)
        created = [payload for method, payload in telegram.calls if method == 'createForumTopic']
        self.assertEqual(created, [{'chat_id': 5001, 'name': 'Buyurtmalarim', 'icon_color': 0x8EEE98}])
        record.refresh_from_db()
        self.assertEqual(record.orders_topic_id, thread)
        intro = telegram.sends()[0]
        self.assertEqual(intro['message_thread_id'], thread)
        self.assertIn('Buyurtmalarim', intro['text'])

    def test_start_prepares_the_shop_and_orders_topics(self):
        chat()
        telegram = Telegram()
        handle_update({'message': {
            'message_id': 1, 'from': {'id': 5001, 'is_bot': False, 'language_code': 'ru'},
            'chat': {'id': 5001, 'type': 'private'}, 'text': '/start',
        }}, telegram.api())
        names = [payload['name'] for method, payload in telegram.calls if method == 'createForumTopic']
        self.assertEqual(names, ['Магазин', 'Мои заказы'])

    def test_language_switch_renames_existing_topics(self):
        chat(shop_topic_id=3, orders_topic_id=4)
        telegram = Telegram()
        handle_update({'callback_query': {
            'id': 'callback-1', 'from': {'id': 5001, 'is_bot': False}, 'data': 'lang:uz',
            'message': {'message_id': 2, 'chat': {'id': 5001, 'type': 'private'}},
        }}, telegram.api())
        renames = [(payload['message_thread_id'], payload['name']) for method, payload in telegram.calls
                   if method == 'editForumTopic']
        self.assertEqual(renames, [(3, 'Do‘kon'), (4, 'Buyurtmalarim')])

    def test_refused_topic_leaves_the_plain_chat(self):
        record = chat()

        class Refusing(Telegram):
            def handle(self, request):
                if request.url.path.endswith('/createForumTopic'):
                    self.calls.append(('createForumTopic', {}))
                    return httpx.Response(400, json={'ok': False, 'description': 'Bad Request: TOPICS_DISABLED'})
                return super().handle(request)

        self.assertIsNone(topic_thread(record, PROMO, Refusing().api()))
        record.refresh_from_db()
        self.assertIsNone(record.promo_topic_id)


@override_settings(**SETTINGS)
class TopicsWithoutTheSwitchTests(TestCase):
    def test_no_topic_is_created_while_the_setting_is_off(self):
        telegram = Telegram()
        self.assertIsNone(topic_thread(chat(), ORDERS, telegram.api()))
        self.assertEqual(telegram.calls, [])

    def test_command_switches_the_bot_settings(self):
        telegram = Telegram()
        with patch('customer_telegram.management.commands.customer_telegram_topics.CustomerTelegramApi',
                   return_value=telegram.api()):
            call_command('customer_telegram_topics', '--on', stdout=StringIO())
            call_command('customer_telegram_topics', '--off', stdout=StringIO())
        self.assertEqual([payload for _method, payload in telegram.calls], [
            {'has_topics_enabled': True, 'has_topic_sidebar': True, 'allows_users_to_create_topics': False},
            {'has_topics_enabled': False, 'has_topic_sidebar': False},
        ])
