"""
File: apps/validations/serializers.py
Why it exists:
    Provides Django REST Framework serializers for ValidationRun, ValidationFailure,
    ChecksumResult, and AgentExecutionLog models.

Inputs:
    - Model instances or JSON structures.

Outputs:
    - Serialized data outputs.

Dependencies:
    - rest_framework.serializers (DRF)
    - apps.validations.models (Validation models definitions)
"""

from rest_framework import serializers
from apps.validations.models import (
    ValidationRun, ValidationFailure, ChecksumResult, AgentExecutionLog, RuleValidationResult, DiagnosticEvent, MalfunctionEvent, InvestigationResult
)

class ValidationFailureSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationFailure
        fields = '__all__'

class ChecksumResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecksumResult
        fields = '__all__'

class AgentExecutionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentExecutionLog
        fields = '__all__'

class RuleValidationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleValidationResult
        fields = '__all__'

class DiagnosticEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosticEvent
        fields = '__all__'

class MalfunctionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = MalfunctionEvent
        fields = '__all__'

class InvestigationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestigationResult
        fields = '__all__'

class CorrectionReportSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.validations.models import CorrectionReport
        model = CorrectionReport
        fields = '__all__'

class ValidationRunSerializer(serializers.ModelSerializer):
    failures = ValidationFailureSerializer(many=True, read_only=True)
    checksums = ChecksumResultSerializer(many=True, read_only=True)
    agent_logs = AgentExecutionLogSerializer(many=True, read_only=True)
    rule_validations = RuleValidationResultSerializer(many=True, read_only=True)
    diagnostic_events = DiagnosticEventSerializer(many=True, read_only=True)
    malfunction_events = MalfunctionEventSerializer(many=True, read_only=True)
    investigations = InvestigationResultSerializer(many=True, read_only=True)
    correction_report = CorrectionReportSerializer(read_only=True)
    executive_audit = serializers.SerializerMethodField()

    class Meta:
        model = ValidationRun
        fields = '__all__'

    def get_executive_audit(self, obj):
        try:
            from apps.ai_auditor.serializers import ExecutiveAuditReportSerializer
            if hasattr(obj, 'executive_audit'):
                return ExecutiveAuditReportSerializer(obj.executive_audit).data
        except Exception:
            pass
        return None

