from django.db import migrations, models


def normalize_order_status(apps, schema_editor):
    order = apps.get_model('store', 'Order')
    order.objects.exclude(status__in=('moderation', 'purchased')).update(status='moderation')


class Migration(migrations.Migration):
    dependencies = [('store', '0033_product_updated_at_id_index')]

    operations = [
        migrations.RunPython(normalize_order_status, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[('purchased', 'Куплен'), ('moderation', 'На модерации')],
                default='moderation',
                max_length=50,
            ),
        ),
    ]
