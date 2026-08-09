import html
import re
from urllib.parse import quote, urljoin, urlparse

from django.db.models import Max, Prefetch, Q
from django.utils.html import strip_tags

from integration.catalog.cursor import decode_cursor, encode_cursor, isoformat_utc
from integration.configuration import https_origin
from integration.errors import IntegrationProblem
from store.models import Category, Product, ProductImage


WHITESPACE = re.compile(r'\s+')


def list_products(cursor, updated_after, limit, language):
    queryset = _product_queryset()
    if updated_after:
        queryset = queryset.filter(updated_at__gt=updated_after)
    state = decode_cursor(cursor, updated_after) if cursor else _initial_state(queryset, updated_after)
    queryset = _apply_window(queryset, state)
    order = ('updated_at', 'pk') if updated_after else ('pk',)
    products = list(queryset.order_by(*order)[: limit + 1])
    has_more = len(products) > limit
    page_products = products[:limit]
    return {
        'items': [serialize_product(product, language) for product in page_products],
        **(_next_cursor(page_products, state, updated_after) if has_more else {}),
        'hasMore': has_more,
    }


def get_product(product_id, language):
    if not product_id.isdigit():
        raise _not_found()
    try:
        product = _product_queryset().get(pk=int(product_id))
    except Product.DoesNotExist:
        raise _not_found() from None
    return serialize_product(product, language)


def serialize_product(product, language):
    name = getattr(product, 'name_{}'.format(language))
    description = _plain_text(getattr(product, 'description_{}'.format(language)) or '')
    country = getattr(product, 'country_{}'.format(language))
    composition = _plain_text(getattr(product, 'composition_{}'.format(language)) or '')
    price = int(product.price)
    discount = int(product.discounted_price)
    return {
        'id': str(product.pk),
        'name': name,
        'description': description,
        'price': {'amount': price, 'currency': 'UZS'},
        **({'salePrice': {'amount': price - discount, 'currency': 'UZS'}} if discount else {}),
        'stock': _stock(product.quantity),
        **({'brand': product.brand.name} if product.brand else {}),
        'categories': [getattr(category, 'name_{}'.format(language)) for category in product.category.all()],
        'attributes': {'country': country, **({'composition': composition} if composition else {})},
        'imageUrls': [_media_url(image.photo.url) for image in product.product_images.all()],
        'url': '{}/product/{}'.format(
            https_origin('SAVDOQ_STOREFRONT_ORIGIN'),
            quote(product.slug, safe=''),
        ),
        'updatedAt': isoformat_utc(product.updated_at),
    }


def _product_queryset():
    return Product.objects.select_related('brand').prefetch_related(
        Prefetch('category', queryset=Category.objects.order_by('pk')),
        Prefetch('product_images', queryset=ProductImage.objects.order_by('pk')),
    )


def _initial_state(queryset, updated_after):
    snapshot = queryset.aggregate(value=Max('updated_at'))['value']
    return {
        'version': 1,
        'mode': 'delta' if updated_after else 'full',
        'updatedAfter': isoformat_utc(updated_after) if updated_after else None,
        'snapshotAt': snapshot,
        'lastId': None,
        'lastUpdatedAt': None,
    }


def _apply_window(queryset, state):
    snapshot = state['snapshotAt']
    if snapshot is None:
        return queryset.none()
    queryset = queryset.filter(updated_at__lte=snapshot)
    if state['lastId'] is None:
        return queryset
    if state['mode'] == 'full':
        return queryset.filter(pk__gt=state['lastId'])
    return queryset.filter(
        Q(updated_at__gt=state['lastUpdatedAt'])
        | Q(updated_at=state['lastUpdatedAt'], pk__gt=state['lastId'])
    )


def _next_cursor(products, state, updated_after):
    last = products[-1]
    payload = {
        'version': 1,
        'mode': state['mode'],
        'updatedAfter': isoformat_utc(updated_after) if updated_after else None,
        'snapshotAt': isoformat_utc(state['snapshotAt']),
        'lastId': last.pk,
        'lastUpdatedAt': isoformat_utc(last.updated_at) if updated_after else None,
    }
    return {'nextCursor': encode_cursor(payload)}


def _stock(quantity):
    quantity = int(quantity)
    return {'status': 'in_stock' if quantity > 0 else 'out_of_stock', 'quantity': quantity}


def _plain_text(value):
    return WHITESPACE.sub(' ', html.unescape(strip_tags(value))).strip()


def _media_url(path):
    expected_origin = https_origin('SAVDOQ_MEDIA_ORIGIN')
    candidate = urljoin('{}/'.format(expected_origin), path.lstrip('/'))
    try:
        parsed = urlparse(candidate)
        candidate_port = parsed.port
    except (TypeError, ValueError):
        raise _unsafe_media_url() from None
    if (
        '{}://{}'.format(parsed.scheme, parsed.hostname) != expected_origin
        or candidate_port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise _unsafe_media_url()
    return candidate


def _unsafe_media_url():
    return IntegrationProblem(503, 'Service unavailable', 'Product media URL is misconfigured')


def _not_found():
    return IntegrationProblem(404, 'Product not found', 'The product was not found')
