import courses.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0002_coursepurchase_request_fingerprint"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="lesson",
            name="video_file",
        ),
        migrations.RemoveField(
            model_name="lesson",
            name="video_reference",
        ),
        migrations.RemoveField(
            model_name="lesson",
            name="video_type",
        ),
        migrations.AddField(
            model_name="lesson",
            name="image",
            field=models.ImageField(
                blank=True, null=True, upload_to=courses.models.lesson_image_path
            ),
        ),
    ]
