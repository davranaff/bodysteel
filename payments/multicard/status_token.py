"""Tamper-evident, expiring capability for reading one payment's status.

It is embedded in the Multicard return URL so the return page (web or app)
can show paid/failed without a session. It reveals only the payment state.
"""
import re

from django.core import signing


SALT = 'payments.multicard.status.v1'
MAX_AGE_SECONDS = 30 * 24 * 3600
TOKEN = re.compile(r'^[A-Za-z0-9_:-]{16,200}$')


def issue_status_token(payment_id):
    return signing.dumps({'p': int(payment_id)}, salt=SALT, compress=False)


def read_status_token(token):
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        return None
    try:
        value = signing.loads(token, salt=SALT, max_age=MAX_AGE_SECONDS)
    except signing.BadSignature:
        return None
    payment_id = value.get('p') if isinstance(value, dict) else None
    return payment_id if isinstance(payment_id, int) and payment_id > 0 else None
