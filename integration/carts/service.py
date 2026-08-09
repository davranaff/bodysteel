import hashlib
import json
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from integration.catalog.cursor import isoformat_utc
from integration.configuration import cart_ttl_seconds, https_origin
from integration.errors import IntegrationProblem
from integration.models import IntegrationCart
from store.models import Product


def create_cart(language, idempotency_key, payload):
    idempotency_digest = _sha256(idempotency_key)
    fingerprint = _fingerprint(language, payload)
    existing = IntegrationCart.objects.filter(idempotency_digest=idempotency_digest).first()
    if existing:
        return _replay(existing, fingerprint)

    try:
        with transaction.atomic():
            existing = (
                IntegrationCart.objects.select_for_update()
                .filter(idempotency_digest=idempotency_digest)
                .first()
            )
            if existing:
                return _replay(existing, fingerprint)
            _assert_sellable(payload['items'])
            cart = IntegrationCart.objects.create(
                idempotency_digest=idempotency_digest,
                request_fingerprint=fingerprint,
                restore_token=secrets.token_urlsafe(32),
                items=payload['items'],
                language=language,
                ai_session_id=payload['attribution']['aiSessionId'],
                channel=payload['attribution']['channel'],
                expires_at=timezone.now() + timedelta(seconds=cart_ttl_seconds()),
            )
    except IntegrityError:
        cart = IntegrationCart.objects.get(idempotency_digest=idempotency_digest)
        return _replay(cart, fingerprint)
    return cart_receipt(cart)


def restore_cart(token):
    if not isinstance(token, str) or not 32 <= len(token) <= 64 or not token.replace('_', '').replace('-', '').isalnum():
        raise _not_found()
    try:
        cart = IntegrationCart.objects.get(restore_token=token)
    except IntegrationCart.DoesNotExist:
        raise _not_found() from None
    if cart.expires_at <= timezone.now():
        raise IntegrationProblem(410, 'Cart expired', 'The restorable cart has expired')

    products = _products_for_items(cart.items, lock=False)
    serialized = []
    for item in cart.items:
        product = products.get(int(item['productId']))
        if not product or product.quantity < item['quantity']:
            raise IntegrationProblem(409, 'Cart unavailable', 'One or more cart items are unavailable')
        serialized.append({'product': _storefront_product(product), 'count': item['quantity']})
    return {
        'items': serialized,
        'expiresAt': isoformat_utc(cart.expires_at),
    }


def cart_receipt(cart):
    return {
        'cartId': str(cart.pk),
        'cartUrl': '{}/cart/restore#{}'.format(
            https_origin('SAVDOQ_STOREFRONT_ORIGIN'),
            cart.restore_token,
        ),
        'expiresAt': isoformat_utc(cart.expires_at),
    }


def _replay(cart, fingerprint):
    if not secrets.compare_digest(cart.request_fingerprint, fingerprint):
        raise IntegrationProblem(409, 'Idempotency conflict', 'The idempotency key was used for another cart')
    return cart_receipt(cart)


def _assert_sellable(items):
    products = _products_for_items(items, lock=True)
    if len(products) != len(items):
        raise IntegrationProblem(422, 'Cart unavailable', 'One or more cart items are unavailable')
    if any(products[int(item['productId'])].quantity < item['quantity'] for item in items):
        raise IntegrationProblem(422, 'Cart unavailable', 'One or more cart items are unavailable')


def _products_for_items(items, lock):
    product_ids = [int(item['productId']) for item in items]
    queryset = Product.objects.filter(pk__in=product_ids)
    if lock:
        queryset = queryset.select_for_update(of=('self',))
    else:
        queryset = queryset.select_related('brand').prefetch_related('product_images')
    return {product.pk: product for product in queryset.order_by('pk')}


def _storefront_product(product):
    return {
        'id': product.pk,
        'slug': product.slug,
        'name_ru': product.name_ru,
        'name_uz': product.name_uz,
        'price': int(product.price),
        'discounted_price': int(product.discounted_price),
        'quantity': int(product.quantity),
        'brand': {'name': product.brand.name} if product.brand else None,
        'product_images': [{'photo': image.photo.url} for image in product.product_images.all()],
    }


def _fingerprint(language, payload):
    canonical = json.dumps(
        {'language': language, **payload},
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True,
    )
    return _sha256(canonical)


def _sha256(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _not_found():
    return IntegrationProblem(404, 'Cart not found', 'The restorable cart was not found')
