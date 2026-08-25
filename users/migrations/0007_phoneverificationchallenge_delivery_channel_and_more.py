from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0006_phoneverificationchallenge_first_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='phoneverificationchallenge',
            name='delivery_channel',
            field=models.CharField(
                choices=[('sms', 'SMS'), ('telegram', 'Telegram')],
                default='sms',
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name='authchallenge',
            name='channel',
            field=models.CharField(
                choices=[('sms', 'SMS'), ('email', 'Email'), ('telegram', 'Telegram')],
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name='authchallenge',
            name='status',
            field=models.CharField(
                choices=[
                    ('awaiting', 'Awaiting Telegram'), ('pending', 'Pending'),
                    ('sent', 'Sent'), ('unknown', 'Delivery unknown'),
                    ('failed', 'Delivery failed'), ('consumed', 'Consumed'), ('locked', 'Locked'),
                ],
                default='pending',
                max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name='phoneverificationchallenge',
            name='status',
            field=models.CharField(
                choices=[
                    ('awaiting', 'Awaiting Telegram'), ('pending', 'Pending'),
                    ('sent', 'Sent'), ('unknown', 'Delivery unknown'),
                    ('failed', 'Delivery failed'), ('consumed', 'Consumed'), ('locked', 'Locked'),
                ],
                default='pending',
                max_length=12,
            ),
        ),
    ]
