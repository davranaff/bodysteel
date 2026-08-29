from django.db import migrations, models
from django.db.models.functions import Lower


def merge_case_insensitive_duplicates(apps, schema_editor):
    Coupon = apps.get_model('store', 'Coupon')
    Order = apps.get_model('store', 'Order')
    database = schema_editor.connection.alias
    groups = {}
    coupons = Coupon.objects.using(database).all().order_by(
        '-is_active', '-created_at', '-pk',
    )
    for coupon in coupons:
        groups.setdefault(coupon.code.casefold(), []).append(coupon)

    for matches in groups.values():
        if len(matches) < 2:
            continue
        canonical, duplicates = matches[0], matches[1:]
        duplicate_ids = [coupon.pk for coupon in duplicates]
        used_count = sum(coupon.used_count for coupon in matches)
        max_uses = max(used_count, *(coupon.max_uses for coupon in matches))
        is_active = any(coupon.is_active for coupon in matches) and used_count < max_uses
        Order.objects.using(database).filter(coupon_id__in=duplicate_ids).update(
            coupon_id=canonical.pk,
        )
        Coupon.objects.using(database).filter(pk__in=duplicate_ids).delete()
        Coupon.objects.using(database).filter(pk=canonical.pk).update(
            used_count=used_count,
            max_uses=max_uses,
            is_active=is_active,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('store', '0043_alter_basket_created_at_alter_basket_order_and_more'),
    ]

    operations = [
        migrations.RunPython(
            merge_case_insensitive_duplicates,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='coupon',
            constraint=models.UniqueConstraint(
                Lower('code'),
                name='store_coupon_code_ci_uniq',
            ),
        ),
    ]
