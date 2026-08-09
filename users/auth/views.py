from rest_framework.views import APIView

from users.auth.client_ip import client_ip
from users.auth.composition import (
    registration_completion_service,
    registration_start_service,
    sign_in_service,
)
from users.auth.errors import AuthProblem
from users.auth.http_boundary import require_storefront_proxy
from users.auth.language import require_language
from users.auth.responses import problem_response, success_response
from users.auth.serializers import (
    CompleteRegistrationSerializer,
    SignInSerializer,
    StartRegistrationSerializer,
)


class StorefrontAuthView(APIView):
    authentication_classes = []
    permission_classes = []
    http_method_names = ['post']

    def execute(self, request, operation):
        language = None
        try:
            require_storefront_proxy(request)
            language = require_language(request)
            return operation(language)
        except AuthProblem as problem:
            return problem_response(problem, language)

    @staticmethod
    def validated(serializer_class, payload):
        serializer = serializer_class(data=payload)
        if not serializer.is_valid():
            raise AuthProblem(400, 'invalid_request', 'Invalid request')
        return serializer.validated_data


class PhoneVerificationView(StorefrontAuthView):
    def post(self, request):
        def operation(language):
            values = self.validated(StartRegistrationSerializer, request.data)
            receipt = registration_start_service().start(
                values['email'], values['phone'], client_ip(request),
            )
            return success_response({
                'challenge_id': str(receipt.challenge_id),
                'expires_in': receipt.expires_in,
                'resend_after': receipt.resend_after,
            }, 201, language)

        return self.execute(request, operation)


class SignUpView(StorefrontAuthView):
    def post(self, request):
        def operation(language):
            values = self.validated(CompleteRegistrationSerializer, request.data)
            user = registration_completion_service().complete(
                values['challenge_id'], values['code'], values['password'],
            )
            return success_response(user, 201, language)

        return self.execute(request, operation)


class SignInView(StorefrontAuthView):
    def post(self, request):
        def operation(language):
            values = self.validated(SignInSerializer, request.data)
            user = sign_in_service().sign_in(
                values['phone'], values['password'], client_ip(request),
            )
            return success_response(user, 200, language)

        return self.execute(request, operation)
