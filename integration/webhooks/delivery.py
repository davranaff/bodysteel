import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as datetime_timezone
from email.utils import parsedate_to_datetime

from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from integration.models import IntegrationWebhookEvent
from integration.webhooks.configuration import require_webhook_configuration
from integration.webhooks.signing import sign_webhook
from integration.webhooks.transport import WebhookTransportError


RETRY_DELAYS = (60, 300, 1_800, 7_200, 86_400)
TRANSIENT_STATUSES = {408, 425, 429, 500, 502, 503, 504}
LEASE_TIMEOUT = timedelta(minutes=5)


@dataclass
class DeliverySummary:
    delivered: int = 0
    retried: int = 0
    failed: int = 0


class WebhookDeliveryService:
    def __init__(self, transport, clock=timezone.now, jitter=None):
        self.transport = transport
        self.clock = clock
        self.jitter = jitter or _random_jitter

    def deliver_batch(self, limit=100):
        configuration = require_webhook_configuration()
        summary = DeliverySummary()
        for _ in range(limit):
            event = _claim_event(self.clock())
            if not event:
                break
            outcome = self._deliver(event, configuration)
            setattr(summary, outcome, getattr(summary, outcome) + 1)
        return summary

    def _deliver(self, event, configuration):
        now = self.clock()
        timestamp = str(int(now.timestamp()))
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'BodySteel-SAVDOQ-Webhook/1.0',
            'X-Webhook-Id': event.event_id,
            'X-Webhook-Timestamp': timestamp,
            'X-Webhook-Signature': sign_webhook(configuration.secret, timestamp, event.body),
        }
        try:
            response = self.transport.send(configuration.url, event.body, headers)
        except WebhookTransportError:
            return self._retry_or_fail(event, now, None, 'network_error')
        if 200 <= response.status_code < 300:
            _mark_delivered(event, now, response.status_code)
            return 'delivered'
        if response.status_code in TRANSIENT_STATUSES:
            retry_after = _retry_after_seconds(response.retry_after, now)
            return self._retry_or_fail(
                event,
                now,
                response.status_code,
                'transient_http',
                retry_after,
            )
        failure = 'redirect_rejected' if 300 <= response.status_code < 400 else 'permanent_http'
        _mark_failed(event, response.status_code, failure)
        return 'failed'

    def _retry_or_fail(self, event, now, status_code, failure_code, retry_after=None):
        if event.attempt_count > len(RETRY_DELAYS):
            _mark_failed(event, status_code, 'retry_exhausted')
            return 'failed'
        base_delay = RETRY_DELAYS[event.attempt_count - 1]
        delay = base_delay + self.jitter(base_delay)
        if retry_after is not None:
            delay = max(delay, retry_after)
        _mark_retry(event, now + timedelta(seconds=delay), status_code, failure_code)
        return 'retried'


def _claim_event(now):
    stale_before = now - LEASE_TIMEOUT
    due = Q(status__in=('pending', 'retry'), next_attempt_at__lte=now) | Q(
        status='delivering',
        locked_at__lte=stale_before,
    ) | Q(status='delivering', locked_at__isnull=True)
    with transaction.atomic():
        queryset = IntegrationWebhookEvent.objects.filter(due).order_by('next_attempt_at', 'created_at')
        if connection.features.has_select_for_update_skip_locked:
            queryset = queryset.select_for_update(skip_locked=True)
        else:
            queryset = queryset.select_for_update()
        event = queryset.first()
        if not event:
            return None
        event.status = 'delivering'
        event.attempt_count += 1
        event.lease_token = secrets.token_hex(16)
        event.locked_at = now
        event.failure_code = ''
        event.save(update_fields=(
            'status',
            'attempt_count',
            'lease_token',
            'locked_at',
            'failure_code',
        ))
        return event


def _mark_delivered(event, now, status_code):
    _leased_event(event).update(
        status='delivered',
        delivered_at=now,
        last_http_status=status_code,
        failure_code='',
        lease_token=None,
        locked_at=None,
    )


def _mark_retry(event, next_attempt_at, status_code, failure_code):
    _leased_event(event).update(
        status='retry',
        next_attempt_at=next_attempt_at,
        last_http_status=status_code,
        failure_code=failure_code,
        lease_token=None,
        locked_at=None,
    )


def _mark_failed(event, status_code, failure_code):
    _leased_event(event).update(
        status='failed',
        last_http_status=status_code,
        failure_code=failure_code,
        lease_token=None,
        locked_at=None,
    )


def _leased_event(event):
    return IntegrationWebhookEvent.objects.filter(
        event_id=event.event_id,
        status='delivering',
        lease_token=event.lease_token,
    )


def _retry_after_seconds(value, now):
    if not value:
        return None
    if value.isdigit():
        return min(int(value), 86_400)
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime_timezone.utc)
        seconds = int((parsed - now.astimezone(datetime_timezone.utc)).total_seconds())
        return min(max(seconds, 0), 86_400)
    except (TypeError, ValueError, OverflowError):
        return None


def _random_jitter(base_delay):
    return secrets.randbelow(max(1, base_delay // 5 + 1))
