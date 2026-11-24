from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer_telegram', '0005_product_widget_kind'),
    ]

    operations = [
        migrations.AddField(
            model_name='customertelegramchat',
            name='shop_topic_id',
            field=models.PositiveIntegerField(blank=True, editable=False, null=True, verbose_name='Тема «Магазин»'),
        ),
        migrations.AddField(
            model_name='customertelegramchat',
            name='orders_topic_id',
            field=models.PositiveIntegerField(blank=True, editable=False, null=True, verbose_name='Тема «Заказы»'),
        ),
        migrations.AddField(
            model_name='customertelegramchat',
            name='promo_topic_id',
            field=models.PositiveIntegerField(blank=True, editable=False, null=True, verbose_name='Тема «Акции»'),
        ),
    ]
