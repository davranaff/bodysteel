from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from notifications.models import PushCampaign, PushDelivery
from notifications.tests.fixtures import PUSH_SETTINGS, campaign, device, operator, shopper


@override_settings(**PUSH_SETTINGS)
class PushAdminTests(TestCase):
    def setUp(self):
        self.actor = operator()
        self.actor.is_superuser = True
        self.actor.save()
        self.client.force_login(self.actor)
        self.campaign = campaign(self.actor)
        device(shopper())
        self.path = reverse('admin:notifications_pushcampaign_preview', args=[self.campaign.pk])

    def test_draft_form_and_preview_render_all_filter_groups(self):
        add = self.client.get(reverse('admin:notifications_pushcampaign_add'))
        self.assertEqual(add.status_code, 200)
        self.assertContains(add, 'last_purchase_product_ids')
        self.assertContains(add, 'has_course_access')
        self.assertContains(add, 'Возраст')
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1 устройств')
        self.assertFalse(PushDelivery.objects.exists())

    def test_confirmation_freezes_and_locked_admin_page_still_renders(self):
        response = self.client.post(self.path, {'operation': 'publish', 'expected_devices': 1})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PushDelivery.objects.count(), 1)
        readonly = self.client.get(reverse('admin:notifications_pushcampaign_change', args=[self.campaign.pk]))
        self.assertEqual(readonly.status_code, 200)
        self.assertContains(readonly, 'Synthetic campaign')
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)

    def test_saved_date_filters_remain_editable_in_datetime_local_inputs(self):
        from datetime import datetime
        from notifications.forms import PushCampaignForm
        self.campaign.audience = {'joined_after': '2026-10-01T12:30:00+05:00'}
        form = PushCampaignForm(instance=self.campaign)
        self.assertIsInstance(form.fields['joined_after'].initial, datetime)
        rendered = str(form['joined_after'])
        self.assertIn('2026-10-01T', rendered)
        self.assertNotIn('+05:00', rendered)

    def test_only_exact_publish_permission_allows_sending(self):
        staff = shopper(2, is_staff=True)
        staff.user_permissions.add(Permission.objects.get(content_type__app_label='notifications', codename='view_pushcampaign'))
        self.client.force_login(staff)
        response = self.client.post(self.path, {'operation': 'publish', 'expected_devices': 1})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PushDelivery.objects.exists())

    def test_unconfigured_admin_is_honest_and_cannot_send(self):
        with override_settings(PUSH_ENABLED=False):
            response = self.client.get(self.path)
            self.assertContains(response, 'Firebase ещё не подключён')
            self.client.post(self.path, {'operation': 'publish', 'expected_devices': 1})
        self.assertFalse(PushDelivery.objects.exists())

    def test_device_admin_does_not_render_credentials(self):
        from notifications.models import PushDevice
        record = PushDevice.objects.first()
        response = self.client.get(reverse('admin:notifications_pushdevice_change', args=[record.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, record.token_ciphertext)
        self.assertNotContains(response, record.credential_digest)

    def test_unsafe_urls_and_oversized_payloads_fail(self):
        from django.core.exceptions import ValidationError
        for url in ('https://evil.example/app', 'https://bodysteel.uz/app?token=private', 'https://bodysteel.uz/checkout'):
            self.campaign.target_url = url
            with self.assertRaises(ValidationError):
                self.campaign.full_clean()
        self.campaign.target_url = ''
        self.campaign.body_ru = '😀' * 1400
        with self.assertRaises(ValidationError):
            self.campaign.full_clean()
