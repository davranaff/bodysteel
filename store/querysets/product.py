import datetime

from django.db.models import Sum, Count, Q, F

from store.querysets.base_queryset import BaseQuerySet


class ProductQueryset(BaseQuerySet):

    def with_rating(self):
        query = self

        query = query.annotate(rating=(Sum('reviews__rating') / Count('reviews__id')))

        return query

    def with_favorite(self, key):
        query = self

        if key:
            query = query.annotate(liked=(Q(favorites__user__auth_token__key=key)))
            return query

        return query

    def with_flags(self, is_leader, is_sale, is_new, is_accessories):
        query = self

        if is_leader:
            query = query.annotate(is_leader_count=F('baskets', filter=Q(baskets__order__isnull=False))).order_by(
                '-is_leader_count')

        if is_sale:
            query = query.filter(discounted_price__gt=0)

        if is_new:
            query = query.filter(created_at__gt=(datetime.datetime.now() - datetime.timedelta(days=30)))

        if is_accessories:
            query = query.filter(category__name__in=['Accessories', 'Аксессуары'])

        return query
