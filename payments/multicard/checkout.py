"""Start (or resume) a Multicard payment for a storefront order.

Idempotency: one live invoice per order payment and channel. A retry returns
the stored checkout URL; a concurrent start sees a short lease and gets 409.
The Multicard HTTP call never runs inside a database transaction.
"""
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from payments.models import Payment
from payments.multicard.client import MulticardClient, MulticardRejected, MulticardUnavailable
from payments.multicard.configuration import require_configuration
from payments.multicard.receipt import build_ofd, order_amount_tiyin
from payments.multicard.status_token import issue_status_token
from payments.multicard.transitions import PROVIDER
from store.models import Order
from users.orders.idempotency import IDEMPOTENCY_KEY, idempotency_digest


CHANNELS = ('web', 'app')
START_LEASE = timedelta(seconds=30)
INVOICE_REUSE_MARGIN = timedelta(minutes=2)


class PaymentNotFound(Exception):
    pass


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


def start_order_payment(order_id, actor, order_key, channel, language, client=None):
    configuration = require_configuration()
    reused = _reserve(order_id, actor, order_key, channel)
    if isinstance(reused, StartedPayment):
        return reused
    payment_id, stale_invoice = reused
    client = client or MulticardClient(configuration)
    order = Order.objects.prefetch_related('baskets__product').get(pk=order_id)
    token = issue_status_token(payment_id)
    try:
        if stale_invoice:
            _cancel_quietly(client, stale_invoice)
        invoice = client.create_invoice(_invoice_body(order, payment_id, token, channel, language, configuration))
    except BaseException:
        _release(payment_id)
        raise
    _store_invoice(payment_id, invoice, channel, configuration)
    return StartedPayment(payment_id, invoice.checkout_url, token, replayed=False)


@transaction.atomic
def _reserve(order_id, actor, order_key, channel):
    order = Order.objects.select_for_update().filter(pk=order_id).first()
    if order is None or not _authorized(order, actor, order_key):
        raise PaymentNotFound()
    if order.fulfillment_status == 'cancelled':
        raise PaymentNotPayable('not_payable')
    payment = _order_payment(order)
    if payment.status == Payment.SUCCEEDED or order.payment_status == 'paid':
        raise PaymentNotPayable('already_paid')
    if payment.status in {Payment.CANCELLED, Payment.REFUNDED}:
        raise PaymentNotPayable('not_payable')
    if payment.amount != order.total_price or payment.amount <= 0:
        raise PaymentNotPayable('not_payable')
    now = timezone.now()
    state = dict(payment.metadata.get('multicard') or {})
    if payment.provider == PROVIDER and payment.status == Payment.PENDING and _reusable(state, channel, now):
        return StartedPayment(payment.pk, state['checkout_url'], issue_status_token(payment.pk), replayed=True)
    lease = _parse_time(state.get('lease_until'))
    if lease and lease > now:
        raise PaymentNotPayable('start_in_progress')
    stale_invoice = state.get('invoice_uuid')
    payment.provider = PROVIDER
    payment.metadata = {**payment.metadata, 'multicard': {'lease_until': (now + START_LEASE).isoformat()}}
    payment.save(update_fields=('provider', 'metadata', 'updated_at'))
    return payment.pk, stale_invoice


def _authorized(order, actor, order_key):
    if order.user_id and getattr(actor, 'is_authenticated', False) and actor.pk == order.user_id:
        return True
    if isinstance(order_key, str) and IDEMPOTENCY_KEY.fullmatch(order_key) and order.idempotency_digest:
        return hmac.compare_digest(idempotency_digest(order_key), order.idempotency_digest)
    return False


def _order_payment(order):
    payment = Payment.objects.select_for_update(of=('self',)).filter(order=order).order_by('-pk').first()
    if payment is None:
        payment = Payment.objects.create(
            order=order, provider=PROVIDER, amount=order.total_price, currency='UZS',
            metadata={'purpose': 'physical_order', 'order_id': order.pk},
        )
    return payment


def _reusable(state, channel, now):
    expires_at = _parse_time(state.get('expires_at'))
    return (
        state.get('channel') == channel
        and isinstance(state.get('checkout_url'), str)
        and expires_at is not None
        and expires_at - INVOICE_REUSE_MARGIN > now
    )


def _invoice_body(order, payment_id, token, channel, language, configuration):
    return_base = (configuration.app_return_url if channel == 'app' else configuration.web_return_url).rstrip('/')
    return {
        'store_id': int(configuration.store_id) if configuration.store_id.isdigit() else configuration.store_id,
        'amount': order_amount_tiyin(order),
        'invoice_id': invoice_id_for(payment_id),
        'lang': language if language in {'ru', 'uz'} else 'ru',
        'return_url': '{}/{}'.format(return_base, token),
        'callback_url': configuration.callback_url,
        'ttl': configuration.invoice_ttl_seconds,
        'ofd': build_ofd(order, list(order.baskets.all()), configuration),
    }


def invoice_id_for(payment_id):
    return 'BS-{}'.format(payment_id)


def payment_id_from_invoice(invoice_id):
    if not isinstance(invoice_id, str) or not invoice_id.startswith('BS-'):
        return None
    value = invoice_id[3:]
    return int(value) if value.isdigit() and len(value) <= 18 and value[0] != '0' else None


@transaction.atomic
def _store_invoice(payment_id, invoice, channel, configuration):
    payment = Payment.objects.select_for_update(of=('self',)).select_related('order').get(pk=payment_id)
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
    if payment.order.payment_status != 'paid':
        payment.order.payment_status = 'pending'
        payment.order.save(update_fields=('payment_status',))


@transaction.atomic
def _release(payment_id):
    payment = Payment.objects.select_for_update(of=('self',)).get(pk=payment_id)
    state = dict(payment.metadata.get('multicard') or {})
    state.pop('lease_until', None)
    payment.metadata = {**payment.metadata, 'multicard': state}
    payment.save(update_fields=('metadata', 'updated_at'))


def _cancel_quietly(client, invoice_uuid):
    try:
        client.cancel_invoice(invoice_uuid)
    except (MulticardUnavailable, MulticardRejected, ValueError):
        # Best effort: if the stale invoice is still paid, the callback for the
        # second transaction is refused and Multicard returns that money.
        pass


def _parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
