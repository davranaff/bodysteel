from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from nutrition.checkout import CheckoutUnavailable, build_quote
from nutrition.checkout_serializers import CheckoutQuoteSerializer
from nutrition.serializers import language_from_request


class CheckoutQuoteAPIView(APIView):
    def post(self, request):
        serializer = CheckoutQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            quote = build_quote(serializer.validated_data)
        except CheckoutUnavailable as error:
            return Response({'detail': str(error)}, status=status.HTTP_409_CONFLICT)
        return Response({
            'data': {
                'subtotal': quote.subtotal,
                'delivery_fee': quote.delivery_fee,
                'total': quote.total,
                'currency': 'UZS',
                'delivery_method_code': quote.delivery_method_code,
                'delivery_zone_code': quote.delivery_zone_code,
                'delivery_slot': quote.delivery_slot.pk if quote.delivery_slot else None,
                'language': language_from_request(request),
            },
        })
