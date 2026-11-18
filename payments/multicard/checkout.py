"""Start (or resume) a Multicard payment for a storefront order.

Idempotency: one live invoice per order payment and channel. A retry returns
the stored checkout URL; a concurrent start sees a short lease and gets 409.
The Multicard HTTP call never runs inside a database transaction.
"""
import hmac

from django.db import transaction

from payments.models import Payment
from payments.multicard.client import MulticardClient
from payments.multicard.configuration import require_configuration
from payments.multicard.invoice_state import (
    PaymentNotPayable,
    StartedPayment,
    cancel_quietly,
    invoice_body,
    invoice_id_for,
    payment_id_from_invoice,
    release,
    store_invoice,
    take_lease,
)
from payments.multicard.receipt import build_ofd, order_amount_tiyin
from payments.multicard.status_token import issue_status_token
from payments.multicard.transitions import PROVIDER
from store.models import Order
from users.orders.idempotency import IDEMPOTENCY_KEY, idempotency_digest


CHANNELS = ('web', 'app')

__all__ = (
    'CHANNELS', 'PaymentNotFound', 'PaymentNotPayable', 'StartedPayment',
    'invoice_id_for', 'payment_id_from_invoice', 'start_order_payment',
)


class PaymentNotFound(Exception):
    pass


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
            cancel_quietly(client, stale_invoice)
        invoice = client.create_invoice(invoice_body(
            configuration, payment_id, token, channel, language,
            order_amount_tiyin(order), build_ofd(order, list(order.baskets.all()), configuration),
        ))
    except BaseException:
        release(payment_id)
        raise
    store_invoice(payment_id, invoice, channel, configuration)
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
    replay, stale_invoice = take_lease(payment, channel)
    if replay is not None:
        return replay
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
