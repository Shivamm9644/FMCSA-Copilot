from django.contrib import admin
from .models import Company, CMV, ELDFile, ELDEvent, AgentJob

admin.site.register(Company)
admin.site.register(CMV)
admin.site.register(ELDFile)
admin.site.register(ELDEvent)
admin.site.register(AgentJob)
