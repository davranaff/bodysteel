"""Which Telegram chats get widgets: ``TELEGRAM_WIDGETS_ROLLOUT`` is empty (nobody, the
previous plain messages), a comma-separated list of chat ids (a trial), or ``all``.

Turning it off needs no release: chats go back to plain messages at once, and widgets
already sent keep answering their taps.

Telegram can also stop accepting widgets from every bot at once (it did so on 13 November
2026). Then ``sendWidget`` answers ``INPUT_MEDIA_WIDGET_NOT_ALLOWED`` whatever the HTML,
so after one such answer both bots use plain messages for ``PAUSE_SECONDS`` and then try
again. The pause lives in the Django cache: each process learns it from its own first refusal.
"""
import logging
import re

from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)
PAUSE_KEY = 'telegram_widgets:refused'
PAUSE_SECONDS = 30 * 60
# Telegram refuses widgets for this bot or chat, not this widget: plain messages instead.
REFUSAL_CODES = frozenset({'INPUT_MEDIA_WIDGET_NOT_ALLOWED'})
# Error descriptions may echo request content; only their upper-case codes are logged.
ERROR_CODE = re.compile(r'\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b')


def widgets_enabled(chat_id):
    value = (getattr(settings, 'TELEGRAM_WIDGETS_ROLLOUT', '') or '').strip().lower()
    if value == 'all':
        allowed = True
    elif not value or chat_id is None:
        return False
    else:
        allowed = str(chat_id).strip() in {part.strip() for part in value.split(',') if part.strip()}
    return allowed and not widgets_paused()


def error_code(description):
    """The Telegram error code in an error description, such as ``INPUT_MEDIA_WIDGET_TOO_LARGE``."""
    match = ERROR_CODE.search(description) if isinstance(description, str) else None
    return match.group(0) if match else ''


def note_refusal(code):
    """Pause widgets when Telegram refuses them as such; return whether it did."""
    if code not in REFUSAL_CODES:
        return False
    try:
        first = cache.add(PAUSE_KEY, code, PAUSE_SECONDS)
    except Exception:
        logger.exception('Widget pause could not be saved')
        return True
    if first:
        logger.warning('Telegram refuses widgets (%s): plain messages for %s minutes',
                       code, PAUSE_SECONDS // 60)
    return True


def widgets_paused():
    try:
        return cache.get(PAUSE_KEY) is not None
    except Exception:
        return False
