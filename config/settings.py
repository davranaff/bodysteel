from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent

DEVELOPMENT_SECRET_KEY = 'unsafe-development-only-change-me'
SECRET_KEY = os.getenv('SECRET_KEY', DEVELOPMENT_SECRET_KEY)

DEBUG = os.getenv('DEBUG', '').strip().lower() in {'1', 'true', 'yes'}

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if host.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'drf_yasg',
    'corsheaders',
    'users',
    'store',
    'courses',
    'payments',
    'nutrition',
    'rest_framework',
    'rest_framework.authtoken',
    'teleg',
    'customer_telegram.apps.CustomerTelegramConfig',
    'integration.apps.IntegrationConfig',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'config.middleware.AuthMiddleware',
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:3000",
    "http://localhost:3003",
    "https://bodysteel.vercel.app",
    "https://bodysteel.uz",
    "https://api.bodysteel.uz",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3003",
    "https://bodysteel.vercel.app",
    "https://bodysteel.uz",
]

ROOT_URLCONF = 'config.urls'

WSGI_APPLICATION = 'config.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'ru'

TIME_ZONE = 'Asia/Tashkent'

USE_I18N = True

USE_TZ = True

LANGUAGES = (
    ('uz', 'Uzbek'),
    ('ru', 'Russia'),
)

STATIC_URL = '/assets/'
STATIC_ROOT = BASE_DIR / 'assets'

MEDIA_URL = '/files/'
MEDIA_ROOT = BASE_DIR / 'files'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'users.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    ),
    'EXCEPTION_HANDLER': 'users.auth.exception_handler.exception_handler',
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.MultiPartRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    )
}

BASE_URL = 'http://localhost:8000/'

LOGIN_URL = 'http://localhost:8000/api/v1/users/signin/'
SIGNUP_URL = 'http://localhost:8000/api/v1/users/signup/'

ESKIZ_FROM_TO = os.getenv("ESKIZ_FROM_TO")
ESKIZ_PROVIDER_EMAIL = os.getenv("ESKIZ_PROVIDER_EMAIL")
ESKIZ_PROVIDER_PASSWORD = os.getenv("ESKIZ_PROVIDER_PASSWORD")
ESKIZ_OTP_TEMPLATE = os.getenv('ESKIZ_OTP_TEMPLATE', '')
SMS_BACKEND = os.getenv('SMS_BACKEND', 'disabled')

BODYSTEEL_STOREFRONT_PROXY_TOKEN = os.getenv('BODYSTEEL_STOREFRONT_PROXY_TOKEN', '')
PHONE_VERIFICATION_HASH_KEY = os.getenv('PHONE_VERIFICATION_HASH_KEY', '')
AUTH_RATE_LIMIT_HASH_KEY = os.getenv('AUTH_RATE_LIMIT_HASH_KEY', '')
AUTH_CHALLENGE_HASH_KEY = os.getenv('AUTH_CHALLENGE_HASH_KEY', '')
PHONE_VERIFICATION_TTL_SECONDS = os.getenv('PHONE_VERIFICATION_TTL_SECONDS', '300')
PHONE_VERIFICATION_RESEND_SECONDS = os.getenv('PHONE_VERIFICATION_RESEND_SECONDS', '60')
PHONE_VERIFICATION_MAX_ATTEMPTS = os.getenv('PHONE_VERIFICATION_MAX_ATTEMPTS', '5')
PASSWORD_RESET_TTL_SECONDS = os.getenv('PASSWORD_RESET_TTL_SECONDS', '600')
PASSWORD_RESET_RESEND_SECONDS = os.getenv('PASSWORD_RESET_RESEND_SECONDS', '60')
PASSWORD_RESET_MAX_ATTEMPTS = os.getenv('PASSWORD_RESET_MAX_ATTEMPTS', '5')
AUTH_TRUSTED_PROXY_NETWORKS = tuple(
    network.strip()
    for network in os.getenv('AUTH_TRUSTED_PROXY_NETWORKS', '').split(',')
    if network.strip()
)

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND")
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = os.getenv("EMAIL_PORT")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
AUTH_EMAIL_BACKEND = os.getenv('AUTH_EMAIL_BACKEND', 'smtp')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@bodysteel.uz')

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
TELEGRAM_API_URL = f'https://api.telegram.org/bot{BOT_TOKEN}'
BOT_POOLING_INTERVAL = 5

