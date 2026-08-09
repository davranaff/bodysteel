from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('store', '0034_order_status_and_stable_save')]

    operations = [
        migrations.AddField(
            model_name='order',
            name='idempotency_digest',
            field=models.CharField(editable=False, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='order',
            name='request_fingerprint',
            field=models.CharField(editable=False, max_length=64, null=True),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(idempotency_digest__isnull=True, request_fingerprint__isnull=True)
                    | models.Q(idempotency_digest__isnull=False, request_fingerprint__isnull=False)
                ),
                name='store_order_idempotency_pair',
            ),
        ),
    ]
