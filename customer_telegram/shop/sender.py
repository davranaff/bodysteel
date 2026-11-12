"""Send the customer widgets and remember them so their queries can be checked."""
import logging

from customer_telegram.bot_api import DeliveryStatus
from customer_telegram.models import CustomerTelegramWidget
from customer_telegram.shop.labels import text, widget_labels
from telegram_widgets.html import render
from telegram_widgets.state import encode


logger = logging.getLogger(__name__)


def send_storefront(chat, api, state, screen='h', search_query='', reply_markup=None):
    language = chat.language or 'ru'
    html = render('storefront', widget_labels(language), state)
    result = api.send_widget(chat.chat_id, html, text(language, 'storefront_caption'), reply_markup=reply_markup)
    return _remember(chat, result, CustomerTelegramWidget.STOREFRONT, screen=screen, search_query=search_query)


def send_order(chat, api, state, caption, order=None, reply_markup=None):
    html = render('order', widget_labels(chat.language), state)
    result = api.send_widget(chat.chat_id, html, caption, reply_markup=reply_markup)
    return _remember(chat, result, CustomerTelegramWidget.ORDER, order=order)


def send_card(chat_id, api, state, caption, language, reply_markup=None):
    html = render('card', widget_labels(language), state)
    return api.send_widget(chat_id, html, caption, reply_markup=reply_markup)


def update_state(api, widget, state):
    """Persist a widget's screen so it survives the app re-creating the widget."""
    result = api.edit_widget_data(widget.chat.chat_id, widget.message_id, encode(state))
    if result.status not in {DeliveryStatus.SENT, DeliveryStatus.FAILED}:
        logger.warning('Customer widget state was not saved', extra={'widget_id': widget.pk})
    return result


def _remember(chat, result, kind, **fields):
    if result.status is not DeliveryStatus.SENT or not result.message_id:
        return None
    return CustomerTelegramWidget.objects.create(chat=chat, message_id=result.message_id, kind=kind, **fields)
