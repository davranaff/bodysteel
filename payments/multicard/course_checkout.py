"""Start (or resume) a Multicard payment for a course.

Courses are digital goods, so they are sold on the website only (channel 'web'):
the app stores require their own billing for digital content inside apps. A
shopper has one open purchase per course; a retry reuses its live invoice. A free
course opens at once, and a course the shopper already owns is never charged.
"""
from dataclasses import dataclass

from django.db import transaction

from courses.models import Course, CoursePurchase
from courses.services import PurchaseUnavailable, open_course_purchase, owns_course
from payments.multicard.client import MulticardClient
from payments.multicard.configuration import require_configuration
from payments.multicard.invoice_state import (
    StartedPayment,
    cancel_quietly,
    invoice_body,
    release,
    store_invoice,
    take_lease,
)
from payments.multicard.receipt import TIYIN, build_course_ofd
from payments.multicard.status_token import issue_status_token
from payments.multicard.transitions import PROVIDER
from payments.services import complete_payment


CHANNEL = 'web'


@dataclass(frozen=True)
class CourseOpened:
    course_slug: str
    already_owned: bool


def start_course_checkout(user, course_slug, language, client=None):
    reserved = _reserve(user, course_slug)
    if not isinstance(reserved, tuple):
        return reserved
    payment_id, stale_invoice, configuration = reserved
    client = client or MulticardClient(configuration)
    purchase = CoursePurchase.objects.get(payments__pk=payment_id)
    token = issue_status_token(payment_id)
    try:
        if stale_invoice:
            cancel_quietly(client, stale_invoice)
        invoice = client.create_invoice(invoice_body(
            configuration, payment_id, token, CHANNEL, language, purchase.amount * TIYIN,
            build_course_ofd(purchase.course_title, purchase.amount, configuration),
        ))
    except BaseException:
        release(payment_id)
        raise
    store_invoice(payment_id, invoice, CHANNEL, configuration)
    return StartedPayment(payment_id, invoice.checkout_url, token, replayed=False)


@transaction.atomic
def _reserve(user, course_slug):
    course = Course.objects.select_for_update().get(slug=course_slug)
    if owns_course(user, course):
        return CourseOpened(course.slug, already_owned=True)
    if not course.is_available_for_sale():
        raise PurchaseUnavailable()
    if course.price == 0:
        _, payment = open_course_purchase(user, course, 'free')
        complete_payment(payment.pk, 'free-{}'.format(payment.pk))
        return CourseOpened(course.slug, already_owned=False)
    # Checked before any row is written, so an unavailable payment leaves nothing behind.
    configuration = require_configuration()
    build_course_ofd(course.title_ru, course.price, configuration)
    _, payment = open_course_purchase(user, course, PROVIDER)
    replay, stale_invoice = take_lease(payment, CHANNEL)
    if replay is not None:
        return replay
    return payment.pk, stale_invoice, configuration
