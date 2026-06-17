import os
import sys
import traceback

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

try:
    from django.core.wsgi import get_wsgi_application

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'companyapi.settings')

    import shutil
    if os.environ.get('VERCEL') == '1' and not os.path.exists('/tmp/db.sqlite3'):
        source_db = os.path.join(path, 'db.sqlite3')
        if os.path.exists(source_db):
            shutil.copy(source_db, '/tmp/db.sqlite3')

    application = get_wsgi_application()
    app = application

except Exception as e:
    tb_str = traceback.format_exc()
    def error_app(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-Type', 'text/plain; charset=utf-8')]
        start_response(status, headers)
        return [f"Django Startup Error:\n\n{tb_str}".encode('utf-8')]
    
    app = error_app

