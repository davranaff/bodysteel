from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import logging

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from integration.regos.config import RegosSyncError, clean, endpoint, normalise, timeout
from store.models import Product


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InventoryRecord:
    item_id: int | None
    code: str
    articul: str
    name: str
    quantity: int


@dataclass
class SyncResult:
    received: int = 0
    updated: int = 0
    linked: int = 0
    unmatched: int = 0
    invalid: int = 0


def sync_from_regos():
    """Read the full selected REGOS inventory and apply it transactionally."""
    api_endpoint = endpoint()
    api_timeout = timeout()
    offset = 0
    records = []
    session = requests.Session()
    while True:
        payload = {'limit': 200, 'offset': offset}
        if settings.REGOS_STOCK_IDS:
            payload['filters'] = [{
                'Field': 'stock_id',
                'Operator': 'In',
                'Value': ','.join(settings.REGOS_STOCK_IDS),
            }]
        try:
            response = session.post(
                '{}/item/getext'.format(api_endpoint),
                json=payload,
                headers={'Content-Type': 'application/json;charset=utf-8'},
                timeout=api_timeout,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as error:
            raise RegosSyncError('REGOS inventory request failed') from error
        if not isinstance(body, dict) or body.get('ok') is not True:
            raise RegosSyncError('REGOS returned an inventory business error')
        page = body.get('result')
        if not isinstance(page, list):
            raise RegosSyncError('REGOS returned an invalid inventory response')
        records.extend(record_from_regos(value) for value in page)
        next_offset = body.get('next_offset')
        total = body.get('total')
        if not isinstance(next_offset, int) or next_offset <= offset or (isinstance(total, int) and next_offset >= total):
            break
        offset = next_offset
    return apply_records(records, source='REGOS API')


def record_from_regos(value):
    if not isinstance(value, dict):
        return None
    item = value.get('item') if isinstance(value.get('item'), dict) else value
    quantity = value.get('quantity') if isinstance(value.get('quantity'), dict) else {}
    return _record(
        item_id=item.get('id'),
        code=item.get('code'),
        articul=item.get('articul'),
        name=item.get('name'),
        quantity=quantity.get('allowed', quantity.get('common')),
    )


def records_from_to_server(params):
    """Accept the documented JSON-RPC To Server payload and common field casing."""
    entries = _find_entry_lists(params)
    return [_record_from_to_server(value) for value in entries]


def apply_records(records, source):
    result = SyncResult()
    for record in records:
        result.received += 1
        if record is None:
            result.invalid += 1
            continue
        with transaction.atomic():
            product = _find_product(record)
            if product is None:
                result.unmatched += 1
                continue
            changed = []
            linked = False
            if record.item_id is not None and product.regos_item_id != record.item_id:
                product.regos_item_id = record.item_id
                changed.append('regos_item_id')
                linked = True
            if record.code and product.regos_item_code != record.code:
                product.regos_item_code = record.code
                changed.append('regos_item_code')
            if record.articul and product.regos_item_articul != record.articul:
                product.regos_item_articul = record.articul
                changed.append('regos_item_articul')
            if product.quantity != record.quantity:
                product.quantity = record.quantity
                changed.extend(('quantity', 'updated_at'))
            if changed:
                product.save(update_fields=tuple(dict.fromkeys(changed)))
                result.updated += 1
            if linked:
                result.linked += 1
    logger.info(
        '%s inventory sync finished: received=%s updated=%s linked=%s unmatched=%s invalid=%s',
        source, result.received, result.updated, result.linked, result.unmatched, result.invalid,
    )
    return result


def _find_product(record):
    if record.item_id is not None:
        product = Product.objects.select_for_update().filter(regos_item_id=record.item_id).first()
        if product:
            return product
    if record.code:
        product = Product.objects.select_for_update().filter(regos_item_code=record.code).first()
        if product:
            return product
    if record.articul:
        product = Product.objects.select_for_update().filter(regos_item_articul=record.articul).first()
        if product:
            return product
    if not record.name:
        return None
    candidates = [
        product for product in Product.objects.select_for_update().filter(
            Q(name_ru__iexact=record.name) | Q(name_uz__iexact=record.name)
        )
        if normalise(product.name_ru) == normalise(record.name)
        or normalise(product.name_uz) == normalise(record.name)
    ]
    return candidates[0] if len(candidates) == 1 else None


def _record_from_to_server(value):
    if not isinstance(value, dict):
        return None
    quantity = _to_server_quantity(value)
    return _record(
        item_id=_value(value, 'id', 'item_id', 'itemId'),
        code=_value(value, 'code', 'item_code', 'itemCode'),
        articul=_value(value, 'articul', 'article', 'item_articul', 'itemArticul'),
        name=_value(value, 'name', 'item_name', 'itemName', 'fullname'),
        quantity=quantity,
    )


def _record(item_id, code, articul, name, quantity):
    try:
        item_id = int(item_id) if item_id not in (None, '') else None
        if item_id is not None and item_id < 1:
            return None
        parsed_quantity = Decimal(str(quantity))
        if parsed_quantity < 0 or parsed_quantity != parsed_quantity.to_integral_value():
            return None
    except (InvalidOperation, TypeError, ValueError):
        return None
    return InventoryRecord(
        item_id=item_id,
        code=clean(code, 100),
        articul=clean(articul, 255),
        name=clean(name, 500),
        quantity=int(parsed_quantity),
    )


def _find_entry_lists(value):
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return []
    for key in ('items', 'data', 'nomenclature', 'products', 'result'):
        candidate = value.get(key)
        if isinstance(candidate, list):
            return candidate
    for key in ('params', 'payload'):
        nested = value.get(key)
        if isinstance(nested, (dict, list)):
            entries = _find_entry_lists(nested)
            if entries:
                return entries
    return []


def _to_server_quantity(value):
    direct = _value(value, 'allowed', 'available_quantity', 'availableQuantity')
    if direct is not None:
        return direct
    quantities = _value(value, 'quantity', 'quantities', 'stock_quantities', 'stockQuantities', 'stocks')
    if isinstance(quantities, list):
        allowed = [_value(entry, 'allowed', 'quantity', 'common') for entry in quantities if isinstance(entry, dict)]
        try:
            return sum(Decimal(str(entry)) for entry in allowed if entry is not None)
        except (InvalidOperation, TypeError, ValueError):
            return None
    return quantities


def _value(value, *keys):
    for key in keys:
        if key in value:
            return value[key]
    return None
