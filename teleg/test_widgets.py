import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from store.models import Basket, Order, Product
from teleg.cards import order_card_html
from teleg.models import Chat
from teleg.stats import period_state
from teleg.utils.notify_message import notify_message
from teleg.widget_api import StaffWidgetError, send_widget
from teleg.widget_queries import handle_staff_widget_query
from telegram_widgets.html import MAXIMUM_COMPRESSED_BYTES, compressed_size
from telegram_widgets.rollout import PAUSE_KEY, widgets_enabled
from telegram_widgets.state import fits


STAFF_SETTINGS = {'BOT_TOKEN': '200000:staff_telegram_token_1234567890123', 'CUSTOMER_TELEGRAM_PUBLIC_ORIGIN': 'https://api.bodysteel.uz',
                  'TELEGRAM_WIDGETS_ROLLOUT': 'all'}


def order(**extra):
    values = dict(pk=371, order_code='0439278651', created_at=timezone.now(), type='dcb', address='Zebiniso 13',
                  full_name='Xakim <b>Xakberdiyev</b>', phone='+998946833883', total_price=1_520_000, address_label='',
                  address_latitude=Decimal('39.774723'), address_longitude=Decimal('64.419841'), customer_note='')
    values.update(extra)
    return SimpleNamespace(**values)


def basket(name, quantity, price):
    return SimpleNamespace(product=SimpleNamespace(name_ru=name), quantity=quantity, price=price)


@override_settings(**STAFF_SETTINGS)
class StaffOrderCardTests(TestCase):
    def test_order_alert_goes_as_a_widget_card_without_the_text_copy(self):
        Chat.objects.create(chat_id='1001', first_name='Staff')
        with patch('teleg.utils.notify_message.send_widget', return_value=55) as send_widget, \
                patch('teleg.utils.notify_message.bot.send_message') as send_message:
            notify_message(order(), [basket('Dymatize ISO100', 1, 1_150_000)], paid=True)
        send_message.assert_not_called()
        chat_id, html, caption = send_widget.call_args.args
        self.assertEqual(chat_id, '1001')
        self.assertIn('✅ Оплачен заказ № 0439278651 · 1 520 000 UZS', caption)
        self.assertIn('ОПЛАЧЕН ОНЛАЙН', html)
        self.assertIn('https://maps.google.com/?q=39.774723,64.419841', html)
        self.assertIn('/admin/store/order/371/change/', html)
        self.assertNotIn('<b>Xakberdiyev</b>', html)

    def test_a_huge_order_drops_items_to_fit_the_4kb_limit(self):
        baskets = [basket('Протеин с очень длинным названием и вкусом номер {}'.format(index), 2, 300_000 + index)
                   for index in range(80)]
        html = order_card_html(order(), baskets)
        self.assertLessEqual(compressed_size(html), MAXIMUM_COMPRESSED_BYTES)
        self.assertIn('… ещё', html)


@override_settings(**STAFF_SETTINGS)
class StaffReportTests(TestCase):
    def setUp(self):
        product = Product.objects.create(name_ru='Креатин', name_uz='Kreatin', price=150_000, quantity=5, slug='kreatin',
                                         country_ru='США', country_uz='AQSH')
        sale = Order.objects.create(total_price=300_000, type='pickup', full_name='Ali Valiyev', phone='+998901234567', address='')
        Basket.objects.create(order=sale, product=product, quantity=2)

    def test_report_counts_sales_and_fits_the_state_limit(self):
        state = period_state('w')
        self.assertTrue(fits(state))
        self.assertIn('Креатин · 2 шт. · 300 000 UZS', state['t'])
        self.assertEqual([button[1] for button in state['b']], ['S:d', 'S:w', 'S:m', 'S:y'])

    def test_period_button_answers_registered_staff_only(self):
        Chat.objects.create(chat_id='1001', first_name='Staff')
        with patch('teleg.widget_queries.answer_widget_query') as deny, \
                patch('teleg.replies.answer_widget_query') as answer, patch('teleg.replies.edit_widget_data') as edit:
            self.assertEqual(handle_staff_widget_query(self.query(1001, 'S:m')), 'answered')
            self.assertEqual(handle_staff_widget_query(self.query(2002, 'S:m')), 'denied')
            self.assertEqual(handle_staff_widget_query(self.query(1001, 'S:x')), 'denied')
        self.assertIn('за последний месяц', json.loads(answer.call_args.args[1])['h'])
        edit.assert_called_once()
        self.assertEqual(deny.call_count, 2)

    def test_webhook_routes_widget_queries_and_checks_the_optional_secret(self):
        body = json.dumps({'update_id': 1, 'widget_query': self.query(1001, 'S:d')})
        with patch('teleg.views.handle_staff_widget_query') as handle:
            response = self.client.post('/telegram/', body, content_type='application/json')
            self.assertEqual(response.status_code, 200)
            handle.assert_called_once()
            with self.settings(STAFF_TELEGRAM_WEBHOOK_SECRET='staff-secret-value'):
                refused = self.client.post('/telegram/', body, content_type='application/json')
                accepted = self.client.post('/telegram/', body, content_type='application/json',
                                            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='staff-secret-value')
        self.assertEqual((refused.status_code, accepted.status_code), (403, 200))
        self.assertEqual(handle.call_count, 2)

    @staticmethod
    def query(sender, data):
        return {'id': 'q-{}'.format(sender), 'from': {'id': sender, 'is_bot': False, 'first_name': 'S'},
                'chat': {'id': sender, 'type': 'private'}, 'message_id': 9, 'chat_instance': '1',
                'type': {'type': 'data'}, 'data': data}


