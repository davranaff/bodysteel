from django.utils import timezone

from integration.catalog.cursor import isoformat_utc
from integration.catalog.products import _stock
from store.models import Product


def read_inventory(product_ids):
    numeric_ids = [int(value) for value in product_ids if value.isdigit()]
    products = Product.objects.filter(pk__in=numeric_ids).only('pk', 'quantity').order_by('pk')
    return {
        'items': [
            {'productId': str(product.pk), 'stock': _stock(product.quantity)}
            for product in products
        ],
        'checkedAt': isoformat_utc(timezone.now()),
    }
