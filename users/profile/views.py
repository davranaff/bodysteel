from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User
from users.serializers.me import UserSerializer


class MeView(APIView):
    http_method_names = ['get', 'put', 'delete']
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(responses={status.HTTP_200_OK: UserSerializer()})
    def get(self, request):
        user = get_object_or_404(User, phone=request.user.phone)
        return Response({'data': UserSerializer(user).data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(responses={status.HTTP_200_OK: UserSerializer()})
    def put(self, request):
        user = get_object_or_404(User, phone=request.user.phone)
        serializer = UserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        payload = serializer.update(user, serializer.validated_data)
        return Response({'data': payload}, status=status.HTTP_200_OK)

    @swagger_auto_schema(responses={status.HTTP_204_NO_CONTENT: 'null'})
    def delete(self, request):
        user = get_object_or_404(User, phone=request.user.phone)
        Token.objects.filter(user=user).delete()
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SignOutView(APIView):
    http_method_names = ['post']
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
