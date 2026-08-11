import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from integration.models import RegosWebhookEvent
from integration.regos.config import RegosSyncError
from integration.regos.sync import archive_regos_item, sync_from_regos, sync_item_from_regos


logger = logging.getLogger(__name__)


def enqueue_webhook(*, event_id, event_type, item_id, payload):
    """Store first, acknowledge REGOS immediately, and deduplicate retries."""
    event, created = RegosWebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            'event_type': event_type,
            'item_id': item_id,
            'payload': payload,
        },
    )
    return event, created


def process_pending_events(limit=20):
    """Process a bounded batch; failed REGOS reads remain queued with backoff."""
    processed = retried = 0
    for _ in range(limit):
        event = _claim_next_event()
        if event is None:
            break
        try:
            _process_event(event)
        except RegosSyncError as error:
            _retry(event.pk, str(error))
            retried += 1
        except Exception:
            logger.exception('Unexpected REGOS webhook processing error for %s', event.event_id)
            _retry(event.pk, 'Unexpected synchronization error')
            retried += 1
        else:
            RegosWebhookEvent.objects.filter(pk=event.pk).update(
                status=RegosWebhookEvent.STATUS_DONE,
                processed_at=timezone.now(),
                last_error='',
            )
            processed += 1
    return processed, retried


def _claim_next_event():
    now = timezone.now()
    with transaction.atomic():
        event = (
            RegosWebhookEvent.objects.select_for_update(skip_locked=True)
            .filter(
                status__in=(RegosWebhookEvent.STATUS_PENDING, RegosWebhookEvent.STATUS_RETRY),
                next_attempt_at__lte=now,
            )
            .order_by('next_attempt_at', 'created_at')
            .first()
        )
        if event is None:
            return None
        event.status = RegosWebhookEvent.STATUS_PROCESSING
        event.attempt_count += 1
        event.last_error = ''
        event.save(update_fields=('status', 'attempt_count', 'last_error'))
        return event


def _process_event(event):
    if event.event_type == 'ItemDeleted' or event.event_type == 'ItemDeleteMarked':
        if event.item_id is not None:
            archive_regos_item(event.item_id)
        return
    if event.event_type == 'ItemAdded' and event.item_id is not None:
        sync_item_from_regos(event.item_id, create_draft=True)
        return
    if event.event_type == 'ItemEdited' and event.item_id is not None:
        sync_item_from_regos(event.item_id)
        return
    # Sale, return, movement and other business events all need the
    # authoritative available quantity from REGOS.
    sync_from_regos()


def _retry(event_id, error):
    event = RegosWebhookEvent.objects.get(pk=event_id)
    seconds = min(60 * (2 ** max(0, event.attempt_count - 1)), 3600)
    event.status = RegosWebhookEvent.STATUS_RETRY
    event.next_attempt_at = timezone.now() + timedelta(seconds=seconds)
    event.last_error = error[:255]
    event.save(update_fields=('status', 'next_attempt_at', 'last_error'))
