from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import get_object_or_404

from store.models import Favorite, Basket
from users.models import User
from users.serializers.basket import BasketSerializer
from users.serializers.me import UserSerializer, GetFavoritesSerializer, CreateFavoritesSerializer
from users.serializers.signin import SigninSerializer
from users.serializers.signup import PhoneVerificationSerializer, SignUpSerializer
from users.utils.random_code import random_code


class Me(APIView):
    allowed_methods = ['get', 'put', 'delete', ]
    http_method_names = ['get', 'put', 'delete', ]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = get_object_or_404(User, phone=request.user.phone)
        serializer = UserSerializer(user).data
        return Response({'data': serializer})

    def put(self, request):
        user = get_object_or_404(User, phone=request.user.phone)
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.update(user, serializer.validated_data)
        return Response({'data': data}, status=status.HTTP_200_OK)

    def delete(self, request):
        user = get_object_or_404(User, phone=request.user.phone)
        user.code = random_code()
        return Response({'data': 'activate code!'}, status=status.HTTP_200_OK)


class SignUp(APIView):
    allowed_methods = ['post', ]
    http_method_names = ['post', ]

    def post(self, request):
        serializer = SignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        check = serializer.check(serializer.data)
        return Response({**check}, status=status.HTTP_200_OK)


class SignIn(APIView):
    allowed_methods = ['post', ]
    http_method_names = ['post', ]

    def post(self, request):
        serializer = SigninSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.check(serializer.data)
        return Response({**data}, status=status.HTTP_200_OK)


class SignOut(APIView):
    allowed_methods = ['put', ]
    http_method_names = ['put', ]

    def post(self, request):
        ...


class PhoneVerification(APIView):
    allowed_methods = ['post', ]
    http_method_names = ['post', ]

    def post(self, request):
        serializer = PhoneVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.create(serializer.data)
        if data.get("error"):
            return Response({**data}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_201_CREATED)


class FavoriteApi(APIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ['get', 'post', 'delete']

    def get(self, request):
        favorites = Favorite.objects.filter(user=request.user).select_related('product')
        serializer = GetFavoritesSerializer(favorites, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CreateFavoritesSerializer(
            data={'user_id': request.user.id, 'product_id': request.data['product_id']})
        serializer.is_valid(raise_exception=True)
        data = serializer.create(serializer.validated_data)
        return Response(data, status=status.HTTP_200_OK)


class BasketAPIView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ['get', 'post', 'put', 'delete']

    def get(self, request):
        basket = Basket.objects.filter(user=request.user).select_related('product')
        serializer = BasketSerializer(instance=basket, many=True).data
        return Response({'data': serializer}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = BasketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, product_id=request.data['product'])
        return Response({'data': serializer.data}, status=status.HTTP_201_CREATED)

    def put(self, request):
        instance = get_object_or_404(Basket, user=request.user, id=request.data['basket'])
        serializer = BasketSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.update(serializer.instance, serializer.validated_data)
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)

    def delete(self, request):

        if len(request.data.get('baskets', [])):
            Basket.objects.filter(user=request.user, id__in=request.data['baskets']).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        instance = get_object_or_404(Basket, user=request.user, id=request.data['basket'])
        instance.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
