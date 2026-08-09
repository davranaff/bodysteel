import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from store.models import Order
from teleg.utils.notify_message import notify_message
from users.orders.creation import create_order
from users.orders.errors import (
    InvalidOrderIdempotencyKey,
    OrderIdempotencyConflict,
    OrderUnavailable,
)
from users.orders.idempotency import parse_idempotency_key
from users.serializers.order import OrderCreateSerializer, OrderSerializer


logger = logging.getLogger(__name__)


class OrderAPIView(APIView):
    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method == 'GET' else []

    @swagger_auto_schema(manual_parameters=[], responses={status.HTTP_200_OK: OrderSerializer(many=True)})
    def get(self, request):
        orders = Order.objects.prefetch_related('baskets').filter(user=request.user)
        return Response({'data': OrderSerializer(orders, many=True).data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'Idempotency-Key',
                openapi.IN_HEADER,
                required=True,
                type=openapi.TYPE_STRING,
            ),
        ],
        responses={status.HTTP_201_CREATED: openapi.Response(description='Order receipt')},
    )
    def post(self, request):
        try:
            idempotency_key = parse_idempotency_key(request.headers.get('Idempotency-Key'))
        except InvalidOrderIdempotencyKey:
            return Response({'detail': 'Idempotency-Key is invalid'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            created = create_order(serializer.validated_data, request.user, idempotency_key)
        except OrderIdempotencyConflict:
            return Response({'detail': 'Idempotency key conflict'}, status=status.HTTP_409_CONFLICT)
        except OrderUnavailable:
            return Response(
                {'detail': 'One or more products are unavailable'},
                status=status.HTTP_409_CONFLICT,
            )

        if not created.replayed:
            _notify_order(created)
        response = Response({'orderId': str(created.order.pk)}, status=status.HTTP_201_CREATED)
        if created.replayed:
            response['Idempotency-Replayed'] = 'true'
        return response


def _notify_order(created):
    baskets = created.order.baskets.select_related('product')
    try:
        notify_message(created.order, baskets, created.coupon)
    except Exception:
        logger.exception('Order notification delivery failed', extra={'order_id': created.order.pk})
