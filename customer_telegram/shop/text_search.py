"""Search answered as a text message while widgets are off.

The best matches with prices, stock and a link to each product on the site, plus a
button to every result there. In-stock products come first among the best matches.
"""
from html import escape
from urllib.parse import quote

from customer_telegram.configuration import require_configuration
from customer_telegram.i18n import message
from customer_telegram.shop.catalog import search_products, unit_price


SHOWN = 5
CONSIDERED = 12
NAME_LIMIT = 90


def text_search(chat, query, api):
    language = chat.language or 'ru'
    products = list(search_products(query, CONSIDERED).select_related('brand'))
    products.sort(key=lambda product: product.quantity <= 0)
    origin = require_configuration().store_origin
    all_results = {'inline_keyboard': [[{
        'text': message(language, 'search_all'),
        'url': '{}/search/{}'.format(origin, quote(query, safe='')),
    }]]}
    if not products:
        catalog = {'inline_keyboard': [[{'text': message(language, 'open_store'), 'url': origin}]]}
        api.send_message(chat.chat_id, message(language, 'search_none').format(escape(query)), catalog)
        return 'search'
    lines = [message(language, 'search_found').format(escape(query))]
    for index, product in enumerate(products[:SHOWN], start=1):
        lines += ['', _product_lines(index, product, language, origin)]
    api.send_message(chat.chat_id, '\n'.join(lines), all_results)
    return 'search'


def _product_lines(index, product, language, origin):
    name = (product.name_uz if language == 'uz' else product.name_ru) or product.name_ru or product.name_uz or ''
    if len(name) > NAME_LIMIT:
        name = name[:NAME_LIMIT - 1] + '…'
    title = escape(name)
    if product.slug:
        title = '<a href="{}/product/{}">{}</a>'.format(origin, escape(quote(product.slug, safe='-_.~')), title)
    price = '<b>{} {}</b>'.format(_money(unit_price(product)), message(language, 'currency'))
    if int(product.discounted_price) > 0:
        price += ' <s>{}</s>'.format(_money(product.price))
    stock = message(language, 'in_stock' if product.quantity > 0 else 'out_of_stock')
    return '{}. {}\n{} · {}'.format(index, title, price, stock)


def _money(value):
    return '{:,}'.format(int(value)).replace(',', ' ')
