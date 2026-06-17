from rest_framework import serializers
from apps.ai_auditor.models import ExecutiveAuditReport

class ExecutiveAuditReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExecutiveAuditReport
        fields = '__all__'
