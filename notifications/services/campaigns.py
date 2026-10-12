from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from notifications.configuration import require_provider_configuration
from notifications.models import PushCampaign, PushDelivery, PushDevice
from notifications.querysets.audience import audience_devices
from users.models import User


@dataclass(frozen=True)
class AudienceSize:
    devices: int
    users: int


def require_permission(actor, action):
    operator = User.objects.filter(pk=actor.pk, is_active=True, is_staff=True, deleted_at__isnull=True).first()
    if operator is None or not operator.has_perm('notifications.' + action + '_pushcampaign'):
        raise PermissionDenied('Campaign operation unavailable')
    return operator


def preview_audience(campaign):
    campaign.full_clean()
    devices = audience_devices(campaign.audience)
    return AudienceSize(devices.count(), devices.order_by().values('user_id').distinct().count())


def save_draft(campaign, actor):
    require_permission(actor, 'change' if not campaign._state.adding else 'add')
    campaign.full_clean()
    with transaction.atomic():
        existing = PushCampaign.objects.select_for_update().filter(pk=campaign.pk).first()
        if existing and existing.status != PushCampaign.Status.DRAFT:
            raise ValidationError('Кампания уже запущена. Создайте новую для изменения сообщения.')
        campaign.status = PushCampaign.Status.DRAFT
        campaign.created_by = existing.created_by if existing else actor
        campaign.save()


def publish_campaign(campaign_id, actor, expected_size=None):
    operator = require_permission(actor, 'publish')
    require_provider_configuration()
    with transaction.atomic():
        campaign = PushCampaign.objects.select_for_update().get(pk=campaign_id)
        if campaign.status != PushCampaign.Status.DRAFT:
            return False
        campaign.full_clean()
        devices = list(audience_devices(campaign.audience).only(
            'pk', 'user_id', 'registration_scope', 'language')[:settings.PUSH_MAX_CAMPAIGN_DEVICES + 1])
        count = len(devices)
        if count == 0 or count > settings.PUSH_MAX_CAMPAIGN_DEVICES:
            raise ValidationError('Аудитория пуста или превышает лимит. Уточните фильтры.')
        if expected_size is not None and count != expected_size:
            raise ValidationError('Аудитория изменилась. Проверьте количество и подтвердите заново.')
        now = timezone.now()
        user_count = len({device.user_id for device in devices})
        batch = []
        for device in devices:
            batch.append(_delivery(campaign, device, now, operator))
            if len(batch) == 500:
                PushDelivery.objects.bulk_create(batch)
                batch = []
        if batch:
            PushDelivery.objects.bulk_create(batch)
        campaign.status = PushCampaign.Status.SCHEDULED if campaign.scheduled_at and campaign.scheduled_at > now else PushCampaign.Status.QUEUED
        campaign.audience_frozen_at = now
        campaign.recipient_count = count
        campaign.user_count = user_count
        campaign.published_by = operator
        campaign.save(update_fields=('status', 'audience_frozen_at', 'recipient_count', 'user_count', 'published_by', 'updated_at'))
    return True


def cancel_campaign(campaign_id, actor):
    require_permission(actor, 'cancel')
    with transaction.atomic():
        campaign = PushCampaign.objects.select_for_update().get(pk=campaign_id)
        if campaign.status in (PushCampaign.Status.COMPLETED, PushCampaign.Status.CANCELLED):
            return False
        campaign.status = PushCampaign.Status.CANCELLED
        campaign.save(update_fields=('status', 'updated_at'))
        campaign.deliveries.filter(status__in=('pending', 'retry')).update(status='skipped', failure_code='campaign_cancelled')
    return True


def queue_test(campaign_id, device_id, actor):
    operator = require_permission(actor, 'test')
    require_provider_configuration()
    with transaction.atomic():
        campaign = PushCampaign.objects.select_for_update().get(pk=campaign_id)
        campaign.full_clean()
        if campaign.status != PushCampaign.Status.DRAFT:
            raise ValidationError('Тест доступен только для черновика.')
        device = PushDevice.objects.filter(pk=device_id, user=operator, is_active=True, permission__in=('authorized', 'provisional')).first()
        if device is None:
            raise ValidationError('Тест можно отправить только на своё разрешённое устройство.')
        if campaign.deliveries.filter(is_test=True, status__in=('pending', 'retry', 'sending')).exists():
            raise ValidationError('Предыдущий тест ещё обрабатывается.')
        delivery = _delivery(campaign, device, timezone.now(), operator)
        delivery.is_test = True
        delivery.next_attempt_at = timezone.now()
        delivery.save()
    return delivery.pk


def _delivery(campaign, device, now, actor):
    language = device.language if device.language in ('ru', 'uz') else 'ru'
    return PushDelivery(campaign=campaign, device=device, user_id=device.user_id,
                        expected_scope=device.registration_scope, language=language,
                        title=getattr(campaign, 'title_' + language), body=getattr(campaign, 'body_' + language),
                        target_url=campaign.target_url, next_attempt_at=campaign.scheduled_at or now,
                        requested_by=actor)
