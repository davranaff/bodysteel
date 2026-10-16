import importlib

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.authtoken.models import Token

from store.catalog.reviews.privacy import ANONYMOUS_AUTHOR
from store.models import Order, Product, Review
from users.auth.account_security import deleted_phone
from users.models import User
from users.validators.phone import validate_phone


PASSWORD = 'BodySteel-secure-2026!'


class AccountDeletionCompletenessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='leaving-shopper', email='leaving@example.test', phone='+998904440001',
            password=PASSWORD, first_name='Ali', last_name='Valiyev',
        )
        self.token = Token.objects.create(user=self.user)
        self.product = Product.objects.create(
            name_ru='Гейнер', name_uz='Gainer', slug='deletion-gainer', price=1000, quantity=1,
        )
        self.review = Review.objects.create(
            product=self.product, user=self.user, rating=4, full_name='Ali Valiyev',
            comment='Мой номер +998904440001', is_published=True,
        )
        self.order = Order.objects.create(
            user=self.user, full_name='Ali Valiyev', phone='+998904440001', address='Toshkent',
            total_price=1000,
        )

    def assert_erased(self):
        self.user.refresh_from_db()
        self.review.refresh_from_db()
        self.order.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.user.phone, deleted_phone(self.user.pk))
        with self.assertRaises(ValidationError):
            validate_phone(self.user.phone)
        self.assertLessEqual(len(self.user.phone), 13)
        # Reviews keep the rating but lose the author link, name and free text.
        self.assertIsNone(self.review.user)
        self.assertEqual(self.review.full_name, ANONYMOUS_AUTHOR)
        self.assertEqual(self.review.comment, '')
        self.assertEqual(self.review.rating, 4)
        # Orders are retained for accounting/legal reasons.
        self.assertEqual((self.order.user_id, self.order.phone), (self.user.pk, '+998904440001'))

    def test_delete_endpoint_anonymizes_reviews_and_uses_safe_phone_placeholder(self):
        response = self.client.post(
            '/api/v1/users/delete/', {'password': PASSWORD, 'confirmation': 'DELETE'},
            content_type='application/json', HTTP_AUTHORIZATION=f'Token {self.token.key}',
        )

        self.assertEqual(response.status_code, 204)
        self.assert_erased()
        detail = self.client.get(f'/api/v1/store/products/{self.product.slug}/').json()['data']
        public = detail['reviews'][0]
        self.assertEqual((public['full_name'], public['user'], public['author_id']), (ANONYMOUS_AUTHOR, None, None))
        self.assertNotIn('Valiyev', str(detail))

    def test_me_delete_shares_the_same_erasure(self):
        response = self.client.delete('/api/v1/users/me/', HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.assertEqual(response.status_code, 204)
        self.assert_erased()

    def test_placeholders_are_unique_and_never_block_real_numbers(self):
        self.client.delete('/api/v1/users/me/', HTTP_AUTHORIZATION=f'Token {self.token.key}')
        other = User.objects.create_user(
            username='second', email='second@example.test', phone='+998904440002', password=PASSWORD,
        )
        self.assertNotEqual(deleted_phone(self.user.pk), deleted_phone(other.pk))
        # The deleted customer's real number is free again for a new account.
        User.objects.create_user(
            username='returning', email='returning@example.test', phone='+998904440001', password=PASSWORD,
        )

    def test_data_migrations_fix_previously_deleted_accounts(self):
        self.user.deleted_at = self.user.date_joined
        self.user.is_active = False
        self.user.phone = '+998123456789'
        self.user.save()
        users_migration = importlib.import_module('users.migrations.0010_deleted_phone_placeholders')
        store_migration = importlib.import_module('store.migrations.0048_review_moderation')

        users_migration.replace_numeric_placeholders(django_apps, None)
        store_migration.anonymize_reviews_of_deleted_accounts(django_apps, None)

        self.user.refresh_from_db()
        self.review.refresh_from_db()
        self.assertEqual(self.user.phone, deleted_phone(self.user.pk))
        self.assertEqual((self.review.user, self.review.comment), (None, ''))
