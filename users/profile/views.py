import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.auth.account_security import (
    change_password,
    delete_account,
    revoke_all_sessions,
    session_payload,
)
from users.auth.composition import contact_verification_service
from users.auth.client_ip import client_ip
from users.auth.errors import AuthProblem
from users.auth.presenter import user_payload
from users.auth.rate_limits import PASSWORD_CHANGE_USER, consume
from users.auth.models import AuthChallenge
from users.auth.serializers import (
    ChangePasswordSerializer,
    ContactVerificationCompleteSerializer,
    DeleteAccountSerializer,
    EmailChangeStartSerializer,
    PhoneChangeStartSerializer,
)
from users.models import User
from users.serializers.me import UserSerializer


class MeView(APIView):
    http_method_names = ['get', 'put', 'delete']
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'data': UserSerializer(request.user).data}, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return _problem(400, 'invalid_request', 'Invalid request')
        try:
            user = serializer.save()
        except IntegrityError:
            return _problem(409, 'account_exists', 'Account already exists')
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'data': user_payload(user, token)}, status=status.HTTP_200_OK)

    @swagger_auto_schema(responses={status.HTTP_204_NO_CONTENT: 'null'})
    def delete(self, request):
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            from customer_telegram.links import unlink_user
            unlink_user(user)
            suffix = uuid.uuid4().hex
            user.username = 'deleted_{}_{}'.format(user.pk, suffix[:16])[:100]
            user.email = 'deleted.{}.{}@invalid.bodysteel.local'.format(user.pk, suffix)
            user.phone = '+998{:09d}'.format((int(suffix[:12], 16) + user.pk) % 1_000_000_000)
            user.first_name = ''
            user.last_name = ''
            user.is_active = False
            user.is_staff = False
            user.is_superuser = False
            user.deleted_at = timezone.now()
            user.phone_verified_at = None
            user.email_verified_at = None
            user.set_unusable_password()
            user.save(update_fields=(
                'username', 'email', 'phone', 'first_name', 'last_name', 'is_active',
                'is_staff', 'is_superuser',
                'deleted_at', 'phone_verified_at', 'email_verified_at', 'password',
            ))
            Token.objects.filter(user=user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SignOutView(APIView):
    http_method_names = ['post']
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangePasswordView(APIView):
    http_method_names = ['put', 'post']
    permission_classes = [IsAuthenticated]

    def put(self, request):
        return self._change(request)

    def post(self, request):
        return self._change(request)

    @staticmethod
    def _change(request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return _problem(400, 'invalid_request', 'Invalid request')
        try:
            consume(PASSWORD_CHANGE_USER, str(request.user.pk), timezone.now())
            payload = change_password(
                request.user,
                serializer.validated_data['current_password'],
                serializer.validated_data['new_password'],
            )
        except AuthProblem as problem:
            return _problem(problem.status, problem.code, problem.message, problem.retry_after)
        return Response({'data': payload}, status=status.HTTP_200_OK)


class DeleteAccountView(APIView):
    http_method_names = ['post']
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeleteAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return _problem(400, 'invalid_request', 'Invalid request')
        try:
            delete_account(
                request.user,
                serializer.validated_data['password'],
                serializer.validated_data['confirmation'],
            )
        except AuthProblem as problem:
            return _problem(problem.status, problem.code, problem.message, problem.retry_after)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionsView(APIView):
    http_method_names = ['get']
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'data': session_payload(request)}, status=status.HTTP_200_OK)


class RevokeAllSessionsView(APIView):
    http_method_names = ['post']
    permission_classes = [IsAuthenticated]

    def post(self, request):
        revoke_all_sessions(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailChangeStartView(APIView):
    http_method_names = ['post']
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = EmailChangeStartSerializer(data=request.data)
        if not serializer.is_valid():
            return _problem(400, 'invalid_request', 'Invalid request')
        return _start_contact(request, AuthChallenge.Channel.EMAIL, serializer.validated_data['email'])


class PhoneChangeStartView(APIView):
    http_method_names = ['post']
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PhoneChangeStartSerializer(data=request.data)
        if not serializer.is_valid():
            return _problem(400, 'invalid_request', 'Invalid request')
        return _start_contact(request, AuthChallenge.Channel.SMS, serializer.validated_data['phone'])


class ContactVerificationCompleteView(APIView):
    http_method_names = ['post']
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ContactVerificationCompleteSerializer(data=request.data)
        if not serializer.is_valid():
            return _problem(400, 'invalid_request', 'Invalid request')
        try:
            payload = contact_verification_service().complete(
                request.user,
                serializer.validated_data['challenge_id'],
                serializer.validated_data['code'],
            )
        except IntegrityError:
            return _problem(409, 'contact_exists', 'Contact is already in use')
        except AuthProblem as problem:
            return _problem(problem.status, problem.code, problem.message, problem.retry_after)
        return Response({'data': payload}, status=status.HTTP_200_OK)


def _start_contact(request, channel, identifier):
    try:
        receipt = contact_verification_service().start(
            request.user, channel, identifier, client_ip(request),
        )
    except AuthProblem as problem:
        return _problem(problem.status, problem.code, problem.message, problem.retry_after)
    return Response({'data': {
        'challenge_id': str(receipt.challenge_id),
        'expires_in': receipt.expires_in,
        'resend_after': receipt.resend_after,
    }}, status=status.HTTP_201_CREATED, headers={'Cache-Control': 'no-store'})


def _problem(status_code, code, message, retry_after=None):
    error = {'code': code, 'message': message}
    headers = {'Cache-Control': 'no-store'}
    if retry_after is not None:
        error['retry_after'] = retry_after
        headers['Retry-After'] = str(retry_after)
    return Response({'error': error}, status=status_code, headers=headers)
