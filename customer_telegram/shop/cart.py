"""The chat's cart: product id to quantity, re-checked against live stock on every change."""
from django.db import transaction

from customer_telegram.models import CustomerTelegramCart
from store.models import Product


MAXIMUM_LINES = 20
MAXIMUM_QUANTITY = 100


def cart_items(chat):
    cart = CustomerTelegramCart.objects.filter(chat=chat).first()
    return _clean(cart.items if cart else {})


def cart_count(chat):
    return sum(cart_items(chat).values())


def change_quantity(chat, product_id, delta):
    """Add ``delta`` (+1 or -1) of a product. Returns '' or the notice key to show."""
    with transaction.atomic():
        cart, _ = CustomerTelegramCart.objects.select_for_update().get_or_create(chat=chat)
        items = _clean(cart.items)
        current = items.get(product_id, 0)
        if delta > 0:
            product = Product.objects.visible_on_storefront().filter(pk=product_id).first()
            if product is None or product.quantity <= 0:
                return 'gone'
            if product_id not in items and len(items) >= MAXIMUM_LINES:
                return 'cart_full'
            if current + delta > min(product.quantity, MAXIMUM_QUANTITY):
                return 'limit'
        quantity = max(0, current + delta)
        if quantity:
            items[product_id] = quantity
        else:
            items.pop(product_id, None)
        cart.items = {str(key): value for key, value in items.items()}
        cart.save(update_fields=('items', 'updated_at'))
    return 'added' if delta > 0 and not current else ''


def clear_cart(chat):
    CustomerTelegramCart.objects.filter(chat=chat).update(items={})


def order_lines(chat):
    """Cart lines the order command accepts, for products that are still on sale."""
    items = cart_items(chat)
    visible = set(Product.objects.visible_on_storefront().filter(pk__in=items).values_list('pk', flat=True))
    return [{'product': pk, 'quantity': quantity} for pk, quantity in items.items() if pk in visible]


def _clean(raw):
    items = {}
    if not isinstance(raw, dict):
        return items
    for key, value in raw.items():
        if str(key).isdigit() and isinstance(value, int) and 0 < value <= MAXIMUM_QUANTITY:
            items[int(key)] = value
    return dict(list(items.items())[:MAXIMUM_LINES])
