import json
import re
from datetime import timezone as datetime_timezone

from django.utils import timezone

from integration.models import IntegrationWebhookEvent, webhook_event_id
from integration.webhooks.configuration import webhook_is_enabled


API_VERSION = '2026-08-01'
PRODUCT_EVENT_TYPES = {'product.created', 'product.updated', 'product.deleted'}
PRODUCT_ID = re.compile(r'^[^\s,/?#]{1,255}$')


def enqueue_product_events(event_type, product_ids, occurred_at=None):
    if event_type not in PRODUCT_EVENT_TYPES:
        raise ValueError('Unsupported product webhook event')
    identifiers = _product_ids(product_ids)
    return _persist([
        _event(event_type, {'productId': product_id}, occurred_at)
        for product_id in identifiers
    ])


def enqueue_inventory_events(product_ids, occurred_at=None):
    identifiers = _product_ids(product_ids)
    events = [
        _event('inventory.updated', {'productIds': identifiers[index:index + 100]}, occurred_at)
        for index in range(0, len(identifiers), 100)
    ]
    return _persist(events)


def enqueue_order_event(data, order_id, occurred_at=None):
    allowed = {
        'orderId',
        'amount',
        'currency',
        'productIds',
        'channel',
        'aiSessionId',
        'experimentVariant',
    }
    required = {'orderId', 'amount', 'currency', 'productIds'}
    if (
        not isinstance(data, dict)
        or not required.issubset(data)
        or not set(data).issubset(allowed)
        or data['orderId'] != str(order_id)
        or not 1 <= len(data['orderId']) <= 200
        or isinstance(data['amount'], bool)
        or not isinstance(data['amount'], int)
        or data['amount'] < 0
        or data['currency'] != 'UZS'
        or not isinstance(data['productIds'], list)
        or len(data['productIds']) > 100
        or _product_ids(data['productIds']) != data['productIds']
        or ('channel' in data and data['channel'] not in {'web', 'telegram'})
        or ('aiSessionId' in data and not _text(data['aiSessionId'], 200))
        or (
            'experimentVariant' in data
            and (
                not _text(data['experimentVariant'], 64)
                or not re.fullmatch(r'[A-Za-z0-9._-]+', data['experimentVariant'])
            )
        )
    ):
        raise ValueError('Invalid order webhook data')
    event = _event(
        'order.completed',
        data,
        occurred_at,
        event_id='order.completed:{}'.format(order_id),
    )
    return _persist([event], ignore_conflicts=True)


def _event(event_type, data, occurred_at, event_id=None):
    occurred_at = occurred_at or timezone.now()
    identifier = event_id or webhook_event_id()
    payload = {
        'id': identifier,
        'type': event_type,
        'apiVersion': API_VERSION,
        'occurredAt': _isoformat_utc(occurred_at),
        'data': data,
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    return IntegrationWebhookEvent(
        event_id=identifier,
        event_type=event_type,
        occurred_at=occurred_at,
        body=body,
    )


def _persist(events, ignore_conflicts=False):
    if not events or not webhook_is_enabled():
        return 0
    IntegrationWebhookEvent.objects.bulk_create(
        events,
        batch_size=200,
        ignore_conflicts=ignore_conflicts,
    )
    return len(events)


def _product_ids(values):
    identifiers = sorted({str(value) for value in values if value is not None}, key=_identifier_key)
    if any(not PRODUCT_ID.fullmatch(value) for value in identifiers):
        raise ValueError('Invalid webhook product ID')
    return identifiers


def _identifier_key(value):
    return (0, int(value)) if value.isdigit() else (1, value)


def _isoformat_utc(value):
    return value.astimezone(datetime_timezone.utc).isoformat().replace('+00:00', 'Z')


def _text(value, maximum):
    return isinstance(value, str) and 1 <= len(value) <= maximum
