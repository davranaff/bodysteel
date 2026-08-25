import hashlib
import hmac
import json

from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import Payment, PaymentEvent
from payments.serializers import EmptyPaymentInputSerializer, PaymentSerializer
from payments.services import complete_payment


def payment_owner(payment, user):
    if payment.course_purchase_id:
        return payment.course_purchase.user_id == user.pk
    return payment.order_id and payment.order.user_id == user.pk


class PaymentStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        payment = Payment.objects.select_related('order', 'course_purchase__user').filter(pk=pk).first()
        if not payment:
            return Response({'detail': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        if not request.user.is_staff and not payment_owner(payment, request.user):
            return Response({'detail': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'data': PaymentSerializer(payment).data})


class PaymentManualCompleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = EmptyPaymentInputSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        payment = Payment.objects.select_related('order', 'course_purchase__user').filter(pk=pk).first()
        if not payment:
            return Response({'detail': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        if not settings.DEBUG and not request.user.is_staff:
            return Response({'detail': 'Manual payments are disabled'}, status=status.HTTP_403_FORBIDDEN)
        if not request.user.is_staff and not payment_owner(payment, request.user):
            return Response({'detail': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        completed = complete_payment(payment.pk, 'manual-{}'.format(payment.pk))
        return Response({'data': PaymentSerializer(completed).data}, status=status.HTTP_200_OK)


class PaymentWebhookAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, provider):
        raw = request.body
        if len(raw) > 64 * 1024:
            return Response({'detail': 'Webhook body is too large'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        signature = request.headers.get('X-Payment-Signature', '')
        secret = getattr(settings, 'PAYMENT_WEBHOOK_SECRET', '')
        expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest() if secret else ''
        if not secret or not hmac.compare_digest(signature, expected):
            return Response({'detail': 'Invalid webhook signature'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response({'detail': 'Invalid webhook body'}, status=status.HTTP_400_BAD_REQUEST)
        required = {'event_id', 'payment_id', 'status'}
        allowed = required | {'provider_payment_id'}
        if set(payload) - allowed or not required.issubset(payload):
            return Response({'detail': 'Invalid webhook body'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(payload['event_id'], str) or not 1 <= len(payload['event_id']) <= 255:
            return Response({'detail': 'Invalid webhook body'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(payload['payment_id'], int) or payload['payment_id'] < 1:
            return Response({'detail': 'Invalid webhook body'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(payload['status'], str) or len(payload['status']) > 32:
            return Response({'detail': 'Invalid webhook body'}, status=status.HTTP_400_BAD_REQUEST)
        if payload['status'] != 'succeeded':
            return Response({'data': {'accepted': True}}, status=status.HTTP_200_OK)
        payment = Payment.objects.filter(pk=payload['payment_id'], provider=provider).first()
        if not payment:
            return Response({'detail': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        payload_hash = hashlib.sha256(raw).hexdigest()
        try:
            with transaction.atomic():
                event = PaymentEvent.objects.create(
                    payment=payment,
                    provider=provider,
                    external_event_id=str(payload['event_id']),
                    event_type='succeeded',
                    payload_hash=payload_hash,
                    processing_status='received',
                )
        except IntegrityError:
            return Response({'data': {'accepted': True, 'replayed': True}}, status=status.HTTP_200_OK)
        complete_payment(payment.pk, payload.get('provider_payment_id'))
        event.processing_status = 'processed'
        event.save(update_fields=('processing_status',))
        return Response({'data': {'accepted': True}}, status=status.HTTP_200_OK)
