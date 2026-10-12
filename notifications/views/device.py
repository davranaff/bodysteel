import json

from django.core.exceptions import RequestDataTooBig
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from notifications.configuration import PushNotConfigured
from notifications.models import PushDevice
from notifications.serializers.device import DeviceSerializer
from notifications.services.devices import device_payload, register_device, unregister_device
from users.auth.errors import AuthProblem
from users.auth.http_boundary import require_storefront_proxy
from users.auth.language import require_language
from users.auth.responses import problem_response, success_response

MAX_BODY_BYTES = 16 * 1024


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key')
        value[key] = item
    return value


def _invalid_constant(value):
    raise ValueError('Non-standard JSON constant')


def _request_body(request):
    if request.query_params:
        raise AuthProblem(400, 'invalid_request', 'Query parameters are not supported')
    length = request.headers.get('Content-Length', '')
    if length and (not length.isdigit() or len(length) > 10 or int(length) > MAX_BODY_BYTES):
        raise AuthProblem(413, 'payload_too_large', 'Request body is too large')
    try:
        body = request.body
    except RequestDataTooBig:
        raise AuthProblem(413, 'payload_too_large', 'Request body is too large') from None
    if len(body) > MAX_BODY_BYTES:
        raise AuthProblem(413, 'payload_too_large', 'Request body is too large')
    if request.method != 'PUT':
        if body:
            raise AuthProblem(400, 'invalid_request', 'Empty request required')
        return None
    if request.content_type != 'application/json':
        raise AuthProblem(415, 'invalid_content_type', 'JSON required')
    try:
        return json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
        raise AuthProblem(400, 'invalid_request', 'Invalid JSON') from None


class PushDeviceView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'put', 'delete']

    def _call(self, request, operation):
        language = None
        try:
            require_storefront_proxy(request)
            language = require_language(request)
            body = _request_body(request)
            return operation(language, body)
        except AuthProblem as problem:
            return problem_response(problem, language)
        except PushNotConfigured:
            return problem_response(AuthProblem(503, 'push_not_configured', 'Push service unavailable'), language)

    def get(self, request, installation_id):
        def operation(language, body):
            device = PushDevice.objects.filter(user=request.user, installation_id=installation_id).first()
            if not device:
                raise AuthProblem(404, 'device_not_found', 'Device not found')
            return success_response(device_payload(device), 200, language)
        return self._call(request, operation)

    def put(self, request, installation_id):
        def operation(language, body):
            serializer = DeviceSerializer(data=body)
            if not serializer.is_valid():
                raise AuthProblem(400, 'invalid_request', 'Invalid device registration')
            result = register_device(request.user, request.auth, installation_id, serializer.validated_data, language)
            return success_response(result, 200, language)
        return self._call(request, operation)

    def delete(self, request, installation_id):
        def operation(language, body):
            unregister_device(request.user, installation_id)
            return success_response(None, 204, language)
        return self._call(request, operation)
