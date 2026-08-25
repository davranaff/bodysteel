from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from customer_telegram.links import start_account_link
from customer_telegram.models import (
    CustomerTelegramCampaign,
    CustomerTelegramCampaignRecipient,
    CustomerTelegramLink,
    CustomerTelegramUpdate,
)
from customer_telegram.tests.base import TELEGRAM_SETTINGS
from users.auth.models import AuthRateLimit
from users.auth.security import rate_limit_digest
from users.models import User


@override_settings(**TELEGRAM_SETTINGS)
class CustomerTelegramCleanupTests(TestCase):
    def test_cleanup_removes_only_safely_stale_technical_records(self):
        now = timezone.now()
        stale_user = self.user('stale', 611)
        stale = start_account_link(stale_user, 'ru')
        stale_link = CustomerTelegramLink.objects.get(
            token_digest__isnull=False, user=stale_user,
        )
        CustomerTelegramLink.objects.filter(pk=stale_link.pk).update(
            expires_at=now - timedelta(days=8),
        )
        active_user = self.user('active', 612)
        start_account_link(active_user, 'ru')

        old_update = CustomerTelegramUpdate.objects.create(
            update_id=7001, update_type='message', status='processed', processed_at=now,
        )
        CustomerTelegramUpdate.objects.filter(pk=old_update.pk).update(
            created_at=now - timedelta(days=31),
        )
        current_update = CustomerTelegramUpdate.objects.create(
            update_id=7002, update_type='message', status='processed', processed_at=now,
        )

        campaign = CustomerTelegramCampaign.objects.create(
            name='Completed', status='completed', title_ru='RU', title_uz='UZ',
            body_ru='RU', body_uz='UZ', recipient_count=1, failed_count=1,
            completed_at=now - timedelta(days=91),
        )
        chat = active_user.customer_telegram_chat if hasattr(active_user, 'customer_telegram_chat') else None
        if chat is None:
            from customer_telegram.models import CustomerTelegramChat
            chat = CustomerTelegramChat.objects.create(
                telegram_user_id=7612, chat_id=7612, language='ru',
            )
        recipient = CustomerTelegramCampaignRecipient.objects.create(
            campaign=campaign, chat=chat, language='ru', rendered_title='RU',
            rendered_body='RU', status='failed', next_attempt_at=now,
        )
        stale_limit = AuthRateLimit.objects.create(
            scope='customer_telegram_link',
            subject_digest=rate_limit_digest('customer_telegram_link', 'stale'),
            window_started_at=now - timedelta(days=1), count=1,
            expires_at=now - timedelta(seconds=1),
        )

        output = StringIO()
        call_command('purge_customer_telegram_records', stdout=output)
        self.assertFalse(CustomerTelegramLink.objects.filter(pk=stale_link.pk).exists())
        self.assertTrue(CustomerTelegramLink.objects.filter(user=active_user).exists())
        self.assertFalse(CustomerTelegramUpdate.objects.filter(pk=old_update.pk).exists())
        self.assertTrue(CustomerTelegramUpdate.objects.filter(pk=current_update.pk).exists())
        self.assertFalse(CustomerTelegramCampaignRecipient.objects.filter(pk=recipient.pk).exists())
        campaign.refresh_from_db()
        self.assertEqual(campaign.failed_count, 1)
        self.assertFalse(AuthRateLimit.objects.filter(pk=stale_limit.pk).exists())
        self.assertIn('security=', output.getvalue())

    @staticmethod
    def user(prefix, suffix):
        return User.objects.create_user(
            username=prefix, email='{}@example.test'.format(prefix),
            phone='+99890123{:04d}'.format(suffix), password='safe-password',
        )
