import logging
from functools import partial

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from notifications.policies.order_updates import order_update_event
from notifications.services.order_updates import enqueue_order_update_safely
from store.models import Order

logger = logging.getLogger('bodysteel.notifications')
STATUS_FIELDS = frozenset({'payment_status', 'fulfillment_status'})


@receiver(pre_save, sender=Order)
def remember_previous_order_statuses(sender, instance, update_fields=None, raw=False, **kwargs):
    instance._push_previous_statuses = None
    if raw or not instance.pk or (update_fields is not None and not STATUS_FIELDS & set(update_fields)):
        return
    try:
        instance._push_previous_statuses = Order.objects.filter(pk=instance.pk).values_list(
            'payment_status', 'fulfillment_status').first()
    except Exception:  # noqa: BLE001 - push bookkeeping must not block the order save
        logger.exception('Order push status snapshot failed (order_id=%s)', instance.pk)


@receiver(post_save, sender=Order)
def queue_order_update_push(sender, instance, created, raw=False, **kwargs):
    previous = getattr(instance, '_push_previous_statuses', None)
    instance._push_previous_statuses = None
    if created or raw or previous is None or instance.user_id is None or not settings.PUSH_ENABLED:
        return
    try:
        event = order_update_event(previous, instance)
        if event:
            transaction.on_commit(partial(enqueue_order_update_safely, instance, event), robust=True)
    except Exception:  # noqa: BLE001 - push bookkeeping must not block the order save
        logger.exception('Order push scheduling failed (order_id=%s)', instance.pk)
