SECRET_KEY = 'kLuKhnqKxOgV'
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'postgres_db',
        'USER': 'postgres_user',
        'PASSWORD': 'postgres_pass',
        'HOST': 'database',
    }
}

STATIC_ROOT = '/code/static'
STATIC_URL = '/static/'

MEDIA_ROOT = '/code/media'
MEDIA_URL = '/media/'

MY_ADMIN_PREFIX = 'adm'
