from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0046_alter_product_regos_catalog_status'),
    ]

    operations = [
        TrigramExtension(),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(
                fields=['product_type', 'regos_catalog_status', '-created_at'],
                name='store_prod_type_stat_cr_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(
                fields=['product_type', 'regos_catalog_status', 'brand'],
                name='store_prod_type_stat_br_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(
                fields=['product_type', 'regos_catalog_status', 'discounted_price'],
                name='store_prod_type_stat_sale_idx',
            ),
        ),
    ]
