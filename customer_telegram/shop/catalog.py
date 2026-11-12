"""Catalog screens of the storefront widget, each a state of at most 1024 bytes."""
from django.db.models import Case, IntegerField, Value, When

from customer_telegram.configuration import require_configuration
from customer_telegram.shop.cart import cart_count, cart_items
from customer_telegram.shop.labels import text
from customer_telegram.shop.thumbnails import product_thumbnail
from store.catalog.search import smart_product_ids
from store.models import Category, Product
from telegram_widgets.state import clip, fit_rows, size


PAGE_SIZE = 5
MAXIMUM_CATEGORIES = 16
SEARCH_LIMIT = 50


def home_screen(chat, notice=''):
    language = chat.language or 'ru'
    categories = Category.objects.filter(
        products__in=Product.objects.visible_on_storefront(),
    ).distinct().order_by('sort', 'pk')[:MAXIMUM_CATEGORIES]
    state = _base('h', chat, notice)
    rows = [[category.pk, _name(category, language)] for category in categories]
    fit_rows(state, 'c', rows, budgets=(40, 28, 20))
    return state


def category_screen(chat, category_id, page):
    category = Category.objects.filter(pk=category_id).first()
    if category is None:
        return home_screen(chat, text(chat.language, 'stale'))
    products = _ordered(Product.objects.visible_on_storefront().filter(category=category))
    return _list_screen(chat, _name(category, chat.language), 'c:{}'.format(category.pk), products, page)


def search_screen(chat, query, page):
    visible = Product.objects.visible_on_storefront()
    ids = smart_product_ids(visible, query)[:SEARCH_LIMIT] if query else []
    order = Case(*[When(pk=pk, then=Value(index)) for index, pk in enumerate(ids)], output_field=IntegerField())
    products = visible.filter(pk__in=ids).order_by(order) if ids else visible.none()
    title = text(chat.language, 'search').format(clip(query, 40))
    return _list_screen(chat, title, 's', products, page)


def product_screen(chat, product_id, back='h', notice=''):
    language = chat.language or 'ru'
    product = Product.objects.visible_on_storefront().select_related('brand').filter(pk=product_id).first()
    if product is None:
        return home_screen(chat, text(language, 'gone'))
    price, old = unit_price(product), _old_price(product)
    state = {
        **_base('p', chat, notice), 'b': back, 'id': product.pk, 't': clip(_name(product, language), 160),
        'pr': price, 'o': old, 'ok': product.quantity > 0, 'q': cart_items(chat).get(product.pk, 0),
    }
    if product.brand_id:
        state['br'] = clip(product.brand.name, 40)
    if product.slug:
        url = '{}/product/{}'.format(require_configuration().store_origin, product.slug)
        if len(url) <= 256:
            state['u'] = url
    state['d'] = clip(_country(product, language), 60)
    image = product_thumbnail(product, 1024 - size(state) - len(',"im":""'))
    if image:
        state['im'] = image
    return state


def unit_price(product):
    return int(product.price) - int(product.discounted_price)


def _list_screen(chat, title, base, products, page):
    page = max(0, int(page))
    window = list(products[page * PAGE_SIZE:(page + 1) * PAGE_SIZE + 1])
    in_cart = cart_items(chat)
    state = {**_base('l', chat), 't': clip(title, 60), 'b': base, 'pg': page, 'mo': len(window) > PAGE_SIZE}
    rows = [
        [product.pk, _name(product, chat.language), unit_price(product), _old_price(product),
         product.quantity > 0, in_cart.get(product.pk, 0)]
        for product in window[:PAGE_SIZE]
    ]
    fit_rows(state, 'i', rows, budgets=(110, 80, 56, 36))
    return state


def _ordered(queryset):
    in_stock = Case(When(quantity__gt=0, then=Value(0)), default=Value(1), output_field=IntegerField())
    return queryset.annotate(_in_stock=in_stock).order_by('_in_stock', '-view_count', 'pk')


def _base(view, chat, notice=''):
    state = {'v': view, 'n': cart_count(chat)}
    if notice:
        state['m'] = notice
    return state


def _old_price(product):
    return int(product.price) if int(product.discounted_price) > 0 else 0


def _name(item, language):
    primary = item.name_uz if language == 'uz' else item.name_ru
    return primary or item.name_ru or item.name_uz or ''


def _country(product, language):
    return (product.country_uz if language == 'uz' else product.country_ru) or ''
