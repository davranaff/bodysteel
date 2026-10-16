from unittest.mock import patch

from django.test import RequestFactory, TestCase
from rest_framework.authtoken.models import Token

from store.admin_reviews import ReviewAdmin
from store.admin_site import bodysteel_admin_site
from store.catalog.reviews.privacy import author_key
from store.models import Favorite, Product, Review
from users.models import User


PUBLIC_REVIEW_KEYS = {
    'id', 'user', 'author_id', 'full_name', 'rating', 'comment', 'product', 'created_at',
}


def make_user(name, phone):
    return User.objects.create_user(
        username=name, email=f'{name}@example.test', phone=phone, password='BodySteel-secure-2026!',
        first_name='Ali', last_name='Valiyev',
    )


class ReviewModerationTests(TestCase):
    def setUp(self):
        self.author = make_user('review-author', '+998901110001')
        self.product = Product.objects.create(
            name_ru='Протеин', name_uz='Protein', slug='review-protein', price=100000, quantity=3,
        )
        self.published = Review.objects.create(
            product=self.product, user=self.author, rating=5, comment='Отлично', is_published=True,
        )
        self.pending = Review.objects.create(
            product=self.product, user=self.author, rating=1, comment='Спам http://x', is_published=False,
        )

    def test_new_reviews_default_to_unpublished(self):
        review = Review.objects.create(product=self.product, rating=4, comment='Новый')
        self.assertFalse(review.is_published)

    @patch('users.views.notify_review.notify_review')
    def test_created_review_waits_for_moderation_and_keeps_storefront_contract(self, notify):
        token = Token.objects.create(user=self.author)
        response = self.client.post(
            '/api/v1/users/reviews/',
            {'rating': 4, 'comment': 'Хорошо', 'product': self.product.pk, 'is_published': True},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response['X-Review-Status'], 'pending_moderation')
        payload = response.json()
        # The website proxy validates this exact key set.
        self.assertEqual(set(payload), {'data', 'bonus'})
        self.assertEqual(
            set(payload['data']),
            {'comment', 'created_at', 'full_name', 'id', 'product', 'rating', 'user'},
        )
        review = Review.objects.get(pk=payload['data']['id'])
        self.assertFalse(review.is_published)
        self.assertEqual(review.user, self.author)
        notify.assert_called_once()

    def test_review_notification_failure_does_not_fail_submission(self):
        from teleg.models import Chat
        Chat.objects.create(chat_id='1', first_name='Staff')
        token = Token.objects.create(user=self.author)
        with patch('teleg.utils.notify_review.bot.send_message', side_effect=RuntimeError('down')), \
                patch('teleg.utils.notify_review.logger.exception') as logged:
            response = self.client.post(
                '/api/v1/users/reviews/',
                {'rating': 5, 'comment': 'Супер', 'product': self.product.pk},
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Token {token.key}',
            )
        self.assertEqual(response.status_code, 201)
        logged.assert_called_once()

    def test_product_detail_returns_only_published_pii_free_reviews(self):
        response = self.client.get(f'/api/v1/store/products/{self.product.slug}/')

        self.assertEqual(response.status_code, 200)
        product = response.json()['data']
        self.assertEqual([review['id'] for review in product['reviews']], [self.published.pk])
        review = product['reviews'][0]
        self.assertEqual(set(review), PUBLIC_REVIEW_KEYS)
        self.assertEqual(review['user'], {'username': 'review-author'})
        self.assertEqual(review['author_id'], author_key(self.author.pk))
        self.assertEqual(product['rating'], 5)
        body = response.content.decode()
        for private in ('review-author@example.test', '+998901110001', 'Valiyev', 'Спам'):
            self.assertNotIn(private, body)

    def test_list_home_and_unprefetched_paths_use_only_published_reviews(self):
        list_response = self.client.get('/api/v1/store/products/')
        listed = next(item for item in list_response.json()['data'] if item['id'] == self.product.pk)
        self.assertEqual(listed['rating'], 5)
        self.assertEqual(len(listed['reviews']), 1)

        home = self.client.get('/api/v1/store/home/').json()['data']
        latest = next(item for item in home['latest_products'] if item['id'] == self.product.pk)
        self.assertEqual(latest['rating'], 5)
        self.assertEqual([review['id'] for review in latest['reviews']], [self.published.pk])

        Favorite.objects.create(user=self.author, product=self.product)
        token = Token.objects.create(user=self.author)
        favorites = self.client.get('/api/v1/users/favorites/', HTTP_AUTHORIZATION=f'Token {token.key}')
        reviews = favorites.json()[0]['product']['reviews']
        self.assertEqual([review['id'] for review in reviews], [self.published.pk])

    def test_rating_is_zero_without_published_reviews(self):
        self.published.is_published = False
        self.published.save()
        product = Product.objects.with_rating().get(pk=self.product.pk)
        self.assertEqual(product.rating, 0)
        self.assertEqual(product.review_count, 0)

    def test_author_key_is_stable_opaque_and_null_without_author(self):
        key = author_key(self.author.pk)
        self.assertEqual(key, author_key(self.author.pk))
        self.assertNotEqual(key, author_key(self.author.pk + 1))
        self.assertEqual(len(key), 32)
        self.assertRegex(key, r'^[0-9a-f]{32}$')
        self.assertIsNone(author_key(None))

    def test_admin_bulk_actions_publish_and_hide_with_audit(self):
        staff = User.objects.create_superuser(
            username='moderator', email='moderator@example.test', phone='+998901110009', password='x' * 12,
        )
        admin = ReviewAdmin(Review, bodysteel_admin_site)
        request = RequestFactory().post('/admin/store/review/')
        request.user = staff
        with patch.object(admin, 'message_user'):
            admin.publish_reviews(request, Review.objects.filter(pk=self.pending.pk))
            self.pending.refresh_from_db()
            self.assertTrue(self.pending.is_published)
            self.assertEqual(self.pending.moderated_by, staff)
            self.assertIsNotNone(self.pending.moderated_at)

            admin.unpublish_reviews(request, Review.objects.filter(pk=self.pending.pk))
        self.pending.refresh_from_db()
        self.assertFalse(self.pending.is_published)

        self.client.force_login(staff)
        changelist = self.client.get('/admin/store/review/?is_published__exact=0')
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, 'На модерации')
