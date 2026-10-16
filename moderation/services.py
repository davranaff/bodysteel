from django.db import IntegrityError, transaction
from django.utils import timezone

from moderation.models import ContentReport
from moderation.notify import notify_staff_about_report
from store.models import Review
from users.auth.errors import AuthProblem
from users.auth.rate_limits import RateLimitPolicy, consume


CONTENT_REPORT_USER = RateLimitPolicy('content_report_user', 10, 3600)
# Defence in depth on top of pre-moderation: a published review reported by
# this many different customers is hidden until staff look at it.
AUTO_HIDE_OPEN_REPORTS = 3


def create_report(reporter, values):
    """Persist a customer's content report and return it.

    Repeating an open report for the same review returns the existing row.
    """
    consume(CONTENT_REPORT_USER, str(reporter.pk), timezone.now())
    review_id = values.get('review_id')
    try:
        with transaction.atomic():
            review = _locked_review(review_id) if review_id is not None else None
            if review is not None:
                existing = ContentReport.objects.filter(
                    reporter=reporter, review=review, status=ContentReport.Status.OPEN,
                ).first()
                if existing is not None:
                    return existing
            report = ContentReport.objects.create(
                reporter=reporter,
                kind=values['kind'],
                review=review,
                reason=values['reason'],
                comment=values.get('comment', ''),
                excerpt=values.get('excerpt', ''),
                conversation_id=values.get('conversation_id'),
            )
            if review is not None:
                _hide_heavily_reported(review)
            transaction.on_commit(lambda: notify_staff_about_report(report))
            return report
    except IntegrityError:
        # A concurrent duplicate tap won the partial unique constraint.
        existing = ContentReport.objects.filter(
            reporter=reporter, review_id=review_id, status=ContentReport.Status.OPEN,
        ).first()
        if existing is None:
            raise
        return existing


def close_reports(queryset, status, staff_user):
    """Resolve or dismiss open reports from the admin."""
    return queryset.filter(status=ContentReport.Status.OPEN).update(
        status=status,
        resolved_by=staff_user,
        resolved_at=timezone.now(),
    )


def _locked_review(review_id):
    review = (
        Review.objects.select_for_update(of=('self',)).select_related('product')
        .filter(pk=review_id).first()
    )
    if review is None:
        raise AuthProblem(404, 'review_not_found', 'Review not found')
    return review


def _hide_heavily_reported(review):
    if not review.is_published:
        return
    reporters = (
        ContentReport.objects.filter(review=review, status=ContentReport.Status.OPEN)
        .values('reporter').distinct().count()
    )
    if reporters >= AUTO_HIDE_OPEN_REPORTS:
        review.is_published = False
        review.save(update_fields=['is_published'])
