from django.core.management.base import BaseCommand, CommandError

from integration.regos.sync import RegosSyncError, sync_from_regos


class Command(BaseCommand):
    help = 'Synchronize BodySteel quantities from REGOS Item/GetExt.'

    def handle(self, *args, **options):
        try:
            result = sync_from_regos()
        except RegosSyncError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(
            'REGOS sync complete: received={0.received} updated={0.updated} linked={0.linked} '
            'unmatched={0.unmatched} invalid={0.invalid}'.format(result)
        ))
