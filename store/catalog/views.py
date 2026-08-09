from rest_framework import status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from store.models import Category, Product
from store.serializers.category import CategorySerializer
from store.serializers.products import ProductSerializer


class ProductViewSet(viewsets.ViewSet):
    def list(self, request):
        offset = request.query_params.get('offset', 0)
        limit = request.query_params.get('limit', 10)
        brand = request.query_params.get('brand')
        is_leader = request.query_params.get('is_leader', False)
        is_sale = request.query_params.get('is_sale', False)
        is_new = request.query_params.get('is_new', False)
        is_accessories = request.query_params.get('is_accessories', False)
        search = request.query_params.get('search')
        fetch_all = request.query_params.get('all')

        products = (
            Product.objects.with_flags(
                is_leader,
                is_sale,
                is_new,
                is_accessories,
                search,
                brand,
            )
            .with_favorite(request.auth)
            .with_rating()
            .order_by_stock()
        )
        if not fetch_all:
            products = products[int(offset):int(limit)]

        return Response(
            {'data': ProductSerializer(products, many=True).data},
            status=status.HTTP_200_OK,
        )

    def retrieve(self, request, slug):
        product = get_object_or_404(
            Product.objects.with_favorite(request.auth).with_rating(),
            slug=slug,
        )
        product.view_count += 1
        product.save()

        related_products = Product.objects.filter(
            category__in=product.category.all(),
        ).order_by_stock()[:4]
        return Response(
            {
                'data': ProductSerializer(product, many=False).data,
                'related': ProductSerializer(related_products, many=True).data,
            },
        )


class CategoryViewSet(viewsets.ViewSet):
    def list(self, request):
        categories = Category.objects.order_by('sort')
        return Response(
            {'data': CategorySerializer(categories, many=True).data},
            status=status.HTTP_200_OK,
        )

    def retrieve(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        products = (
            Product.objects.with_favorite(request.auth)
            .with_rating()
            .filter(category=category)
            .order_by_stock()
        )
        return Response(
            {
                'data': {
                    'category': CategorySerializer(category).data,
                    'products': ProductSerializer(products, many=True).data,
                },
            },
            status=status.HTTP_200_OK,
        )
