import importlib
from io import BytesIO, StringIO
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from PIL import Image
from django.apps import apps
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.forms.widgets import Textarea
from django.test import override_settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from store.admin import ProductsAdmin
from store.content.html import sanitize_html
from store.content.policies.v2 import sanitize_html_v2
from store.models import Product
from store.serializers.products import ProductSerializer
from store.widgets import RichHtmlWidget


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

        self.assertIn('href="/internal"', sanitized)
        self.assertNotIn('src=', sanitized)

    def test_rich_policy_preserves_editor_formatting_and_local_media(self):
        sanitized = sanitize_html_v2(
            '<p class="lead" style="text-align:center;color:#b52020">'
            '<strong>Текст</strong></p><img src="/files/blog/cover.jpg" width="640">'
            '<script>alert(1)</script><a href="//evil.test">bad</a>'
        )

        self.assertIn('class="lead"', sanitized)
        self.assertIn('style="text-align:center;color:#b52020"', sanitized)
        self.assertIn('src="/files/blog/cover.jpg"', sanitized)
        self.assertIn('width="640"', sanitized)
        self.assertNotIn('<script', sanitized)
        self.assertNotIn('//evil.test', sanitized)


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

    def test_admin_uses_visual_rich_html_widget_with_safe_upload(self):
        form = ProductsAdmin(Product, AdminSite()).get_form(request=None)
        widget = form.base_fields['description_ru'].widget

        self.assertIsInstance(widget, Textarea)
        self.assertIsInstance(widget, RichHtmlWidget)
        self.assertIn('bs-rich-html-source', widget.attrs['class'])
        self.assertEqual(widget.attrs['data-rich-html-editor'], 'true')
        self.assertEqual(
            widget.attrs['data-upload-url'],
            reverse('bodysteel_admin:rich-html-upload'),
        )
        self.assertIn('body-steel-rich-html.css', ' '.join(widget.media._css['all']))
        self.assertIn('admin/js/body-steel-rich-html.js', widget.media._js)

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


class RichHtmlImageUploadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='rich-editor-admin',
            email='editor@example.test',
            phone='+998901110001',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_upload_requires_an_image(self):
        response = self.client.post(
            reverse('bodysteel_admin:rich-html-upload'),
            {'image': SimpleUploadedFile('note.txt', b'not an image', content_type='text/plain')},
        )

        self.assertEqual(response.status_code, 400)

    def test_upload_stores_verified_image_and_returns_media_url(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            image = Image.new('RGB', (2, 2), '#b52020')
            payload = BytesIO()
            image.save(payload, format='PNG')
            response = self.client.post(
                reverse('bodysteel_admin:rich-html-upload'),
                {'image': SimpleUploadedFile('pasted.png', payload.getvalue(), content_type='image/png')},
            )

        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.json()['url'], r'^/files/rich-content/\d{4}/\d{2}/[a-f0-9]{32}\.png$')

    def test_upload_rejects_non_staff_user(self):
        self.client.logout()
        user = get_user_model().objects.create_user(
            username='shopper',
            email='shopper@example.test',
            phone='+998901110002',
            password='test-password',
        )
        self.client.force_login(user)

        response = self.client.post(reverse('bodysteel_admin:rich-html-upload'))

        self.assertEqual(response.status_code, 302)
