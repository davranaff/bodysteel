import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Course
from courses.serializers import EmptyInputSerializer, language_from_request
from courses.services import PurchaseUnavailable
from payments.multicard.client import MulticardRejected, MulticardUnavailable
from payments.multicard.configuration import MulticardNotConfigured
from payments.multicard.course_checkout import CourseOpened, start_course_checkout
from payments.multicard.invoice_state import PaymentNotPayable


logger = logging.getLogger(__name__)


def _problem(http_status, detail, code):
    return Response({'detail': detail, 'error': {'code': code}}, status=http_status)


class CourseCheckoutAPIView(APIView):
    """Website course checkout: a Multicard link, or the course itself when it is free or owned."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        serializer = EmptyInputSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            outcome = start_course_checkout(request.user, slug, language_from_request(request))
        except Course.DoesNotExist:
            return _problem(status.HTTP_404_NOT_FOUND, 'Course not found', 'not_found')
        except PurchaseUnavailable:
            return _problem(status.HTTP_409_CONFLICT, 'Course is not on sale', 'not_on_sale')
        except PaymentNotPayable as error:
            return _problem(status.HTTP_409_CONFLICT, 'Course payment is already starting', error.code)
        except MulticardNotConfigured:
            return _problem(status.HTTP_503_SERVICE_UNAVAILABLE, 'Online payment is unavailable', 'payment_unavailable')
        except MulticardRejected as error:
            logger.warning('Multicard rejected a course invoice', extra={'course': slug, 'code': error.code})
            return _problem(status.HTTP_502_BAD_GATEWAY, 'Payment provider rejected the request', 'provider_rejected')
        except MulticardUnavailable:
            return _problem(status.HTTP_503_SERVICE_UNAVAILABLE, 'Online payment is unavailable', 'payment_unavailable')
        if isinstance(outcome, CourseOpened):
            return Response(
                {'data': {'status': 'owned' if outcome.already_owned else 'opened', 'course_slug': outcome.course_slug}},
                status=status.HTTP_200_OK if outcome.already_owned else status.HTTP_201_CREATED,
            )
        return Response({'data': {
            'status': 'payment',
            'course_slug': slug,
            'payment_id': outcome.payment_id,
            'checkout_url': outcome.checkout_url,
            'status_token': outcome.status_token,
            'replayed': outcome.replayed,
        }}, status=status.HTTP_200_OK if outcome.replayed else status.HTTP_201_CREATED)
