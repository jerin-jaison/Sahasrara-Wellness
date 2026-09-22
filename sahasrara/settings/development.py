from .base import *

DEBUG = True

try:
    import debug_toolbar
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')
except ImportError:
    pass

INTERNAL_IPS = ['127.0.0.1']

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Relax axes in dev
AXES_ENABLED = False

SITE_URL = 'http://127.0.0.1:8000'
