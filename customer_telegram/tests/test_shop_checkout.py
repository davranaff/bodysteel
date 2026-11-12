from unittest.mock import patch

from django.test import TestCase, override_settings

from customer_telegram.i18n import message
from customer_telegram.models import CustomerTelegramCart, CustomerTelegramCheckout
from customer_telegram.orders import orders_page
from customer_telegram.shop.payments import notify_customer_paid
from customer_telegram.tests.base import TELEGRAM_SETTINGS
from customer_telegram.tests.shop_base import CHAT_ID, ShopFixtures
from payments.multicard.checkout import StartedPayment
from payments.multicard.fixtures import MULTICARD_SETTINGS
from store.models import Order


CONTACT = {'phone_number': '998901234567', 'first_name': 'Ali', 'last_name': 'Valiyev', 'user_id': CHAT_ID}


@override_settings(**TELEGRAM_SETTINGS, MULTICARD_ENABLED=False)
class CheckoutTests(ShopFixtures, TestCase):
    def fill_cart_and_choose(self, delivery_type='pickup'):
        self.send(message('ru', 'menu_catalog'))
        widget = self.storefront()
        self.tap(widget, 'a:{}'.format(self.whey.pk))
        self.tap(widget, 'a:{}'.format(self.creatine.pk))
        _, options = self.tap(widget, 'o')
        self.assertIn(delivery_type, [row[0] for row in options['dl']])
        _, state = self.tap(widget, 't:{}'.format(delivery_type))
        self.assertEqual(state['v'], 'w')
        return widget

    def test_pickup_order_without_online_payment_is_placed_once_and_staff_notified(self):
        self.fill_cart_and_choose('pickup')
        prompt = self.api.widgets[-1]
        self.assertTrue(prompt['reply_markup']['keyboard'][0][0]['request_contact'])
        self.assertEqual(self.send(contact=CONTACT), 'checkout_confirm')
        order_widget = self.order_widget()
        self.assertIn('"st":"c"', self.api.widgets[-1]['html'])
        with patch('customer_telegram.shop.placement.notify_message') as notify:
            _, state = self.tap(order_widget, 'y')
            _, replay = self.tap(order_widget, 'y')
        self.assertEqual(state['st'], 'cod')
        self.assertEqual(replay['c'], state['c'])
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.get()
        self.assertEqual((order.phone, order.full_name, order.type), ('+998901234567', 'Ali Valiyev', 'pickup'))
        self.assertEqual(order.total_price, 400_000 + 150_000)
        self.assertEqual(order.customer_note, 'Заказ из Telegram-бота')
        notify.assert_called_once()
        self.assertEqual(CustomerTelegramCart.objects.get(chat=self.chat).items, {})
        self.whey.refresh_from_db()

    def test_someone_elses_contact_is_refused(self):
        self.fill_cart_and_choose('pickup')
        self.assertEqual(self.send(contact={**CONTACT, 'user_id': CHAT_ID + 9}), 'checkout_contact')
        self.assertEqual(CustomerTelegramCheckout.objects.get(chat=self.chat).phone, '')

    def test_foreign_phone_number_is_refused(self):
        self.fill_cart_and_choose('pickup')
        self.assertEqual(self.send(contact={**CONTACT, 'phone_number': '+79001234567'}), 'checkout_contact')

    def test_delivery_asks_for_address_and_accepts_location_inside_uzbekistan(self):
        self.fill_cart_and_choose('dcb')
        self.assertEqual(self.send(contact=CONTACT), 'checkout_address')
        self.assertEqual(self.send(location={'latitude': 55.75, 'longitude': 37.61}), 'checkout_address')
        self.assertEqual(self.send(location={'latitude': 39.774723, 'longitude': 64.419841}), 'checkout_confirm')
        checkout = CustomerTelegramCheckout.objects.get(chat=self.chat)
        self.assertEqual(str(checkout.latitude), '39.774723')
        with patch('customer_telegram.shop.placement.notify_message'):
            self.tap(self.order_widget(), 'y')
        order = Order.objects.get()
        self.assertEqual((str(order.address_latitude), order.type), ('39.774723', 'dcb'))

    def test_typed_address_and_menu_buttons_still_work_during_checkout(self):
        self.fill_cart_and_choose('dcb')
        self.send(contact=CONTACT)
        self.assertEqual(self.send(message('ru', 'menu_cart')), 'cart')
        self.assertEqual(self.send('ул. Навои, 15'), 'checkout_confirm')
        self.assertEqual(CustomerTelegramCheckout.objects.get(chat=self.chat).address, 'ул. Навои, 15')

    def test_repeat_order_can_reuse_saved_contact(self):
        self.fill_cart_and_choose('pickup')
        self.send(contact=CONTACT)
        self.fill_cart_and_choose('pickup')
        prompt = self.api.widgets[-1]['reply_markup']['keyboard']
        self.assertEqual(prompt[1][0]['text'], '↩️ Как в прошлый раз')
        self.assertEqual(self.send('↩️ Как в прошлый раз'), 'checkout_confirm')

    def test_bot_orders_appear_in_my_orders_without_a_linked_account(self):
        self.fill_cart_and_choose('pickup')
        self.send(contact=CONTACT)
        with patch('customer_telegram.shop.placement.notify_message'):
            self.tap(self.order_widget(), 'y')
        page = orders_page(self.chat, 0)
        self.assertIn(Order.objects.get().order_code, page.text)


@override_settings(**TELEGRAM_SETTINGS, **MULTICARD_SETTINGS)
class OnlinePaymentTests(ShopFixtures, TestCase):
    def place(self):
        self.send(message('ru', 'menu_catalog'))
        widget = self.storefront()
        self.tap(widget, 'a:{}'.format(self.creatine.pk))
        self.tap(widget, 't:pickup')
        self.send(contact=CONTACT)
        started = StartedPayment(5, 'https://checkout.multicard.test/invoice/abc', 'token', replayed=False)
        with patch('customer_telegram.shop.placement.start_order_payment', return_value=started) as start, \
                patch('customer_telegram.shop.placement.notify_message') as notify:
            _, state = self.tap(self.order_widget(), 'y')
        return state, start, notify

    def test_pay_tap_creates_prepaid_order_and_adds_payment_button(self):
        state, start, notify = self.place()
        self.assertEqual(state['st'], 'p')
        self.assertEqual(state['u'], 'https://checkout.multicard.test/invoice/abc')
        args = start.call_args.args
        self.assertEqual((args[3], args[4]), ('web', 'ru'))
        self.assertTrue(args[2].startswith('tg.'))
        notify.assert_not_called()
        markup = next(edit for edit in self.api.edits if edit[0] == 'markup')
        self.assertEqual(markup[3]['inline_keyboard'][0][0]['url'], 'https://checkout.multicard.test/invoice/abc')

    def test_paid_callback_turns_the_widget_paid_and_notifies_the_customer(self):
        self.place()
        order = Order.objects.get()
        Order.objects.filter(pk=order.pk).update(payment_status='paid')
        self.assertEqual(notify_customer_paid(order.pk, api=self.api), 1)
        data_edit = [edit for edit in self.api.edits if edit[0] == 'data'][-1]
        self.assertIn('"st":"ok"', data_edit[3])
        self.assertIn('оплачен', self.api.widgets[-1]['caption'])
        _, state = self.tap(self.order_widget(), 'v')
        self.assertEqual(state['st'], 'ok')
