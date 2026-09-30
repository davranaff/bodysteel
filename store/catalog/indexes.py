from django.db import models


PRODUCT_INDEXES = [
    models.Index(fields=['updated_at', 'id'], name='store_prod_updated_id_idx'),
    models.Index(
        fields=['product_type', 'regos_catalog_status', '-created_at'],
        name='store_prod_type_stat_cr_idx',
    ),
    models.Index(
        fields=['product_type', 'regos_catalog_status', 'brand'],
        name='store_prod_type_stat_br_idx',
    ),
    models.Index(
        fields=['product_type', 'regos_catalog_status', 'discounted_price'],
        name='store_prod_type_stat_sale_idx',
    ),
]
