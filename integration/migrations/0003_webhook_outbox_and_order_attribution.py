import django.db.models.deletion
import django.utils.timezone
import integration.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('integration', '0002_integrationcart_expires_at_index'),
        ('store', '0034_order_status_and_stable_save'),
    ]

    operations = [
        migrations.AlterField(
            model_name='integrationcart',
            name='ai_session_id',
            field=models.CharField(max_length=200),
        ),
        migrations.CreateModel(
            name='IntegrationOrderAttribution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('cart', models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='order_attribution',
                    to='integration.integrationcart',
                )),
                ('order', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='savdoq_attribution',
                    to='store.order',
                )),
            ],
        ),
        migrations.CreateModel(
            name='IntegrationWebhookEvent',
            fields=[
                ('event_id', models.CharField(
                    default=integration.models.webhook_event_id,
                    editable=False,
                    max_length=200,
                    primary_key=True,
                    serialize=False,
                )),
                ('event_type', models.CharField(editable=False, max_length=32)),
                ('body', models.TextField(editable=False)),
                ('occurred_at', models.DateTimeField(editable=False)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('delivering', 'Delivering'),
                        ('retry', 'Retry'),
                        ('delivered', 'Delivered'),
                        ('failed', 'Failed'),
                    ],
                    default='pending',
                    max_length=16,
                )),
                ('attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('next_attempt_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('lease_token', models.CharField(blank=True, editable=False, max_length=64, null=True)),
                ('locked_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('last_http_status', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('failure_code', models.CharField(blank=True, default='', max_length=32)),
                ('delivered_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ('next_attempt_at', 'created_at'),
                'indexes': [models.Index(
                    fields=['status', 'next_attempt_at'],
                    name='integration_webhook_due_idx',
                )],
            },
        ),
    ]
