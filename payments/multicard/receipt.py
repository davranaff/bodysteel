"""Fiscal receipt (OFD) lines for a Multicard invoice.

Amounts are in tiyin (1 UZS = 100 tiyin). The order discount is allocated to
product lines proportionally (largest remainder), so the line totals always add
up to the charged amount and every line satisfies ``qty * price == total``.
"""
from dataclasses import dataclass

from payments.multicard.configuration import MulticardNotConfigured


TIYIN = 100


@dataclass(frozen=True)
class _Line:
    name: str
    quantity: int
    total: int
    ikpu: str
    package_code: str


def order_amount_tiyin(order):
    return int(order.total_price) * TIYIN


def build_ofd(order, baskets, configuration):
    products = [_product_line(basket, configuration) for basket in baskets if basket.quantity > 0]
    if not products:
        raise MulticardNotConfigured('empty receipt')
    discount = int(order.discount_price) * TIYIN
    subtotal = sum(line.total for line in products)
    products = _allocate_discount(products, min(discount, subtotal))
    lines = list(products)
    if order.delivery_fee:
        if not configuration.delivery_ikpu or not configuration.delivery_package_code:
            raise MulticardNotConfigured('delivery fiscal code')
        lines.append(_Line(
            name='Доставка', quantity=1, total=int(order.delivery_fee) * TIYIN,
            ikpu=configuration.delivery_ikpu, package_code=configuration.delivery_package_code,
        ))
    if sum(line.total for line in lines) != order_amount_tiyin(order):
        raise MulticardNotConfigured('receipt total mismatch')
    return [item for line in lines for item in _items(line, configuration)]


def _product_line(basket, configuration):
    product = basket.product
    ikpu = (product.ikpu_code if product else '') or configuration.default_ikpu
    package_code = (product.package_code if product else '') or configuration.default_package_code
    if not ikpu or not package_code:
        raise MulticardNotConfigured('product fiscal code')
    name = (basket.product_name_ru or (product.name_ru if product else '') or 'Товар')[:255]
    return _Line(
        name=name, quantity=int(basket.quantity), total=int(basket.unit_price) * int(basket.quantity) * TIYIN,
        ikpu=ikpu, package_code=package_code,
    )


def _allocate_discount(lines, discount):
    if not discount:
        return lines
    subtotal = sum(line.total for line in lines)
    shares = [discount * line.total // subtotal for line in lines]
    remainders = sorted(
        range(len(lines)), key=lambda index: (discount * lines[index].total) % subtotal, reverse=True,
    )
    for index in remainders[:discount - sum(shares)]:
        shares[index] += 1
    return [
        _Line(line.name, line.quantity, line.total - share, line.ikpu, line.package_code)
        for line, share in zip(lines, shares)
    ]


def _items(line, configuration):
    """Split a line so each emitted item has an integral unit price."""
    unit, remainder = divmod(line.total, line.quantity)
    parts = [(line.quantity - remainder, unit), (remainder, unit + 1)]
    return [_item(line, quantity, price, configuration) for quantity, price in parts if quantity]


def _item(line, quantity, price, configuration):
    item = {
        'qty': quantity,
        'price': price,
        'total': quantity * price,
        'mxik': line.ikpu,
        'package_code': line.package_code,
        'name': line.name,
    }
    if configuration.vat_percent is not None:
        item['vat'] = configuration.vat_percent
    if configuration.tin:
        item['tin'] = configuration.tin
    return item
