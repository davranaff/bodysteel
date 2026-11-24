"""Order alerts as rich messages and staff invites from the bot owner (Bot API 10.5)."""
import json
from unittest.mock import patch

import httpx
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from teleg import views
from teleg.models import Chat
from teleg.test_widgets import STAFF_SETTINGS, basket, order
from teleg.utils.notify_message import notify_message
from teleg.utils.order_rich import PAUSE_KEY, rich_order_html
from telegram_widgets.rollout import PAUSE_KEY as WIDGET_PAUSE_KEY

TEXT_ONLY = {**STAFF_SETTINGS, 'TELEGRAM_WIDGETS_ROLLOUT': ''}


class RichOrderHtmlTests(TestCase):
    def test_short_order_opens_a_table_and_escapes_names(self):
        html = rich_order_html(['🛒 <b>Новый заказ № 1</b>', '', '💵 <b>Оплата при получении</b>'],
                               [('Whey <Gold>', 2, 300_000)], ['', '💰 <b>Итого: 300 000 UZS</b>'])
        self.assertTrue(html.startswith('<p>🛒 <b>Новый заказ № 1</b></p><p>💵 <b>Оплата при получении</b></p>'))
        self.assertIn('<details open><summary>📦 <b>Товары · 1</b></summary><table bordered striped compact>', html)
        self.assertIn('<tr><td>Whey &lt;Gold&gt;</td><td align="center">2</td><td align="right">300 000</td></tr>', html)
        self.assertTrue(html.endswith('</details><p>💰 <b>Итого: 300 000 UZS</b></p>'))

    def test_long_order_folds_the_table(self):
        html = rich_order_html(['x'], [('Item', 1, 1_000)] * 7, [])
        self.assertIn('<details><summary>📦 <b>Товары · 7</b></summary>', html)

    def test_huge_order_points_to_the_admin(self):
        html = rich_order_html(['x'], [('Item', 1, 1_000)] * 85, [])
        self.assertEqual(html.count('<tr><td>'), 80)
        self.assertIn('… ещё 5 поз.', html)


def rich_transport(status=200, body=None):
    calls = []

    def handler(request):
        calls.append((request.url.path.rsplit('/', 1)[-1], json.loads(request.content)))
        return httpx.Response(status, json=body or {'ok': True, 'result': {'message_id': 91}})
    return httpx.MockTransport(handler), calls


@override_settings(**TEXT_ONLY)
class RichOrderDeliveryTests(TestCase):
    def setUp(self):
        for key in (PAUSE_KEY, WIDGET_PAUSE_KEY):
            cache.delete(key)
            self.addCleanup(cache.delete, key)
        Chat.objects.create(chat_id='1001', first_name='Owner')

    def notify(self, transport, located=False):
        real_client = httpx.Client
        coordinates = {} if located else {'address_latitude': None, 'address_longitude': None}
        with patch('teleg.widget_api.httpx.Client', side_effect=lambda **options: real_client(transport=transport)), \
                patch('teleg.utils.notify_message.bot.send_message') as send_message, \
                patch('teleg.utils.notify_message.bot.send_venue') as send_venue:
            notify_message(order(**coordinates), [basket('Креатин', 2, 300_000)])
        return send_message, send_venue

    def test_alert_is_one_rich_message_with_the_buttons(self):
        transport, calls = rich_transport()
        send_message, send_venue = self.notify(transport, located=True)
        self.assertEqual([method for method, _ in calls], ['sendRichMessage'])
        payload = calls[0][1]
        self.assertEqual(payload['chat_id'], '1001')
        self.assertIn('<td>Креатин</td>', payload['rich_message']['html'])
        self.assertIn('inline_keyboard', payload['reply_markup'])
        send_message.assert_not_called()
        self.assertEqual(send_venue.call_args.kwargs['reply_to_message_id'], 91)

    def test_refused_rich_message_falls_back_to_text_and_pauses(self):
        transport, calls = rich_transport(400, {'ok': False, 'description': 'Bad Request: RICH_MESSAGE_NOT_ALLOWED'})
        send_message, _ = self.notify(transport)
        send_message.assert_called_once()
        self.assertTrue(cache.get(PAUSE_KEY))
        self.notify(transport)
        self.assertEqual(len(calls), 1, 'paused: the next alert does not ask Telegram again')

    @override_settings(STAFF_TELEGRAM_RICH_ORDERS=False)
    def test_switch_off_sends_plain_text(self):
        transport, calls = rich_transport()
        send_message, _ = self.notify(transport)
        self.assertEqual(calls, [])
        send_message.assert_called_once()


def invite_update(chat_type='private', inviter_id=42, chat_id=5005):
    return {'update_id': 1, 'message': {
        'message_id': 3, 'date': 1, 'chat': {'id': chat_id, 'type': chat_type, 'first_name': 'Aziz <x>', 'username': 'aziz'},
        'from': {'id': chat_id, 'is_bot': False, 'first_name': 'Aziz'},
        'write_access_allowed': {'inviter': {'id': inviter_id, 'is_bot': False, 'first_name': 'Owner'}},
    }}


@override_settings(STAFF_TELEGRAM_WEBHOOK_SECRET='')
class OwnerInviteTests(TestCase):
    def post(self, update):
        request = RequestFactory().post('/teleg/', data=json.dumps(update), content_type='application/json')
        with patch('teleg.views.reply') as reply, patch.object(views.bot, 'process_new_updates') as process:
            response = views.index(request)
        self.assertEqual(response.status_code, 200)
        return reply, process

    def test_invited_person_becomes_staff_and_is_greeted(self):
        reply, process = self.post(invite_update())
        chat = Chat.objects.get(chat_id='5005')
        self.assertEqual((chat.first_name, chat.username), ('Aziz <x>', 'aziz'))
        self.assertIn('Aziz &lt;x&gt;', reply.call_args.args[2])
        process.assert_not_called()

    def test_second_invite_registers_once_and_stays_quiet(self):
        self.post(invite_update())
        reply, _ = self.post(invite_update())
        self.assertEqual(Chat.objects.filter(chat_id='5005').count(), 1)
        reply.assert_not_called()

    @override_settings(STAFF_TELEGRAM_OWNER_IDS=frozenset({7}))
    def test_invite_from_someone_else_is_ignored(self):
        with self.assertLogs('teleg.invites', 'WARNING'):
            _, process = self.post(invite_update(inviter_id=42))
        self.assertFalse(Chat.objects.filter(chat_id='5005').exists())
        process.assert_called_once()

    def test_group_service_message_is_not_an_invite(self):
        self.post(invite_update(chat_type='group', chat_id=-100))
        self.assertFalse(Chat.objects.exists())
