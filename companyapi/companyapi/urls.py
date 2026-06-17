from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/v1/auth/", include("apps.api_auth.urls")),
    path("api/v1/", include("apps.upload.urls")),
    path("api/v1/", include("apps.ai_auditor.urls")),
    path('full-check/', TemplateView.as_view(template_name='full_check.html'), name='full_check'),
    path('', TemplateView.as_view(template_name='portfolio.html'), name='home'),
    path('portfolio/', TemplateView.as_view(template_name='portfolio.html'), name='portfolio'),
]
