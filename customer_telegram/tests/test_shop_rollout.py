from django.test import TestCase, override_settings

from customer_telegram.i18n import message
from customer_telegram.tests.base import TELEGRAM_SETTINGS
from customer_telegram.tests.shop_base import CHAT_ID, ShopFixtures
from telegram_widgets.rollout import widgets_enabled


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
