from django.test import SimpleTestCase, override_settings

from integration.checks import integration_configuration_checks
from integration.tests.fixtures import INTEGRATION_SETTINGS


class IntegrationConfigurationChecksTests(SimpleTestCase):
    @override_settings(
        DEBUG=False,
        SAVDOQ_INTEGRATION_CHECK_ENABLED=True,
        SAVDOQ_INTEGRATION_CREDENTIALS=(),
    )
    def test_production_check_rejects_missing_credentials(self):
        issues = integration_configuration_checks(None)

        self.assertEqual([issue.id for issue in issues], ['integration.E002'])

    @override_settings(
        DEBUG=False,
        SAVDOQ_INTEGRATION_CHECK_ENABLED=True,
        **INTEGRATION_SETTINGS,
    )
    def test_production_check_accepts_distinct_full_and_read_credentials(self):
        issues = integration_configuration_checks(None)

        self.assertEqual(issues, [])

    @override_settings(
        DEBUG=False,
        SAVDOQ_INTEGRATION_CHECK_ENABLED=True,
        SAVDOQ_INTEGRATION_CREDENTIALS=(
            {'token': 'a' * 32, 'scopes': ('products:read', 'inventory:read', 'carts:write')},
            {'token': 'a' * 32, 'scopes': ('products:read', 'inventory:read')},
        ),
    )
    def test_production_check_rejects_reused_credentials(self):
        issues = integration_configuration_checks(None)

        self.assertEqual([issue.id for issue in issues], ['integration.E002'])
