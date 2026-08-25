from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from customer_telegram.models import CustomerTelegramCampaign, CustomerTelegramChat
from customer_telegram.tests.base import TELEGRAM_SETTINGS
from store.admin_site import bodysteel_admin_site
from users.models import User


@override_settings(**TELEGRAM_SETTINGS)
class CustomerTelegramCampaignAdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = bodysteel_admin_site._registry[CustomerTelegramCampaign]
        self.user = User.objects.create_user(
            username='campaign-admin', email='campaign-admin@example.test',
            phone='+998901234601', password='safe-password', is_staff=True,
        )
        self.chat = CustomerTelegramChat.objects.create(
            telegram_user_id=6001, chat_id=6001, language='ru', marketing_opt_in=True,
        )
        self.campaign = CustomerTelegramCampaign.objects.create(
            name='Admin sale', title_ru='Скидка', title_uz='Chegirma',
            body_ru='Сегодня', body_uz='Bugun', test_recipient=self.chat,
        )

    def test_publish_needs_permission_and_explicit_confirmation(self):
        denied = self.request({'confirm_publish': 'yes'})
        with patch.object(self.admin, 'message_user'):
            self.admin.publish_campaigns(
                denied, CustomerTelegramCampaign.objects.filter(pk=self.campaign.pk),
            )
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, CustomerTelegramCampaign.DRAFT)

        self.grant('publish_customertelegramcampaign')
        confirmation = self.admin.publish_campaigns(
            self.request({}), CustomerTelegramCampaign.objects.filter(pk=self.campaign.pk),
        )
        self.assertIsInstance(confirmation, TemplateResponse)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, CustomerTelegramCampaign.DRAFT)

        with patch.object(self.admin, 'message_user'):
            self.admin.publish_campaigns(
                self.request({'confirm_publish': 'yes'}),
                CustomerTelegramCampaign.objects.filter(pk=self.campaign.pk),
            )
            self.admin.publish_campaigns(
                self.request({'confirm_publish': 'yes'}),
                CustomerTelegramCampaign.objects.filter(pk=self.campaign.pk),
            )
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, CustomerTelegramCampaign.QUEUEING)

    def test_change_form_publish_button_uses_confirmation(self):
        request = self.request({})
        with self.assertRaises(PermissionDenied):
            self.admin.publish_campaign_view(request, str(self.campaign.pk))

        self.grant('change_customertelegramcampaign')
        self.grant('publish_customertelegramcampaign')
        confirmation = self.admin.publish_campaign_view(
            self.get_request(), str(self.campaign.pk),
        )
        self.assertIsInstance(confirmation, TemplateResponse)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, CustomerTelegramCampaign.DRAFT)

        with patch.object(self.admin, 'message_user'):
            response = self.admin.publish_campaign_view(
                self.request({'confirm_publish': 'yes'}), str(self.campaign.pk),
            )
        self.assertEqual(response.status_code, 302)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, CustomerTelegramCampaign.QUEUEING)

    @patch('customer_telegram.admin.send_test_campaign', return_value=True)
    def test_test_send_has_separate_permission_and_one_explicit_recipient(self, send):
        with patch.object(self.admin, 'message_user'):
            self.admin.test_campaigns(
                self.request({}), CustomerTelegramCampaign.objects.filter(pk=self.campaign.pk),
            )
        send.assert_not_called()
        self.grant('test_customertelegramcampaign')
        with patch.object(self.admin, 'message_user'):
            self.admin.test_campaigns(
                self.request({}), CustomerTelegramCampaign.objects.filter(pk=self.campaign.pk),
            )
        send.assert_called_once()
        self.assertEqual(send.call_args.args[1], self.chat)

    def test_scheduled_campaign_can_be_cancelled_before_start(self):
        self.campaign.status = CustomerTelegramCampaign.SCHEDULED
        self.campaign.scheduled_at = timezone.now() + timedelta(hours=1)
        self.campaign.save(update_fields=('status', 'scheduled_at', 'updated_at'))
        with patch.object(self.admin, 'message_user'):
            self.admin.cancel_campaigns(
                self.request({}), CustomerTelegramCampaign.objects.filter(pk=self.campaign.pk),
            )
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, CustomerTelegramCampaign.CANCELLED)

    def grant(self, codename):
        self.user.user_permissions.add(Permission.objects.get(codename=codename))
        for name in ('_perm_cache', '_user_perm_cache', '_group_perm_cache'):
            if hasattr(self.user, name):
                delattr(self.user, name)

    def request(self, payload):
        request = self.factory.post('/admin/customer-telegram/', payload)
        request.user = self.user
        return request

    def get_request(self):
        request = self.factory.get('/admin/customer-telegram/')
        request.user = self.user
        return request
