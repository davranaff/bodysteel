from django.apps import apps
from django.core.management.base import BaseCommand

from store.content.html import sanitize_html
from store.fields import SanitizedHtmlField


class Command(BaseCommand):
    help = 'Count stored rich HTML values that the current sanitizer would change.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default='default')

    def handle(self, *args, **options):
        database = options['database']
        total = 0
        for model in apps.get_app_config('store').get_models():
            for field in model._meta.local_fields:
                if not isinstance(field, SanitizedHtmlField):
                    continue
                changed = self._count_changes(model, field.name, database)
                if changed:
                    self.stdout.write(f'{model._meta.label}.{field.name}: {changed}')
                total += changed
        self.stdout.write(self.style.SUCCESS(f'total values requiring sanitization: {total}'))

    @staticmethod
    def _count_changes(model, field_name, database):
        values = model.objects.using(database).values_list(field_name, flat=True)
        return sum(
            sanitize_html(value) != value
            for value in values.iterator(chunk_size=500)
        )
