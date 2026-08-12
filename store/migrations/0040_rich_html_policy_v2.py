from django.db import migrations

from store.content.policies.v2 import sanitize_html_v2


HTML_FIELDS = {
    'Blog': ('description_ru', 'description_uz'),
    'Category': ('description',),
    'Menu': (
        'about_ru', 'about_uz', 'blog_ru', 'blog_uz', 'bukhara_description_ru',
        'bukhara_description_uz', 'delivery_and_payment_ru', 'delivery_and_payment_uz',
        'set_product_ru', 'set_product_uz', 'uzbekistan_description_ru',
        'uzbekistan_description_uz',
    ),
    'Product': ('composition_ru', 'composition_uz', 'description_ru', 'description_uz'),
}


def upgrade_existing_html(apps, schema_editor):
    database = schema_editor.connection.alias
    for model_name, field_names in HTML_FIELDS.items():
        model = apps.get_model('store', model_name)
        for record in model.objects.using(database).only('pk', *field_names).iterator(chunk_size=200):
            changed = []
            for field_name in field_names:
                value = getattr(record, field_name)
                sanitized = sanitize_html_v2(value)
                if sanitized != value:
                    setattr(record, field_name, sanitized)
                    changed.append(field_name)
            if changed:
                record.save(using=database, update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [('store', '0039_product_regos_catalog_status')]

    operations = [migrations.RunPython(upgrade_existing_html, migrations.RunPython.noop)]
