from django.shortcuts import render
from rest_framework.views import APIView


class Me(APIView):
    http_method_names = ['get', 'put', 'delete',]

    def get(self, request):
        ...

    def put(self, request):
        ...

    def delete(self, request):
        ...


class SignUp(APIView):
    http_method_names = ['post',]

    def post(self, request):
        ...


class SignIn(APIView):
    http_method_names = ['post',]

    def post(self, request):
        ...


class SignOut(APIView):
    http_method_names = ['put',]

    def post(self, request):
        ...
