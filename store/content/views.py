from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from store.models import Blog, Brand, Category, Menu, Product, SetOfProduct
from store.serializers.blogs import BlogSerializer
from store.serializers.brand import BrandSerializer
from store.serializers.category import CategorySerializer
from store.serializers.menu import MenuSerializer
from store.serializers.products import ProductSerializer
from store.serializers.set_of_product import SetOfProductsSerializerWithCount


class HomePageAPIView(APIView):
    allowed_methods = ['get']

    def get(self, request):
        payload = {
            'set_of_products': SetOfProductsSerializerWithCount(
                SetOfProduct.objects.annotate(products_count=Count('products')).all(),
                many=True,
            ).data,
            'categories': CategorySerializer(
                Category.objects.order_by('sort')[:9],
                many=True,
            ).data,
            'leader_products': ProductSerializer(
                Product.objects.with_rating()
                .with_favorite(request.auth)
                .order_by_stock('-view_count')[:5],
                many=True,
            ).data,
            'sale_products': ProductSerializer(
                Product.objects.with_rating()
                .with_favorite(request.auth)
                .filter(discounted_price__gt=0)
                .order_by_stock()[:10],
                many=True,
            ).data,
            'latest_products': ProductSerializer(
                Product.objects.with_rating().with_favorite(request.auth).order_by_stock()[:10],
                many=True,
            ).data,
            'brands': BrandSerializer(Brand.objects.all()[:6], many=True).data,
            'blogs': BlogSerializer(Blog.objects.all()[:6], many=True).data,
        }
        return Response({'data': payload}, status=status.HTTP_200_OK)


class AboutAPIView(APIView):
    allowed_methods = ['get']

    def get(self, request):
        menu = Menu.objects.filter(is_active=True).first()
        return Response(
            {'data': MenuSerializer(menu, many=False).data},
            status=status.HTTP_200_OK,
        )


class BlogViewSet(viewsets.ViewSet):
    def list(self, request):
        params = request.query_params.dict()
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 10))
        menu = Menu.objects.filter(is_active=True).first()
        blogs = Blog.objects.order_by('-created_at')[offset:limit]
        return Response(
            {
                'data': {
                    'blogs': BlogSerializer(blogs, many=True).data,
                    **MenuSerializer(menu, many=False).data,
                },
            },
            status=status.HTTP_200_OK,
        )

    def retrieve(self, request, slug=None):
        blog = get_object_or_404(Blog, slug=slug)
        return Response(
            {
                'data': {
                    'recommendations': BlogSerializer(Blog.objects.all()[:5], many=True).data,
                    'detail': BlogSerializer(blog, many=False).data,
                },
            },
            status=status.HTTP_200_OK,
        )


class SetOfProductViewSet(viewsets.ViewSet):
    def list(self, request):
        sets = SetOfProduct.objects.annotate(products_count=Count('products')).all()
        menu = Menu.objects.filter(is_active=True).first()
        return Response(
            {
                'data': {
                    'set_of_products': SetOfProductsSerializerWithCount(sets, many=True).data,
                    **MenuSerializer(menu).data,
                },
            },
            status=status.HTTP_200_OK,
        )

    def retrieve(self, request, slug):
        products = (
            Product.objects.with_rating()
            .with_favorite(request.auth)
            .filter(set_of_products__slug=slug)
            .order_by_stock()
        )
        product_set = get_object_or_404(SetOfProduct, slug=slug)
        return Response(
            {
                'data': {
                    'products': ProductSerializer(products, many=True).data,
                    'name_uz': product_set.name_uz,
                    'name_ru': product_set.name_ru,
                },
            },
            status=status.HTTP_200_OK,
        )


class BrandAPIView(APIView):
    allowed_methods = ['get']

    def get(self, request):
        return Response(
            {'data': BrandSerializer(Brand.objects.all(), many=True).data},
            status=status.HTTP_200_OK,
        )


class DeliveryAndPaymentsAPIView(APIView):
    allowed_methods = ['get']

    def get(self, request):
        menu = Menu.objects.filter(is_active=True).first()
        return Response(
            {'data': MenuSerializer(menu).data},
            status=status.HTTP_200_OK,
        )
