import base64
import hashlib
import hmac
import secrets
from urllib.parse import urlencode

from customer_telegram.configuration import require_configuration


PREFIXES = {
    'registration_otp': 'r',
    'password_reset_otp': 'p',
    'account_link': 'a',
}
MAXIMUM_BIGINT = (1 << 63) - 1


def valid_telegram_id(value):
    return type(value) is int and 0 < value <= MAXIMUM_BIGINT


def valid_update_id(value):
    return type(value) is int and 0 <= value <= MAXIMUM_BIGINT


def new_start_parameter(purpose):
    prefix = PREFIXES[purpose]
    random_value = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('=')
    return '{}_{}'.format(prefix, random_value)


def link_digest(start_parameter):
    configuration = require_configuration()
    return hmac.new(
        configuration.link_hash_key,
        start_parameter.encode('ascii'),
        hashlib.sha256,
    ).hexdigest()


def build_deep_link(start_parameter):
    configuration = require_configuration()
    query = urlencode({'start': start_parameter})
    return 'https://t.me/{}?{}'.format(configuration.username, query)
