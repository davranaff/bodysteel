import hashlib
import json

from django.db import transaction

from courses.models import Course, CoursePurchase
from payments.models import Payment


class PurchaseConflict(Exception):
    pass


class PurchaseUnavailable(Exception):
    pass


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def purchase_fingerprint(user, course):
    value = json.dumps({'user': user.pk, 'course': course.pk}, separators=(',', ':'), sort_keys=True)
    return digest(value)


@transaction.atomic
def create_purchase(user, course_slug, idempotency_key):
    key_digest = digest(idempotency_key)
    course = Course.objects.select_for_update().get(slug=course_slug)
    if not course.is_available_for_sale():
        raise PurchaseUnavailable()
    fingerprint = purchase_fingerprint(user, course)
    existing = CoursePurchase.objects.filter(idempotency_digest=key_digest).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise PurchaseConflict()
        return existing, existing.payments.order_by('-created_at').first(), True
    purchase = CoursePurchase.objects.create(
        user=user,
        course=course,
        course_title=course.title_ru,
        amount=course.price,
        currency=course.currency,
        status=CoursePurchase.PENDING,
        idempotency_digest=key_digest,
        request_fingerprint=fingerprint,
    )
    payment = Payment.objects.create(
        course_purchase=purchase,
        provider='manual',
        amount=purchase.amount,
        currency=purchase.currency,
        status=Payment.CREATED,
        idempotency_digest=key_digest,
        metadata={'purpose': 'course_purchase', 'course_id': course.pk},
    )
    return purchase, payment, False
