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
            many=True
        ).data
        serializer_category = CategorySerializer(Category.objects.all().order_by('sort')[:9], many=True).data
        serializer_leader_products = ProductSerializer(
            (
                Product.objects
                .with_rating()
                .with_favorite(request.auth)
                .order_by_stock('-view_count')[:5]
            ),
            many=True).data
        serializer_sale_products = ProductSerializer(
            (
                Product.objects.with_rating().with_favorite(request.auth).filter(discounted_price__gt=0).order_by_stock()[:10]
            ),
            many=True).data
        serializer_latest_products = ProductSerializer(
            (
                Product.objects
                .with_rating()
                .with_favorite(request.auth)
                .order_by_stock()[:10]
            ),
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
        menu = Menu.objects.filter(is_active=True).first()
        serializer = MenuSerializer(menu, many=False).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)


class BlogViewSet(viewsets.ViewSet):

    def list(self, request):
        params = request.query_params.dict()

        menu = Menu.objects.filter(is_active=True).first()
        blogs = Blog.objects.order_by('-created_at')[int(params.get('offset', 0)):int(params.get('limit', 10))]
        blog_serializer = BlogSerializer(blogs, many=True).data
        menu_serializer = MenuSerializer(menu, many=False).data

        return Response({'data': {"blogs": blog_serializer, **menu_serializer}}, status=status.HTTP_200_OK)

    def retrieve(self, request, slug=None):
        blog = get_object_or_404(Blog, slug=slug)
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

        menu = Menu.objects.filter(is_active=True).first()
        menu_serializer = MenuSerializer(menu).data

        return Response({'data': {'set_of_products': serializer, **menu_serializer}}, status=status.HTTP_200_OK)

    def retrieve(self, request, slug):
        set_of_product = (
            Product.objects
            .with_rating()
            .with_favorite(request.auth)
            .filter(set_of_products__slug=slug)
            .order_by_stock()
        )
        serializer = ProductSerializer(set_of_product, many=True).data
        set_data = SetOfProduct.objects.get(slug=slug)
        return Response({'data': {
            'products': serializer,
            'name_uz': set_data.name_uz,
            'name_ru': set_data.name_ru
        }}, status=status.HTTP_200_OK)


class BrandAPIView(APIView):
    allowed_methods = ['get', ]

    def get(self, request):
        brands = Brand.objects.all()
        serializer = BrandSerializer(brands, many=True).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)


class DeliveryAndPaymentsAPIView(APIView):
    allowed_methods = ['get', ]

    def get(self, request):
        menu = Menu.objects.filter(is_active=True).first()
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
        brand = request.query_params.get('brand', None)
        is_leader = request.query_params.get('is_leader', False)
        is_sale = request.query_params.get('is_sale', False)
        is_new = request.query_params.get('is_new', False)
        is_accessories = request.query_params.get('is_accessories', False)
        search = request.query_params.get('search', None)
        all = request.query_params.get('all', None)

        products = (
            Product.objects
            .with_flags(is_leader, is_sale, is_new, is_accessories, search, brand)
            .with_favorite(request.auth)
            .with_rating()
            .order_by_stock()
        )

        if not all:
            products = products[int(offset):int(limit)]

        serializer = ProductSerializer(products, many=True).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)

    def retrieve(self, request, slug):
        product = get_object_or_404(Product.objects.with_favorite(request.auth).with_rating(), slug=slug)

        product.view_count += 1

        product.save()

        serializer = ProductSerializer(product, many=False).data

        related_products = Product.objects.filter(category__in=product.category.all()).order_by_stock()[:4]
        serializer_related = ProductSerializer(related_products, many=True).data

        return Response({'data': serializer, 'related': serializer_related})


class CategoryViewSet(viewsets.ViewSet):

    def list(self, request):
        categories = Category.objects.all().order_by('sort')
        serializer = CategorySerializer(categories, many=True).data

        return Response({'data': serializer}, status=status.HTTP_200_OK)

    def retrieve(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        category_products = Product.objects.with_favorite(request.auth).with_rating().filter(category=category).order_by_stock()
        serializer = ProductSerializer(category_products, many=True).data
        category_serializer = CategorySerializer(category).data

        return Response({'data': {
            'category': category_serializer,
            'products': serializer,
        }}, status=status.HTTP_200_OK)
