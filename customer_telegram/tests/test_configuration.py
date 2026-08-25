from django.test import SimpleTestCase, override_settings

from customer_telegram.configuration import (
    CustomerTelegramConfigurationError,
    customer_telegram_enabled,
    require_configuration,
)
from customer_telegram.tests.base import TELEGRAM_SETTINGS


class ConfigurationTests(SimpleTestCase):
    @override_settings(CUSTOMER_TELEGRAM_ENABLED=False)
    def test_disabled_is_safe(self):
        self.assertFalse(customer_telegram_enabled())
        with self.assertRaises(CustomerTelegramConfigurationError):
            require_configuration()

    @override_settings(**TELEGRAM_SETTINGS)
    def test_valid_configuration(self):
        configuration = require_configuration()
        self.assertEqual(configuration.username, 'BodySteelClientBot')
        self.assertTrue(configuration.campaigns_enabled)

    @override_settings(**{**TELEGRAM_SETTINGS, 'DEBUG': False})
    def test_valid_production_configuration(self):
        self.assertEqual(require_configuration().webhook_url, TELEGRAM_SETTINGS[
            'CUSTOMER_TELEGRAM_WEBHOOK_URL'
        ])

    @override_settings(**{
        **TELEGRAM_SETTINGS,
        'DEBUG': False,
        'CUSTOMER_TELEGRAM_LINK_HASH_KEY': 'unsafe-local-only-key-000000000000001',
    })
    def test_unsafe_development_secret_is_rejected_in_production(self):
        with self.assertRaises(CustomerTelegramConfigurationError):
            require_configuration()

    @override_settings(**{**TELEGRAM_SETTINGS, 'CUSTOMER_TELEGRAM_BOT_TOKEN': ''})
    def test_missing_customer_token_is_rejected(self):
        with self.assertRaises(CustomerTelegramConfigurationError):
            require_configuration()

    @override_settings(**{**TELEGRAM_SETTINGS, 'CUSTOMER_TELEGRAM_BOT_TOKEN': 'not-a-token'})
    def test_malformed_customer_token_is_rejected(self):
        with self.assertRaises(CustomerTelegramConfigurationError):
            require_configuration()

    @override_settings(**{**TELEGRAM_SETTINGS, 'CUSTOMER_TELEGRAM_BOT_TOKEN': TELEGRAM_SETTINGS['BOT_TOKEN']})
    def test_customer_token_must_differ_from_staff_bot(self):
        with self.assertRaises(CustomerTelegramConfigurationError):
            require_configuration()

    @override_settings(**{**TELEGRAM_SETTINGS, 'CUSTOMER_TELEGRAM_WEBHOOK_SECRET': 'short'})
    def test_short_webhook_secret_is_rejected(self):
        with self.assertRaises(CustomerTelegramConfigurationError):
            require_configuration()

    @override_settings(**{**TELEGRAM_SETTINGS, 'CUSTOMER_TELEGRAM_BOT_USERNAME': 'unsafe name'})
    def test_unsafe_username_is_rejected(self):
        with self.assertRaises(CustomerTelegramConfigurationError):
            require_configuration()

    @override_settings(**{
        **TELEGRAM_SETTINGS,
        'CUSTOMER_TELEGRAM_BOT_USERNAME': '{}Bot'.format('A' * 30),
    })
    def test_overlong_username_is_rejected(self):
        with self.assertRaises(CustomerTelegramConfigurationError):
            require_configuration()

    @override_settings(**{
        **TELEGRAM_SETTINGS,
        'CUSTOMER_TELEGRAM_WEBHOOK_URL': 'https://evil.example/telegram/customer/webhook/',
    })
    def test_webhook_must_match_exact_public_origin(self):
        with self.assertRaises(CustomerTelegramConfigurationError):
            require_configuration()

    @override_settings(**{
        **TELEGRAM_SETTINGS,
        'CUSTOMER_TELEGRAM_LINK_HASH_KEY': TELEGRAM_SETTINGS['AUTH_RATE_LIMIT_HASH_KEY'],
    })
    def test_secrets_must_be_independent(self):
        with self.assertRaises(CustomerTelegramConfigurationError):
            require_configuration()
