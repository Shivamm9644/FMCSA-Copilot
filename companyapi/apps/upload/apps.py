"""
File: apps/upload/apps.py
Why it exists:
    Configures the apps.upload Django application name.
"""

from django.apps import AppConfig

class UploadConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.upload'
