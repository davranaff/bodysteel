from dataclasses import dataclass

from django.db import IntegrityError, transaction

from integration.orders.attribution import attach_order_attribution
from store.models import Basket, Coupon, Menu, Order, Product
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
        quantities = _aggregate_quantities(command['baskets'])
        products = _lock_products(quantities)
        subtotal = sum(_unit_price(products[product_id]) * quantity for product_id, quantity in quantities.items())
        user, subtotal = _apply_bonus(actor, subtotal)
        coupon, subtotal = _apply_coupon(command.get('coupon_code'), subtotal)
        order = Order.objects.create(
            user=user,
            total_price=max(0, subtotal),
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


def _lock_products(quantities):
    products = {
        product.pk: product
        for product in Product.objects.visible_on_storefront().select_for_update().filter(pk__in=quantities).order_by('pk')
    }
    if len(products) != len(quantities):
        raise OrderUnavailable('One or more products are unavailable')
    if any(products[product_id].quantity < quantity for product_id, quantity in quantities.items()):
        raise OrderUnavailable('Requested product quantity is unavailable')
    return products


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
