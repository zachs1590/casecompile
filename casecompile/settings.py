"""
Django settings for casecompile project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'umx=qzpcc10rt=c1$nrstlo9fn%i1tjtii+d(1@zddt&u#axh='

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = [ 'www.casecompile.com' ]


# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.webdesign',

    'south',
    'sekizai',
    'crispy_forms',
    'caxiam',
    'casecompile',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.common.BrokenLinkEmailsMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'caxiam.debug_middleware.CaxiamDebugMiddleware'
)

ROOT_URLCONF = 'casecompile.urls'

WSGI_APPLICATION = 'casecompile.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(os.path.dirname(BASE_DIR), 'static')

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(BASE_DIR, 'casecompile', 'templates'),
)

TEMPLATE_LOADERS = (
    (
        (
          'django.template.loaders.filesystem.Loader',
          'django.template.loaders.app_directories.Loader',
        )
    ),
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',   # not in Django's default set, but useful
    'django.core.context_processors.static',
    'django.core.context_processors.tz',
    #'cms.context_processors.media',
    'sekizai.context_processors.sekizai',
)

# normal email settings
EMAIL_BACKEND = 'caxiam.django_smtp_ssl.SSLEmailBackend'
EMAIL_HOST = ''
EMAIL_PORT = 465
EMAIL_USE_TLS = True
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''

# who to email in case of problems
ADMINS = (
    ( 'Django Error (casecompile)', 'zach.stevenson@caxiam.com', ),
)

# where such email comes from
# (this is only used for error messages)
SERVER_EMAIL = 'zach.stevenson@caxiam.com'

# email settings
CAXIAM_EMAIL_FROM = 'noreply@casecompile'
CAXIAM_EMAIL_TEMPLATE_BASE = ''
CAXIAM_EMAIL_SITE_HOSTNAME = ALLOWED_HOSTS[0]

# error message modules
CAXIAM_AJAX_FORM_ERROR_MESSAGES = (
        'caxiam.ajax.form_errors',
    )


# crispy forms setup
CRISPY_TEMPLATE_PACK = 'bootstrap3'


#-------
# app-specific settings
#

# slurp in any local overrides
from settings_local_post import *

MANAGERS = ADMINS
