from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from store.admin_catalog import ProductAdmin
from store.admin_site import bodysteel_admin_site
from store.models import Order


class AdminPanelRenderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username='body-steel-admin',
            email='body-steel-admin@example.com',
            phone='+998900000099',
            password='strong-admin-password',
            first_name='Body',
            last_name='Steel',
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_dashboard_uses_body_steel_workspace(self):
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bs-dashboard')
        self.assertContains(response, 'BODY STEEL')
        self.assertContains(response, 'body-steel-logo.png')
        self.assertContains(response, 'body-steel-dashboard.css')
        self.assertContains(response, 'body-steel-palette.css')
        self.assertContains(response, 'Быстрые действия')
        self.assertContains(response, 'id="nav-sidebar"')

    def test_catalog_and_users_lists_render(self):
        for url in ('/admin/store/product/', '/admin/users/user/', '/admin/teleg/chat/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'body-steel.css')
                self.assertContains(response, 'bs-brand')
                self.assertContains(response, 'bs-topnav')

    def test_every_admin_menu_entry_has_an_explicit_russian_title(self):
        request = RequestFactory().get('/admin/')
        request.user = self.admin_user
        app_list = bodysteel_admin_site.get_app_list(request)

        visible_apps = {app['app_label'] for app in app_list}
        visible_models = {
            model['model']._meta.label_lower
            for app in app_list
            for model in app['models']
        }
        self.assertEqual(visible_apps, set(bodysteel_admin_site.menu_app_titles))
        self.assertEqual(visible_models, set(bodysteel_admin_site.menu_model_titles))
        self.assertEqual(
            next(app['name'] for app in app_list if app['app_label'] == 'customer_telegram'),
            'Клиентский Telegram-бот',
        )
        self.assertIn(
            'Рассылки',
            {model['name'] for app in app_list for model in app['models']},
        )

    def test_every_admin_model_and_field_has_a_russian_label(self):
        for model in bodysteel_admin_site._registry:
            with self.subTest(model=model._meta.label):
                self.assertTrue(self._contains_cyrillic(str(model._meta.verbose_name)))
                self.assertTrue(self._contains_cyrillic(str(model._meta.verbose_name_plural)))
            fields = (*model._meta.fields, *model._meta.many_to_many)
            for field in fields:
                if field.name == 'id':
                    continue
                with self.subTest(model=model._meta.label, field=field.name):
                    label = str(field.verbose_name)
                    self.assertNotEqual(label, field.name.replace('_', ' '))
                    self.assertTrue(self._contains_cyrillic(label), label)

    @staticmethod
    def _contains_cyrillic(value):
        return any('\u0400' <= character <= '\u04ff' for character in value)

    def test_regos_mapping_fields_are_editable(self):
        readonly_fields = ProductAdmin.readonly_fields

        self.assertNotIn('regos_item_id', readonly_fields)
        self.assertNotIn('regos_item_code', readonly_fields)
        self.assertNotIn('regos_item_articul', readonly_fields)

    def test_login_uses_body_steel_workspace(self):
        self.client.logout()
        response = self.client.get('/admin/login/?next=/admin/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'body-steel-login.css')
        self.assertContains(response, 'body-steel-logo.png')
        self.assertContains(response, 'bs-login-shell')
        self.assertContains(response, 'data-password-toggle')

    def test_login_error_state_is_readable(self):
        self.client.logout()
        response = self.client.post(
            '/admin/login/?next=/admin/',
            {'username': 'wrong-user', 'password': 'wrong-password'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bs-login-alert')
        self.assertContains(response, 'Проверьте логин и пароль')


class OrderLocationAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username='order-map-admin',
            email='order-map-admin@example.com',
            phone='+998900000098',
            password='strong-admin-password',
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_order_change_page_shows_location_read_only_with_map_links(self):
        order = Order.objects.create(
            type='dcb', full_name='Map Customer', phone='+998901234567', address='Бухара, Накшбанди 5',
            address_latitude='39.774723', address_longitude='64.419841', address_label='Ляби-Хауз',
        )

        response = self.client.get(reverse('admin:store_order_change', args=(order.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ляби-Хауз')
        self.assertContains(response, 'https://maps.google.com/?q=39.774723,64.419841')
        self.assertContains(response, 'https://yandex.uz/maps/?pt=64.419841,39.774723&amp;z=17&amp;l=map')
        self.assertNotContains(response, 'name="address_latitude"')

    def test_order_without_location_has_no_map_links(self):
        order = Order.objects.create(type='pickup', full_name='Pickup Customer', phone='+998901234567')

        response = self.client.get(reverse('admin:store_order_change', args=(order.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'maps.google.com')
