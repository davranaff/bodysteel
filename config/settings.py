from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-i(!^3@q&)btg5%skz2wc0tr(t(3avq20p3+*alul)$wv2(awq('

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    'ckeditor',
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
    'rest_framework',
    'rest_framework.authtoken',
    'teleg',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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
    "https://bodysteel.vercel.app",
    "https://bosyteel.uz",
    "https://api.bosyteel.uz",
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

ESKIZ_FROM_TO = ''
ESKIZ_PROVIDER_EMAIL = 'deff0427@gmail.com'
ESKIZ_PROVIDER_PASSWORD = 'l52LiHIsfeshhp2MbQO9T6rrqPuBJ28W574tipJw'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'deff0427@gmail.com'
EMAIL_HOST_PASSWORD = 'jpmuregetnbuntfe'

BOT_TOKEN = '7099818467:AAEdJSuitqCYDiJNJDeahew7Ob5p1Vl-IHM'
TELEGRAM_API_URL = f'https://api.telegram.org/bot{BOT_TOKEN}'
BOT_POOLING_INTERVAL = 5


if not DEBUG:
    from .settings_prod import *
else:
    from .settings_dev import *