@override_settings(**{**STAFF_SETTINGS, 'TELEGRAM_WIDGETS_ROLLOUT': '1001'})
class StaffRolloutTests(TestCase):
    def test_only_trial_chats_get_the_widget_others_keep_the_text_alert(self):
        Chat.objects.create(chat_id='1001', first_name='Owner')
        Chat.objects.create(chat_id='1002', first_name='Staff')
        with patch('teleg.utils.notify_message.send_widget', return_value=55) as send_widget, \
                patch('teleg.utils.notify_message.bot.send_message') as send_message, \
                patch('teleg.utils.notify_message.bot.send_venue'):
            notify_message(order(), [basket('Креатин', 1, 150_000)])
        self.assertEqual([call.args[0] for call in send_widget.call_args_list], ['1001'])
        self.assertEqual([call.args[0] for call in send_message.call_args_list], ['1002'])


def refusing_transport(description='Bad Request: INPUT_MEDIA_WIDGET_NOT_ALLOWED'):
    calls = []

    def handler(request):
        calls.append(request.url.path.rsplit('/', 1)[-1])
        return httpx.Response(400, json={'ok': False, 'error_code': 400, 'description': description})
    return httpx.MockTransport(handler), calls


@override_settings(**STAFF_SETTINGS)
class StaffWidgetRefusalTests(TestCase):
    """Telegram stopped accepting widgets from every bot (13 November 2026)."""

    def setUp(self):
        cache.delete(PAUSE_KEY)
        self.addCleanup(cache.delete, PAUSE_KEY)

    def test_refusal_keeps_only_the_code_and_pauses_widgets(self):
        transport, calls = refusing_transport()
        with self.assertRaises(StaffWidgetError) as raised:
            send_widget('1001', '<p>x</p>', 'x', client=httpx.Client(transport=transport))
        self.assertEqual(raised.exception.code, 'INPUT_MEDIA_WIDGET_NOT_ALLOWED')
        self.assertEqual(calls, ['sendWidget'])
        self.assertFalse(widgets_enabled('1001'))

    def test_order_alert_asks_telegram_once_then_sends_text_to_everyone(self):
        Chat.objects.create(chat_id='1001', first_name='Owner')
        Chat.objects.create(chat_id='1002', first_name='Staff')
        transport, calls = refusing_transport()
        real_client = httpx.Client
        with patch('teleg.widget_api.httpx.Client', side_effect=lambda **options: real_client(transport=transport)), \
                patch('teleg.utils.notify_message.bot.send_message') as send_message, \
                self.assertLogs('teleg.utils.notify_message', 'WARNING') as logs:
            notify_message(order(address_latitude=None, address_longitude=None), [basket('Креатин', 1, 150_000)])
        self.assertEqual(calls, ['sendWidget'])
        self.assertEqual([call.args[0] for call in send_message.call_args_list], ['1001', '1002'])
        self.assertIn('INPUT_MEDIA_WIDGET_NOT_ALLOWED', logs.output[0])
        self.assertNotIn('Xakberdiyev', ''.join(logs.output))

    def test_other_refusals_are_logged_but_do_not_pause(self):
        transport, _ = refusing_transport('Bad Request: INPUT_MEDIA_WIDGET_TOO_LARGE')
        with self.assertRaises(StaffWidgetError) as raised:
            send_widget('1001', '<p>x</p>', 'x', client=httpx.Client(transport=transport))
        self.assertEqual(raised.exception.code, 'INPUT_MEDIA_WIDGET_TOO_LARGE')
        self.assertTrue(widgets_enabled('1001'))
