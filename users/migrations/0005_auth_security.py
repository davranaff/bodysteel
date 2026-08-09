import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_remove_user_bonus'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='code',
        ),
        migrations.RemoveField(
            model_name='user',
            name='verification',
        ),
        migrations.CreateModel(
            name='AuthRateLimit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(max_length=40)),
                ('subject_digest', models.CharField(max_length=64)),
                ('window_started_at', models.DateTimeField()),
                ('count', models.PositiveIntegerField(default=0)),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'indexes': [models.Index(fields=['expires_at'], name='users_rate_exp_idx')],
                'constraints': [models.UniqueConstraint(
                    fields=('scope', 'subject_digest', 'window_started_at'),
                    name='users_rate_scope_subject_window_uniq',
                )],
            },
        ),
        migrations.CreateModel(
            name='PhoneVerificationChallenge',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('delivery_id', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(max_length=13, unique=True)),
                ('code_digest', models.CharField(max_length=64)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('sent', 'Sent'),
                        ('unknown', 'Delivery unknown'),
                        ('failed', 'Delivery failed'),
                        ('consumed', 'Consumed'),
                        ('locked', 'Locked'),
                    ],
                    default='pending',
                    max_length=12,
                )),
                ('attempts_remaining', models.PositiveSmallIntegerField(default=5)),
                ('expires_at', models.DateTimeField()),
                ('resend_after', models.DateTimeField()),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('consumed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['expires_at'], name='users_otp_exp_idx'),
                    models.Index(fields=['email'], name='users_otp_email_idx'),
                ],
            },
        ),
    ]
