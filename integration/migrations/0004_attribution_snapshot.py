import django.db.models.deletion
from django.db import migrations, models


def snapshot_attribution(apps, schema_editor):
    attribution_model = apps.get_model('integration', 'IntegrationOrderAttribution')
    for attribution in attribution_model.objects.select_related('cart').iterator(chunk_size=500):
        attribution.ai_session_id = attribution.cart.ai_session_id
        attribution.channel = attribution.cart.channel
        attribution.save(update_fields=('ai_session_id', 'channel'))


class Migration(migrations.Migration):
    dependencies = [('integration', '0003_webhook_outbox_and_order_attribution')]

    operations = [
        migrations.AddField(
            model_name='integrationorderattribution',
            name='ai_session_id',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='integrationorderattribution',
            name='channel',
            field=models.CharField(
                choices=[('web', 'Web'), ('telegram', 'Telegram')],
                max_length=16,
                null=True,
            ),
        ),
        migrations.RunPython(snapshot_attribution, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='integrationorderattribution',
            name='ai_session_id',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name='integrationorderattribution',
            name='channel',
            field=models.CharField(
                choices=[('web', 'Web'), ('telegram', 'Telegram')],
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name='integrationorderattribution',
            name='cart',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='order_attribution',
                to='integration.integrationcart',
            ),
        ),
    ]
