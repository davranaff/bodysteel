import requests
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Point the staff bot webhook at this backend, with widget queries enabled.'

    def add_arguments(self, parser):
        parser.add_argument('domain', type=str, help='Backend Domain')

    def handle(self, *args, **options):
        bot_url = settings.BOT_URL
        domain = options['domain'].removeprefix('https://').strip('/')
        payload = {
            # teleg.urls serves the webhook at /telegram/; /telegram/webhook is a 404.
            'url': 'https://{}/telegram/'.format(domain),
            'allowed_updates': ['message', 'callback_query', 'widget_query'],
        }
        if settings.STAFF_TELEGRAM_WEBHOOK_SECRET:
            payload['secret_token'] = settings.STAFF_TELEGRAM_WEBHOOK_SECRET
        response = requests.post('{}/setWebhook'.format(bot_url), json=payload, timeout=10)
        # The response can echo the token-bearing URL; print only the outcome.
        self.stdout.write('setWebhook: {}'.format('ok' if response.ok and response.json().get('ok') else 'failed'))
