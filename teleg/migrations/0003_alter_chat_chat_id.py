# Generated by Django 5.0.2 on 2025-06-21 13:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("teleg", "0002_alter_chat_chat_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chat",
            name="chat_id",
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
