"""Staff access by an invite from the bot owner (Bot API 10.5).

The owner opens ``https://t.me/botinvite/<staff bot username>`` and picks up to ten people. For each
of them Telegram sends a ``write_access_allowed`` service message whose ``inviter`` is the bot owner;
the person is then registered like one who sent a valid ``key:`` phrase. The update arrives on the
webhook, which already checks Telegram's secret token.
"""
import logging
from html import escape

from django.conf import settings
from django.db import IntegrityError

from teleg.models import Chat


logger = logging.getLogger(__name__)


def owner_invite(message):
    """The invited private chat, or None when the message is not an owner invite we accept."""
    if not isinstance(message, dict):
        return None
    access = message.get('write_access_allowed')
    inviter = access.get('inviter') if isinstance(access, dict) else None
    chat = message.get('chat')
    if not isinstance(inviter, dict) or not isinstance(chat, dict) or chat.get('type') != 'private':
        return None
    chat_id, inviter_id = chat.get('id'), inviter.get('id')
    if not isinstance(chat_id, int) or chat_id <= 0 or not isinstance(inviter_id, int):
        return None
    owners = getattr(settings, 'STAFF_TELEGRAM_OWNER_IDS', frozenset())
    if owners and inviter_id not in owners:
        logger.warning('Staff bot invite from an unexpected inviter ignored')
        return None
    return chat


def register_invited(chat):
    """Register the invited chat; True when it is new."""
    try:
        _record, created = Chat.objects.get_or_create(chat_id=chat['id'], defaults={
            'first_name': _text(chat.get('first_name')) or '',
            'last_name': _text(chat.get('last_name')),
            'username': _text(chat.get('username')),
        })
    except IntegrityError:
        return False
    return created


def invited_greeting(chat, help_text):
    name = escape(_text(chat.get('first_name')) or '')
    return '👋 <b>Добро пожаловать{}!</b>\nВладелец пригласил вас в бот сотрудников BodySteel: заказы и отчёты будут приходить сюда.\n\n{}'.format(
        ', ' + name if name else '', help_text,
    )


def _text(value):
    return value[:255] if isinstance(value, str) else None
