"""Multicard callback signatures (docs.multicard.uz, "Callback").

* Success callback: ``md5("{store_id}{invoice_id}{amount}{secret}")``.
* Status webhooks: the docs give two forms, ``md5("{uuid}{amount}{secret}")``
  and ``sha1("{uuid}{invoice_id}{amount}{secret}")``; both require the secret,
  so either is accepted. All comparisons are constant-time.
"""
import hashlib
import hmac
import re


SIGNATURE = re.compile(r'^[0-9a-fA-F]{32}([0-9a-fA-F]{8})?$')


def callback_signature(store_id, invoice_id, amount, secret):
    return _md5('{}{}{}{}'.format(store_id, invoice_id, amount, secret))


def verify_callback_signature(payload, secret):
    expected = callback_signature(payload['store_id'], payload['invoice_id'], payload['amount'], secret)
    return _matches(payload.get('sign'), [expected])


def webhook_signatures(uuid, invoice_id, amount, secret):
    return [
        _md5('{}{}{}'.format(uuid, amount, secret)),
        hashlib.sha1('{}{}{}{}'.format(uuid, invoice_id, amount, secret).encode('utf-8')).hexdigest(),
    ]


def verify_webhook_signature(payload, secret):
    expected = webhook_signatures(payload['uuid'], payload['invoice_id'], payload['amount'], secret)
    return _matches(payload.get('sign'), expected)


def _md5(value):
    return hashlib.md5(value.encode('utf-8'), usedforsecurity=False).hexdigest()


def _matches(signature, candidates):
    if not isinstance(signature, str) or not SIGNATURE.fullmatch(signature):
        return False
    signature = signature.lower().encode('ascii')
    matched = False
    for candidate in candidates:
        matched |= hmac.compare_digest(signature, candidate.encode('ascii'))
    return matched
