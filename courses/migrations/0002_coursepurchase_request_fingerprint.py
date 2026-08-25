from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursepurchase",
            name="request_fingerprint",
            field=models.CharField(default="", max_length=64),
        ),
    ]
