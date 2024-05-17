import datetime

from django.db.models import Sum, Count, Case, When, Value, FloatField, Q, FilteredRelation
from store.querysets.base_queryset import BaseQuerySet


class ProductQueryset(BaseQuerySet):

    def with_rating(self):
        query = self

        query = query.annotate(
            review_count=Count('reviews__id'),
            rating=Case(
                When(review_count=0, then=Value(0)),
                default=Sum('reviews__rating') / Case(
                    When(review_count=0, then=Value(1)),
                    default=Count('reviews__id'),
                    output_field=FloatField()
                ),
                output_field=FloatField()
            )
        )

        return query

    def with_favorite(self, key):
        query = self

        if key:
            query = query.annotate(liked=(Q(favorites__user__auth_token__key=key)))
            return query

        return query

    def with_flags(self, is_leader, is_sale, is_new, is_accessories, search, brand):
        query = self

        if brand is not None:
            query = query.filter(Q(brand__name__icontains=brand))

        if search is not None:
            query = query.filter(Q(name_ru__icontains=search) | Q(name_uz__icontains=search) | Q(
                category__name_uz__icontains=search) | Q(category__name_ru__icontains=search))

        if is_new:
            query = query.filter(created_at__gt=(datetime.datetime.now() - datetime.timedelta(days=30)))

        if is_sale:
            query = query.filter(discounted_price__gt=0)

        if is_accessories:
            query = query.filter(category__name_ru__in=['Accessories', 'Аксессуары'])

        if is_leader:
            query = query.annotate(
                is_leader_count=FilteredRelation('baskets', condition=Q(baskets__order__isnull=False))).order_by(
                '-is_leader_count')

        return query
