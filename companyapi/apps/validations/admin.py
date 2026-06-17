from django.contrib import admin
from .models import ValidationRun, ValidationFailure, ChecksumResult, AgentExecutionLog, RuleValidationResult, DiagnosticEvent, MalfunctionEvent, InvestigationResult, CorrectionReport

admin.site.register(ValidationRun)
admin.site.register(ValidationFailure)
admin.site.register(ChecksumResult)
admin.site.register(AgentExecutionLog)
admin.site.register(RuleValidationResult)
admin.site.register(DiagnosticEvent)
admin.site.register(MalfunctionEvent)
admin.site.register(InvestigationResult)
admin.site.register(CorrectionReport)
