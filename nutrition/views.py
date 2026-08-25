from datetime import date

from django.db.models import Prefetch, Q
from rest_framework import status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from nutrition.models import DeliveryMethod, DeliverySlot, DeliveryZone, NutritionProfile
from nutrition.serializers import DeliveryMethodSerializer, NutritionProfileSerializer, language_from_request
from store.models import Product
from store.serializers.products import ProductSerializer


def nutrition_queryset():
    return Product.objects.visible_on_storefront().filter(
        product_type__in=(Product.TYPE_MEAL, Product.TYPE_MEAL_KIT),
    ).select_related('brand', 'nutrition_profile').prefetch_related(
        'product_images', 'category', 'nutrition_profile__tags',
        'nutrition_profile__allergens', 'nutrition_profile__allowed_delivery_methods',
    )


class NutritionProductSerializer(ProductSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = getattr(instance, 'nutrition_profile', None)
        data['product_type'] = instance.product_type
        data['nutrition_profile'] = (
            NutritionProfileSerializer(
                profile,
                context={'language': self.context.get('language', 'ru')},
            ).data
            if profile else None
        )
        return data


class NutritionViewSet(viewsets.ViewSet):
    def list(self, request):
        language = language_from_request(request)
        products = nutrition_queryset()
        kind = request.query_params.get('kind')
        search = request.query_params.get('search')
        if kind in (NutritionProfile.DISH, NutritionProfile.KIT):
            products = products.filter(nutrition_profile__kind=kind)
        if search:
            products = products.filter(Q(name_ru__icontains=search) | Q(name_uz__icontains=search))
        return Response({
            'data': NutritionProductSerializer(products, many=True, context={'language': language}).data,
        })


class NutritionProductViewSet(viewsets.ViewSet):
    def retrieve(self, request, slug):
        product = get_object_or_404(nutrition_queryset(), slug=slug)
        return Response({
            'data': NutritionProductSerializer(
                product,
                context={'language': language_from_request(request)},
            ).data,
        })


class DeliveryOptionsAPIView(APIView):
    def get(self, request):
        language = language_from_request(request)
        zone_code = request.query_params.get('zone')
        delivery_date = request.query_params.get('date')
        zones = DeliveryZone.objects.filter(is_active=True).order_by('name_ru')
        methods = DeliveryMethod.objects.filter(is_active=True).order_by('name_ru')
        payload = {
            'methods': DeliveryMethodSerializer(
                methods, many=True, context={'language': language},
            ).data,
            'zones': [
                {
                    'code': zone.code,
                    'name': getattr(zone, 'name_{}'.format(language)),
                    'fee': zone.fee,
                }
                for zone in zones
            ],
            'slots': [],
        }
        if zone_code and delivery_date:
            try:
                parsed_date = date.fromisoformat(delivery_date)
            except ValueError:
                parsed_date = None
            if parsed_date:
                slots = DeliverySlot.objects.filter(
                    zone__code=zone_code,
                    delivery_date=parsed_date,
                    is_active=True,
                ).order_by('starts_at')
                payload['slots'] = [
                    {
                        'id': slot.pk,
                        'date': slot.delivery_date.isoformat(),
                        'starts_at': slot.starts_at.strftime('%H:%M'),
                        'ends_at': slot.ends_at.strftime('%H:%M'),
                        'available': slot.has_capacity(),
                    }
                    for slot in slots
                ]
        return Response(payload, status=status.HTTP_200_OK)
