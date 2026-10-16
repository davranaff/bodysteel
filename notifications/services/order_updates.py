import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from notifications.configuration import PushNotConfigured, require_provider_configuration
from notifications.models import PushDelivery, PushDevice
from notifications.policies.order_updates import ORDER_EVENTS, ORDER_TARGET_URL, order_update_copy

logger = logging.getLogger('bodysteel.notifications')


def dedupe_key(order_id, event, device_id):
    return 'order:{}:{}:{}'.format(order_id, event, device_id)


def eligible_order_devices(user_id, now):
    # Transactional: OS permission and activity are required; marketing consent is not.
    return PushDevice.objects.filter(
        user_id=user_id, user__is_active=True, user__deleted_at__isnull=True, is_active=True,
        permission__in=(PushDevice.Permission.AUTHORIZED, PushDevice.Permission.PROVISIONAL),
        last_seen_at__gte=now - timedelta(days=settings.PUSH_DEVICE_STALE_DAYS),
    ).exclude(token_ciphertext='').only('pk', 'user_id', 'registration_scope', 'language')


def enqueue_order_update(order, event):
    """Queue one frozen, localized alert per eligible device; returns the number of new rows.

    Push off/unconfigured enqueues nothing, so enabling push later never releases a stale backlog.
    """
    if event not in ORDER_EVENTS:
        raise ValueError('Unknown order update event')
    if order.pk is None or order.user_id is None:
        return 0
    try:
        require_provider_configuration()
    except PushNotConfigured:
        return 0
    now = timezone.now()
    devices = list(eligible_order_devices(order.user_id, now)[:settings.PUSH_MAX_DEVICES_PER_USER])
    keys = {device.pk: dedupe_key(order.pk, event, device.pk) for device in devices}
    existing = set(PushDelivery.objects.filter(dedupe_key__in=keys.values()).values_list('dedupe_key', flat=True))
    rows = []
    for device in devices:
        if keys[device.pk] in existing:
            continue
        language = device.language if device.language in ('ru', 'uz') else 'ru'
        title, body = order_update_copy(event, language, order.order_code)
        rows.append(PushDelivery(
            kind=PushDelivery.Kind.ORDER_UPDATE, order_id=order.pk, order_event=event,
            dedupe_key=keys[device.pk], device=device, user_id=order.user_id,
            expected_scope=device.registration_scope, language=language, title=title, body=body,
            target_url=ORDER_TARGET_URL, next_attempt_at=now,
        ))
    # A concurrent enqueue of the same key is dropped by the unique dedupe_key.
    PushDelivery.objects.bulk_create(rows, ignore_conflicts=True)
    return len(rows)


def enqueue_order_update_safely(order, event):
    """on_commit entry point: an order save must never fail because of push bookkeeping."""
    try:
        return enqueue_order_update(order, event)
    except Exception:  # noqa: BLE001 - logged without order PII, never re-raised into checkout/admin
        logger.exception('Order push enqueue failed (order_id=%s, event=%s)', order.pk, event)
        return 0
