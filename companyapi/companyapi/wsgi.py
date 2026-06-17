import os
import sys
# Add the parent directory to sys.path
path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.append(path)

"""
WSGI config for companyapi project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'companyapi.settings')

import shutil
if os.environ.get('VERCEL') == '1' and not os.path.exists('/tmp/db.sqlite3'):
    source_db = os.path.join(path, 'db.sqlite3')
    if os.path.exists(source_db):
        shutil.copy(source_db, '/tmp/db.sqlite3')

application = get_wsgi_application()

app = application
