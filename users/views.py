from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView

from users.serializers.signup import PhoneVerificationSerializer


class Me(APIView):
    http_method_names = ['get', 'put', 'delete', ]

    def get(self, request):
        ...

    def put(self, request):
        ...

    def delete(self, request):
        ...


class SignUp(APIView):
    http_method_names = ['post', ]

    def post(self, request):
        print(request)
        return Response({'message': 'Hello World!'}, status=200)


class SignIn(APIView):
    http_method_names = ['post', ]

    def post(self, request):
        ...


class SignOut(APIView):
    http_method_names = ['put', ]

    def post(self, request):
        ...


class PhoneVerification(APIView):
    http_method_names = ['post', ]

    def post(self, request):
        print(request.data)
        serializer = PhoneVerificationSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.create(serializer.data)
            return Response({'message': 'Success', 'data': data}, status=200)
        return Response({'error': 'Phone not valid!'}, status=500)


class CodeVerification(APIView):
    http_method_names = ['post', ]

    def post(self, request):
        print(request.data)
        return Response({'message': 'Hello World!'}, status=200)
