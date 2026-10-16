from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import F

from integration.orders.attribution import attach_order_attribution
from nutrition.checkout import CheckoutUnavailable, build_quote
from payments.models import Payment
from store.commerce.discounts import price_discounts
from store.models import Basket, Coupon, Order
from users.orders.errors import OrderUnavailable
from users.orders.idempotency import (
    find_replay,
    idempotency_digest,
    legacy_request_fingerprint,
    request_fingerprint,
)


@dataclass(frozen=True)
class CreatedOrder:
    order: Order
    coupon: Coupon | None
    replayed: bool


def create_order(command, actor, idempotency_key):
    digest = idempotency_digest(idempotency_key)
    fingerprint = request_fingerprint(command, actor)
    legacy_fingerprint = legacy_request_fingerprint(command, actor)
    existing = find_replay(digest, fingerprint, legacy_fingerprint)
    if existing:
        return CreatedOrder(order=existing, coupon=existing.coupon, replayed=True)

    try:
        return _create_order(command, actor, digest, fingerprint)
    except IntegrityError:
        existing = find_replay(digest, fingerprint, legacy_fingerprint)
        if existing:
            return CreatedOrder(order=existing, coupon=existing.coupon, replayed=True)
        raise


def _create_order(command, actor, digest, fingerprint):
    with transaction.atomic():
        try:
            quote = build_quote(command, lock=True)
        except CheckoutUnavailable as error:
            raise OrderUnavailable(str(error), error.code) from error
        quantities = quote.quantities
        products = quote.products
        pricing = price_discounts(quote.subtotal, actor, command.get('coupon_code'), lock=True)
        _spend_discounts(pricing)
        user = pricing.user
        coupon = pricing.coupon
        total = pricing.discounted_subtotal + quote.delivery_fee
        order = Order.objects.create(
            user=user,
            total_price=total,
            subtotal_price=quote.subtotal,
            discount_price=pricing.discount,
            delivery_fee=quote.delivery_fee,
            delivery_method_code=quote.delivery_method_code,
            delivery_zone_code=quote.delivery_zone_code,
            delivery_slot_date=quote.delivery_slot.delivery_date if quote.delivery_slot else None,
            delivery_slot_label=(
                '{}-{}'.format(quote.delivery_slot.starts_at.strftime('%H:%M'), quote.delivery_slot.ends_at.strftime('%H:%M'))
                if quote.delivery_slot else ''
            ),
            customer_note=command.get('customer_note', ''),
            type=command['type'],
            full_name=command['full_name'],
            phone=command['phone'],
            address=command['address'],
            address_latitude=command.get('address_latitude'),
            address_longitude=command.get('address_longitude'),
            address_label=command.get('address_label') or '',
            coupon=coupon,
            status='moderation',
            idempotency_digest=digest,
            request_fingerprint=fingerprint,
        )
        _persist_baskets(order, user, products, quantities)
        if quote.delivery_slot:
            quote.delivery_slot.reserved_count = F('reserved_count') + 1
            quote.delivery_slot.save(update_fields=('reserved_count',))
        Payment.objects.create(
            order=order,
            provider='manual',
            amount=total,
            currency='UZS',
            status=Payment.CREATED,
            idempotency_digest=digest,
            metadata={'purpose': 'physical_order', 'order_id': order.pk},
        )
        attach_order_attribution(
            order,
            command.get('integration_cart_token'),
            quantities,
        )
        return CreatedOrder(order=order, coupon=coupon, replayed=False)


def _spend_discounts(pricing):
    # The rows were locked by price_discounts(lock=True) in this transaction.
    if pricing.bonus_eligible:
        pricing.user.bonus_used = True
        pricing.user.save(update_fields=('bonus_used',))
    if pricing.coupon is not None:
        pricing.coupon.used_count += 1
        pricing.coupon.save(update_fields=('used_count',))


def _persist_baskets(order, user, products, quantities):
    for product_id, quantity in quantities.items():
        product = products[product_id]
        Basket.objects.create(
            order=order,
            user=user,
            product=product,
            quantity=quantity,
        )
