import hashlib
import json
import logging

from django.conf import settings
from django.core.cache import cache
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import Payment
from payments.multicard.callbacks import parse_callback, parse_webhook
from payments.multicard.checkout import (
    CHANNELS,
    PaymentNotFound,
    PaymentNotPayable,
    payment_id_from_invoice,
    start_order_payment,
)
from payments.multicard.client import MulticardClient, MulticardRejected, MulticardUnavailable
from payments.multicard.configuration import MulticardNotConfigured, multicard_enabled, require_configuration
from payments.multicard.signatures import verify_callback_signature, verify_webhook_signature
from payments.multicard.status_token import read_status_token
from payments.multicard.transitions import apply_invoice_state, record_failure, record_refund, record_success
from users.auth.client_ip import client_ip


logger = logging.getLogger(__name__)
MAXIMUM_CALLBACK_BYTES = 16 * 1024
POLL_INTERVAL_SECONDS = 4
PUBLIC_STATUS = {
    Payment.CREATED: 'pending',
    Payment.PENDING: 'pending',
    Payment.SUCCEEDED: 'paid',
    Payment.FAILED: 'failed',
    Payment.CANCELLED: 'cancelled',
    Payment.REFUNDED: 'refunded',
}


def _problem(http_status, detail, code):
    return Response({'detail': detail, 'error': {'code': code}}, status=http_status)


class PaymentStartInputSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=CHANNELS)
    order_key = serializers.RegexField(r'^[A-Za-z0-9._:-]{16,128}$', required=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({'non_field_errors': ['Unknown payment request field']})
        return super().to_internal_value(data)


class PaymentMethodsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'data': {'multicard': multicard_enabled()}})


class MulticardOrderPaymentAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, order_id):
        serializer = PaymentStartInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        language = 'uz' if request.headers.get('Accept-Language', '').lower().startswith('uz') else 'ru'
        try:
            started = start_order_payment(
                order_id, request.user, serializer.validated_data.get('order_key'),
                serializer.validated_data['channel'], language,
            )
        except PaymentNotFound:
            return _problem(status.HTTP_404_NOT_FOUND, 'Order not found', 'not_found')
        except PaymentNotPayable as error:
            return _problem(status.HTTP_409_CONFLICT, 'Order cannot be paid online', error.code)
        except MulticardNotConfigured:
            return _problem(status.HTTP_503_SERVICE_UNAVAILABLE, 'Online payment is unavailable', 'payment_unavailable')
        except MulticardRejected as error:
            logger.warning('Multicard rejected an invoice', extra={'order_id': order_id, 'code': error.code})
            return _problem(status.HTTP_502_BAD_GATEWAY, 'Payment provider rejected the request', 'provider_rejected')
        except MulticardUnavailable:
            return _problem(status.HTTP_503_SERVICE_UNAVAILABLE, 'Online payment is unavailable', 'payment_unavailable')
        return Response({'data': {
            'payment_id': started.payment_id,
            'checkout_url': started.checkout_url,
            'status_token': started.status_token,
            'replayed': started.replayed,
        }}, status=status.HTTP_200_OK if started.replayed else status.HTTP_201_CREATED)


class MulticardPaymentStatusAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        payment_id = read_status_token(token)
        payment = Payment.objects.select_related('order').filter(pk=payment_id, order__isnull=False).first()
        if payment is None:
            return _problem(status.HTTP_404_NOT_FOUND, 'Payment not found', 'not_found')
        if payment.provider == 'multicard' and payment.status == Payment.PENDING:
            _reconcile(payment)
            payment.refresh_from_db()
            payment.order.refresh_from_db(fields=('payment_status',))
        return Response({'data': {
            'payment_id': payment.pk,
            'order_id': str(payment.order_id),
            'order_code': payment.order.order_code,
            'amount': payment.amount,
            'currency': payment.currency,
            'status': PUBLIC_STATUS.get(payment.status, 'pending'),
            'paid_at': payment.paid_at.isoformat() if payment.paid_at else None,
        }}, headers={'Cache-Control': 'no-store'})


def _reconcile(payment):
    """Ask Multicard directly when the callback has not been processed yet."""
    invoice_uuid = (payment.metadata.get('multicard') or {}).get('invoice_uuid')
    if not invoice_uuid or not cache.add('payments:multicard:poll:{}'.format(payment.pk), 1, POLL_INTERVAL_SECONDS):
        return
    try:
        invoice = MulticardClient(require_configuration()).get_invoice(invoice_uuid)
    except (MulticardNotConfigured, MulticardRejected, MulticardUnavailable, ValueError):
        return
    apply_invoice_state(payment.pk, invoice)


class _CallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def _read(self, request):
        raw = request.body
        if len(raw) > MAXIMUM_CALLBACK_BYTES:
            return None, None
        allowed_ips = getattr(settings, 'MULTICARD_CALLBACK_ALLOWED_IPS', ())
        if allowed_ips and client_ip(request) not in allowed_ips:
            return None, None
        try:
            return raw, json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return None, None


class MulticardCallbackAPIView(_CallbackView):
    """Success callback. Any answer except ``200 {"success": true}`` refunds the shopper."""

    def post(self, request):
        raw, payload = self._read(request)
        callback = parse_callback(payload)
        try:
            configuration = require_configuration()
        except MulticardNotConfigured:
            return Response({'success': False, 'message': 'Оплата временно недоступна'}, status=503)
        if callback is None or not verify_callback_signature(callback, configuration.secret):
            return Response({'success': False, 'message': 'Неверная подпись'}, status=status.HTTP_400_BAD_REQUEST)
        if str(callback['store_id']) != configuration.store_id:
            return Response({'success': False, 'message': 'Неверная касса'}, status=status.HTTP_400_BAD_REQUEST)
        payment_id = payment_id_from_invoice(callback['invoice_id'])
        outcome = record_success(
            payment_id, callback['uuid'], callback['amount'],
            'callback:{}'.format(callback['uuid']), hashlib.sha256(raw).hexdigest(),
        ) if payment_id else None
        if outcome is None or not outcome.accepted:
            message = outcome.message if outcome else 'Счёт не найден'
            logger.warning('Multicard callback refused', extra={'payment_id': payment_id, 'reason': message})
            return Response({'success': False, 'message': message}, status=status.HTTP_200_OK)
        return Response({'success': True}, status=status.HTTP_200_OK)


class MulticardWebhookAPIView(_CallbackView):
    """Optional per-status webhooks (draft/progress/success/error/revert)."""

    def post(self, request):
        raw, payload = self._read(request)
        webhook = parse_webhook(payload)
        try:
            configuration = require_configuration()
        except MulticardNotConfigured:
            return Response({'success': False}, status=503)
        if webhook is None or not verify_webhook_signature(webhook, configuration.secret):
            return Response({'success': False}, status=status.HTTP_400_BAD_REQUEST)
        payment_id = payment_id_from_invoice(webhook['invoice_id'])
        if payment_id:
            event_id = 'webhook:{}:{}'.format(webhook['uuid'], webhook['status'])
            payload_hash = hashlib.sha256(raw).hexdigest()
            if webhook['status'] == 'success':
                record_success(payment_id, webhook['uuid'], webhook['amount'], event_id, payload_hash)
            elif webhook['status'] == 'error':
                record_failure(payment_id, webhook['uuid'], event_id, payload_hash)
            elif webhook['status'] == 'revert':
                record_refund(payment_id, webhook['uuid'], event_id, payload_hash)
        return Response({'success': True}, status=status.HTTP_200_OK)
