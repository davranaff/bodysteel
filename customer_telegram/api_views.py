from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from customer_telegram.configuration import (
    CustomerTelegramConfigurationError,
    require_configuration,
)
from customer_telegram.links import (
    start_account_link,
    start_password_reset,
    start_registration,
    unlink_user,
)
from customer_telegram.models import CustomerTelegramChat
from users.auth.client_ip import client_ip
from users.auth.errors import AuthProblem
from users.auth.http_boundary import require_storefront_proxy
from users.auth.language import require_language
from users.auth.responses import problem_response, success_response
from users.auth.serializers import PasswordResetRequestSerializer, StartRegistrationSerializer


class TelegramStorefrontView(APIView):
    authentication_classes = []
    permission_classes = []
    http_method_names = ['post']

    def execute(self, request, operation):
        language = None
        try:
            require_configuration()
            require_storefront_proxy(request)
            language = require_language(request)
            return operation(language)
        except AuthProblem as problem:
            return problem_response(problem, language)
        except CustomerTelegramConfigurationError:
            return problem_response(
                AuthProblem(503, 'telegram_unavailable', 'Telegram verification is unavailable'),
                language,
            )

    @staticmethod
    def validated(serializer_class, payload):
        serializer = serializer_class(data=payload)
        if not serializer.is_valid():
            raise AuthProblem(400, 'invalid_request', 'Invalid request')
        return serializer.validated_data


class TelegramRegistrationStartView(TelegramStorefrontView):
    def post(self, request):
        def operation(language):
            values = self.validated(StartRegistrationSerializer, request.data)
            receipt = start_registration(values, client_ip(request), language)
            return success_response(_receipt_payload(receipt), 201, language)

        return self.execute(request, operation)


class TelegramPasswordResetStartView(TelegramStorefrontView):
    def post(self, request):
        def operation(language):
            values = self.validated(PasswordResetRequestSerializer, request.data)
            receipt = start_password_reset(values['identifier'], client_ip(request), language)
            return success_response(_receipt_payload(receipt), 202, language)

        return self.execute(request, operation)


class TelegramAccountView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get']

    def get(self, request):
        chat = CustomerTelegramChat.objects.filter(user=request.user).first()
        return Response({'data': {
            'connected': bool(chat and chat.is_active),
            'notifications': bool(chat and chat.is_active and chat.marketing_opt_in),
        }}, headers={'Cache-Control': 'no-store'})


class TelegramAccountLinkStartView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ['post']

    def post(self, request):
        try:
            require_configuration()
            language = require_language(request)
            receipt = start_account_link(request.user, language)
        except AuthProblem as problem:
            return problem_response(problem)
        except CustomerTelegramConfigurationError:
            return problem_response(
                AuthProblem(503, 'telegram_unavailable', 'Telegram verification is unavailable'),
            )
        return success_response({
            'expires_in': receipt.expires_in,
            'telegram_url': receipt.telegram_url,
        }, 201, language)


class TelegramAccountUnlinkView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ['post']

    def post(self, request):
        unlink_user(request.user)
        return Response(status=204, headers={'Cache-Control': 'no-store'})


def _receipt_payload(receipt):
    return {
        'challenge_id': receipt.challenge_id,
        'expires_in': receipt.expires_in,
        'resend_after': receipt.resend_after,
        'telegram_url': receipt.telegram_url,
    }
