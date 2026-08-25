from django.test import TestCase

from customer_telegram.models import CustomerTelegramChat
from customer_telegram.orders import order_detail, orders_page
from store.models import Basket, Order, Product
from users.models import User


class CustomerTelegramOrderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='orders', email='orders@example.test', phone='+998901234571', password='safe-pass',
        )
        self.other = User.objects.create_user(
            username='other', email='other@example.test', phone='+998901234572', password='safe-pass',
        )
        self.chat = CustomerTelegramChat.objects.create(
            user=self.user, telegram_user_id=3001, chat_id=3001, language='uz',
        )

    def test_only_linked_user_orders_are_listed_and_paginated(self):
        own = [self.order(self.user, index) for index in range(6)]
        self.order(self.other, 99)
        self.order(None, 100)
        first = orders_page(self.chat, 0)
        second = orders_page(self.chat, 1)
        self.assertIn(own[-1].order_code, first.text)
        self.assertNotIn(own[0].order_code, first.text)
        self.assertIn(own[0].order_code, second.text)
        self.assertEqual(len(first.reply_markup['inline_keyboard'][0:5]), 5)

    def test_order_detail_uses_snapshot_and_rechecks_ownership(self):
        order = self.order(self.user, 1)
        Basket.objects.create(
            order=order, user=self.user, product=None, quantity=2,
            unit_price=125_000, product_name_ru='Снимок RU', product_name_uz='UZ surati',
        )
        detail = order_detail(self.chat, order.pk)
        self.assertIn('UZ surati', detail.text)
        self.assertIn('2 × 125 000 = 250 000 UZS', detail.text)
        forbidden = order_detail(self.chat, self.order(self.other, 2).pk)
        self.assertNotIn(self.other.phone, forbidden.text)
        self.assertIn('mavjud emas', forbidden.text)

    def test_snapshot_fallback_order_deleted_product_and_old_row_are_localized(self):
        order = self.order(self.user, 3)
        product = Product.objects.create(
            name_ru='Текущее RU', name_uz='Hozirgi UZ', price=90_000,
            quantity=10, slug='current-product', country_ru='UZ', country_uz='UZ',
        )
        basket = Basket.objects.create(
            order=order, user=self.user, product=product, quantity=1,
        )
        Basket.objects.filter(pk=basket.pk).update(product_name_ru='', product_name_uz='')
        self.assertIn('Hozirgi UZ', order_detail(self.chat, order.pk).text)

        Basket.objects.filter(pk=basket.pk).update(
            product_name_ru='Снимок удалённого', product_name_uz='O‘chirilgan surat',
        )
        product.delete()
        self.assertIn('O‘chirilgan surat', order_detail(self.chat, order.pk).text)

        Basket.objects.filter(pk=basket.pk).update(product_name_ru='', product_name_uz='')
        self.assertIn('<b>Mahsulot</b>', order_detail(self.chat, order.pk).text)

    def test_ru_snapshot_statuses_and_sensitive_checkout_fields_are_not_rendered(self):
        self.chat.language = 'ru'
        self.chat.save(update_fields=('language', 'updated_at'))
        order = self.order(self.user, 4)
        order.address = 'Secret address 44'
        order.customer_note = 'Secret note'
        order.save(update_fields=('address', 'customer_note'))
        Basket.objects.create(
            order=order, user=self.user, product=None, quantity=1,
            unit_price=50_000, product_name_ru='Русский снимок', product_name_uz='UZ snapshot',
        )
        detail = order_detail(self.chat, order.pk)
        self.assertIn('Русский снимок', detail.text)
        self.assertIn('Оплачен', detail.text)
        self.assertIn('Подтверждён', detail.text)
        self.assertNotIn(order.phone, detail.text)
        self.assertNotIn(order.address, detail.text)
        self.assertNotIn(order.customer_note, detail.text)

    def test_inactive_user_is_blocked_and_detail_query_count_is_bounded(self):
        order = self.order(self.user, 5)
        for index in range(8):
            Basket.objects.create(
                order=order, user=self.user, product=None, quantity=1,
                unit_price=10_000 + index,
                product_name_ru='Товар {}'.format(index),
                product_name_uz='Mahsulot {}'.format(index),
            )
        with self.assertNumQueries(2):
            detail = order_detail(self.chat, order.pk)
        self.assertEqual(detail.text.count('Mahsulot '), 8)
        self.user.is_active = False
        self.user.save(update_fields=('is_active',))
        self.assertIn('ulang', orders_page(self.chat, 0).text)

    @staticmethod
    def order(user, index):
        return Order.objects.create(
            user=user,
            total_price=100_000 + index,
            type='pickup',
            full_name='Test Customer',
            phone='+998901234571',
            address='Test',
            payment_status='paid',
            fulfillment_status='confirmed',
        )
