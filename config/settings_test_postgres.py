import os

from django.core.exceptions import ImproperlyConfigured

from config.settings import *  # noqa: F403


REQUIRED_DATABASE_SETTINGS = {
    'NAME': os.getenv('TEST_DATABASE_NAME', ''),
    'USER': os.getenv('TEST_DATABASE_USER', ''),
    'PASSWORD': os.getenv('TEST_DATABASE_PASSWORD', ''),
    'HOST': os.getenv('TEST_DATABASE_HOST', '127.0.0.1'),
    'PORT': os.getenv('TEST_DATABASE_PORT', '5432'),
}

if not all(REQUIRED_DATABASE_SETTINGS.values()):
    raise ImproperlyConfigured(
        'TEST_DATABASE_NAME, TEST_DATABASE_USER and TEST_DATABASE_PASSWORD are required'
    )

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        **REQUIRED_DATABASE_SETTINGS,
        'CONN_MAX_AGE': 0,
    },
}
