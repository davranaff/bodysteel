# Generated by Django 5.0.2 on 2024-05-16 23:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_user_bonus_user_bonus_used'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='bonus',
        ),
    ]
