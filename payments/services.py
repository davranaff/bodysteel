from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from courses.models import CourseAccess, CoursePurchase
from payments.models import Payment


@transaction.atomic
def complete_payment(payment_id, provider_payment_id=None):
    payment = Payment.objects.select_for_update().select_related('course_purchase__course', 'order').get(pk=payment_id)
    if payment.status == Payment.SUCCEEDED:
        return payment
    if payment.status in {Payment.CANCELLED, Payment.REFUNDED}:
        return payment
    payment.status = Payment.SUCCEEDED
    payment.provider_payment_id = provider_payment_id or payment.provider_payment_id or 'manual-{}'.format(payment.pk)
    payment.paid_at = timezone.now()
    payment.save(update_fields=('status', 'provider_payment_id', 'paid_at', 'updated_at'))
    if payment.course_purchase_id:
        _complete_course_purchase(payment)
    elif payment.order_id:
        payment.order.payment_status = 'paid'
        payment.order.save(update_fields=('payment_status',))
    return payment


def _complete_course_purchase(payment):
    purchase = CoursePurchase.objects.select_for_update().select_related('course').get(pk=payment.course_purchase_id)
    purchase.status = CoursePurchase.PAID
    purchase.paid_at = purchase.paid_at or timezone.now()
    purchase.save(update_fields=('status', 'paid_at'))
    expires_at = None
    if purchase.course.access_duration_days:
        expires_at = timezone.now() + timedelta(days=purchase.course.access_duration_days)
    access, _ = CourseAccess.objects.select_for_update().get_or_create(
        user=purchase.user,
        course=purchase.course,
        defaults={
            'purchase': purchase,
            'source': 'purchase',
            'status': CourseAccess.ACTIVE,
            'expires_at': expires_at,
        },
    )
    if access.status != CourseAccess.ACTIVE:
        access.status = CourseAccess.ACTIVE
        access.purchase = purchase
        access.revoked_at = None
        access.revoke_reason = ''
        access.expires_at = expires_at
        access.save(update_fields=('status', 'purchase', 'revoked_at', 'revoke_reason', 'expires_at'))

__all__ = ('complete_payment',)
