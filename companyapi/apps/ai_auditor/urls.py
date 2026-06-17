from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.ai_auditor.views import ReportViewSet, ChatViewSet

router = DefaultRouter()
router.register(r'chat', ChatViewSet, basename='chat')
router.register(r'reports', ReportViewSet, basename='reports')

urlpatterns = [
    path('', include(router.urls)),
]
