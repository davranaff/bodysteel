from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from teleg.models import Chat
from teleg.utils.notify_message import format_order_notification, notify_message, order_buttons
from teleg.widget_api import StaffWidgetError


class OrderNotificationFormatTests(TestCase):
    """The text message, sent when Telegram refuses the widget card."""

    def setUp(self):
        patcher = patch('teleg.utils.notify_message.send_widget', side_effect=StaffWidgetError('refused'))
        self.send_widget = patcher.start()
        self.addCleanup(patcher.stop)
        rich = patch('teleg.utils.notify_message.send_rich_order', return_value=None)
        rich.start()
        self.addCleanup(rich.stop)

    def test_formats_readable_html_and_escapes_customer_content(self):
        order = self.order()
        order.full_name = 'Xakim & Co'
        baskets = [
            self.basket('Dymatize <ISO100>', 1, 1_150_000),
            self.basket('Rule One Creatine', 2, 370_000),
        ]

        text = format_order_notification(order, baskets)

        self.assertIn('🛒 <b>Новый заказ № 0439278651</b>', text)
        self.assertIn('💵 <b>Оплата при получении</b>', text)
        self.assertIn('👤 <b>Xakim &amp; Co</b>', text)
        self.assertIn('📞 +998946833883\n', text)
        self.assertNotIn('<code>+998946833883</code>', text)
        self.assertIn('<blockquote>1. <b>Dymatize &lt;ISO100&gt;</b>', text)
        self.assertIn('2 шт. × 185 000 = 370 000 UZS</blockquote>', text)
        self.assertIn('💰 <b>Итого: 1 520 000 UZS</b>', text)
        self.assertLessEqual(len(text), 3900)

    @patch('teleg.utils.notify_message.logger.exception')
    @patch('teleg.utils.notify_message.bot.send_message')
    def test_one_failed_chat_does_not_block_other_recipients(self, send_message, _log):
        Chat.objects.create(chat_id='1001', first_name='First')
        Chat.objects.create(chat_id='1002', first_name='Second')
        send_message.side_effect = [RuntimeError('blocked'), None]

        notify_message(self.order(), [self.basket('Product', 1, 100_000)])

        self.assertEqual(send_message.call_count, 2)
        self.assertTrue(all(call.kwargs['parse_mode'] == 'HTML' for call in send_message.call_args_list))

    def test_location_adds_label_and_map_links(self):
        order = self.located_order()
        order.address_label = 'Ляби-Хауз <центр>'

        text = format_order_notification(order, [self.basket('Product', 1, 100_000)])

        self.assertIn('📍 Zebiniso 13\n', text)
        self.assertIn('🏷 Ляби-Хауз &lt;центр&gt;\n', text)
        buttons = order_buttons(order).to_dict()['inline_keyboard']
        self.assertEqual(buttons[0][0]['url'], 'https://maps.google.com/?q=39.774723,64.419841')
        self.assertEqual(buttons[0][1]['url'], 'https://yandex.uz/maps/?pt=64.419841,39.774723&z=17&l=map')

    def test_order_without_location_has_no_map_links(self):
        text = format_order_notification(self.order(), [self.basket('Product', 1, 100_000)])

        buttons = order_buttons(self.order())
        titles = [button['text'] for row in (buttons.to_dict()['inline_keyboard'] if buttons else []) for button in row]
        self.assertFalse([title for title in titles if '🗺' in title])
        self.assertNotIn('🏷', text)

    @patch('teleg.utils.notify_message.bot.send_venue')
    @patch('teleg.utils.notify_message.bot.send_message')
    def test_venue_replies_to_the_order_message(self, send_message, send_venue):
        Chat.objects.create(chat_id='1001', first_name='First')
        send_message.return_value = SimpleNamespace(message_id=77)

        notify_message(self.located_order(), [self.basket('Product', 1, 100_000)])

        send_venue.assert_called_once_with(
            '1001', 39.774723, 64.419841,
            title='Адрес доставки', address='Zebiniso 13', reply_to_message_id=77,
        )

    @patch('teleg.utils.notify_message.logger.exception')
    @patch('teleg.utils.notify_message.bot.send_venue')
    @patch('teleg.utils.notify_message.bot.send_message')
    def test_venue_failure_is_logged_and_not_raised(self, send_message, send_venue, log):
        Chat.objects.create(chat_id='1001', first_name='First')
        Chat.objects.create(chat_id='1002', first_name='Second')
        send_message.return_value = SimpleNamespace(message_id=5)
        send_venue.side_effect = [RuntimeError('venue rejected'), None]

        notify_message(self.located_order(), [self.basket('Product', 1, 100_000)])

        self.assertEqual(send_message.call_count, 2)
        self.assertEqual(send_venue.call_count, 2)
        log.assert_called_once()
        self.assertEqual(log.call_args.args[0], 'Telegram order venue failed')

    @patch('teleg.utils.notify_message.bot.send_venue')
    @patch('teleg.utils.notify_message.bot.send_message')
    def test_no_venue_without_coordinates(self, send_message, send_venue):
        Chat.objects.create(chat_id='1001', first_name='First')

        notify_message(self.order(), [self.basket('Product', 1, 100_000)])

        send_message.assert_called_once()
        send_venue.assert_not_called()

    @classmethod
    def located_order(cls):
        order = cls.order()
        order.address_latitude = Decimal('39.774723')
        order.address_longitude = Decimal('64.419841')
        order.address_label = ''
        return order

    @staticmethod
    def order():
        return SimpleNamespace(
            pk=371,
            order_code='0439278651',
            created_at=timezone.now(),
            type='dcb',
            address='Zebiniso 13',
            full_name='Xakim Xakberdiyev',
            phone='+998946833883',
            total_price=1_520_000,
        )

    @staticmethod
    def basket(name, quantity, price):
        return SimpleNamespace(
            product=SimpleNamespace(name_ru=name),
            quantity=quantity,
            price=price,
        )


class StaffTextMessageTests(TestCase):
    def test_report_text_quotes_products_with_names_in_bold(self):
        from teleg.replies import report_text
        text = report_text({'h': '📊 Продажи <день>', 't': [
            '~20.11.2026 — 21.11.2026', '!Позиций: 1 · Сумма: 300 000 UZS', '-', 'Whey <Gold> · 2 шт. · 300 000 UZS',
        ]})
        self.assertTrue(text.startswith('<b>📊 Продажи &lt;день&gt;</b>\n<i>20.11.2026 — 21.11.2026</i>'))
        self.assertIn('<blockquote><b>Whey &lt;Gold&gt;</b>\n2 шт. · 300 000 UZS</blockquote>', text)

    def test_review_alert_escapes_customer_text_and_quotes_the_comment(self):
        from teleg.utils.notify_review import format_review_notification
        text = format_review_notification({
            'id': 7, 'first_name': 'Ali', 'last_name': '<b>', 'phone': '+998901234567',
            'comment': 'Отлично <script>', 'product': 'Whey & Co',
        })
        self.assertIn('💬 <b>Новый отзыв на модерации</b>', text)
        self.assertIn('📦 <b>Whey &amp; Co</b>', text)
        self.assertIn('👤 Ali &lt;b&gt; · +998901234567', text)
        self.assertIn('<blockquote>Отлично &lt;script&gt;</blockquote>', text)
