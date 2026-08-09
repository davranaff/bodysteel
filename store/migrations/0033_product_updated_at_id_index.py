from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('store', '0032_product_updated_at')]

    operations = [
        migrations.AddIndex(
            model_name='product',
            index=models.Index(
                fields=['updated_at', 'id'],
                name='store_prod_updated_id_idx',
            ),
        ),
    ]
