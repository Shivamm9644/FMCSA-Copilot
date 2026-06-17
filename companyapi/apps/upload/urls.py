"""
File: apps/upload/urls.py
Why it exists:
    Configures REST API URL paths for the upload app.
    Registers the ELDFileViewSet on the router.

Inputs:
    - URL paths.

Outputs:
    - Django urlpatterns patterns list.

Dependencies:
    - rest_framework.routers (DRF router builder)
    - apps.upload.views (Upload views ViewSet)
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.upload.views import ELDFileViewSet, DashboardViewSet, AgentViewSet
from django.views.generic import TemplateView

router = DefaultRouter()
router.register(r'eld', ELDFileViewSet, basename='restructured-eld')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')
router.register(r'agent', AgentViewSet, basename='agent')

urlpatterns = [
    path('', include(router.urls)),
    path('full-check/', TemplateView.as_view(template_name='full_check.html'), name='full_check'),
]
