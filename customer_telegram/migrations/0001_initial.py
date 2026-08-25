import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('users', '0007_phoneverificationchallenge_delivery_channel_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerTelegramUpdate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('update_id', models.BigIntegerField(unique=True)),
                ('update_type', models.CharField(max_length=32)),
                ('status', models.CharField(default='processing', max_length=16)),
                ('failure_code', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='CustomerTelegramChat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telegram_user_id', models.BigIntegerField(unique=True)),
                ('chat_id', models.BigIntegerField(unique=True)),
                ('language', models.CharField(blank=True, choices=[('ru', 'Русский'), ('uz', 'O‘zbekcha')], default='', max_length=2)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('marketing_opt_in', models.BooleanField(db_index=True, default=False)),
                ('marketing_consent_source', models.CharField(blank=True, default='', max_length=32)),
                ('marketing_opted_in_at', models.DateTimeField(blank=True, null=True)),
                ('marketing_opted_out_at', models.DateTimeField(blank=True, null=True)),
                ('linked_at', models.DateTimeField(blank=True, null=True)),
                ('blocked_at', models.DateTimeField(blank=True, null=True)),
                ('last_seen_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='customer_telegram_chat', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Telegram-клиент',
                'verbose_name_plural': 'Telegram-клиенты',
            },
        ),
        migrations.CreateModel(
            name='CustomerTelegramCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('scheduled', 'Scheduled'), ('queueing', 'Queueing'), ('sending', 'Sending'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('failed', 'Failed')], db_index=True, default='draft', max_length=12)),
                ('title_ru', models.CharField(max_length=200)),
                ('title_uz', models.CharField(max_length=200)),
                ('body_ru', models.TextField(validators=[django.core.validators.MaxLengthValidator(3200)])),
                ('body_uz', models.TextField(validators=[django.core.validators.MaxLengthValidator(3200)])),
                ('button_text_ru', models.CharField(blank=True, default='', max_length=64)),
                ('button_text_uz', models.CharField(blank=True, default='', max_length=64)),
                ('button_url', models.URLField(blank=True, default='', max_length=500)),
                ('scheduled_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('audience_built_at', models.DateTimeField(blank=True, null=True)),
                ('recipient_count', models.PositiveIntegerField(default=0)),
                ('delivered_count', models.PositiveIntegerField(default=0)),
                ('failed_count', models.PositiveIntegerField(default=0)),
                ('blocked_count', models.PositiveIntegerField(default=0)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='customer_telegram_campaigns', to=settings.AUTH_USER_MODEL)),
                ('test_recipient', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='test_campaigns', to='customer_telegram.customertelegramchat')),
            ],
            options={
                'permissions': (
                    ('test_customertelegramcampaign', 'Can test customer Telegram campaign'),
                    ('publish_customertelegramcampaign', 'Can publish customer Telegram campaign'),
                ),
            },
        ),
        migrations.CreateModel(
            name='CustomerTelegramCampaignRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(choices=[('ru', 'Русский'), ('uz', 'O‘zbekcha')], max_length=2)),
                ('rendered_title', models.CharField(max_length=200)),
                ('rendered_body', models.TextField(max_length=3200)),
                ('rendered_button_text', models.CharField(blank=True, default='', max_length=64)),
                ('rendered_button_url', models.URLField(blank=True, default='', max_length=500)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sending', 'Sending'), ('delivered', 'Delivered'), ('retry', 'Retry'), ('failed', 'Failed'), ('skipped', 'Skipped'), ('blocked', 'Blocked')], default='pending', max_length=12)),
                ('attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('next_attempt_at', models.DateTimeField(db_index=True)),
                ('lease_token', models.CharField(blank=True, editable=False, max_length=64, null=True)),
                ('locked_at', models.DateTimeField(blank=True, null=True)),
                ('telegram_message_id', models.BigIntegerField(blank=True, null=True)),
                ('failure_code', models.CharField(blank=True, default='', max_length=64)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipients', to='customer_telegram.customertelegramcampaign')),
                ('chat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='campaign_deliveries', to='customer_telegram.customertelegramchat')),
            ],
            options={
                'indexes': [models.Index(fields=['status', 'next_attempt_at'], name='customer_tg_delivery_due_idx')],
                'constraints': [models.UniqueConstraint(fields=('campaign', 'chat'), name='customer_tg_campaign_chat_uniq')],
            },
        ),
        migrations.CreateModel(
            name='CustomerTelegramLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_digest', models.CharField(editable=False, max_length=64, unique=True)),
                ('purpose', models.CharField(choices=[('registration_otp', 'Registration OTP'), ('password_reset_otp', 'Password reset OTP'), ('account_link', 'Account link')], max_length=24)),
                ('language', models.CharField(choices=[('ru', 'Русский'), ('uz', 'O‘zbekcha')], max_length=2)),
                ('state', models.CharField(choices=[('awaiting_start', 'Awaiting start'), ('awaiting_contact', 'Awaiting contact'), ('delivering', 'Delivering'), ('delivered', 'Delivered'), ('consumed', 'Consumed'), ('locked', 'Locked'), ('expired', 'Expired'), ('failed', 'Failed')], default='awaiting_start', max_length=20)),
                ('contact_attempts_remaining', models.PositiveSmallIntegerField(default=3)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('consumed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('auth_challenge', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='customer_telegram_link', to='users.authchallenge')),
                ('chat', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='links', to='customer_telegram.customertelegramchat')),
                ('registration_challenge', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='customer_telegram_link', to='users.phoneverificationchallenge')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='customer_telegram_links', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [
                    models.CheckConstraint(
                        condition=(
                            models.Q(purpose='registration_otp', registration_challenge__isnull=False, auth_challenge__isnull=True, user__isnull=True)
                            | models.Q(purpose='password_reset_otp', registration_challenge__isnull=True, auth_challenge__isnull=False, user__isnull=True)
                            | models.Q(purpose='account_link', registration_challenge__isnull=True, auth_challenge__isnull=True, user__isnull=False)
                        ),
                        name='customer_tg_link_exact_target',
                    ),
                ],
            },
        ),
    ]
