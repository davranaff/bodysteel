import json
import re
from datetime import datetime

from django.core.exceptions import RequestDataTooBig
from django.utils import timezone

from integration.errors import IntegrationProblem, invalid_request


PRODUCT_ID = re.compile(r'^[^\s,/?#]{1,255}$')
IDEMPOTENCY_KEY = re.compile(r'^[A-Za-z0-9._:-]{8,128}$')
MAXIMUM_JSON_BYTES = 64 * 1_024


def parse_product_list_request(request):
    _allow_query_parameters(request, {'cursor', 'limit', 'updatedAfter'})
    cursor = _optional_query_value(request, 'cursor')
    updated_after = _optional_query_value(request, 'updatedAfter')
    if cursor is not None and (not 1 <= len(cursor) <= 2_048 or _has_control(cursor)):
        raise invalid_request()
    parsed_updated_after = _parse_datetime(updated_after) if updated_after is not None else None
    limit = _parse_limit(_optional_query_value(request, 'limit'))
    return cursor, parsed_updated_after, limit


def parse_product_id(value):
    if not isinstance(value, str) or not PRODUCT_ID.fullmatch(value):
        raise invalid_request('The product ID is invalid')
    return value


def parse_inventory_ids(request):
    _allow_query_parameters(request, {'ids'})
    raw_ids = _required_query_value(request, 'ids').split(',')
    if not 1 <= len(raw_ids) <= 100 or any(not PRODUCT_ID.fullmatch(value) for value in raw_ids):
        raise invalid_request()
    return list(dict.fromkeys(raw_ids))


def require_idempotency_key(request):
    value = request.headers.get('Idempotency-Key')
    if not value or not IDEMPOTENCY_KEY.fullmatch(value):
        raise invalid_request('Idempotency-Key must contain 8 to 128 safe ASCII characters')
    return value


def parse_json_body(request):
    media_type = request.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
    if media_type != 'application/json':
        raise IntegrationProblem(415, 'Unsupported media type', 'Content-Type must be application/json')
    declared_length = request.headers.get('Content-Length')
    if declared_length and (not declared_length.isdigit() or int(declared_length) > MAXIMUM_JSON_BYTES):
        raise IntegrationProblem(413, 'Payload too large', 'The request body exceeds 64 KiB')
    try:
        body = request.body
    except RequestDataTooBig:
        raise IntegrationProblem(413, 'Payload too large', 'The request body exceeds 64 KiB') from None
    if not body or len(body) > MAXIMUM_JSON_BYTES:
        status = 413 if len(body) > MAXIMUM_JSON_BYTES else 400
        title = 'Payload too large' if status == 413 else 'Invalid JSON'
        raise IntegrationProblem(status, title, 'The request body must contain bounded valid JSON')
    try:
        return json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (UnicodeDecodeError, ValueError, TypeError):
        raise IntegrationProblem(400, 'Invalid JSON', 'The request body must contain valid JSON') from None


def _allow_query_parameters(request, allowed):
    if any(name not in allowed for name in request.GET):
        raise invalid_request()


def _optional_query_value(request, name):
    values = request.GET.getlist(name)
    if len(values) > 1:
        raise invalid_request()
    return values[0] if values else None


def _required_query_value(request, name):
    value = _optional_query_value(request, name)
    if value is None or value == '':
        raise invalid_request()
    return value


def _parse_limit(value):
    if value is None:
        return 50
    if not value.isdigit() or value.startswith('0') or not 1 <= int(value) <= 100:
        raise invalid_request()
    return int(value)


def _parse_datetime(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise invalid_request()
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, ValueError):
        raise invalid_request() from None
    if not timezone.is_aware(parsed):
        raise invalid_request()
    return parsed


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key')
        value[key] = item
    return value


def _invalid_constant(value):
    raise ValueError('Non-standard JSON constant')


def _has_control(value):
    return any(ord(character) <= 31 or ord(character) == 127 for character in value)
