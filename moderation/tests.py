import uuid
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings
from rest_framework.authtoken.models import Token

from moderation.admin import ContentReportAdmin
from moderation.models import ContentReport
from moderation.notify import format_report_notification, notify_staff_about_report
from moderation.services import CONTENT_REPORT_USER
from store.admin_site import bodysteel_admin_site
from store.models import Product, Review
from teleg.models import Chat
from users.auth.test_registration import SECURITY_SETTINGS
from users.models import User


URL = '/api/v1/users/content-reports/'


def make_user(name, phone):
    return User.objects.create_user(
        username=name, email=f'{name}@example.test', phone=phone, password='BodySteel-secure-2026!',
    )


@override_settings(**SECURITY_SETTINGS)
@patch('moderation.services.notify_staff_about_report')
class ContentReportApiTests(TestCase):
    def setUp(self):
        self.user = make_user('reporter', '+998902220001')
        self.token = Token.objects.create(user=self.user)
        product = Product.objects.create(
            name_ru='Креатин', name_uz='Kreatin', slug='report-creatine', price=1000, quantity=1,
        )
        self.review = Review.objects.create(
            product=product, rating=1, comment='Плохой отзыв', is_published=True,
        )

    def post(self, body, token=None, language='ru'):
        headers = {'HTTP_AUTHORIZATION': f'Token {(token or self.token).key}'}
        if language:
            headers['HTTP_ACCEPT_LANGUAGE'] = language
        return self.client.post(URL, body, content_type='application/json', **headers)

    def test_review_report_is_created_and_staff_notified_after_commit(self, notify):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post({
                'kind': 'review', 'reason': 'offensive', 'review_id': self.review.pk,
                'comment': '  грубость  ',
            })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response['Content-Language'], 'ru')
        report = ContentReport.objects.get()
        self.assertEqual(response.json(), {'data': {'id': report.pk}})
        self.assertEqual(
            (report.reporter, report.kind, report.review, report.reason, report.comment, report.status),
            (self.user, 'review', self.review, 'offensive', 'грубость', 'open'),
        )
        notify.assert_called_once_with(report)

    def test_ai_answer_report_stores_excerpt_and_conversation(self, notify):
        conversation = uuid.uuid4()
        response = self.post({
            'kind': 'ai_answer', 'reason': 'incorrect', 'excerpt': 'Пейте 10 литров воды',
            'conversation_id': str(conversation), 'review_id': None,
        }, language='uz')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response['Content-Language'], 'uz')
        report = ContentReport.objects.get()
        self.assertEqual(report.excerpt, 'Пейте 10 литров воды')
        self.assertEqual(report.conversation_id, conversation)
        self.assertIsNone(report.review)

    def test_invalid_bodies_are_rejected_without_side_effects(self, notify):
        cases = [
            {'kind': 'review', 'reason': 'spam'},
            {'kind': 'ai_answer', 'reason': 'spam'},
            {'kind': 'ai_answer', 'reason': 'spam', 'excerpt': '   '},
            {'kind': 'review', 'reason': 'spam', 'review_id': self.review.pk, 'excerpt': 'x'},
            {'kind': 'ai_answer', 'reason': 'spam', 'excerpt': 'x', 'review_id': self.review.pk},
            {'kind': 'review', 'reason': 'spam', 'review_id': self.review.pk, 'conversation_id': str(uuid.uuid4())},
            {'kind': 'review', 'reason': 'rude', 'review_id': self.review.pk},
            {'kind': 'post', 'reason': 'spam', 'review_id': self.review.pk},
            {'kind': 'review', 'reason': 'spam', 'review_id': self.review.pk, 'extra': 1},
            {'kind': 'review', 'reason': 'spam', 'review_id': self.review.pk, 'comment': 'x' * 501},
            {'kind': 'ai_answer', 'reason': 'spam', 'excerpt': 'x' * 2001},
            {'kind': 'ai_answer', 'reason': 'spam', 'excerpt': 'x', 'conversation_id': 'nope'},
            {'kind': 'review', 'reason': 'spam', 'review_id': 'abc'},
            ['kind', 'review'],
        ]
        for body in cases:
            with self.subTest(body=body):
                response = self.post(body)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['error']['code'], 'invalid_request')
        self.assertFalse(ContentReport.objects.exists())

    def test_malformed_json_returns_problem(self, notify):
        response = self.client.post(
            URL, '{bad', content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {self.token.key}', HTTP_ACCEPT_LANGUAGE='ru',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'invalid_request')

    def test_missing_review_returns_not_found(self, notify):
        response = self.post({'kind': 'review', 'reason': 'spam', 'review_id': 999_999})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], 'review_not_found')

    def test_authentication_and_language_are_required(self, notify):
        unauthenticated = self.client.post(
            URL, {'kind': 'ai_answer', 'reason': 'spam', 'excerpt': 'x'},
            content_type='application/json', HTTP_ACCEPT_LANGUAGE='ru',
        )
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(unauthenticated.json()['error']['code'], 'unauthorized')

        no_language = self.post({'kind': 'ai_answer', 'reason': 'spam', 'excerpt': 'x'}, language=None)
        self.assertEqual(no_language.status_code, 406)
        self.assertEqual(no_language.json()['error']['code'], 'language_not_acceptable')

    def test_repeated_open_review_report_is_idempotent(self, notify):
        body = {'kind': 'review', 'reason': 'spam', 'review_id': self.review.pk}
        first = self.post(body)
        second = self.post(body)

        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(ContentReport.objects.count(), 1)

    def test_reports_are_rate_limited_per_user(self, notify):
        body = {'kind': 'ai_answer', 'reason': 'other', 'excerpt': 'Ответ'}
        for _ in range(CONTENT_REPORT_USER.limit):
            self.assertEqual(self.post(body).status_code, 201)

        limited = self.post(body)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()['error']['code'], 'rate_limited')
        self.assertIn('Retry-After', limited)

        other = make_user('other-reporter', '+998902220002')
        self.assertEqual(self.post(body, token=Token.objects.create(user=other)).status_code, 201)

    def test_review_is_hidden_after_three_distinct_open_reports(self, notify):
        body = {'kind': 'review', 'reason': 'offensive', 'review_id': self.review.pk}
        for index in range(3):
            self.review.refresh_from_db()
            self.assertTrue(self.review.is_published)
            reporter = make_user(f'reporter-{index}', f'+99890222001{index}')
            self.assertEqual(self.post(body, token=Token.objects.create(user=reporter)).status_code, 201)

        self.review.refresh_from_db()
        self.assertFalse(self.review.is_published)


