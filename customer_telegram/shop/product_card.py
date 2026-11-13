"""The product card: one widget message per product with its photo and description.

A widget shows images only as ``data:`` URLs inside its HTML, and the whole HTML must
stay under 4096 bytes compressed. The card therefore bakes the product in and spends
what the text leaves on the largest photo that still fits; the cart quantity is the
only thing that changes, so it lives in the chat state.
"""
from html import unescape

from django.utils.html import strip_tags

from customer_telegram.configuration import require_configuration
from customer_telegram.shop.cart import cart_count, cart_items
from customer_telegram.shop.labels import text, widget_labels
from customer_telegram.shop.thumbnails import cached_photo_uri, first_photo
from store.models import Product
from telegram_widgets.html import WidgetTooLarge, render
from telegram_widgets.state import clip


# Largest first: a smaller photo is tried only when a larger one does not fit.
PHOTO_ATTEMPTS = (
    (320, 36), (288, 34), (256, 32), (240, 30), (224, 28), (208, 26), (192, 24), (176, 22), (160, 20), (128, 20), (96, 20),
)
# Below this side the photo is too small to be worth a shorter description.
GOOD_PHOTO_SIDE = 200
DESCRIPTION_BUDGETS = (520, 360, 220, 120, 0)
# Only the words the card uses: every byte of labels is a byte less of photo.
CARD_LABELS = ('sum', 'wait', 'err', 'in', 'out', 'add', 'cart', 'site')


def card_state(chat, product_id, notice=''):
    state = {'q': cart_items(chat).get(product_id, 0), 'n': cart_count(chat)}
    if notice:
        state['m'] = notice
    return state


def product_card_html(chat, product):
    """The card's HTML with the best photo and description that fit, or ``None``."""
    language = chat.language or 'ru'
    labels = {key: value for key, value in widget_labels(language).items() if key in CARD_LABELS}
    base = _card_data(chat, product, language)
    description = _plain(product.description_uz if language == 'uz' else product.description_ru) or _plain(
        product.description_ru,
    )
    photo = first_photo(product)
    best = None
    for budget in DESCRIPTION_BUDGETS:
        data = dict(base)
        if description and budget:
            data['d'] = clip(description, budget)
        html, side = _with_photo(labels, data, photo)
        if html and (side >= GOOD_PHOTO_SIDE or not photo):
            return html
        if html and (best is None or side > best[1]):
            best = (html, side)
    return best[0] if best else None


def visible_product(product_id):
    return Product.objects.visible_on_storefront().select_related('brand').filter(pk=product_id).first()


def unit_price(product):
    return int(product.price) - int(product.discounted_price)


def _with_photo(labels, data, photo):
    if photo is not None:
        for side, quality in PHOTO_ATTEMPTS:
            uri = cached_photo_uri(photo, side, quality)
            if uri is None:
                break
            try:
                return render('product', labels, {**data, 'im': uri}), side
            except WidgetTooLarge:
                continue
    try:
        return render('product', labels, data), 0
    except WidgetTooLarge:
        return None, 0


def _card_data(chat, product, language):
    name = (product.name_uz if language == 'uz' else product.name_ru) or product.name_ru or product.name_uz or ''
    data = {
        'id': product.pk, 't': clip(name, 160), 'pr': unit_price(product),
        'o': int(product.price) if int(product.discounted_price) > 0 else 0, 'ok': product.quantity > 0,
        'q': cart_items(chat).get(product.pk, 0), 'n': cart_count(chat),
    }
    if product.brand_id:
        data['br'] = clip(product.brand.name, 40)
    country = (product.country_uz if language == 'uz' else product.country_ru) or ''
    if country:
        data['c'] = clip(country, 40)
    if product.slug:
        url = '{}/product/{}'.format(require_configuration().store_origin, product.slug)
        if len(url) <= 256:
            data['u'] = url
    return data


def _plain(value):
    return ' '.join(unescape(strip_tags(value or '')).split())


def card_caption(chat, product):
    language = chat.language or 'ru'
    name = (product.name_uz if language == 'uz' else product.name_ru) or product.name_ru or ''
    return clip('{} · {} {}'.format(name, '{:,}'.format(unit_price(product)).replace(',', ' '),
                                    widget_labels(language)['sum']), 200) or text(language, 'storefront_caption')
