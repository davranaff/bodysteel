from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from customer_telegram.bot_api import DeliveryStatus
from customer_telegram.campaigns import (
    LEASE_TIMEOUT,
    RETRY_DELAYS,
    build_campaign_audience,
    deliver_campaign_batch,
    queue_due_campaigns,
    send_test_campaign,
)
from customer_telegram.models import (
    CustomerTelegramCampaign,
    CustomerTelegramCampaignRecipient,
    CustomerTelegramChat,
)
from customer_telegram.tests.base import FakeTelegramApi, TELEGRAM_SETTINGS


@override_settings(**TELEGRAM_SETTINGS)
class CampaignDeliveryTests(TestCase):
    def setUp(self):
        self.ru = CustomerTelegramChat.objects.create(
            telegram_user_id=4001, chat_id=4001, language='ru', marketing_opt_in=True,
        )
        self.uz = CustomerTelegramChat.objects.create(
            telegram_user_id=4002, chat_id=4002, language='uz', marketing_opt_in=True,
        )
        self.campaign = CustomerTelegramCampaign.objects.create(
            name='August sale', status=CustomerTelegramCampaign.QUEUEING,
            title_ru='Скидка', title_uz='Chegirma',
            body_ru='Только сегодня', body_uz='Faqat bugun',
        )

    def test_audience_is_idempotent_and_localized(self):
        self.assertEqual(build_campaign_audience(self.campaign.pk), 2)
        self.assertEqual(build_campaign_audience(self.campaign.pk), 2)
        self.assertEqual(self.campaign.recipients.count(), 2)
        api = FakeTelegramApi()
        summary = deliver_campaign_batch(limit=10, api=api)
        self.assertEqual(summary.delivered, 2)
        texts = {chat_id: text for chat_id, text, _markup, _mode in api.messages}
        self.assertIn('Скидка', texts[4001])
        self.assertIn('Chegirma', texts[4002])
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, CustomerTelegramCampaign.COMPLETED)

    def test_opt_out_after_queue_is_skipped(self):
        build_campaign_audience(self.campaign.pk)
        CustomerTelegramChat.objects.filter(pk=self.ru.pk).update(marketing_opt_in=False)
        summary = deliver_campaign_batch(limit=2, api=FakeTelegramApi())
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.delivered, 1)

    def test_rate_limit_is_retried_and_block_marks_chat(self):
        self.uz.delete()
        build_campaign_audience(self.campaign.pk)
        rate_api = FakeTelegramApi(DeliveryStatus.RATE_LIMITED, retry_after=600)
        summary = deliver_campaign_batch(limit=1, api=rate_api)
        self.assertEqual(summary.retried, 1)
        recipient = CustomerTelegramCampaignRecipient.objects.get()
        self.assertEqual(recipient.status, CustomerTelegramCampaignRecipient.RETRY)
        self.assertGreaterEqual(recipient.next_attempt_at, timezone.now())
        recipient.next_attempt_at = timezone.now()
        recipient.save(update_fields=('next_attempt_at',))
        CustomerTelegramChat.objects.filter(pk=self.ru.pk).update(
            marketing_next_send_at=timezone.now() - timedelta(seconds=1),
        )
        summary = deliver_campaign_batch(limit=1, api=FakeTelegramApi(DeliveryStatus.BLOCKED))
        self.assertEqual(summary.blocked, 1)
        self.ru.refresh_from_db()
        self.assertFalse(self.ru.is_active)
        self.assertFalse(self.ru.marketing_opt_in)

    def test_scheduled_campaign_waits_until_due(self):
        self.campaign.status = CustomerTelegramCampaign.SCHEDULED
        self.campaign.scheduled_at = timezone.now() + timedelta(hours=1)
        self.campaign.save(update_fields=('status', 'scheduled_at', 'updated_at'))
        queue_due_campaigns(now=timezone.now())
        self.assertEqual(self.campaign.recipients.count(), 0)
        queue_due_campaigns(now=self.campaign.scheduled_at + timedelta(seconds=1))
        self.assertEqual(self.campaign.recipients.count(), 2)

    def test_permanent_failure_and_retry_exhaustion_are_bounded(self):
        self.uz.delete()
        build_campaign_audience(self.campaign.pk)
        summary = deliver_campaign_batch(limit=1, api=FakeTelegramApi(DeliveryStatus.FAILED))
        self.assertEqual(summary.failed, 1)
        recipient = CustomerTelegramCampaignRecipient.objects.get()
        self.assertEqual(recipient.failure_code, 'permanent_error')

        self.campaign.status = CustomerTelegramCampaign.SENDING
        self.campaign.completed_at = None
        self.campaign.save(update_fields=('status', 'completed_at', 'updated_at'))
        recipient.status = CustomerTelegramCampaignRecipient.RETRY
        recipient.attempt_count = len(RETRY_DELAYS)
        recipient.next_attempt_at = timezone.now()
        recipient.save(update_fields=('status', 'attempt_count', 'next_attempt_at', 'updated_at'))
        CustomerTelegramChat.objects.filter(pk=self.ru.pk).update(
            marketing_next_send_at=timezone.now() - timedelta(seconds=1),
        )
        summary = deliver_campaign_batch(limit=1, api=FakeTelegramApi(DeliveryStatus.UNKNOWN))
        self.assertEqual(summary.failed, 1)
        recipient.refresh_from_db()
        self.assertEqual(recipient.failure_code, 'retry_exhausted')

    def test_stale_lease_is_recovered(self):
        self.uz.delete()
        build_campaign_audience(self.campaign.pk)
        recipient = CustomerTelegramCampaignRecipient.objects.get()
        recipient.status = CustomerTelegramCampaignRecipient.SENDING
        recipient.lease_token = 'abandoned-lease'
        recipient.locked_at = timezone.now() - LEASE_TIMEOUT - timedelta(seconds=1)
        recipient.save(update_fields=('status', 'lease_token', 'locked_at', 'updated_at'))
        summary = deliver_campaign_batch(limit=1, api=FakeTelegramApi())
        self.assertEqual(summary.delivered, 1)

    def test_test_send_is_single_recipient_and_html_is_escaped(self):
        self.campaign.status = CustomerTelegramCampaign.DRAFT
        self.campaign.title_ru = '<sale>'
        self.campaign.body_ru = '<b>plain</b>'
        self.campaign.save(update_fields=('status', 'title_ru', 'body_ru', 'updated_at'))
        api = FakeTelegramApi()
        self.assertTrue(send_test_campaign(self.campaign, self.ru, api))
        self.assertEqual(len(api.messages), 1)
        self.assertIn('&lt;sale&gt;', api.messages[0][1])
        self.assertIn('&lt;b&gt;plain&lt;/b&gt;', api.messages[0][1])
        self.assertEqual(self.campaign.recipients.count(), 0)

    def test_campaign_button_rejects_external_url(self):
        self.campaign.button_text_ru = 'Открыть'
        self.campaign.button_text_uz = 'Ochish'
        self.campaign.button_url = 'https://attacker.example/sale'
        with self.assertRaises(ValidationError):
            self.campaign.full_clean()

    def test_two_campaigns_to_same_chat_are_spaced_by_one_second(self):
        self.uz.delete()
        second = CustomerTelegramCampaign.objects.create(
            name='Second sale', status=CustomerTelegramCampaign.QUEUEING,
            title_ru='Ещё скидка', title_uz='Yana chegirma',
            body_ru='Сегодня', body_uz='Bugun',
        )
        now = timezone.now()
        build_campaign_audience(self.campaign.pk, now)
        build_campaign_audience(second.pk, now)
        summary = deliver_campaign_batch(limit=2, api=FakeTelegramApi(), now=now)
        self.assertEqual(summary.delivered, 1)
        self.assertEqual(summary.retried, 1)
        throttled = CustomerTelegramCampaignRecipient.objects.get(status='retry')
        self.assertEqual(throttled.failure_code, 'chat_throttled')
        self.assertGreaterEqual(throttled.next_attempt_at, now + timedelta(seconds=1))
