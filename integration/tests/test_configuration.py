from django.test import SimpleTestCase, override_settings

from integration.checks import integration_configuration_checks
from integration.configuration import https_origin
from integration.errors import IntegrationProblem
from integration.tests.fixtures import INTEGRATION_SETTINGS


class IntegrationConfigurationChecksTests(SimpleTestCase):
    @override_settings(
        DEBUG=True,
        SAVDOQ_ALLOW_LOCAL_ORIGINS=True,
        SAVDOQ_STOREFRONT_ORIGIN='http://host.docker.internal:3000',
    )
    def test_local_development_origin_keeps_its_explicit_port(self):
        self.assertEqual(https_origin('SAVDOQ_STOREFRONT_ORIGIN'), 'http://host.docker.internal:3000')

    @override_settings(
        DEBUG=False,
        SAVDOQ_ALLOW_LOCAL_ORIGINS=True,
        SAVDOQ_STOREFRONT_ORIGIN='http://host.docker.internal:3000',
    )
    def test_local_origin_is_still_rejected_outside_debug(self):
        with self.assertRaisesMessage(IntegrationProblem, 'Integration origin is misconfigured'):
            https_origin('SAVDOQ_STOREFRONT_ORIGIN')

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
        SAVDOQ_INTEGRATION_CHECK_ENABLED=False,
        SAVDOQ_INTEGRATION_CREDENTIALS=(),
    )
    def test_disabled_integration_fails_closed_without_fake_credentials(self):
        self.assertEqual(integration_configuration_checks(None), [])

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
