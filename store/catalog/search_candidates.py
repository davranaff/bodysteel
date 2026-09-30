from django.contrib.postgres.search import TrigramSimilarity
from django.db import connection
from django.db.models import FloatField, Value
from django.db.models.functions import Greatest


_SEARCH_FIELDS = (
    'name_ru',
    'name_uz',
    'slug',
    'regos_item_code',
    'regos_item_articul',
    'brand__name',
    'category__name_ru',
    'category__name_uz',
)
_MINIMUM_SIMILARITY = .08


def shortlist_products(queryset, search_keys):
    """Let PostgreSQL discard unrelated rows before precise Python ranking."""
    if connection.vendor != 'postgresql':
        return queryset

    terms = tuple(sorted({key for key in search_keys if key}))
    if not terms:
        return queryset.none()

    similarities = [
        TrigramSimilarity(field, Value(term))
        for term in terms
        for field in _SEARCH_FIELDS
    ]
    candidate_ids = (
        queryset.order_by()
        .annotate(search_similarity=Greatest(*similarities, output_field=FloatField()))
        .filter(search_similarity__gte=_MINIMUM_SIMILARITY)
        .values_list('pk', flat=True)
        .distinct()
    )
    return queryset.filter(pk__in=candidate_ids)
