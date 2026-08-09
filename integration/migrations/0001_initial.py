import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='IntegrationCart',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('idempotency_digest', models.CharField(editable=False, max_length=64, unique=True)),
                ('request_fingerprint', models.CharField(editable=False, max_length=64)),
                ('restore_token', models.CharField(editable=False, max_length=64, unique=True)),
                ('items', models.JSONField()),
                ('language', models.CharField(choices=[('ru', 'Russian'), ('uz', 'Uzbek')], max_length=2)),
                ('ai_session_id', models.CharField(max_length=255)),
                ('channel', models.CharField(choices=[('web', 'Web'), ('telegram', 'Telegram')], max_length=16)),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ('-created_at',)},
        ),
    ]
