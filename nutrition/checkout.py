from dataclasses import dataclass

from django.db.models import Q

from nutrition.models import DeliveryMethod, DeliverySlot, DeliveryZone, NutritionProfile
from store.models import Menu, Product


class CheckoutUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Quote:
    products: dict
    quantities: dict
    subtotal: int
    delivery_fee: int
    delivery_method_code: str
    delivery_zone_code: str
    delivery_slot: DeliverySlot | None

    @property
    def total(self):
        return self.subtotal + self.delivery_fee


def aggregate(items):
    quantities = {}
    for item in items:
        product_id = int(item['product'])
        quantities[product_id] = quantities.get(product_id, 0) + int(item['quantity'])
        if quantities[product_id] > 100:
            raise CheckoutUnavailable('Requested product quantity is unavailable')
    return quantities


def build_quote(command, lock=False):
    quantities = aggregate(command['baskets'])
    queryset = Product.objects.visible_on_storefront().filter(pk__in=quantities).select_related('nutrition_profile')
    if lock:
        queryset = queryset.select_for_update()
    products = {product.pk: product for product in queryset}
    if len(products) != len(quantities):
        raise CheckoutUnavailable('One or more products are unavailable')
    if any(products[pk].quantity < quantity for pk, quantity in quantities.items()):
        raise CheckoutUnavailable('Requested product quantity is unavailable')
    method_code = command.get('delivery_method_code') or _legacy_method(command.get('type'))
    zone_code = command.get('delivery_zone_code') or ''
    slot = _find_slot(command.get('delivery_slot_id'), zone_code, lock)
    delivery_fee = _delivery_fee(method_code, zone_code, command.get('type'), sum(
        _unit_price(products[pk]) * quantity for pk, quantity in quantities.items()
    ))
    _validate_product_delivery(products.values(), method_code, command.get('type'))
    return Quote(
        products=products,
        quantities=quantities,
        subtotal=sum(_unit_price(products[pk]) * quantity for pk, quantity in quantities.items()),
        delivery_fee=delivery_fee,
        delivery_method_code=method_code,
        delivery_zone_code=zone_code,
        delivery_slot=slot,
    )


def _unit_price(product):
    return int(product.price) - int(product.discounted_price)


def _legacy_method(order_type):
    return {'dcb': 'city-courier', 'dtu': 'uzbekistan-courier', 'pickup': 'pickup'}.get(order_type, '')


def _find_slot(slot_id, zone_code, lock):
    if not slot_id:
        return None
    queryset = DeliverySlot.objects.filter(pk=slot_id, zone__code=zone_code, is_active=True)
    if lock:
        queryset = queryset.select_for_update()
    slot = queryset.first()
    if not slot or not slot.has_capacity():
        raise CheckoutUnavailable('Delivery slot is unavailable')
    return slot


def _delivery_fee(method_code, zone_code, order_type, subtotal):
    if method_code:
        method = DeliveryMethod.objects.filter(code=method_code, is_active=True).first()
        if method:
            if subtotal < method.minimum_order:
                raise CheckoutUnavailable('Minimum order amount is not reached')
            if method.free_from is not None and subtotal >= method.free_from:
                return 0
            zone_fee = DeliveryZone.objects.filter(code=zone_code, is_active=True).values_list('fee', flat=True).first() or 0
            return int(method.base_fee) + int(zone_fee)
    if order_type == 'dtu':
        return int(Menu.objects.get(is_active=True).delivery_price)
    return 0


def _validate_product_delivery(products, method_code, order_type):
    for product in products:
        profile = getattr(product, 'nutrition_profile', None)
        if not profile or not profile.allowed_delivery_methods.exists():
            continue
        allowed = set(profile.allowed_delivery_methods.values_list('code', flat=True))
        if method_code and method_code not in allowed:
            raise CheckoutUnavailable('Selected delivery method is not available for one or more products')
