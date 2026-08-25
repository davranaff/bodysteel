from django.db.models import Case, IntegerField, When
from rest_framework import status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from store.models import Category, Product
from store.catalog.search import smart_product_ids
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
            Product.objects.visible_on_storefront().sports_catalog().with_flags(
                is_leader,
                is_sale,
                is_new,
                is_accessories,
                None,
                brand,
            )
        )
        order_fields = ('-created_at',)
        if search:
            ranked_ids = smart_product_ids(products, search)
            products = products.filter(pk__in=ranked_ids)
            if ranked_ids:
                products = products.annotate(search_rank=Case(
                    *(When(pk=product_id, then=position) for position, product_id in enumerate(ranked_ids)),
                    default=len(ranked_ids),
                    output_field=IntegerField(),
                ))
                order_fields = ('search_rank', '-created_at')
        products = products.with_favorite(request.auth).with_rating().order_by_stock(*order_fields)
        if not fetch_all:
            products = products[int(offset):int(limit)]

        return Response(
            {'data': ProductSerializer(products, many=True).data},
            status=status.HTTP_200_OK,
        )

    def retrieve(self, request, slug):
        product = get_object_or_404(
            Product.objects.visible_on_storefront().with_favorite(request.auth).with_rating(),
            slug=slug,
        )
        product.view_count += 1
        product.save()

        related_products = Product.objects.visible_on_storefront().filter(
            category__in=product.category.all(),
        ).exclude(pk=product.pk)
        if product.product_type in (Product.TYPE_MEAL, Product.TYPE_MEAL_KIT):
            related_products = related_products.filter(
                product_type__in=(Product.TYPE_MEAL, Product.TYPE_MEAL_KIT),
            )
        else:
            related_products = related_products.sports_catalog()
        related_products = related_products.distinct().order_by_stock()[:4]
        return Response(
            {
                'data': ProductSerializer(product, many=False).data,
                'related': ProductSerializer(related_products, many=True).data,
            },
        )


class CategoryViewSet(viewsets.ViewSet):
    def list(self, request):
        categories = Category.objects.filter(
            products__product_type=Product.TYPE_SUPPLEMENT,
            products__regos_catalog_status__in=('manual', 'published'),
        ).distinct().order_by('sort')
        return Response(
            {'data': CategorySerializer(categories, many=True).data},
            status=status.HTTP_200_OK,
        )

    def retrieve(self, request, slug):
        category = get_object_or_404(Category, slug=slug)
        products = (
            Product.objects.visible_on_storefront().sports_catalog().with_favorite(request.auth)
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
