from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('integration', '0001_initial')]

    operations = [
        migrations.AlterField(
            model_name='integrationcart',
            name='expires_at',
            field=models.DateTimeField(db_index=True),
        ),
    ]
