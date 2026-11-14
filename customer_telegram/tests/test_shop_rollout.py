from django.core.cache import cache
from django.test import TestCase, override_settings

from customer_telegram.bot_api import DeliveryStatus
from customer_telegram.i18n import message
from customer_telegram.shop.checkout import _card
from customer_telegram.tests.base import TELEGRAM_SETTINGS, FakeTelegramApi
from customer_telegram.tests.shop_base import CHAT_ID, ShopFixtures
from telegram_widgets.rollout import PAUSE_KEY, widgets_enabled


@override_settings(**{**TELEGRAM_SETTINGS, 'TELEGRAM_WIDGETS_ROLLOUT': ''})
class WidgetsOffTests(ShopFixtures, TestCase):
    def test_without_rollout_the_bot_answers_exactly_as_before(self):
        self.assertEqual(self.send('/help'), 'help')
        self.assertEqual(self.api.widgets, [])
        chat_id, text, markup, _ = self.api.messages[-1]
        self.assertEqual(text, message('ru', 'help'))
        self.assertIn([{'text': message('ru', 'menu_language')}, {'text': message('ru', 'menu_store')}], markup['keyboard'])

    def test_store_button_links_to_the_site_and_text_is_not_a_search(self):
        self.assertEqual(self.send(message('ru', 'menu_store')), 'store')
        self.assertEqual(self.api.messages[-1][2]['inline_keyboard'][0][0]['url'], 'https://bodysteel.uz')
        self.assertEqual(self.send('креатин'), 'unknown')
        self.assertEqual(self.api.widgets, [])


@override_settings(**{**TELEGRAM_SETTINGS, 'TELEGRAM_WIDGETS_ROLLOUT': '{}, 42'.format(CHAT_ID)})
class WidgetsTrialTests(ShopFixtures, TestCase):
    def test_trial_chat_gets_the_shop(self):
        self.assertEqual(self.send(message('ru', 'menu_catalog')), 'catalog')
        self.assertEqual(len(self.api.widgets), 1)
        self.assertTrue(widgets_enabled(42))
        self.assertFalse(widgets_enabled(43))
        self.assertFalse(widgets_enabled(None))


REFUSED_WIDGETS = 'INPUT_MEDIA_WIDGET_NOT_ALLOWED'


@override_settings(**TELEGRAM_SETTINGS)
class WidgetsRefusedByTelegramTests(ShopFixtures, TestCase):
    """Telegram stopped accepting widgets from every bot (13 November 2026)."""

    def setUp(self):
        super().setUp()
        self.api = FakeTelegramApi(widget_status=DeliveryStatus.FAILED, widget_error=REFUSED_WIDGETS)
        cache.delete(PAUSE_KEY)
        self.addCleanup(cache.delete, PAUSE_KEY)

    def test_refused_catalog_points_to_the_site_and_the_bot_goes_plain(self):
        self.assertEqual(self.send(message('ru', 'menu_catalog')), 'store')
        _, body, markup, _ = self.api.messages[-1]
        self.assertIn('https://bodysteel.uz', body)
        self.assertIn([{'text': message('ru', 'menu_language')}, {'text': message('ru', 'menu_store')}], markup['keyboard'])
        self.assertFalse(widgets_enabled(CHAT_ID))
        # The old keyboard's cart button now links to the site, without asking Telegram again.
        self.assertEqual(self.send(message('ru', 'menu_cart')), 'store')
        self.assertEqual(self.api.messages[-1][2]['inline_keyboard'][0][0]['url'], 'https://bodysteel.uz')
        self.assertEqual(self.send('/help'), 'help')
        self.assertEqual(self.api.widget_attempts, 1)

    def test_refused_search_points_to_the_site(self):
        self.assertEqual(self.send('креатин'), 'store')
        self.assertIn('https://bodysteel.uz', self.api.messages[-1][1])

    def test_widgets_come_back_when_the_pause_ends(self):
        self.send(message('ru', 'menu_catalog'))
        cache.delete(PAUSE_KEY)
        self.api.widget_status = DeliveryStatus.SENT
        self.assertEqual(self.send(message('ru', 'menu_catalog')), 'catalog')
        self.assertEqual(len(self.api.widgets), 1)

    def test_a_refused_widget_of_another_kind_does_not_pause_the_others(self):
        self.api = FakeTelegramApi(widget_status=DeliveryStatus.FAILED, widget_error='INPUT_MEDIA_WIDGET_TOO_LARGE')
        self.assertEqual(self.send(message('ru', 'menu_catalog')), 'store')
        self.assertTrue(widgets_enabled(CHAT_ID))

    def test_an_unknown_outcome_sends_nothing_more(self):
        # The widget may have been delivered: a second answer would be a duplicate.
        self.api = FakeTelegramApi(widget_status=DeliveryStatus.UNKNOWN)
        self.assertEqual(self.send(message('ru', 'menu_catalog')), 'catalog')
        self.assertEqual(self.api.messages, [])

    def test_refused_checkout_card_goes_as_a_plain_message_with_its_keyboard(self):
        keyboard = {'keyboard': [[{'text': 'x', 'request_contact': True}]]}
        _card(self.chat, self.api, 'Шаг 1 из 3', keyboard)
        self.assertEqual(self.api.messages[-1][:3], (CHAT_ID, 'Шаг 1 из 3', keyboard))
