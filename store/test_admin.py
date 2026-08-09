from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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
        self.assertContains(response, 'body-steel-dashboard.css')
        self.assertContains(response, 'Быстрые действия')

    def test_catalog_and_users_lists_render(self):
        for url in ('/admin/store/product/', '/admin/users/user/', '/admin/teleg/chat/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'body-steel.css')
                self.assertContains(response, 'bs-brand')
                self.assertContains(response, 'bs-topnav')
