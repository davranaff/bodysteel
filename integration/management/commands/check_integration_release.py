import json

from django.core.checks import run_checks
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = 'Run the safe production preflight for the SAVDOQ Integration API.'

    def handle(self, *args, **options):
        system_check_errors = _system_check_error_count()
        migrations_current = _migrations_are_current()
        ready = system_check_errors == 0 and migrations_current
        self.stdout.write(
            json.dumps(
                {
                    'event': 'bodysteel_integration_release_preflight',
                    'status': 'passed' if ready else 'blocked',
                    'systemCheckErrors': system_check_errors,
                    'migrationsCurrent': migrations_current,
                },
                separators=(',', ':'),
            )
        )
        if not ready:
            raise CommandError('Integration release preflight failed')


def _system_check_error_count():
    try:
        return sum(1 for issue in run_checks() if issue.is_serious())
    except Exception:
        return 1


def _migrations_are_current():
    try:
        executor = MigrationExecutor(connection)
        return not executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception:
        return False
