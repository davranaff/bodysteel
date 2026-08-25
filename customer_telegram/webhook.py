import hmac
import json
import logging

from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from customer_telegram.configuration import (
    CustomerTelegramConfigurationError,
    customer_telegram_enabled,
    require_configuration,
)
from customer_telegram.handlers import handle_update
from customer_telegram.models import CustomerTelegramUpdate
from customer_telegram.security import valid_telegram_id, valid_update_id
from users.auth.errors import AuthProblem
from users.auth.rate_limits import (
    CUSTOMER_TELEGRAM_UPDATE,
    CUSTOMER_TELEGRAM_USER,
    consume,
)


logger = logging.getLogger(__name__)
MAXIMUM_WEBHOOK_BYTES = 64 * 1024


@csrf_exempt
def customer_telegram_webhook(request):
    if not customer_telegram_enabled():
        return HttpResponse(status=404)
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        configuration = require_configuration()
    except CustomerTelegramConfigurationError:
        return HttpResponse(status=503)
    supplied = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not isinstance(supplied, str) or not hmac.compare_digest(
        supplied, configuration.webhook_secret,
    ):
        return HttpResponse(status=403)
    content_type = request.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
    if content_type != 'application/json':
        return HttpResponse(status=415)
    length = request.headers.get('Content-Length', '')
    if length.isdigit() and int(length) > MAXIMUM_WEBHOOK_BYTES:
        return HttpResponse(status=413)
    body = request.body
    if len(body) > MAXIMUM_WEBHOOK_BYTES:
        return HttpResponse(status=413)
    try:
        payload = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'detail': 'Invalid update'}, status=400)
    if not isinstance(payload, dict) or not valid_update_id(payload.get('update_id')):
        return JsonResponse({'detail': 'Invalid update'}, status=400)
    update_type = _update_type(payload)
    if update_type is None:
        return HttpResponse(status=200)
    record = _claim_update(payload['update_id'], update_type)
    if record is None:
        return HttpResponse(status=200)
    try:
        _apply_rate_limits(payload, update_type)
        handle_update(payload)
    except AuthProblem as problem:
        failure_code = 'rate_limited' if problem.status == 429 else 'security_rejected'
        CustomerTelegramUpdate.objects.filter(pk=record.pk).update(
            status='failed', failure_code=failure_code, processed_at=timezone.now(),
        )
        return HttpResponse(status=200)
    except Exception:
        logger.error('Customer Telegram update processing failed', extra={'update_record_id': record.pk})
        CustomerTelegramUpdate.objects.filter(pk=record.pk).update(
            status='failed', failure_code='processing_error', processed_at=timezone.now(),
        )
        return HttpResponse(status=200)
    CustomerTelegramUpdate.objects.filter(pk=record.pk).update(
        status='processed', processed_at=timezone.now(),
    )
    return HttpResponse(status=200)


def _claim_update(update_id, update_type):
    try:
        with transaction.atomic():
            record, created = CustomerTelegramUpdate.objects.get_or_create(
                update_id=update_id,
                defaults={'update_type': update_type},
            )
    except IntegrityError:
        return None
    return record if created else None


def _update_type(payload):
    present = [name for name in ('message', 'callback_query') if name in payload]
    if len(present) != 1 or not isinstance(payload[present[0]], dict):
        return None
    return present[0]


def _apply_rate_limits(payload, update_type):
    now = timezone.now()
    update_id = payload['update_id']
    consume(CUSTOMER_TELEGRAM_UPDATE, str(update_id), now)
    update = payload[update_type]
    sender = update.get('from') if update_type == 'message' else update.get('from')
    sender_id = sender.get('id') if isinstance(sender, dict) else None
    if valid_telegram_id(sender_id):
        consume(CUSTOMER_TELEGRAM_USER, str(sender_id), now)
