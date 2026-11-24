from django.core.management.base import BaseCommand, CommandError

from customer_telegram.bot_api import CustomerTelegramApi, DeliveryStatus


class Command(BaseCommand):
    help = (
        'Switch topics in private chats with the customer bot (Bot API setMySettings). '
        'Set CUSTOMER_TELEGRAM_TOPICS to the same value so the bot files its messages into topics.'
    )

    def add_arguments(self, parser):
        state = parser.add_mutually_exclusive_group(required=True)
        state.add_argument('--on', action='store_true', help='Topics with a sidebar; shoppers cannot add or delete topics.')
        state.add_argument('--off', action='store_true', help='Back to one plain chat.')

    def handle(self, *args, **options):
        enabled = bool(options['on'])
        settings = {'has_topics_enabled': enabled, 'has_topic_sidebar': enabled}
        if enabled:
            settings['allows_users_to_create_topics'] = False
        result = CustomerTelegramApi().set_my_settings(**settings)
        if result.status is not DeliveryStatus.SENT:
            raise CommandError('Telegram refused the topic settings ({}).'.format(result.error_code or 'no code'))
        self.stdout.write(self.style.SUCCESS('Customer bot topics {}.'.format('on' if enabled else 'off')))
