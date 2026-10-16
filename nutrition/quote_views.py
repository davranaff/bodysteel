from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from nutrition.checkout import CheckoutUnavailable, build_quote
from nutrition.checkout_serializers import CheckoutQuoteSerializer
from nutrition.serializers import language_from_request
from store.commerce.discounts import price_discounts


class CheckoutQuoteAPIView(APIView):
    def post(self, request):
        serializer = CheckoutQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        command = serializer.validated_data
        try:
            quote = build_quote(command)
        except CheckoutUnavailable as error:
            return checkout_problem(error)
        # The same pricing function runs (with row locks) during order creation.
        pricing = price_discounts(quote.subtotal, request.user, command.get('coupon_code'))
        return Response({
            'data': {
                'subtotal': quote.subtotal,
                'bonus_discount': pricing.bonus_discount,
                'coupon_discount': pricing.coupon_discount,
                'coupon_applied': pricing.coupon_applied,
                'discount': pricing.discount,
                'delivery_fee': quote.delivery_fee,
                'total': pricing.discounted_subtotal + quote.delivery_fee,
                'currency': 'UZS',
                'delivery_method_code': quote.delivery_method_code,
                'delivery_zone_code': quote.delivery_zone_code,
                'delivery_slot': quote.delivery_slot.pk if quote.delivery_slot else None,
                'language': language_from_request(request),
            },
        })


def checkout_problem(error):
    """409 with the legacy ``detail`` plus a stable ``error.code`` for clients."""
    message = str(error)
    return Response(
        {'detail': message, 'error': {'code': error.code, 'message': message}},
        status=status.HTTP_409_CONFLICT,
        headers={'Cache-Control': 'no-store'},
    )
