from django.core.management import BaseCommand
from django.conf import settings

from requests import request

import json, os


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
            get notify.eskiz.uz token
        """

        data = {
            'email': settings.ESKIZ_PROVIDER_EMAIL,
            'password': settings.ESKIZ_PROVIDER_PASSWORD
        }

        response = request('POST', 'https://notify.eskiz.uz/api/auth/login', data=json.dumps(data),
                           headers={"Content-Type": "application/json"})

        if response.status_code == 200:
            os.environ.setdefault('ESKIZ_JWT_TOKEN', response.json().get('data').get('token'))

            print('Token received successfully!')
            return

        print('Something went wrong!')

