import hashlib
import json
import secrets

from django.db import transaction
from django.utils import timezone

from courses.models import Course, CourseAccess, CoursePurchase
from payments.models import Payment


OPEN_STATUSES = (CoursePurchase.CREATED, CoursePurchase.PENDING)


class PurchaseConflict(Exception):
    pass


class PurchaseUnavailable(Exception):
    pass


class CourseOwned(Exception):
    pass


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def purchase_fingerprint(user, course):
    value = json.dumps({'user': user.pk, 'course': course.pk}, separators=(',', ':'), sort_keys=True)
    return digest(value)


def owns_course(user, course):
    access = CourseAccess.objects.filter(user=user, course=course, status=CourseAccess.ACTIVE).first()
    return bool(access and access.is_active())


@transaction.atomic
def create_purchase(user, course_slug, idempotency_key):
    # The key is scoped to the buyer, so two shoppers who send the same key get two purchases.
    key_digest = digest('{}:{}'.format(user.pk, idempotency_key))
    course = Course.objects.select_for_update().get(slug=course_slug)
    if not course.is_available_for_sale():
        raise PurchaseUnavailable()
    fingerprint = purchase_fingerprint(user, course)
    existing = CoursePurchase.objects.filter(idempotency_digest=key_digest).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise PurchaseConflict()
        return existing, existing.payments.order_by('-created_at').first(), True
    if owns_course(user, course):
        raise CourseOwned()
    purchase, payment = _new_purchase(user, course, key_digest, 'manual')
    return purchase, payment, False


def open_course_purchase(user, course, provider):
    """The shopper's one open purchase of a course and its payment, both locked.

    Runs inside the caller's transaction with the course row locked. An open purchase
    made at an older price is cancelled: a late payment of its invoice is then refused
    by the callback and Multicard returns the money.
    """
    purchase = (
        CoursePurchase.objects.select_for_update()
        .filter(user=user, course=course, status__in=OPEN_STATUSES).order_by('-created_at').first()
    )
    if purchase is not None and purchase.amount != course.price:
        _cancel(purchase)
        purchase = None
    if purchase is None:
        return _new_purchase(user, course, digest('open:{}'.format(secrets.token_hex(24))), provider)
    payment = (
        Payment.objects.select_for_update(of=('self',))
        .filter(course_purchase=purchase).exclude(status__in=(Payment.CANCELLED, Payment.REFUNDED))
        .order_by('-pk').first()
    )
    if payment is None:
        payment = _new_payment(purchase, digest('retry:{}'.format(secrets.token_hex(24))), provider)
    return purchase, payment


def _new_purchase(user, course, key_digest, provider):
    purchase = CoursePurchase.objects.create(
        user=user,
        course=course,
        course_title=course.title_ru,
        amount=course.price,
        currency=course.currency,
        status=CoursePurchase.PENDING if provider == 'manual' else CoursePurchase.CREATED,
        idempotency_digest=key_digest,
        request_fingerprint=purchase_fingerprint(user, course),
    )
    return purchase, _new_payment(purchase, key_digest, provider)


def _new_payment(purchase, key_digest, provider):
    return Payment.objects.create(
        course_purchase=purchase,
        provider=provider,
        amount=purchase.amount,
        currency=purchase.currency,
        status=Payment.CREATED,
        idempotency_digest=key_digest,
        metadata={'purpose': 'course_purchase', 'course_id': purchase.course_id},
    )


def _cancel(purchase):
    purchase.status = CoursePurchase.CANCELLED
    purchase.save(update_fields=('status',))
    Payment.objects.filter(course_purchase=purchase).exclude(status=Payment.SUCCEEDED).update(
        status=Payment.CANCELLED, updated_at=timezone.now(),
    )
