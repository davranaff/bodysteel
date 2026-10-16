import logging
from html import escape

from teleg.models import Chat as ChatModel


logger = logging.getLogger(__name__)
PREVIEW_LIMIT = 300


def notify_staff_about_report(report):
    """Best-effort staff Telegram alert, mirroring ``teleg.utils.notify_message``.

    Only moderation context is sent: no reporter name, phone, email or account id.
    """
    from teleg.views import bot

    text = format_report_notification(report)
    chat_ids = ChatModel.objects.values_list('chat_id', flat=True).distinct()
    for chat_id in chat_ids:
        try:
            bot.send_message(chat_id, text=text, parse_mode='HTML')
        except Exception:
            logger.exception('Telegram content report notification failed', extra={'report_id': report.pk})


def format_report_notification(report):
    lines = [
        '🚩 <b>НОВАЯ ЖАЛОБА НА КОНТЕНТ</b>',
        f'<b>№ {report.pk}</b> · {escape(report.get_kind_display())}',
        f'Причина: {escape(report.get_reason_display())}',
    ]
    if report.review_id is not None:
        product = getattr(report.review.product, 'name_ru', '') or '—'
        lines.append(f'Отзыв #{report.review_id} · {escape(product)}')
        lines.append(f'Текст отзыва: {_preview(report.review.comment)}')
        if not report.review.is_published:
            lines.append('<i>Отзыв скрыт с витрины до проверки.</i>')
    if report.excerpt:
        lines.append(f'Фрагмент ответа ИИ: {_preview(report.excerpt)}')
    if report.comment:
        lines.append(f'Комментарий: {_preview(report.comment)}')
    lines.append('Проверьте в админке: Модерация контента → Жалобы на контент.')
    return '\n'.join(lines)


def _preview(value):
    value = ' '.join(str(value or '').split())
    if len(value) > PREVIEW_LIMIT:
        value = value[:PREVIEW_LIMIT - 1] + '…'
    return escape(value) or '—'
