from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from django.utils.datastructures import MultiValueDict

from courses.forms import LessonMaterialUploadForm
from courses.models import Course, CourseAccess, CourseModule, CoursePurchase, Lesson
from payments.models import Payment
from users.models import User


class CoursePurchaseFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='course-user', email='course@example.test', phone='+998901234567', password='password123',
        )
        self.course = Course.objects.create(
            slug='weight-loss-30', title_ru='Похудение за 30 дней', title_uz='30 kunda ozish',
            summary_ru='Программа', summary_uz='Dastur', description_ru='<p>Text</p>', description_uz='<p>Matn</p>',
            price=250000, status=Course.PUBLISHED, duration_days=30,
        )
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token {}'.format(Token.objects.create(user=self.user).key))

    def test_purchase_is_idempotent_and_access_follows_successful_payment(self):
        headers = {'HTTP_IDEMPOTENCY_KEY': 'course-test-key-1234'}
        response = self.client.post('/api/v1/courses/weight-loss-30/purchases/', {}, format='json', **headers)
        self.assertEqual(response.status_code, 201)
        purchase = CoursePurchase.objects.get()
        payment = Payment.objects.get(course_purchase=purchase)
        self.assertEqual(purchase.status, CoursePurchase.PENDING)
        self.assertFalse(CourseAccess.objects.exists())

        replay = self.client.post('/api/v1/courses/weight-loss-30/purchases/', {}, format='json', **headers)
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.data['data']['id'], response.data['data']['id'])
        self.assertEqual(CoursePurchase.objects.count(), 1)

        with override_settings(DEBUG=True):
            completed = self.client.post('/api/v1/payments/{}/manual-complete/'.format(payment.pk), {}, format='json')
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(CoursePurchase.objects.get().status, CoursePurchase.PAID)
        self.assertTrue(CourseAccess.objects.filter(user=self.user, course=self.course, status='active').exists())

        history = self.client.get('/api/v1/courses/purchases/', HTTP_ACCEPT_LANGUAGE='uz')
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data['data'][0]['course_slug'], self.course.slug)
        self.assertEqual(history.data['data'][0]['course_title'], self.course.title_uz)
        self.assertEqual(history.data['data'][0]['status'], CoursePurchase.PAID)
        self.assertEqual(history.data['data'][0]['access']['status'], CourseAccess.ACTIVE)

    def test_another_user_cannot_open_personal_course(self):
        response = self.client.get('/api/v1/courses/me/weight-loss-30/')
        self.assertEqual(response.status_code, 403)


class LessonMaterialUploadTests(TestCase):
    def setUp(self):
        course = Course.objects.create(
            slug='mixed-media-course', title_ru='Смешанный курс', title_uz='Aralash kurs',
            summary_ru='Программа', summary_uz='Dastur', description_ru='<p>Text</p>',
            description_uz='<p>Matn</p>', price=0, status=Course.PUBLISHED,
        )
        module = CourseModule.objects.create(
            course=course, title_ru='Модуль', title_uz='Modul', position=1,
        )
        self.lesson = Lesson.objects.create(
            module=module, title_ru='Урок', title_uz='Dars', position=1,
        )

    def test_upload_form_accepts_multiple_mixed_media_files(self):
        files = MultiValueDict({'files': [
            SimpleUploadedFile('board.jpg', b'image', content_type='image/jpeg'),
            SimpleUploadedFile('walkthrough.mp4', b'video', content_type='video/mp4'),
        ]})
        form = LessonMaterialUploadForm(
            {'lesson': self.lesson.pk, 'is_downloadable': 'on'},
            files,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data['files']), 2)
