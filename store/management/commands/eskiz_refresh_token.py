from django.core.management import BaseCommand

from requests import request
import os


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
            refresh notify.eskiz.uz token
        """

        jwt_token = os.environ.get('ESKIZ_JWT_TOKEN')

        print(os.getenv('ESKIZ_JWT_TOKEN'))

        if jwt_token:
            response = request('PATCH', 'https://notify.eskiz.uz/api/auth/refresh',
                               headers={'Authorization': f'Bearer {jwt_token}'})

            if response.status_code == 200:
                os.environ.setdefault('ESKIZ_JWT_TOKEN', response.json().get('data').get('token'))

                print('Token updated successfully!')

            print('Something went wrong!')

        print('First get a token', 'run command `eskiz_get_token`', sep='\n')
