from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import logging

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify

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
    price: int | None = None


@dataclass
class SyncResult:
    received: int = 0
    updated: int = 0
    linked: int = 0
    unmatched: int = 0
    invalid: int = 0
    created: int = 0
    archived: int = 0


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


def sync_item_from_regos(item_id, *, create_draft=False):
    """Refresh one REGOS item, creating only an explicitly announced draft."""
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return SyncResult(received=1, invalid=1)
    if item_id < 1:
        return SyncResult(received=1, invalid=1)
    try:
        response = requests.post(
            '{}/item/getext'.format(endpoint()),
            json={
                'limit': 1,
                'offset': 0,
                'filters': [{'Field': 'id', 'Operator': 'In', 'Value': str(item_id)}],
            },
            headers={'Content-Type': 'application/json;charset=utf-8'},
            timeout=timeout(),
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as error:
        raise RegosSyncError('REGOS item request failed') from error
    page = body.get('result') if isinstance(body, dict) and body.get('ok') is True else None
    if not isinstance(page, list):
        raise RegosSyncError('REGOS returned an invalid item response')
    records = [record_from_regos(value) for value in page]
    records = [record for record in records if record and record.item_id == item_id]
    if not records:
        return SyncResult(received=1, unmatched=1)
    return apply_records(
        records,
        source='REGOS item event',
        create_drafts=create_draft,
        update_catalog=True,
    )


def archive_regos_item(item_id):
    """Hide a deleted REGOS item without deleting the audit trail or images."""
    result = SyncResult(received=1)
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        result.invalid = 1
        return result
    if item_id < 1:
        result.invalid = 1
        return result
    with transaction.atomic():
        product = Product.objects.select_for_update().filter(regos_item_id=item_id).first()
        if product is None:
            result.unmatched = 1
            return result
        changed = []
        if product.regos_catalog_status != Product.REGOS_STATUS_ARCHIVED:
            product.regos_catalog_status = Product.REGOS_STATUS_ARCHIVED
            changed.append('regos_catalog_status')
        if product.quantity:
            product.quantity = 0
            changed.append('quantity')
        if changed:
            changed.append('updated_at')
            product.save(update_fields=tuple(changed))
            result.updated = 1
        result.archived = 1
    logger.info('REGOS item archived: item_id=%s archived=%s', item_id, result.archived)
    return result


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
        price=_value(item, 'price', 'sale_price', 'salePrice') or _value(value, 'price', 'sale_price', 'salePrice'),
    )


def records_from_to_server(params):
    """Accept the documented JSON-RPC To Server payload and common field casing."""
    entries = _find_entry_lists(params)
    return [_record_from_to_server(value) for value in entries]


def apply_records(records, source, *, create_drafts=False, update_catalog=False):
    result = SyncResult()
    for record in records:
        result.received += 1
        if record is None:
            result.invalid += 1
            continue
        with transaction.atomic():
            product = _find_product(record)
            if product is None:
                if create_drafts:
                    product = _create_draft(record)
                    if product is not None:
                        result.created += 1
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
            if update_catalog and product.regos_catalog_status in {
                Product.REGOS_STATUS_DRAFT,
                Product.REGOS_STATUS_PUBLISHED,
            }:
                if record.price is not None and product.price != record.price:
                    product.price = record.price
                    changed.append('price')
                # Names for published cards are editorial content.  Drafts can
                # safely follow REGOS until an administrator publishes them.
                if product.regos_catalog_status == Product.REGOS_STATUS_DRAFT and record.name:
                    has_name_collision = Product.objects.exclude(pk=product.pk).filter(
                        Q(name_ru__iexact=record.name) | Q(name_uz__iexact=record.name)
                    ).exists()
                    if not has_name_collision:
                        if product.name_ru != record.name:
                            product.name_ru = record.name
                            changed.append('name_ru')
                        if product.name_uz != record.name:
                            product.name_uz = record.name
                            changed.append('name_uz')
            if changed:
                if 'updated_at' not in changed:
                    changed.append('updated_at')
                product.save(update_fields=tuple(dict.fromkeys(changed)))
                result.updated += 1
            if linked:
                result.linked += 1
    logger.info(
        '%s inventory sync finished: received=%s updated=%s created=%s linked=%s unmatched=%s invalid=%s',
        source, result.received, result.updated, result.created, result.linked, result.unmatched, result.invalid,
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


def _create_draft(record):
    if record.item_id is None or not record.name:
        return None
    name = record.name[:500]
    # Product names are unique in this project.  A name collision is handled
    # by _find_product above; never overwrite a different local card here.
    if Product.objects.filter(Q(name_ru__iexact=name) | Q(name_uz__iexact=name)).exists():
        return None
    return Product.objects.create(
        regos_item_id=record.item_id,
        regos_item_code=record.code,
        regos_item_articul=record.articul,
        regos_catalog_status=Product.REGOS_STATUS_DRAFT,
        name_ru=name,
        name_uz=name,
        price=record.price or 0,
        quantity=record.quantity,
        slug=_draft_slug(record.item_id, name),
        country_ru='REGOS',
        country_uz='REGOS',
    )


def _draft_slug(item_id, name):
    root = 'regos-{}-{}'.format(item_id, slugify(name) or 'item')[:255]
    candidate = root[:255]
    suffix = 2
    while Product.objects.filter(slug=candidate).exists():
        ending = '-{}'.format(suffix)
        candidate = '{}{}'.format(root[:255 - len(ending)], ending)
        suffix += 1
    return candidate


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
        price=_value(value, 'price', 'sale_price', 'salePrice'),
    )


def _record(item_id, code, articul, name, quantity, price=None):
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
        price=_price(price),
    )


def _price(value):
    if value in (None, ''):
        return None
    try:
        parsed = Decimal(str(value))
        if parsed < 0 or parsed != parsed.to_integral_value():
            return None
        return int(parsed)
    except (InvalidOperation, TypeError, ValueError):
        return None


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
