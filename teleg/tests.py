from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from teleg.models import Chat
from teleg.utils.notify_message import format_order_notification, notify_message


class OrderNotificationFormatTests(TestCase):
    def test_formats_readable_html_and_escapes_customer_content(self):
        order = self.order()
        order.full_name = 'Xakim & Co'
        baskets = [
            self.basket('Dymatize <ISO100>', 1, 1_150_000),
            self.basket('Rule One Creatine', 2, 370_000),
        ]

        text = format_order_notification(order, baskets)

        self.assertIn('🛒 <b>НОВЫЙ ЗАКАЗ</b>', text)
        self.assertIn('<b>№ 0439278651</b>', text)
        self.assertIn('Xakim &amp; Co', text)
        self.assertIn('📞 +998946833883\n', text)
        self.assertNotIn('<code>+998946833883</code>', text)
        self.assertIn('Dymatize &lt;ISO100&gt;', text)
        self.assertIn('2 шт. × 185 000 = 370 000 UZS', text)
        self.assertIn('💰 <b>ИТОГО: 1 520 000 UZS</b>', text)
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
        self.assertIn('<a href="https://maps.google.com/?q=39.774723,64.419841">Открыть на карте</a>', text)
        self.assertIn('<a href="https://yandex.uz/maps/?pt=64.419841,39.774723&amp;z=17&amp;l=map">', text)

    def test_order_without_location_has_no_map_links(self):
        text = format_order_notification(self.order(), [self.basket('Product', 1, 100_000)])

        self.assertNotIn('Открыть на карте', text)
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
