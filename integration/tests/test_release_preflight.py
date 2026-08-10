import json
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

class IntegrationReleasePreflightTests(SimpleTestCase):
    @patch('integration.management.commands.check_integration_release._migrations_are_current')
    @patch('integration.management.commands.check_integration_release._system_check_error_count')
    def test_passed_result_contains_only_safe_aggregate_fields(
        self,
        system_check_errors,
        migrations_current,
    ):
        system_check_errors.return_value = 0
        migrations_current.return_value = True

        output = self._run_command()

        self.assertEqual(
            output,
            {
                'event': 'bodysteel_integration_release_preflight',
                'status': 'passed',
                'systemCheckErrors': 0,
                'migrationsCurrent': True,
            },
        )

    @patch('integration.management.commands.check_integration_release._migrations_are_current')
    @patch('integration.management.commands.check_integration_release._system_check_error_count')
    def test_blocked_result_is_nonzero_without_internal_details(
        self,
        system_check_errors,
        migrations_current,
    ):
        system_check_errors.return_value = 1
        migrations_current.return_value = False

        from io import StringIO

        output = StringIO()
        with self.assertRaises(CommandError):
            call_command('check_integration_release', stdout=output)
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                'event': 'bodysteel_integration_release_preflight',
                'status': 'blocked',
                'systemCheckErrors': 1,
                'migrationsCurrent': False,
            },
        )

    @staticmethod
    def _run_command():
        from io import StringIO

        output = StringIO()
        call_command('check_integration_release', stdout=output)
        return json.loads(output.getvalue())
