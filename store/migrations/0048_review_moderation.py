import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


ANONYMOUS_AUTHOR = 'Покупатель'


def anonymize_reviews_of_deleted_accounts(apps, schema_editor):
    # Accounts deleted before review anonymization existed keep only their rating.
    Review = apps.get_model('store', 'Review')
    Review.objects.filter(user__deleted_at__isnull=False).update(
        user=None, full_name=ANONYMOUS_AUTHOR, comment='',
    )


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0047_catalog_search_performance"),
        ("users", "0009_savdoq_shopper_session"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="is_published",
            # Existing reviews were already public: backfill them as published,
            # then switch the default so new reviews wait for staff approval.
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text="Только опубликованные отзывы видны покупателям и учитываются в рейтинге",
                verbose_name="Опубликован",
            ),
        ),
        migrations.AlterField(
            model_name="review",
            name="is_published",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Только опубликованные отзывы видны покупателям и учитываются в рейтинге",
                verbose_name="Опубликован",
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="moderated_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Дата модерации"
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="moderated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Модератор",
            ),
        ),
        migrations.RunPython(anonymize_reviews_of_deleted_accounts, migrations.RunPython.noop),
    ]
