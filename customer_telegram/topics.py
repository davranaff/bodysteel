"""Topics in the private chat with the customer bot (Bot API 9.3+, sidebar since 10.5).

With ``CUSTOMER_TELEGRAM_TOPICS`` on (and the bot switched by ``customer_telegram_topics --on``), each
chat gets three topics in a sidebar: the shop (search and menu), the shopper's orders and payments,
and promotions. A reply goes to the topic the shopper wrote in; the bot's own messages go to their
topic. Every failure falls back to the plain chat, so a topic can never lose a message.
"""
import contextvars
from contextlib import contextmanager

from django.conf import settings

from customer_telegram.i18n import message
from customer_telegram.models import CustomerTelegramChat


SHOP, ORDERS, PROMO = 'shop', 'orders', 'promo'
# Topic icon colours from the fixed Bot API palette: blue, green, pink.
TOPICS = {
    SHOP: ('shop_topic_id', 'topic_shop', 'topic_shop_intro', 0x6FB9F0),
    ORDERS: ('orders_topic_id', 'topic_orders', 'topic_orders_intro', 0x8EEE98),
    PROMO: ('promo_topic_id', 'topic_promo', 'topic_promo_intro', 0xFF93B2),
}
_thread = contextvars.ContextVar('customer_telegram_thread', default=None)


def topics_enabled():
    return bool(getattr(settings, 'CUSTOMER_TELEGRAM_TOPICS', False))


@contextmanager
def replying_in(chat_id, thread_id):
    """Messages to ``chat_id`` sent inside the block go to ``thread_id`` (None: the plain chat)."""
    token = _thread.set((chat_id, thread_id) if isinstance(thread_id, int) and thread_id > 0 else None)
    try:
        yield
    finally:
        _thread.reset(token)


def reply_thread(chat_id):
    current = _thread.get()
    return current[1] if current and current[0] == chat_id else None


def replying_to(payload):
    """Replies to an incoming message (or a tap on a button under one) go to its topic."""
    source = payload.get('message') if isinstance(payload, dict) and 'data' in payload else payload
    source = source if isinstance(source, dict) else {}
    chat = source.get('chat') if isinstance(source.get('chat'), dict) else {}
    return replying_in(chat.get('id'), source.get('message_thread_id'))


def topic_thread(chat, kind, api):
    """The thread id of ``chat``'s ``kind`` topic, creating it on first use; None without topics."""
    if not topics_enabled() or chat is None:
        return None
    field, name_key, intro_key, color = TOPICS[kind]
    existing = getattr(chat, field)
    if existing:
        return existing
    language = chat.language or 'ru'
    thread = api.create_forum_topic(chat.chat_id, message(language, name_key), color)
    if not thread:
        return None
    CustomerTelegramChat.objects.filter(pk=chat.pk).update(**{field: thread})
    setattr(chat, field, thread)
    with replying_in(chat.chat_id, thread):
        api.send_message(chat.chat_id, message(language, intro_key))
    return thread


def ensure_topics(chat, api, kinds=(SHOP, ORDERS)):
    return {kind: topic_thread(chat, kind, api) for kind in kinds}


def rename_topics(chat, api):
    """After a language switch the topic names follow the new language."""
    if not topics_enabled():
        return
    language = chat.language or 'ru'
    for field, name_key, _intro, _color in TOPICS.values():
        thread = getattr(chat, field)
        if thread:
            api.edit_forum_topic(chat.chat_id, thread, message(language, name_key))


def forget_thread(chat_id, thread_id):
    """A topic Telegram no longer knows is dropped, so it is created again next time."""
    for field, *_rest in TOPICS.values():
        CustomerTelegramChat.objects.filter(chat_id=chat_id, **{field: thread_id}).update(**{field: None})
