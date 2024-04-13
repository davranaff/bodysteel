import requests
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain', type=str, help='Backend Domain')

    def handle(self, *args, **options):
        bot_url = settings.BOT_URL
        webhook = options['domain'].strip('https://').strip('/')
        requests.get(f'{bot_url}/deleteWebhook')
        requests.get(f'{bot_url}/setWebhook?url=https://{webhook}/telegram/webhook')
