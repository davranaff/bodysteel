from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import get_object_or_404

from store.models import Favorite, Basket, Coupon
from store.serializers.review import ReviewSerializer
from teleg.utils import notify_review
from users.serializers.basket import BasketSerializer, CreateBasketsListSerializer
from users.serializers.favorites import GetFavoritesSerializer, CreateFavoritesSerializer, CreateFavoritesListSerializer
from store.serializers.coupon import CouponSerializer

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

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
                             "baskets": [
                                 {
                                     "product_id": "integer",
                                     "quantity": "integer",
                                 }
                             ],
                         }})})
    def post(self, request):
        serializer = CreateBasketsListSerializer(data={'baskets': request.data['baskets']})
        serializer.is_valid(raise_exception=True)
        data = serializer.create({**serializer.validated_data, 'user': request.user.id})
        return Response(data, status=status.HTTP_201_CREATED)


class ReviewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ['post']

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: ReviewSerializer()})
    def post(self, request):
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.create({
            **serializer.validated_data,
            'user': request.user,
        })

        notify_review.notify_review({
            "id": data.id,
            "rating": data.rating,
            "username": data.user.username,
            "email": data.user.email,
            "first_name": data.user.first_name,
            "last_name": data.user.last_name,
            "phone": data.user.phone,
            "created_at": data.created_at,
            "comment": data.comment,
            "product": data.product.name_ru,
        })

        return Response({'data': {
            "id": data.id,
            "rating": data.rating,
            "user": {
                "id": data.user.id,
                "username": data.user.username,
                "email": data.user.email,
                "first_name": data.user.first_name,
                "last_name": data.user.last_name,
                "phone": data.user.phone,
            },
            "full_name": f"{data.user.first_name} {data.user.last_name}",
            "created_at": data.created_at,
            "comment": data.comment,
            "product": data.product.id,
        }, 'bonus': {
            'bonus_used': request.user.bonus_used,
        }}, status=status.HTTP_201_CREATED)


class CouponAPIView(APIView):
    allowed_methods = ['post', 'get']

    @swagger_auto_schema(manual_parameters=[],
                         responses={status.HTTP_200_OK: CouponSerializer(many=True)})
    def get(self, request):
        coupon_code = request.query_params.get('key')

        # Если ключ не указан, возвращаем список доступных купонов
        if not coupon_code:
            coupons = Coupon.objects.filter(is_active=True)
            serializer = CouponSerializer(coupons, many=True).data
            return Response({'data': serializer}, status=status.HTTP_200_OK)

        # Если ключ указан, проверяем его и возвращаем процент скидки или null
        try:
            coupon = Coupon.objects.get(code=coupon_code, is_active=True)

            if not coupon.can_use():
                return Response({'discount_percent': None}, status=status.HTTP_200_OK)

            return Response({'discount_percent': coupon.discount_percent}, status=status.HTTP_200_OK)
        except Coupon.DoesNotExist:
            return Response({'discount_percent': None}, status=status.HTTP_200_OK)

    # @swagger_auto_schema(manual_parameters=[],
    #                      request_body=CouponValidateSerializer,
    #                      responses={status.HTTP_200_OK: CouponSerializer})
    # def post(self, request):
    #     serializer = CouponValidateSerializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)

    #     # Проверяем существует ли купон и доступен ли он для использования
    #     coupon = get_object_or_404(Coupon, code=serializer.validated_data['code'], is_active=True)

    #     # Проверяем, достиг ли купон максимального количества использований
    #     if not coupon.can_use():
    #         return Response({'error': 'Купон больше не может быть использован'},
    #                        status=status.HTTP_400_BAD_REQUEST)

    #     coupon_serializer = CouponSerializer(coupon).data
    #     return Response({'data': coupon_serializer}, status=status.HTTP_200_OK)
