import hashlib
import hmac


def sign_webhook(secret, timestamp, body):
    signing_input = '{}.{}'.format(timestamp, body).encode('utf-8')
    digest = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).hexdigest()
    return 'v1={}'.format(digest)
