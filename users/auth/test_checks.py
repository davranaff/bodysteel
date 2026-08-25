from django.test import SimpleTestCase, override_settings

from users.auth.checks import auth_configuration_checks


VALID_AUTH_SETTINGS = {
    'BODYSTEEL_STOREFRONT_PROXY_TOKEN': 'proxy-token-with-at-least-thirty-two-characters',
    'PHONE_VERIFICATION_HASH_KEY': 'phone-hash-key-with-at-least-thirty-two-characters',
    'AUTH_RATE_LIMIT_HASH_KEY': 'rate-hash-key-with-at-least-thirty-two-characters',
    'AUTH_TRUSTED_PROXY_NETWORKS': (),
}


class AuthConfigurationChecksTests(SimpleTestCase):
    @override_settings(**VALID_AUTH_SETTINGS, DEBUG=False, SMS_BACKEND='disabled')
    def test_disabled_sms_backend_does_not_require_fake_eskiz_credentials(self):
        issues = auth_configuration_checks(None)

        self.assertNotIn('users.E003', [issue.id for issue in issues])

    @override_settings(**VALID_AUTH_SETTINGS, DEBUG=False, SMS_BACKEND='eskiz')
    def test_enabled_eskiz_backend_requires_real_provider_configuration(self):
        issues = auth_configuration_checks(None)

        self.assertIn('users.E003', [issue.id for issue in issues])

    @override_settings(**VALID_AUTH_SETTINGS, DEBUG=False, SMS_BACKEND='local')
    def test_local_sms_backend_is_rejected_outside_debug(self):
        issues = auth_configuration_checks(None)

        self.assertIn('users.E003', [issue.id for issue in issues])
