from .base import *

DEBUG = False

# Render & Hostinger settings
render_extra = ['www.sahasrarawellness.com', 'sahasrarawellness.com', 'sahasrara-wellness-hxsw.onrender.com', 'sahasrara-wellness.onrender.com', '.onrender.com', '*']
for h in render_extra:
    if h not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(h)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True


# Nginx handles SSL at the proxy level
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Essential for Razorpay cross-domain POST callbacks preserving session
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
