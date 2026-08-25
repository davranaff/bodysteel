from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import F

from integration.orders.attribution import attach_order_attribution
from nutrition.checkout import CheckoutUnavailable, build_quote
from payments.models import Payment
from store.models import Basket, Coupon, Order, Product
from users.models import User
from users.orders.errors import OrderUnavailable
from users.orders.idempotency import find_replay, idempotency_digest, request_fingerprint


@dataclass(frozen=True)
class CreatedOrder:
    order: Order
    coupon: Coupon | None
    replayed: bool


def create_order(command, actor, idempotency_key):
    digest = idempotency_digest(idempotency_key)
    fingerprint = request_fingerprint(command, actor)
    existing = find_replay(digest, fingerprint)
    if existing:
        return CreatedOrder(order=existing, coupon=existing.coupon, replayed=True)

    try:
        return _create_order(command, actor, digest, fingerprint)
    except IntegrityError:
        existing = find_replay(digest, fingerprint)
        if existing:
            return CreatedOrder(order=existing, coupon=existing.coupon, replayed=True)
        raise


def _create_order(command, actor, digest, fingerprint):
    with transaction.atomic():
        try:
            quote = build_quote(command, lock=True)
        except CheckoutUnavailable as error:
            raise OrderUnavailable(str(error)) from error
        quantities = quote.quantities
        products = quote.products
        subtotal = quote.subtotal
        user, subtotal = _apply_bonus(actor, subtotal)
        coupon, subtotal = _apply_coupon(command.get('coupon_code'), subtotal)
        total = max(0, subtotal) + quote.delivery_fee
        order = Order.objects.create(
            user=user,
            total_price=total,
            subtotal_price=quote.subtotal,
            discount_price=max(0, quote.subtotal - subtotal),
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


def _aggregate_quantities(items):
    quantities = {}
    for item in items:
        product_id = item['product']
        quantities[product_id] = quantities.get(product_id, 0) + item['quantity']
        if quantities[product_id] > 100:
            raise OrderUnavailable('Requested product quantity is unavailable')
    return quantities


def _apply_bonus(actor, subtotal):
    if not getattr(actor, 'is_authenticated', False):
        return None, subtotal
    user = User.objects.select_for_update().get(pk=actor.pk)
    if user.bonus_used:
        return user, subtotal
    menu = Menu.objects.get(is_active=True)
    user.bonus_used = True
    user.save(update_fields=('bonus_used',))
    return user, max(0, subtotal - int(menu.bonus))


def _apply_coupon(code, subtotal):
    if not code:
        return None, subtotal
    coupon = Coupon.objects.select_for_update().filter(code=code, is_active=True).first()
    if not coupon or not coupon.can_use():
        return None, subtotal
    discount = int(subtotal * (coupon.discount_percent / 100))
    coupon.used_count += 1
    coupon.save(update_fields=('used_count',))
    return coupon, max(0, subtotal - discount)


def _persist_baskets(order, user, products, quantities):
    for product_id, quantity in quantities.items():
        product = products[product_id]
        Basket.objects.create(
            order=order,
            user=user,
            product=product,
            quantity=quantity,
        )


def _unit_price(product):
    return int(product.price) - int(product.discounted_price)
