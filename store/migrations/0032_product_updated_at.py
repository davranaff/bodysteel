from django.db import migrations, models
from django.utils import timezone


def backfill_product_updated_at(apps, schema_editor):
    product = apps.get_model('store', 'Product')
    product.objects.filter(updated_at__isnull=True).update(updated_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [('store', '0031_alter_filial_photo_filialphoto')]

    operations = [
        migrations.AddField(
            model_name='product',
            name='updated_at',
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(backfill_product_updated_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='product',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
