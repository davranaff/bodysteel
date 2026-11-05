"""Order-payment state transitions driven by Multicard.

Payment: created -> pending -> succeeded | failed (retryable) ; succeeded -> refunded
Order.payment_status mirrors it: unpaid -> pending -> paid | failed ; paid -> refunded

Every transition locks the payment row, so a callback, a webhook and a status
poll racing each other converge on one outcome without duplicate side effects.
"""
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from payments.models import Payment, PaymentEvent
from payments.multicard.receipt import order_amount_tiyin
from payments.services import complete_payment


PROVIDER = 'multicard'


@dataclass(frozen=True)
class CallbackOutcome:
    accepted: bool
    message: str = ''


def lock_payment(payment_id):
    return (
        Payment.objects.select_for_update(of=('self',))
        .select_related('order')
        .filter(pk=payment_id, provider=PROVIDER, order__isnull=False)
        .first()
    )


@transaction.atomic
def record_success(payment_id, transaction_uuid, amount_tiyin, event_id, payload_hash):
    """Apply a paid transaction. A rejected outcome makes Multicard refund it."""
    payment = lock_payment(payment_id)
    if payment is None:
        return CallbackOutcome(False, 'Счёт не найден')
    if amount_tiyin != order_amount_tiyin(payment.order) or amount_tiyin != payment.amount * 100:
        return CallbackOutcome(False, 'Сумма не совпадает с заказом')
    if payment.status == Payment.SUCCEEDED:
        if payment.provider_payment_id == transaction_uuid:
            return CallbackOutcome(True)
        # A second, different transaction for an already paid order: refuse so
        # Multicard returns the money instead of double-charging the shopper.
        return CallbackOutcome(False, 'Заказ уже оплачен')
    if payment.status in {Payment.CANCELLED, Payment.REFUNDED}:
        return CallbackOutcome(False, 'Заказ отменён')
    if payment.order.fulfillment_status == 'cancelled':
        return CallbackOutcome(False, 'Заказ отменён')
    if Payment.objects.filter(provider_payment_id=transaction_uuid).exclude(pk=payment.pk).exists():
        return CallbackOutcome(False, 'Транзакция уже учтена')
    _record_event(payment, event_id, 'success', payload_hash)
    complete_payment(payment.pk, transaction_uuid)
    return CallbackOutcome(True)


@transaction.atomic
def record_failure(payment_id, transaction_uuid, event_id, payload_hash):
    payment = lock_payment(payment_id)
    if payment is None or payment.status != Payment.PENDING:
        return
    current = (payment.metadata.get('multicard') or {}).get('payment_uuid')
    if transaction_uuid and current and current != transaction_uuid:
        return
    _record_event(payment, event_id, 'error', payload_hash)
    payment.status = Payment.FAILED
    payment.save(update_fields=('status', 'updated_at'))
    payment.order.payment_status = 'failed'
    payment.order.save(update_fields=('payment_status',))


@transaction.atomic
def record_refund(payment_id, transaction_uuid, event_id, payload_hash):
    payment = lock_payment(payment_id)
    if payment is None or payment.status != Payment.SUCCEEDED:
        return
    if payment.provider_payment_id != transaction_uuid:
        return
    _record_event(payment, event_id, 'revert', payload_hash)
    payment.status = Payment.REFUNDED
    payment.save(update_fields=('status', 'updated_at'))
    payment.order.payment_status = 'refunded'
    payment.order.save(update_fields=('payment_status',))


def apply_invoice_state(payment_id, invoice):
    """Reconcile a polled invoice (used when a callback has not arrived yet)."""
    if invoice.payment_status == 'success' and invoice.payment_uuid:
        payment = Payment.objects.select_related('order').get(pk=payment_id)
        record_success(
            payment_id, invoice.payment_uuid, payment.amount * 100,
            'poll:{}'.format(invoice.payment_uuid), '',
        )
    elif invoice.payment_status == 'error':
        record_failure(payment_id, invoice.payment_uuid, 'poll-error:{}'.format(invoice.payment_uuid or invoice.uuid), '')
    elif invoice.payment_status == 'revert' and invoice.payment_uuid:
        record_refund(payment_id, invoice.payment_uuid, 'poll-revert:{}'.format(invoice.payment_uuid), '')


def _record_event(payment, event_id, event_type, payload_hash):
    try:
        with transaction.atomic():
            PaymentEvent.objects.create(
                payment=payment,
                provider=PROVIDER,
                external_event_id=event_id[:255],
                event_type=event_type,
                payload_hash=payload_hash or '-',
                processing_status='processed',
            )
    except IntegrityError:
        # An exact replay of an already recorded event; the state change above
        # is idempotent, so the duplicate row is simply not written again.
        pass
