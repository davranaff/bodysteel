import hashlib
import json
import re
import secrets

from store.models import Order
from users.orders.errors import InvalidOrderIdempotencyKey, OrderIdempotencyConflict


IDEMPOTENCY_KEY = re.compile(r'^[A-Za-z0-9._:-]{16,128}$')


def parse_idempotency_key(value):
    if not isinstance(value, str) or not IDEMPOTENCY_KEY.fullmatch(value):
        raise InvalidOrderIdempotencyKey()
    return value


def idempotency_digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def request_fingerprint(command, actor):
    canonical = json.dumps(
        {
            'actorId': str(actor.pk) if getattr(actor, 'is_authenticated', False) else None,
            'fullName': command['full_name'],
            'phone': command['phone'],
            'address': command['address'],
            'type': command['type'],
            'baskets': _canonical_baskets(command['baskets']),
            'couponCode': command.get('coupon_code'),
            'integrationCartToken': command.get('integration_cart_token'),
        },
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def find_replay(digest, fingerprint):
    order = Order.objects.select_related('coupon').filter(idempotency_digest=digest).first()
    if not order:
        return None
    if not secrets.compare_digest(order.request_fingerprint or '', fingerprint):
        raise OrderIdempotencyConflict()
    return order


def _canonical_baskets(items):
    quantities = {}
    for item in items:
        product_id = int(item['product'])
        quantities[product_id] = quantities.get(product_id, 0) + int(item['quantity'])
    return [
        {'product': product_id, 'quantity': quantity}
        for product_id, quantity in sorted(quantities.items())
    ]
