from rest_framework.views import APIView, Response
from rest_framework import status
from django.db.models import Count

from store.models import SetOfProduct, Category, Product, Brand, Blog
from store.serializers.blogs import BlogSerializer
from store.serializers.brand import BrandSerializer
from store.serializers.category import CategorySerializer
from store.serializers.products import ProductSerializer
from store.serializers.set_of_product import SetOfProductsSerializerForHome


class HomaPageAPIView(APIView):
    allowed_methods = ['get', ]

    def get(self, request):
        serializer_set_of_products = SetOfProductsSerializerForHome(SetOfProduct
                                                                    .objects
                                                                    .annotate(products_count=Count('products'))
                                                                    .all(),
                                                                    many=True).data
        serializer_category = CategorySerializer(Category.objects.all(), many=True).data
        serializer_leader_products = ProductSerializer(Product.objects.filter(baskets__order__isnull=False)[:5],
                                                       many=True).data
        serializer_sale_products = ProductSerializer(Product.objects.filter(discounted_price__gt=0)[:5], many=True).data
        serializer_latest_products = ProductSerializer(Product.objects.all().order_by('-created_at')[:8],
                                                       many=True).data
        serializer_brands = BrandSerializer(Brand.objects.all()[:6], many=True).data
        serializer_blogs = BlogSerializer(Blog.objects.all()[:6], many=True).data

        return Response({
            'data': {
                'set_of_products': serializer_set_of_products,
                'categories': serializer_category,
                'leader_products': serializer_leader_products,
                'sale_products': serializer_sale_products,
                'latest_products': serializer_latest_products,
                'brands': serializer_brands,
                'blogs': serializer_blogs,
            }
        }, status=status.HTTP_200_OK)
