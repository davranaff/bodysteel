"""Invoice bookkeeping shared by order and course payments.

A payment row keeps at most one live Multicard invoice in ``metadata['multicard']``.
A retry on the same channel gets the stored checkout URL back; a concurrent start
sees a short lease and gets 409. The Multicard HTTP call itself never runs inside
a database transaction, so these helpers are the only places that lock the row.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from payments.models import Payment
from payments.multicard.client import MulticardRejected, MulticardUnavailable
from payments.multicard.status_token import issue_status_token
from payments.multicard.transitions import PROVIDER


START_LEASE = timedelta(seconds=30)
INVOICE_REUSE_MARGIN = timedelta(minutes=2)


class PaymentNotPayable(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class StartedPayment:
    payment_id: int
    checkout_url: str
    status_token: str
    replayed: bool


def take_lease(payment, channel):
    """With the payment row locked: replay a live invoice, or lease the row for a new one.

    Returns ``(StartedPayment, None)`` for a replay, otherwise ``(None, stale_invoice_uuid)``.
    """
    now = timezone.now()
    state = dict(payment.metadata.get('multicard') or {})
    if payment.provider == PROVIDER and payment.status == Payment.PENDING and _reusable(state, channel, now):
        return StartedPayment(payment.pk, state['checkout_url'], issue_status_token(payment.pk), replayed=True), None
    lease = parse_time(state.get('lease_until'))
    if lease and lease > now:
        raise PaymentNotPayable('start_in_progress')
    payment.provider = PROVIDER
    payment.metadata = {**payment.metadata, 'multicard': {'lease_until': (now + START_LEASE).isoformat()}}
    payment.save(update_fields=('provider', 'metadata', 'updated_at'))
    return None, state.get('invoice_uuid')


@transaction.atomic
def store_invoice(payment_id, invoice, channel, configuration):
    payment = (
        Payment.objects.select_for_update(of=('self',))
        .select_related('order', 'course_purchase').get(pk=payment_id)
    )
    now = timezone.now()
    if payment.status != Payment.SUCCEEDED:
        payment.status = Payment.PENDING
    payment.metadata = {**payment.metadata, 'multicard': {
        'invoice_uuid': invoice.uuid,
        'checkout_url': invoice.checkout_url,
        'channel': channel,
        'created_at': now.isoformat(),
        'expires_at': (now + timedelta(seconds=configuration.invoice_ttl_seconds)).isoformat(),
    }}
    payment.save(update_fields=('status', 'metadata', 'updated_at'))
    if payment.order_id and payment.order.payment_status != 'paid':
        payment.order.payment_status = 'pending'
        payment.order.save(update_fields=('payment_status',))
    purchase = payment.course_purchase
    if purchase is not None and purchase.status == purchase.CREATED:
        purchase.status = purchase.PENDING
        purchase.save(update_fields=('status',))


@transaction.atomic
def release(payment_id):
    payment = Payment.objects.select_for_update(of=('self',)).get(pk=payment_id)
    state = dict(payment.metadata.get('multicard') or {})
    state.pop('lease_until', None)
    payment.metadata = {**payment.metadata, 'multicard': state}
    payment.save(update_fields=('metadata', 'updated_at'))


def cancel_quietly(client, invoice_uuid):
    try:
        client.cancel_invoice(invoice_uuid)
    except (MulticardUnavailable, MulticardRejected, ValueError):
        # Best effort: if the stale invoice is still paid, the callback for the
        # second transaction is refused and Multicard returns that money.
        pass


def invoice_body(configuration, payment_id, token, channel, language, amount_tiyin, ofd):
    return_base = (configuration.app_return_url if channel == 'app' else configuration.web_return_url).rstrip('/')
    return {
        'store_id': int(configuration.store_id) if configuration.store_id.isdigit() else configuration.store_id,
        'amount': amount_tiyin,
        'invoice_id': invoice_id_for(payment_id),
        'lang': language if language in {'ru', 'uz'} else 'ru',
        'return_url': '{}/{}'.format(return_base, token),
        'callback_url': configuration.callback_url,
        'ttl': configuration.invoice_ttl_seconds,
        'ofd': ofd,
    }


def invoice_id_for(payment_id):
    return 'BS-{}'.format(payment_id)


def payment_id_from_invoice(invoice_id):
    if not isinstance(invoice_id, str) or not invoice_id.startswith('BS-'):
        return None
    value = invoice_id[3:]
    return int(value) if value.isdigit() and len(value) <= 18 and value[0] != '0' else None


def _reusable(state, channel, now):
    expires_at = parse_time(state.get('expires_at'))
    return (
        state.get('channel') == channel
        and isinstance(state.get('checkout_url'), str)
        and expires_at is not None
        and expires_at - INVOICE_REUSE_MARGIN > now
    )


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
