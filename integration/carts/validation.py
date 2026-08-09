import re

from integration.errors import invalid_request


PRODUCT_ID = re.compile(r'^[^\s,/?#]{1,255}$')


def validate_cart_payload(value):
    if not isinstance(value, dict) or set(value) != {'items', 'attribution'}:
        raise invalid_request('The cart request is invalid')
    items = _items(value['items'])
    attribution = _attribution(value['attribution'])
    return {'items': items, 'attribution': attribution}


def _items(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 20:
        raise invalid_request('The cart request is invalid')
    quantities = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != {'productId', 'quantity'}:
            raise invalid_request('The cart request is invalid')
        product_id = item['productId']
        quantity = item['quantity']
        if not isinstance(product_id, str) or not PRODUCT_ID.fullmatch(product_id) or not product_id.isdigit():
            raise invalid_request('The cart request is invalid')
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 100:
            raise invalid_request('The cart request is invalid')
        quantities[product_id] = quantities.get(product_id, 0) + quantity
        if quantities[product_id] > 100:
            raise invalid_request('The cart request is invalid')
    return [
        {'productId': product_id, 'quantity': quantity}
        for product_id, quantity in sorted(quantities.items(), key=lambda item: int(item[0]))
    ]


def _attribution(value):
    if not isinstance(value, dict) or set(value) != {'aiSessionId', 'channel'}:
        raise invalid_request('The cart request is invalid')
    session_id = value['aiSessionId']
    channel = value['channel']
    if (
        not isinstance(session_id, str)
        or not 1 <= len(session_id) <= 200
        or _has_control(session_id)
        or channel not in {'web', 'telegram'}
    ):
        raise invalid_request('The cart request is invalid')
    return {'aiSessionId': session_id, 'channel': channel}


def _has_control(value):
    return any(ord(character) <= 31 or ord(character) == 127 for character in value)
