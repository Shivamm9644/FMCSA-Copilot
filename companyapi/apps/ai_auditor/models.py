from django.db import models
from apps.validations.models import ValidationRun

class ExecutiveAuditReport(models.Model):
    validation_run = models.OneToOneField(ValidationRun, on_delete=models.CASCADE, related_name='executive_audit')
    summary = models.TextField()
    remediation_plan = models.TextField(blank=True, null=True)
    llm_raw_response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Audit Report for Run {self.validation_run_id}"
