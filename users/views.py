from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import get_object_or_404

from store.models import Favorite, Basket, Order
from store.serializers.review import ReviewSerializer
from users.models import User
from users.serializers.basket import BasketSerializer, CreateBasketsListSerializer
from users.serializers.me import UserSerializer
from users.serializers.favorites import GetFavoritesSerializer, CreateFavoritesSerializer, CreateFavoritesListSerializer
from users.serializers.order import OrderSerializer, OrderCreateSerializer
from users.serializers.signin import SigninSerializer
from users.serializers.signup import PhoneVerificationSerializer, SignUpSerializer
from users.utils.random_code import random_code

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from django.db.models import Sum


class Me(APIView):
    allowed_methods = ['get', 'put', 'delete', ]
    http_method_names = ['get', 'put', 'delete', ]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(manual_parameters=[], responses={status.HTTP_200_OK: UserSerializer()},
                         operation_description='Чтобы получить данные от своего пользователя')
    def get(self, request):
        user = get_object_or_404(User, phone=request.user.phone)
        serializer = UserSerializer(user).data
        return Response({'data': serializer}, status=status.HTTP_200_OK)

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: UserSerializer()})
    def put(self, request):
        user = get_object_or_404(User, phone=request.user.phone)
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.update(user, serializer.validated_data)
        return Response({'data': data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(manual_parameters=[], responses={status.HTTP_204_NO_CONTENT: 'null'})
    def delete(self, request):
        user = get_object_or_404(User, phone=request.user.phone)
        user.code = random_code()
        return Response({'data': 'activate code!'}, status=status.HTTP_204_NO_CONTENT)


class SignUp(APIView):
    allowed_methods = ['post', ]
    http_method_names = ['post', ]

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: openapi.Response(description='', examples={'data': {
                             "id": 'integer',
                             "username": 'string',
                             "phone": 'string',
                             'token': 'string'
                         }})})
    def post(self, request):
        serializer = SignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        check = serializer.check(serializer.data)
        return Response({**check}, status=status.HTTP_200_OK)


class SignIn(APIView):
    allowed_methods = ['post', ]
    http_method_names = ['post', ]

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: openapi.Response(description='', examples={'data': {
                             "id": 'integer',
                             "username": 'string',
                             "phone": 'string',
                             'token': 'string'
                         }})})
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

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: openapi.Response(description='', examples={'data': {
                             "id": 'integer',
                             "username": 'string',
                             "phone": 'string',
                             'token': 'string'
                         }})})
    def post(self, request):
        serializer = PhoneVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.create(serializer.data)
        if data.get("error"):
            return Response({**data}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_201_CREATED)


class FavoriteApi(APIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ['get', 'post']

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: GetFavoritesSerializer(many=True)})
    def get(self, request):
        favorites = Favorite.objects.filter(user=request.user).select_related('product')
        serializer = GetFavoritesSerializer(favorites, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: CreateFavoritesSerializer()})
    def post(self, request):
        serializer = CreateFavoritesSerializer(
            data={'user_id': request.user.id, 'product_id': request.data['product_id']})
        serializer.is_valid(raise_exception=True)
        data = serializer.create(serializer.validated_data)
        return Response(data, status=status.HTTP_200_OK)


class CreateFavoritesView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ['post']

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_201_CREATED: openapi.Response(description='', examples={'data': {
                             "products": 'array<integer>',
                         }})})
    def post(self, request):
        serializer = CreateFavoritesListSerializer(
            data={'user_id': request.user.id, 'products': request.data['products']})
        serializer.is_valid(raise_exception=True)
        data = serializer.create(serializer.validated_data)
        return Response(data, status=status.HTTP_201_CREATED)


class BasketAPIView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ['get', 'post', 'put', 'delete']

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: BasketSerializer(many=True)})
    def get(self, request):
        basket = Basket.objects.filter(user=request.user, order__isnull=True).select_related('product')
        serializer = BasketSerializer(instance=basket, many=True).data
        return Response({'data': serializer}, status=status.HTTP_200_OK)

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: openapi.Response(description='', examples={'data': {
                             "quantity": 'integer',
                             "product": 'integer<product_id>'
                         }})})
    def post(self, request):
        serializer = BasketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, product_id=request.data['product'])
        return Response({'data': serializer.data}, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: openapi.Response(description='', examples={'data': {
                             "quantity": 'integer',
                             "basket": 'integer<basket_id>',
                         }})})
    def put(self, request):
        instance = get_object_or_404(Basket, user=request.user, id=request.data['basket'])
        serializer = BasketSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.update(serializer.instance, serializer.validated_data)
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: openapi.Response(description='', examples={'data': {
                             "basket": "integer<basket_id>",
                             "baskets": "array<basket_id>"
                         }})})
    def delete(self, request):
        if len(request.data.get('baskets', [])):
            Basket.objects.filter(user=request.user, id__in=request.data['baskets']).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        instance = get_object_or_404(Basket, user=request.user, id=request.data['basket'])
        instance.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class CreateBasketsView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ['post']

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_201_CREATED: openapi.Response(description='', examples={'data': {
                             "baskets": 'array<dict<:product_id:<int>, :quantity:<int>>>',
                         }})})
    def post(self, request):
        serializer = CreateBasketsListSerializer(
            data={'user': request.user.id, 'baskets': request.data['baskets']})
        serializer.is_valid(raise_exception=True)
        data = serializer.create(serializer.validated_data)
        return Response(data, status=status.HTTP_201_CREATED)


class OrderAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: OrderSerializer(many=True)})
    def get(self, request):
        orders = Order.objects.prefetch_related('baskets').filter(user=request.user)
        serializer = OrderSerializer(orders, many=True).data
        return Response({'data': serializer}, status=status.HTTP_200_OK)

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: openapi.Response(description='', examples={'data': {
                             "type": "string",
                             "full_name": "string",
                             "phone": "string",
                         }})})
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        total_price = Basket.objects.filter(user=request.user).aggregate(total_price=Sum('price'))['total_price']
        full_name = request.user.get_full_name()
        phone = request.user.phone

        data = serializer.create({
            **serializer.validated_data,
            'total_price': total_price,
            'full_name': serializer.validated_data.get('full_name', full_name),
            'phone': serializer.validated_data.get('phone', phone),
            'user': request.user
        })

        Basket.objects.filter(user=request.user, order__isnull=True).update(order=data)

        return Response(status=status.HTTP_201_CREATED)


class ReviewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ['post']

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: ReviewSerializer()})
    def post(self, request):
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.create({
            **serializer.validated_data,
            'user': request.user,
        })
        return Response(status=status.HTTP_201_CREATED)