class ContentReportStaffTests(TestCase):
    def setUp(self):
        self.reporter = make_user('private-reporter', '+998903330001')
        self.staff = User.objects.create_superuser(
            username='report-admin', email='report-admin@example.test', phone='+998903330009',
            password='x' * 12,
        )
        product = Product.objects.create(name_ru='Омега', name_uz='Omega', slug='report-omega', price=1, quantity=1)
        self.review = Review.objects.create(product=product, rating=2, comment='<b>текст</b>', is_published=True)
        self.review_report = ContentReport.objects.create(
            reporter=self.reporter, kind='review', review=self.review, reason='spam', comment='реклама',
        )
        self.ai_report = ContentReport.objects.create(
            reporter=self.reporter, kind='ai_answer', reason='incorrect', excerpt='Ответ ИИ',
        )

    def test_notification_contains_moderation_context_but_no_reporter_identity(self):
        text = format_report_notification(self.review_report)
        self.assertIn(f'Отзыв #{self.review.pk}', text)
        self.assertIn('&lt;b&gt;текст&lt;/b&gt;', text)
        self.assertIn('реклама', text)
        for private in ('private-reporter', '+998903330001', 'private-reporter@example.test'):
            self.assertNotIn(private, text)
        self.assertIn('Ответ ИИ', format_report_notification(self.ai_report))

    def test_notification_is_best_effort(self):
        Chat.objects.create(chat_id='42', first_name='Staff')
        with patch('teleg.views.bot.send_message', side_effect=RuntimeError('down')) as send, \
                patch('moderation.notify.logger.exception') as logged:
            notify_staff_about_report(self.review_report)
        send.assert_called_once()
        logged.assert_called_once()

    def test_admin_actions_resolve_dismiss_and_hide(self):
        admin = ContentReportAdmin(ContentReport, bodysteel_admin_site)
        request = RequestFactory().post('/admin/moderation/contentreport/')
        request.user = self.staff
        with patch.object(admin, 'message_user'):
            admin.resolve_and_hide_reviews(request, ContentReport.objects.filter(pk=self.review_report.pk))
            admin.dismiss_reports(request, ContentReport.objects.filter(pk=self.ai_report.pk))

        self.review.refresh_from_db()
        self.review_report.refresh_from_db()
        self.ai_report.refresh_from_db()
        self.assertFalse(self.review.is_published)
        self.assertEqual(self.review.moderated_by, self.staff)
        self.assertEqual((self.review_report.status, self.review_report.resolved_by), ('resolved', self.staff))
        self.assertIsNotNone(self.review_report.resolved_at)
        self.assertEqual(self.ai_report.status, 'dismissed')

        with patch.object(admin, 'message_user'):
            admin.resolve_reports(request, ContentReport.objects.all())
        self.ai_report.refresh_from_db()
        self.assertEqual(self.ai_report.status, 'dismissed')

    def test_admin_pages_render_with_filters(self):
        self.client.force_login(self.staff)
        changelist = self.client.get('/admin/moderation/contentreport/?status__exact=open&kind__exact=review')
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, 'Открыта')
        change = self.client.get(f'/admin/moderation/contentreport/{self.review_report.pk}/change/')
        self.assertEqual(change.status_code, 200)
        reviews = self.client.get('/admin/store/review/')
        self.assertEqual(reviews.status_code, 200)
