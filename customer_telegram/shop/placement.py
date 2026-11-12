"""Turn a confirmed checkout into a storefront order and a Multicard payment.

The order goes through the same ``create_order`` as the site, with an idempotency key
derived from the checkout attempt, so a repeated tap replays the same order.
"""
import logging

from django.contrib.auth.models import AnonymousUser
from django.db import transaction

from customer_telegram.models import CustomerTelegramCheckout
from customer_telegram.shop.cart import clear_cart, order_lines
from customer_telegram.shop.cart_screens import unavailable_reason
from customer_telegram.shop.checkout import idempotency_key
from customer_telegram.shop.labels import text
from customer_telegram.shop.order_screens import CASH, FAILED, PAID, PENDING, confirm_state, order_state
from payments.multicard.checkout import PaymentNotFound, PaymentNotPayable, start_order_payment
from payments.multicard.client import MulticardRejected, MulticardUnavailable
from payments.multicard.configuration import MulticardNotConfigured, multicard_enabled
from teleg.utils.notify_message import notify_message
from users.orders.creation import create_order
from users.orders.errors import OrderIdempotencyConflict, OrderUnavailable


logger = logging.getLogger(__name__)


def place_and_pay(chat, widget):
    """Returns ``(state, pay_url)`` for the order widget after a "pay" tap."""
    language = chat.language or 'ru'
    checkout = CustomerTelegramCheckout.objects.filter(chat=chat).select_related('order').first()
    if checkout is None or checkout.step not in {checkout.CONFIRM, checkout.PLACED}:
        return {'v': 'o', 'st': FAILED, 'm': text(language, 'stale')}, None
    order = checkout.order
    if order is None:
        order, error = _create(chat, checkout)
        if order is None:
            return confirm_state(chat, checkout, error), None
    widget.order = order
    widget.save(update_fields=('order',))
    if order.payment_status == 'paid':
        return order_state(order, language, PAID, notice=text(language, 'paid')), None
    if not multicard_enabled():
        return order_state(order, language, CASH), None
    return _start_payment(chat, checkout, order, language)


def payment_state(chat, widget):
    language = chat.language or 'ru'
    order = widget.order
    if order is None:
        return {'v': 'o', 'st': FAILED, 'm': text(language, 'stale')}
    order.refresh_from_db(fields=('payment_status',))
    if order.payment_status == 'paid':
        return order_state(order, language, PAID, notice=text(language, 'paid'))
    checkout = CustomerTelegramCheckout.objects.filter(chat=chat, order=order).first()
    url = _pending_url(order)
    return order_state(order, language, PENDING if url else FAILED, url=url,
                       notice=text(language, 'not_paid_yet' if checkout else 'stale'))


def _create(chat, checkout):
    language = chat.language or 'ru'
    lines = order_lines(chat)
    if not lines:
        return None, text(language, 'unavailable_other')
    command = {
        'baskets': lines, 'type': checkout.delivery_type, 'full_name': checkout.full_name or checkout.phone,
        'phone': checkout.phone, 'address': checkout.address or '', 'customer_note': 'Заказ из Telegram-бота',
    }
    if checkout.latitude is not None and checkout.longitude is not None:
        command.update(address_latitude=checkout.latitude, address_longitude=checkout.longitude)
    if multicard_enabled():
        command['payment_method'] = 'online'
    actor = _actor(chat)
    try:
        created = create_order(command, actor, idempotency_key(checkout))
    except OrderUnavailable as error:
        return None, text(language, 'checkout_failed').format(unavailable_reason(language, error.code))
    except OrderIdempotencyConflict:
        return None, text(language, 'stale')
    with transaction.atomic():
        CustomerTelegramCheckout.objects.filter(pk=checkout.pk).update(
            step=CustomerTelegramCheckout.PLACED, order=created.order,
        )
    clear_cart(chat)
    if not created.replayed and not multicard_enabled():
        _notify_staff(created)
    return created.order, ''


def _start_payment(chat, checkout, order, language):
    try:
        started = start_order_payment(order.pk, _actor(chat), idempotency_key(checkout), 'web', language)
    except PaymentNotPayable as error:
        if error.code == 'already_paid':
            return order_state(order, language, PAID, notice=text(language, 'paid')), None
        return order_state(order, language, FAILED, notice=text(language, 'pay_unavailable')), None
    except (PaymentNotFound, MulticardNotConfigured, MulticardRejected, MulticardUnavailable):
        logger.warning('Customer bot payment start failed', extra={'order_id': order.pk})
        return order_state(order, language, FAILED, notice=text(language, 'pay_unavailable')), None
    return order_state(order, language, PENDING, url=started.checkout_url), started.checkout_url


def _pending_url(order):
    payment = order.payments.order_by('-pk').first()
    state = (payment.metadata.get('multicard') or {}) if payment else {}
    url = state.get('checkout_url')
    return url if isinstance(url, str) and url.startswith('https://') else None


def _actor(chat):
    user = chat.user
    if user is not None and user.is_active and user.deleted_at is None:
        return user
    return AnonymousUser()


def _notify_staff(created):
    try:
        notify_message(created.order, created.order.baskets.select_related('product'), created.coupon)
    except Exception:
        logger.exception('Order notification delivery failed', extra={'order_id': created.order.pk})
