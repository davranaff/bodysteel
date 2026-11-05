"""Shared test fixtures for the Multicard integration (imported by test modules only)."""
import hashlib

from payments.models import Payment
from payments.multicard.client import Invoice
from store.models import Basket, Order, Product


SECRET = 'test-multicard-secret-value'
INVOICE_UUID = '1efd8630-b886-11f0-af7c-005056b4367d'
PAYMENT_UUID = 'e60d8ebc-b9fe-11ef-b159-005056b4367d'
ORDER_KEY = 'checkout-multicard-key-0001'
MULTICARD_SETTINGS = {
    'MULTICARD_ENABLED': True,
    'MULTICARD_BASE_URL': 'https://dev-mesh.multicard.test',
    'MULTICARD_APPLICATION_ID': 'rhmt_test',
    'MULTICARD_SECRET': SECRET,
    'MULTICARD_STORE_ID': '6',
    'MULTICARD_CALLBACK_URL': 'https://api.example.test/api/v1/payments/multicard/callback/',
    'MULTICARD_WEB_RETURN_URL': 'https://shop.example.test/payment/multicard',
    'MULTICARD_APP_RETURN_URL': 'https://shop.example.test/app/payment',
    'MULTICARD_DEFAULT_IKPU': '06401004002000000',
    'MULTICARD_DEFAULT_PACKAGE_CODE': '1506113',
    'MULTICARD_DELIVERY_IKPU': '10112006002000000',
    'MULTICARD_DELIVERY_PACKAGE_CODE': '1209885',
    'MULTICARD_VAT_PERCENT': '',
    'MULTICARD_TIN': '',
    'MULTICARD_INVOICE_TTL_SECONDS': '1800',
    'MULTICARD_TIMEOUT_SECONDS': '5',
    'MULTICARD_CALLBACK_ALLOWED_IPS': (),
}


def make_order(user=None, quantity=2, unit_price=100_000, discount=0, delivery_fee=0, slug='mc-product'):
    product = Product.objects.create(
        name_ru='Протеин {}'.format(slug), name_uz='Protein {}'.format(slug), price=unit_price,
        quantity=10, slug=slug, country_ru='Узбекистан', country_uz='O‘zbekiston',
    )
    subtotal = unit_price * quantity
    order = Order.objects.create(
        user=user, total_price=subtotal - discount + delivery_fee, subtotal_price=subtotal,
        discount_price=discount, delivery_fee=delivery_fee, type='pickup', full_name='Multicard Customer',
        phone='+998901234560', address='-', idempotency_digest=hashlib.sha256(ORDER_KEY.encode()).hexdigest(), request_fingerprint='f' * 64,
    )
    Basket.objects.create(order=order, user=user, product=product, quantity=quantity)
    payment = Payment.objects.create(
        order=order, provider='manual', amount=order.total_price, currency='UZS',
        idempotency_digest=order.idempotency_digest,
    )
    return order, payment


class FakeClient:
    def __init__(self, status='draft', payment_uuid=None):
        self.created = []
        self.cancelled = []
        self.status = status
        self.payment_uuid = payment_uuid

    def create_invoice(self, body):
        self.created.append(body)
        return Invoice(INVOICE_UUID, 'https://checkout.multicard.test/invoice/{}'.format(INVOICE_UUID), 'draft', None)

    def get_invoice(self, invoice_uuid):
        return Invoice(invoice_uuid, 'https://checkout.multicard.test/x', self.status, self.payment_uuid)

    def cancel_invoice(self, invoice_uuid):
        self.cancelled.append(invoice_uuid)
