"""Strict parsing of Multicard callback and webhook bodies.

Unknown extra fields are tolerated (Multicard may add fields), but every field
used for a decision is type- and size-checked before the signature is checked.
"""
import re


UUID = re.compile(r'^[0-9a-fA-F-]{36}$')
SIGN = re.compile(r'^[0-9a-fA-F]{32,40}$')
WEBHOOK_STATUSES = {'draft', 'progress', 'billing', 'success', 'error', 'revert', 'hold'}


def parse_callback(payload):
    if not isinstance(payload, dict):
        return None
    store_id = payload.get('store_id')
    if isinstance(store_id, bool) or not isinstance(store_id, (int, str)) or len(str(store_id)) > 64:
        return None
    common = _common(payload)
    if common is None:
        return None
    return {**common, 'store_id': store_id}


def parse_webhook(payload):
    if not isinstance(payload, dict):
        return None
    common = _common(payload)
    if common is None or payload.get('status') not in WEBHOOK_STATUSES:
        return None
    return {**common, 'status': payload['status']}


def _common(payload):
    uuid = payload.get('uuid')
    invoice_id = payload.get('invoice_id')
    amount = payload.get('amount')
    sign = payload.get('sign')
    if isinstance(amount, str) and amount.isdigit() and len(amount) <= 15 and amount[0] != '0':
        amount = int(amount)
    if not isinstance(uuid, str) or not UUID.fullmatch(uuid):
        return None
    if not isinstance(invoice_id, str) or not 1 <= len(invoice_id) <= 255:
        return None
    if isinstance(amount, bool) or not isinstance(amount, int) or not 0 < amount < 10 ** 15:
        return None
    if not isinstance(sign, str) or not SIGN.fullmatch(sign):
        return None
    return {'uuid': uuid, 'invoice_id': invoice_id, 'amount': amount, 'sign': sign}
