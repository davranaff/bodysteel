"""Multicard payment gateway settings.

Every value comes from the environment so switching from the sandbox to
production is only an environment change. Credentials are server-only.
"""
import os


def _flag(name):
    return os.getenv(name, '').strip().lower() in {'1', 'true', 'yes'}


MULTICARD_ENABLED = _flag('MULTICARD_ENABLED')
# Sandbox by default; production is https://mesh.multicard.uz
MULTICARD_BASE_URL = os.getenv('MULTICARD_BASE_URL', 'https://dev-mesh.multicard.uz').strip()
MULTICARD_APPLICATION_ID = os.getenv('MULTICARD_APPLICATION_ID', '').strip()
MULTICARD_SECRET = os.getenv('MULTICARD_SECRET', '').strip()
MULTICARD_STORE_ID = os.getenv('MULTICARD_STORE_ID', '').strip()
# Public HTTPS URL of PaymentMulticardCallbackAPIView, reachable by Multicard.
MULTICARD_CALLBACK_URL = os.getenv('MULTICARD_CALLBACK_URL', '').strip()
# Where Multicard sends the shopper back. The signed status token is appended.
MULTICARD_WEB_RETURN_URL = os.getenv(
    'MULTICARD_WEB_RETURN_URL', 'https://bodysteel.uz/payment/multicard',
).strip()
MULTICARD_APP_RETURN_URL = os.getenv(
    'MULTICARD_APP_RETURN_URL', 'https://bodysteel.uz/app/payment',
).strip()
# Fiscal receipt (OFD) classification. Product.ikpu_code/package_code win;
# these are fallbacks for products that do not have their own codes yet.
MULTICARD_DEFAULT_IKPU = os.getenv('MULTICARD_DEFAULT_IKPU', '').strip()
MULTICARD_DEFAULT_PACKAGE_CODE = os.getenv('MULTICARD_DEFAULT_PACKAGE_CODE', '').strip()
MULTICARD_DELIVERY_IKPU = os.getenv('MULTICARD_DELIVERY_IKPU', '').strip()
MULTICARD_DELIVERY_PACKAGE_CODE = os.getenv('MULTICARD_DELIVERY_PACKAGE_CODE', '').strip()
MULTICARD_VAT_PERCENT = os.getenv('MULTICARD_VAT_PERCENT', '').strip()
MULTICARD_TIN = os.getenv('MULTICARD_TIN', '').strip()
MULTICARD_INVOICE_TTL_SECONDS = os.getenv('MULTICARD_INVOICE_TTL_SECONDS', '1800').strip()
MULTICARD_TIMEOUT_SECONDS = os.getenv('MULTICARD_TIMEOUT_SECONDS', '10').strip()
# Optional exact-IP allowlist for callbacks (Multicard sends from 195.158.26.90).
# Empty means "signature only", which is safe behind proxies that rewrite IPs.
MULTICARD_CALLBACK_ALLOWED_IPS = tuple(
    value.strip() for value in os.getenv('MULTICARD_CALLBACK_ALLOWED_IPS', '').split(',') if value.strip()
)
