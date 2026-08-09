import importlib
from io import StringIO
from types import SimpleNamespace

from django.apps import apps
from django.contrib.admin.sites import AdminSite
from django.core.management import call_command
from django.db import connection
from django.forms.widgets import Textarea
from django.test import SimpleTestCase, TestCase

from store.admin import ProductsAdmin
from store.content.html import sanitize_html
from store.models import Product
from store.serializers.products import ProductSerializer


MALICIOUS_HTML = (
    '<h2 style="position:fixed" onclick="steal()">Описание</h2>'
    '<script>alert(1)</script>'
    '<a href="javascript:alert(2)">bad</a>'
    '<a href="https://example.test/catalog">safe</a>'
    '<img src="https://example.test/product.jpg" onerror="steal()">'
)


class HtmlSanitizerTests(SimpleTestCase):
    def test_preserves_safe_formatting_and_removes_executable_content(self):
        sanitized = sanitize_html(MALICIOUS_HTML)

        self.assertIn('<h2>Описание</h2>', sanitized)
        self.assertNotIn('script', sanitized)
        self.assertNotIn('alert(1)', sanitized)
        self.assertNotIn('javascript:', sanitized)
        self.assertNotIn('onclick', sanitized)
        self.assertNotIn('onerror', sanitized)
        self.assertNotIn('style=', sanitized)
        self.assertIn('href="https://example.test/catalog"', sanitized)
        self.assertIn('rel="noopener noreferrer"', sanitized)
        self.assertIn('src="https://example.test/product.jpg"', sanitized)

    def test_denies_relative_and_protocol_relative_urls(self):
        sanitized = sanitize_html(
            '<a href="/internal">relative</a><img src="//tracker.test/pixel">'
        )

        self.assertNotIn('href=', sanitized)
        self.assertNotIn('src=', sanitized)


class SanitizedHtmlFieldTests(TestCase):
    def test_sanitizes_new_content_before_persistence(self):
        product = Product.objects.create(
            name_ru='Безопасный HTML',
            name_uz='Xavfsiz HTML',
            description_ru=MALICIOUS_HTML,
            description_uz='<p>Tavsif</p>',
            price=100_000,
            quantity=1,
            slug='safe-html-product',
            country_ru='Узбекистан',
            country_uz='O‘zbekiston',
        )

        product.refresh_from_db()
        self.assertEqual(product.description_ru, sanitize_html(MALICIOUS_HTML))

    def test_data_migration_sanitizes_rows_written_outside_model_save(self):
        product = Product.objects.create(
            name_ru='Миграция HTML',
            name_uz='HTML migratsiyasi',
            price=100_000,
            quantity=1,
            slug='html-migration-product',
            country_ru='Узбекистан',
            country_uz='O‘zbekiston',
        )
        Product.objects.filter(pk=product.pk).update(description_ru=MALICIOUS_HTML)
        migration = importlib.import_module('store.migrations.0036_sanitize_rich_html')

        migration.sanitize_existing_html(
            apps,
            SimpleNamespace(connection=connection),
        )

        product.refresh_from_db()
        self.assertEqual(product.description_ru, sanitize_html(MALICIOUS_HTML))

    def test_serializer_sanitizes_content_written_outside_model_save(self):
        product = Product.objects.create(
            name_ru='API HTML',
            name_uz='API HTML uz',
            price=100_000,
            quantity=1,
            slug='api-html-product',
            country_ru='Узбекистан',
            country_uz='O‘zbekiston',
        )
        Product.objects.filter(pk=product.pk).update(description_ru=MALICIOUS_HTML)
        product.refresh_from_db()

        serialized = ProductSerializer(product).data

        self.assertEqual(serialized['description_ru'], sanitize_html(MALICIOUS_HTML))

    def test_admin_uses_builtin_textarea_without_ckeditor_media(self):
        form = ProductsAdmin(Product, AdminSite()).get_form(request=None)
        widget = form.base_fields['description_ru'].widget

        self.assertIsInstance(widget, Textarea)
        self.assertNotIn('ckeditor', ' '.join(widget.media._js).lower())

    def test_audit_command_reports_counts_without_content(self):
        product = Product.objects.create(
            name_ru='Аудит HTML',
            name_uz='HTML auditi',
            price=100_000,
            quantity=1,
            slug='html-audit-product',
            country_ru='Узбекистан',
            country_uz='O‘zbekiston',
        )
        Product.objects.filter(pk=product.pk).update(description_ru=MALICIOUS_HTML)
        output = StringIO()

        call_command('audit_rich_html', stdout=output)

        report = output.getvalue()
        self.assertIn('store.Product.description_ru: 1', report)
        self.assertIn('total values requiring sanitization: 1', report)
        self.assertNotIn('alert(1)', report)
