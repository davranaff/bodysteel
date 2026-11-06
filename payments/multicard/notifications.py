"""Staff alert for an order once Multicard has confirmed its payment."""
import logging

from store.models import Order
from teleg.utils.notify_message import notify_message


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
