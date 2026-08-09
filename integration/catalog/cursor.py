from datetime import datetime, timezone as datetime_timezone

from django.core import signing
from django.utils import timezone

from integration.errors import invalid_request


CURSOR_SALT = 'savdoq.integration.catalog.cursor.v1'


def encode_cursor(payload):
    return signing.Signer(salt=CURSOR_SALT).sign_object(payload, compress=True)


def decode_cursor(value, updated_after):
    try:
        payload = signing.Signer(salt=CURSOR_SALT).unsign_object(value)
    except (signing.BadSignature, TypeError, ValueError):
        raise invalid_request('The catalog cursor is invalid') from None
    if not _valid_payload(payload, updated_after):
        raise invalid_request('The catalog cursor is invalid')
    return {
        **payload,
        'snapshotAt': _parse_datetime(payload['snapshotAt']),
        'lastUpdatedAt': _parse_datetime(payload['lastUpdatedAt']) if payload['lastUpdatedAt'] else None,
    }


def _valid_payload(payload, updated_after):
    if not isinstance(payload, dict) or set(payload) != {
        'version',
        'mode',
        'updatedAfter',
        'snapshotAt',
        'lastId',
        'lastUpdatedAt',
    }:
        return False
    expected_boundary = isoformat_utc(updated_after) if updated_after else None
    return (
        payload['version'] == 1
        and payload['mode'] in {'full', 'delta'}
        and payload['updatedAfter'] == expected_boundary
        and payload['mode'] == ('delta' if updated_after else 'full')
        and isinstance(payload['lastId'], int)
        and payload['lastId'] > 0
        and isinstance(payload['snapshotAt'], str)
        and (payload['lastUpdatedAt'] is None or isinstance(payload['lastUpdatedAt'], str))
        and _dates_are_valid(payload)
    )


def _dates_are_valid(payload):
    try:
        snapshot = _parse_datetime(payload['snapshotAt'])
        last_updated = _parse_datetime(payload['lastUpdatedAt']) if payload['lastUpdatedAt'] else None
    except ValueError:
        return False
    return (payload['mode'] == 'full' and last_updated is None) or (
        payload['mode'] == 'delta' and last_updated is not None and last_updated <= snapshot
    )


def _parse_datetime(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not timezone.is_aware(parsed):
        raise ValueError('Cursor timestamp must be timezone-aware')
    return parsed


def isoformat_utc(value):
    return value.astimezone(datetime_timezone.utc).isoformat().replace('+00:00', 'Z')
