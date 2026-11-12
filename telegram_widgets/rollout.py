"""Which Telegram chats get widgets: ``TELEGRAM_WIDGETS_ROLLOUT`` is empty (nobody, the
previous plain messages), a comma-separated list of chat ids (a trial), or ``all``.

Turning it off needs no release: chats go back to plain messages at once, and widgets
already sent keep answering their taps.
"""
from django.conf import settings


def widgets_enabled(chat_id):
    value = (getattr(settings, 'TELEGRAM_WIDGETS_ROLLOUT', '') or '').strip().lower()
    if value == 'all':
        return True
    if not value or chat_id is None:
        return False
    return str(chat_id).strip() in {part.strip() for part in value.split(',') if part.strip()}
