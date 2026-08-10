import base64
import hmac
import json

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from integration.regos.config import RegosSyncError
from integration.regos.sync import apply_records, records_from_to_server, sync_from_regos


MAX_BODY_BYTES = 1 * 1024 * 1024
REQUEST_ID_LIMIT = 128


@method_decorator(csrf_exempt, name='dispatch')
class RegosToServerView(View):
    """JSON-RPC 2.0 receiver for the REGOS Store Management To Server export."""

    http_method_names = ['post']

    def post(self, request):
        if not _is_authorized(request.headers.get('Authorization', '')):
            response = JsonResponse({'jsonrpc': '2.0', 'error': {'code': -32600, 'message': 'Unauthorized'}, 'id': None}, status=401)
            response['WWW-Authenticate'] = 'Basic realm="BodySteel REGOS"'
            return response
        media_type = request.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
        if media_type != 'application/json':
            return _error(None, -32600, 'Content-Type must be application/json', status=415)
        try:
            body = request.body
        except RequestDataTooBig:
            return _error(None, -32600, 'Request body is too large', status=413)
        if not body or len(body) > MAX_BODY_BYTES:
            return _error(None, -32600, 'Request body is too large', status=413 if body else 400)
        try:
            payload = json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return _error(None, -32700, 'Parse error')
        if not isinstance(payload, dict):
            return _error(None, -32600, 'Invalid Request')
        request_id = payload.get('id')
        if not _valid_request_id(request_id):
            return _error(None, -32600, 'Invalid Request')
        params = payload.get('params', payload)
        if not isinstance(params, (dict, list)):
            return _error(request_id, -32602, 'Invalid params')
        records = records_from_to_server(params)
        result = apply_records(records, source='REGOS To Server')
        return JsonResponse({
            'jsonrpc': '2.0',
            'id': request_id,
            'result': {
                'received': result.received,
                'updated': result.updated,
                'unmatched': result.unmatched,
                'invalid': result.invalid,
            },
        })


@method_decorator(csrf_exempt, name='dispatch')
class RegosWebhookView(View):
    """Receiver for REGOS local-integration ``HandleWebhook`` callbacks.

    REGOS webhook data describes the changed document, not the authoritative
    available balance.  Therefore every accepted callback performs a fresh
    Item/GetExt read and applies its ``allowed`` quantity.
    """

    http_method_names = ['post']

    def post(self, request):
        media_type = request.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
        if media_type != 'application/json':
            return _error(None, -32600, 'Content-Type must be application/json', status=415)
        try:
            body = request.body
        except RequestDataTooBig:
            return _error(None, -32600, 'Request body is too large', status=413)
        if not body or len(body) > MAX_BODY_BYTES:
            return _error(None, -32600, 'Request body is too large', status=413 if body else 400)
        try:
            payload = json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return _error(None, -32700, 'Parse error')
        if not isinstance(payload, dict):
            return _error(None, -32600, 'Invalid Request')
        connected_integration_id = payload.get('connected_integration_id')
        if (
            payload.get('action') != 'HandleWebhook'
            or not isinstance(payload.get('event_id'), str)
            or not isinstance(payload.get('data'), dict)
            or not _is_connected_integration(connected_integration_id)
        ):
            return _error(None, -32600, 'Invalid Request', status=401)
        try:
            result = sync_from_regos()
        except RegosSyncError:
            # A non-2xx response lets REGOS retry a transient failed callback.
            return JsonResponse({'ok': False, 'error': 'Inventory synchronization failed'}, status=503)
        return JsonResponse({
            'ok': True,
            'result': {
                'received': result.received,
                'updated': result.updated,
                'unmatched': result.unmatched,
                'invalid': result.invalid,
            },
        })


def _is_authorized(header):
    username = getattr(settings, 'REGOS_TO_SERVER_USERNAME', '')
    password = getattr(settings, 'REGOS_TO_SERVER_PASSWORD', '')
    if not username or not password or len(header) > 1024 or not header.startswith('Basic '):
        return False
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode('utf-8')
    except (ValueError, UnicodeDecodeError):
        return False
    presented_username, separator, presented_password = decoded.partition(':')
    return bool(separator) and hmac.compare_digest(presented_username, username) and hmac.compare_digest(presented_password, password)


def _is_connected_integration(value):
    expected = getattr(settings, 'REGOS_CONNECTED_INTEGRATION_ID', '')
    return (
        bool(expected)
        and isinstance(value, (str, int))
        and len(str(value)) <= 1024
        and hmac.compare_digest(str(value), str(expected))
    )


def _valid_request_id(value):
    return value is None or (
        isinstance(value, (str, int)) and not isinstance(value, bool)
        and (not isinstance(value, str) or 1 <= len(value) <= REQUEST_ID_LIMIT)
    )


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key')
        value[key] = item
    return value


def _error(request_id, code, message, status=400):
    return JsonResponse({'jsonrpc': '2.0', 'error': {'code': code, 'message': message}, 'id': request_id}, status=status)
