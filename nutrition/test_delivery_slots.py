from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from nutrition.models import DeliverySlot, DeliveryZone


OPTIONS_URL = '/api/v1/nutrition/delivery/options/'


class DeliverySlotListingTests(TestCase):
    def setUp(self):
        self.zone = DeliveryZone.objects.create(code='center', name_ru='Центр', name_uz='Markaz')
        # Fixed "now": 12:00 local time, so morning/afternoon slots are deterministic.
        self.today = timezone.localdate()
        self.now = timezone.make_aware(datetime.combine(self.today, time(12)))
        self.patcher = patch('django.utils.timezone.now', return_value=self.now)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_started_and_cut_off_slots_are_hidden(self):
        self.slot(self.today, 9, 11)
        self.slot(self.today, 11, 13)
        self.slot(self.today, 14, 16, cutoff_at=self.now - timedelta(minutes=1))
        open_slot = self.slot(self.today, 16, 18, cutoff_at=self.now + timedelta(hours=1))
        no_cutoff = self.slot(self.today, 18, 20)
        full = self.slot(self.today, 20, 22, reserved=5)

        slots = self.options(self.today)

        self.assertEqual([slot['id'] for slot in slots], [open_slot.pk, no_cutoff.pk, full.pk])
        self.assertEqual([slot['available'] for slot in slots], [True, True, False])

    def test_past_dates_return_no_slots(self):
        yesterday = self.today - timedelta(days=1)
        self.slot(yesterday, 18, 20)

        self.assertEqual(self.options(yesterday), [])

    def test_future_slots_are_listed(self):
        tomorrow = self.today + timedelta(days=1)
        slot = self.slot(tomorrow, 9, 11, cutoff_at=self.now + timedelta(hours=10))

        self.assertEqual([item['id'] for item in self.options(tomorrow)], [slot.pk])

    def options(self, delivery_date):
        response = self.client.get(OPTIONS_URL, {'zone': 'center', 'date': delivery_date.isoformat()})
        self.assertEqual(response.status_code, 200)
        return response.json()['slots']

    def slot(self, delivery_date, starts, ends, cutoff_at=None, reserved=0):
        return DeliverySlot.objects.create(
            zone=self.zone, delivery_date=delivery_date, starts_at=time(starts), ends_at=time(ends),
            cutoff_at=cutoff_at, capacity=5, reserved_count=reserved,
        )
