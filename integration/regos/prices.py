"""Site prices follow REGOS when REGOS changes, not on every sync.

REGOS ``Item/GetExt`` returns each item's price for the integration's price type
(``Розничная цена``, in sum). Every sync remembers it in ``Product.regos_price``.
The first reading only remembers it, so the prices admins set stay as they are.
A card takes the REGOS price later, when:

- the remembered REGOS price changes (a price document or a card edit in REGOS);
- or REGOS reports the item as added or edited (``ItemAdded``/``ItemEdited``).

That applies to REGOS draft and published cards always, and to every other linked
card while ``REGOS_SYNC_PRICES`` is on. A card with a site discount keeps its price:
the discount is a fixed amount set by hand, and some of those sales are already
inside the REGOS price, so copying it could give the buyer the same sale twice.
Archived cards keep theirs, and a zero REGOS price means "no price".
"""
from decimal import Decimal, InvalidOperation
import logging

from django.conf import settings

from store.models import Product


logger = logging.getLogger(__name__)
_CATALOG_MANAGED = frozenset((Product.REGOS_STATUS_DRAFT, Product.REGOS_STATUS_PUBLISHED))
_PRICE_KEYS = ('price', 'sale_price', 'salePrice')


def prices_follow_regos():
    return bool(getattr(settings, 'REGOS_SYNC_PRICES', False))


def follow_price(product, price, *, item_event=False):
    """Remember REGOS's price on ``product`` and copy it when it should follow REGOS.

    Returns True when ``product.price`` changed; the caller saves the row, and
    compares ``product.regos_price`` with its old value to store the reading.
    """
    if not price:
        return False
    previous, product.regos_price = product.regos_price, price
    changed_in_regos = previous is not None and previous != price
    if product.price == price or not (changed_in_regos or item_event):
        return False
    if product.discounted_price or product.regos_catalog_status == Product.REGOS_STATUS_ARCHIVED:
        return False
    if not prices_follow_regos() and product.regos_catalog_status not in _CATALOG_MANAGED:
        return False
    logger.info('REGOS price: product=%s %s -> %s', product.pk, product.price, price)
    product.price = price
    return True


def parse_price(value):
    """A whole, non-negative sum amount, or None."""
    if value in (None, '') or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0 or parsed != parsed.to_integral_value():
        return None
    return int(parsed)


def row_price(row, item):
    """The price of one GetExt row, ignoring a price type that is not in sum."""
    price_type = row.get('pricetype')
    currency = price_type.get('currency') if isinstance(price_type, dict) else None
    if isinstance(currency, dict) and currency.get('code_chr') not in (None, 'UZS'):
        return None
    for source in (item, row):
        price = parse_price(next((source[key] for key in _PRICE_KEYS if key in source), None))
        if price:
            return price
    return None


def price_preview(records):
    """Linked cards whose price differs from REGOS, without writing anything.

    Returns ``(product, regos_price, note)`` rows; ``note`` is '' for a card that
    takes the REGOS price once REGOS changes that price or the item.
    """
    regos = {record.item_id: record.price for record in records if record and record.item_id}
    rows = []
    products = Product.objects.filter(regos_item_id__in=regos).exclude(
        regos_catalog_status=Product.REGOS_STATUS_ARCHIVED,
    ).order_by('name_ru')
    for product in products:
        price = regos[product.regos_item_id]
        if price == product.price:
            continue
        if not price:
            note = 'в REGOS нет цены'
        elif product.discounted_price:
            note = 'скидка на сайте, цена не меняется'
        else:
            note = ''
        rows.append((product, price, note))
    return rows
