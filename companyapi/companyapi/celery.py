import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'companyapi.settings')

app = Celery('companyapi')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