CUSTOMER_TELEGRAM_ENABLED = os.getenv(
    'CUSTOMER_TELEGRAM_ENABLED', '',
).strip().lower() in {'1', 'true', 'yes'}
CUSTOMER_TELEGRAM_CAMPAIGNS_ENABLED = os.getenv(
    'CUSTOMER_TELEGRAM_CAMPAIGNS_ENABLED', '',
).strip().lower() in {'1', 'true', 'yes'}
CUSTOMER_TELEGRAM_BOT_TOKEN = os.getenv('CUSTOMER_TELEGRAM_BOT_TOKEN', '')
CUSTOMER_TELEGRAM_BOT_USERNAME = os.getenv('CUSTOMER_TELEGRAM_BOT_USERNAME', '')
CUSTOMER_TELEGRAM_WEBHOOK_SECRET = os.getenv('CUSTOMER_TELEGRAM_WEBHOOK_SECRET', '')
CUSTOMER_TELEGRAM_LINK_HASH_KEY = os.getenv('CUSTOMER_TELEGRAM_LINK_HASH_KEY', '')
CUSTOMER_TELEGRAM_PUBLIC_ORIGIN = os.getenv(
    'CUSTOMER_TELEGRAM_PUBLIC_ORIGIN', 'https://api.bodysteel.uz',
)
CUSTOMER_TELEGRAM_WEBHOOK_URL = os.getenv(
    'CUSTOMER_TELEGRAM_WEBHOOK_URL',
    f'{CUSTOMER_TELEGRAM_PUBLIC_ORIGIN}/telegram/customer/webhook/',
)
CUSTOMER_TELEGRAM_STORE_ORIGIN = os.getenv(
    'CUSTOMER_TELEGRAM_STORE_ORIGIN', 'https://bodysteel.uz',
)
CUSTOMER_TELEGRAM_LINK_TTL_SECONDS = os.getenv(
    'CUSTOMER_TELEGRAM_LINK_TTL_SECONDS', '300',
)
CUSTOMER_TELEGRAM_CONTACT_MAX_ATTEMPTS = os.getenv(
    'CUSTOMER_TELEGRAM_CONTACT_MAX_ATTEMPTS', '3',
)


SAVDOQ_INTEGRATION_CREDENTIALS = tuple(
    credential
    for credential in (
        {
            'token': os.getenv('SAVDOQ_INTEGRATION_FULL_TOKEN', ''),
            'scopes': ('products:read', 'inventory:read', 'carts:write'),
        },
        {
            'token': os.getenv('SAVDOQ_INTEGRATION_READ_TOKEN', ''),
            'scopes': ('products:read', 'inventory:read'),
        },
    )
    if credential['token']
)
SAVDOQ_INTEGRATION_CHECK_ENABLED = not DEBUG
SAVDOQ_STOREFRONT_ORIGIN = os.getenv('SAVDOQ_STOREFRONT_ORIGIN', 'https://bodysteel.uz')
SAVDOQ_MEDIA_ORIGIN = os.getenv('SAVDOQ_MEDIA_ORIGIN', 'https://api.bodysteel.uz')
SAVDOQ_ALLOW_LOCAL_ORIGINS = (
    DEBUG and os.getenv('SAVDOQ_ALLOW_LOCAL_ORIGINS', '').strip().lower() in {'1', 'true', 'yes'}
)
SAVDOQ_CART_TTL_SECONDS = int(os.getenv('SAVDOQ_CART_TTL_SECONDS', '3600'))
SAVDOQ_WEBHOOK_URL = os.getenv('SAVDOQ_WEBHOOK_URL', '')
SAVDOQ_WEBHOOK_SECRET = os.getenv('SAVDOQ_WEBHOOK_SECRET', '')

# REGOS remains the inventory source of truth.  These settings are deliberately
# server-only: no REGOS credential is ever exposed through the Next.js app.
REGOS_INTEGRATION_KEY = os.getenv('REGOS_INTEGRATION_KEY', '')
REGOS_API_ENDPOINT = os.getenv('REGOS_API_ENDPOINT', '')
REGOS_STOCK_IDS = tuple(
    value.strip()
    for value in os.getenv('REGOS_STOCK_IDS', '').split(',')
    if value.strip()
)
REGOS_API_TIMEOUT_SECONDS = int(os.getenv('REGOS_API_TIMEOUT_SECONDS', '15'))
REGOS_TO_SERVER_USERNAME = os.getenv('REGOS_TO_SERVER_USERNAME', '')
REGOS_TO_SERVER_PASSWORD = os.getenv('REGOS_TO_SERVER_PASSWORD', '')
REGOS_CONNECTED_INTEGRATION_ID = os.getenv('REGOS_CONNECTED_INTEGRATION_ID', '')
PAYMENT_WEBHOOK_SECRET = os.getenv('PAYMENT_WEBHOOK_SECRET', '')


if not DEBUG:
    from .settings_prod import *
else:
    try:
        from .settings_dev import *
    except ModuleNotFoundError as error:
        if error.name != 'config.settings_dev':
            raise
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': os.getenv('SQLITE_DATABASE_PATH', BASE_DIR / 'db.sqlite3'),
            },
        }


if not DEBUG and SECRET_KEY == DEVELOPMENT_SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY must be configured in production')
