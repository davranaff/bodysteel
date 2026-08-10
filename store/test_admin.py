from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from store.admin_catalog import ProductAdmin


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
