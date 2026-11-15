"""Send the customer widgets and remember them so their queries can be checked."""
import logging

from customer_telegram.bot_api import DeliveryStatus
from customer_telegram.models import CustomerTelegramWidget
from customer_telegram.shop.labels import text, widget_labels
from customer_telegram.shop.product_card import card_caption, card_state, product_card_html
from telegram_widgets.html import render
from telegram_widgets.rollout import note_refusal
from telegram_widgets.state import encode


logger = logging.getLogger(__name__)


def send_storefront(chat, api, state, screen='h', search_query='', reply_markup=None):
    language = chat.language or 'ru'
    html = render('storefront', widget_labels(language), state)
    caption = text(language, 'storefront_caption')
    result = _checked(api.send_widget(chat.chat_id, html, caption, reply_markup=reply_markup))
    return _remember(chat, result, CustomerTelegramWidget.STOREFRONT, screen=screen, search_query=search_query)


def send_order(chat, api, state, caption, order=None, reply_markup=None):
    html = render('order', widget_labels(chat.language), state)
    result = _checked(api.send_widget(chat.chat_id, html, caption, reply_markup=reply_markup))
    return _remember(chat, result, CustomerTelegramWidget.ORDER, order=order)


def send_product(chat, api, product):
    """The product card with its photo; ``None`` when it cannot be sent."""
    html = product_card_html(chat, product)
    if html is None:
        return None
    result = _checked(api.send_widget(
        chat.chat_id, html, card_caption(chat, product), chat_data=encode(card_state(chat, product.pk)),
    ))
    return _remember(chat, result, CustomerTelegramWidget.PRODUCT, screen='p:{}'.format(product.pk))


def send_card(chat_id, api, state, caption, language, reply_markup=None):
    html = render('card', widget_labels(language), state)
    return _checked(api.send_widget(chat_id, html, caption, reply_markup=reply_markup))


def update_state(api, widget, state):
    """Persist a widget's screen so it survives the app re-creating the widget."""
    result = api.edit_widget_data(widget.chat.chat_id, widget.message_id, encode(state))
    if result.status not in {DeliveryStatus.SENT, DeliveryStatus.FAILED}:
        logger.warning('Customer widget state was not saved', extra={'widget_id': widget.pk})
    return result


def _checked(result):
    """Log a refused widget; a refusal of widgets as such pauses them for both bots."""
    if result.status is DeliveryStatus.FAILED:
        code = getattr(result, 'error_code', '')
        if not note_refusal(code):
            logger.warning('Customer widget refused (%s)', code or 'no code')
    return result


class WidgetRefused:
    """Falsy stand-in for a widget Telegram refused, so the caller can answer another way.

    Any other failure stays ``None``: an unknown outcome may already be delivered.
    """

    def __bool__(self):
        return False


REFUSED = WidgetRefused()


def _remember(chat, result, kind, **fields):
    if result.status is DeliveryStatus.FAILED:
        return REFUSED
    if result.status is not DeliveryStatus.SENT or not result.message_id:
        return None
    return CustomerTelegramWidget.objects.create(chat=chat, message_id=result.message_id, kind=kind, **fields)
