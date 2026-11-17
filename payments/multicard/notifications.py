"""Staff alerts once Multicard has confirmed a payment, for an order or a course."""
import logging
from html import escape

from courses.models import CoursePurchase
from customer_telegram.shop.payments import notify_customer_paid
from store.models import Order
from teleg.models import Chat as ChatModel
from teleg.utils.notify_message import notify_message
from teleg.views import bot


logger = logging.getLogger(__name__)


def notify_paid_order(order_id):
    order = Order.objects.select_related('coupon').filter(pk=order_id).first()
    if order is None:
        return
    try:
        notify_message(order, order.baskets.select_related('product'), order.coupon, paid=True)
    except Exception:
        # The payment is already committed; a failed alert must not undo it.
        logger.exception('Paid order notification delivery failed', extra={'order_id': order_id})
    try:
        notify_customer_paid(order_id)
    except Exception:
        logger.exception('Customer bot payment notice failed', extra={'order_id': order_id})


def notify_paid_course(purchase_id):
    purchase = CoursePurchase.objects.select_related('user').filter(pk=purchase_id).first()
    if purchase is None:
        return
    text = format_course_notification(purchase)
    for recipient_number, chat_id in enumerate(
        ChatModel.objects.values_list('chat_id', flat=True).distinct(), start=1,
    ):
        try:
            bot.send_message(chat_id, text=text, parse_mode='HTML')
        except Exception:
            # The payment is already committed; a failed alert must not undo it.
            logger.exception('Paid course notification failed', extra={
                'purchase_id': purchase_id, 'recipient_number': recipient_number,
            })


def format_course_notification(purchase):
    user = purchase.user
    buyer = ' · '.join(value for value in (user.get_full_name().strip() or user.username, user.phone or '') if value)
    return (
        '✅ <b>ОПЛАЧЕН КУРС</b> · Multicard\n'
        '<b>Курс:</b> {}\n'
        '<b>Сумма:</b> {} {}\n'
        '<b>Покупатель:</b> {}\n'
        '<b>Покупка:</b> № {}'
    ).format(
        escape(purchase.course_title), f'{int(purchase.amount):,}'.replace(',', ' '),
        escape(purchase.currency), escape(buyer), purchase.pk,
    )
