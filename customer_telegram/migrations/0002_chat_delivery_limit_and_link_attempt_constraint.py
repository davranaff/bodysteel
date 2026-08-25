from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('customer_telegram', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customertelegramchat',
            name='marketing_next_send_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='customertelegramchat',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    telegram_user_id=models.F('chat_id'), telegram_user_id__gt=0,
                ),
                name='customer_tg_private_chat_identity',
            ),
        ),
        migrations.AddConstraint(
            model_name='customertelegramlink',
            constraint=models.CheckConstraint(
                condition=models.Q(contact_attempts_remaining__gte=0),
                name='customer_tg_contact_attempts_gte_0',
            ),
        ),
    ]
