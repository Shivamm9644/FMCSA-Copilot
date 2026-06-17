"""
File: apps/parser/apps.py
Why it exists:
    Configures the apps.parser Django application name.
"""

from django.apps import AppConfig

class ParserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.parser'
