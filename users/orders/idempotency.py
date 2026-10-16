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


LOCATION_FIELDS = ('address_latitude', 'address_longitude', 'address_label')


def request_fingerprint(command, actor):
    """Fingerprint of every input that changes the created order (v2)."""
    return _digest({
        **_legacy_canonical(command, actor),
        'version': 2,
        'deliveryMethodCode': command.get('delivery_method_code') or '',
        'deliveryZoneCode': command.get('delivery_zone_code') or '',
        'deliverySlotId': command.get('delivery_slot_id'),
        'customerNote': command.get('customer_note') or '',
        'addressLatitude': _coordinate(command.get('address_latitude')),
        'addressLongitude': _coordinate(command.get('address_longitude')),
        'addressLabel': command.get('address_label') or '',
    })


def legacy_request_fingerprint(command, actor):
    """Fingerprint stored before v2, or ``None`` when it cannot describe ``command``.

    Orders created before the delivery/location fields were fingerprinted keep
    replaying. A map location did not exist then, so a request carrying one can
    never be a replay of such an order.
    """
    if any(command.get(field) not in (None, '') for field in LOCATION_FIELDS):
        return None
    return _digest(_legacy_canonical(command, actor))


def find_replay(digest, fingerprint, legacy_fingerprint=None):
    order = Order.objects.select_related('coupon').filter(idempotency_digest=digest).first()
    if not order:
        return None
    stored = order.request_fingerprint or ''
    matches = secrets.compare_digest(stored, fingerprint)
    if legacy_fingerprint is not None:
        matches = secrets.compare_digest(stored, legacy_fingerprint) or matches
    if not matches:
        raise OrderIdempotencyConflict()
    return order


def _legacy_canonical(command, actor):
    return {
        'actorId': str(actor.pk) if getattr(actor, 'is_authenticated', False) else None,
        'fullName': command['full_name'],
        'phone': command['phone'],
        'address': command['address'],
        'type': command['type'],
        'baskets': _canonical_baskets(command['baskets']),
        'couponCode': command.get('coupon_code'),
        'integrationCartToken': command.get('integration_cart_token'),
    }


def _digest(canonical):
    encoded = json.dumps(canonical, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def _coordinate(value):
    return None if value is None else '{:.6f}'.format(value)


def _canonical_baskets(items):
    quantities = {}
    for item in items:
        product_id = int(item['product'])
        quantities[product_id] = quantities.get(product_id, 0) + int(item['quantity'])
    return [
        {'product': product_id, 'quantity': quantity}
        for product_id, quantity in sorted(quantities.items())
    ]
