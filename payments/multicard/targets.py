"""What a Multicard payment pays for: a storefront order or a course purchase.

Transitions call these with the payment row already locked, so the target row is
read and changed inside the same transaction.
"""
from django.utils import timezone

from courses.models import CourseAccess, CoursePurchase
from payments.multicard.notifications import notify_paid_course, notify_paid_order
from payments.multicard.receipt import TIYIN, order_amount_tiyin


def amount_tiyin(payment):
    if payment.order_id:
        return order_amount_tiyin(payment.order)
    return payment.course_purchase.amount * TIYIN


def refusal(payment):
    """Why a paid transaction must be returned, or '' when it can be accepted."""
    if payment.order_id:
        return 'Заказ отменён' if payment.order.fulfillment_status == 'cancelled' else ''
    purchase = payment.course_purchase
    if purchase.status in {CoursePurchase.CANCELLED, CoursePurchase.REFUNDED}:
        return 'Покупка курса отменена'
    access = (
        CourseAccess.objects.filter(user_id=purchase.user_id, course_id=purchase.course_id)
        .exclude(purchase=purchase).first()
    )
    if access is not None and access.is_active():
        return 'Курс уже открыт'
    return ''


def mark_failed(payment):
    # A course purchase stays open after a failed attempt, so the shopper can pay again.
    if payment.order_id:
        payment.order.payment_status = 'failed'
        payment.order.save(update_fields=('payment_status',))


def mark_refunded(payment):
    if payment.order_id:
        payment.order.payment_status = 'refunded'
        payment.order.save(update_fields=('payment_status',))
        return
    purchase = CoursePurchase.objects.select_for_update().get(pk=payment.course_purchase_id)
    purchase.status = CoursePurchase.REFUNDED
    purchase.save(update_fields=('status',))
    CourseAccess.objects.filter(purchase=purchase, status=CourseAccess.ACTIVE).update(
        status=CourseAccess.REVOKED, revoked_at=timezone.now(), revoke_reason='Оплата возвращена',
    )


def paid_notice(payment):
    """The staff alert to send once the payment row is committed."""
    if payment.order_id:
        order_id = payment.order_id
        return lambda: notify_paid_order(order_id)
    purchase_id = payment.course_purchase_id
    return lambda: notify_paid_course(purchase_id)
