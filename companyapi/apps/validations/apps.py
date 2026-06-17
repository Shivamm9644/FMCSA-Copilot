"""
File: apps/validations/apps.py
Why it exists:
    Configures the apps.validations Django application name.
"""

from django.apps import AppConfig

class ValidationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.validations'
