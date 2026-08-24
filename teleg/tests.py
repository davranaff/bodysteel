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
