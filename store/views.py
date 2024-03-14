from rest_framework.views import APIView, Response
from rest_framework import status
from rest_framework.generics import get_object_or_404
from django.db.models import Count
from rest_framework import viewsets

from store.models import SetOfProduct, Category, Product, Brand, Blog, Menu, Filial
from store.serializers.blogs import BlogSerializer
from store.serializers.brand import BrandSerializer
from store.serializers.category import CategorySerializer
from store.serializers.filiales import FilialSerializer
from store.serializers.menu import MenuSerializer
from store.serializers.products import ProductSerializer
from store.serializers.set_of_product import SetOfProductsSerializerWithCount


class HomaPageAPIView(APIView):
    allowed_methods = ['get', ]

    def get(self, request):
        serializer_set_of_products = SetOfProductsSerializerWithCount(SetOfProduct
                                                                      .objects
                                                                      .annotate(products_count=Count('products'))
                                                                      .all(),
                                                                      many=True).data
        serializer_category = CategorySerializer(Category.objects.all(), many=True).data
        serializer_leader_products = ProductSerializer(
            Product.objects.with_rating().with_favorite(request.auth).filter(baskets__order__isnull=False)[:5],
            many=True).data
        serializer_sale_products = ProductSerializer(
            Product.objects.with_rating().with_favorite(request.auth).filter(discounted_price__gt=0)[:5],
            many=True).data
        serializer_latest_products = ProductSerializer(
            Product.objects.with_rating().with_favorite(request.auth).all().order_by('-created_at')[:8],
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


class AboutAPIView(APIView):
    allowed_methods = ['get', ]

    def get(self, request):
        menu = get_object_or_404(Menu, is_active=True)
        serializer = MenuSerializer(menu, many=False).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)


class BlogViewSet(viewsets.ViewSet):

    def list(self, request):
        params = request.query_params.dict()

        menu = get_object_or_404(Menu, is_active=True)
        blogs = Blog.objects.order_by('-created_at')[int(params.get('offset', 0)):int(params.get('limit', 10))]
        blog_serializer = BlogSerializer(blogs, many=True).data
        menu_serializer = MenuSerializer(menu, many=False).data

        return Response({'data': {"blogs": blog_serializer, **menu_serializer}}, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        blog = get_object_or_404(Blog, pk=pk)
        blog_serializer = BlogSerializer(blog, many=False).data

        blogs = Blog.objects.all()[:5]
        blogs_serializer = BlogSerializer(blogs, many=True).data

        return Response({'data': {'recommendations': blogs_serializer, 'detail': blog_serializer}},
                        status=status.HTTP_200_OK)


class SetOfProductViewSet(viewsets.ViewSet):

    def list(self, request):
        serializer = SetOfProductsSerializerWithCount(SetOfProduct
                                                      .objects
                                                      .annotate(products_count=Count('products'))
                                                      .all(), many=True).data

        menu = get_object_or_404(Menu, is_active=True)
        menu_serializer = MenuSerializer(menu).data

        return Response({'data': {'set_of_products': serializer, **menu_serializer}}, status=status.HTTP_200_OK)

    def retrieve(self, request, pk):
        set_of_product = Product.objects.with_rating().with_favorite(request.auth).filter(
            set_of_products_id=pk)
        serializer = ProductSerializer(set_of_product, many=True).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)


class BrandAPIView(APIView):
    allowed_methods = ['get', ]

    def get(self, request):
        brands = Brand.objects.all()
        serializer = BrandSerializer(brands, many=True).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)


class DeliveryAndPaymentsAPIView(APIView):
    allowed_methods = ['get', ]

    def get(self, request):
        menu = get_object_or_404(Menu, is_active=True)
        serializer = MenuSerializer(menu).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)


class FilialAPIView(APIView):
    allowed_methods = ['get', ]

    def get(self, request):
        filiales = Filial.objects.all()
        serializer = FilialSerializer(filiales, many=True).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)


class ProductViewSet(viewsets.ViewSet):

    def list(self, request):
        offset = request.query_params.get('offset', 0)
        limit = request.query_params.get('limit', 10)
        is_leader = request.query_params.get('is_leader', False)
        is_sale = request.query_params.get('is_sale', False)
        is_new = request.query_params.get('is_new', False)
        is_accessories = request.query_params.get('is_accessories', False)
        search = request.query_params.get('search', None)

        products = Product.objects.with_flags(is_leader, is_sale, is_new, is_accessories, search).with_favorite(
            request.auth).with_rating().all()[offset:limit]

        serializer = ProductSerializer(products, many=True).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)

    def retrieve(self, request, pk):
        product = get_object_or_404(Product.objects.with_favorite(request.auth).with_rating(), pk=pk)

        product.view_count += 1

        product.save()

        serializer = ProductSerializer(product, many=False).data

        return Response({'data': serializer})


class CategoryViewSet(viewsets.ViewSet):

    def list(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)

    def retrieve(self, request, pk):
        category_products = Product.objects.with_favorite(request.auth).with_rating().filter(category_id=pk)
        serializer = ProductSerializer(category_products, many=True).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)
