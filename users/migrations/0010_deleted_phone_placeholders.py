from django.db import migrations


def replace_numeric_placeholders(apps, schema_editor):
    # Older deletions stored a random ``+998…`` value that a real customer could
    # later need. Rewrite them to the non-numeric ``del:<hex id>`` placeholder.
    User = apps.get_model('users', 'User')
    for user in User.objects.filter(deleted_at__isnull=False).only('pk', 'phone').iterator():
        placeholder = f'del:{user.pk:09x}'
        if user.phone != placeholder:
            User.objects.filter(pk=user.pk).update(phone=placeholder)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_savdoq_shopper_session'),
    ]

    operations = [
        migrations.RunPython(replace_numeric_placeholders, migrations.RunPython.noop),
    ]
