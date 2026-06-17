"""
File: apps/validations/models.py
Why it exists:
    Defines Django MySQL models representing validation audits, rule failures,
    mathematical checksum outputs, and validation execution profiling.
    This maintains a complete audit trail of the compliance process.

Inputs:
    - Results and logs produced during file check validations.

Outputs:
    - Django database models mapping to MySQL tables.

Dependencies:
    - django.db (Django Database engine)
    - apps.upload.models.ELDFile (Ingested ELD file database record)
"""

from django.db import models
from apps.upload.models import ELDFile

class ValidationRun(models.Model):
    """
    Represents the execution context and master status for validating an ELD file.
    """
    eld_file = models.ForeignKey(ELDFile, on_delete=models.CASCADE, related_name='validation_runs')
    status = models.CharField(
        max_length=20, 
        choices=(('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')), 
        default='pending'
    )
    compliance_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    risk_level = models.CharField(
        max_length=10, 
        choices=(('LOW', 'LOW'), ('MEDIUM', 'MEDIUM'), ('HIGH', 'HIGH')), 
        default='LOW'
    )
    severity_level = models.CharField(
        max_length=10, 
        choices=(('NONE', 'NONE'), ('WARNING', 'WARNING'), ('CRITICAL', 'CRITICAL')), 
        default='NONE'
    )
    run_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Run {self.id} for File {self.eld_file_id} ({self.status})"

class ValidationFailure(models.Model):
    """
    Tracks details of specific rule validation failures (e.g. HOS violations).
    """
    validation_run = models.ForeignKey(ValidationRun, on_delete=models.CASCADE, related_name='failures')
    agent_name = models.CharField(max_length=100)
    check_name = models.CharField(max_length=100)
    severity = models.CharField(
        max_length=20, 
        choices=(('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical'))
    )
    description = models.TextField()
    raw_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Failure {self.check_name} in Run {self.validation_run_id}"

class ChecksumResult(models.Model):
    """
    Stores individual line checksum results and file checksum verification results.
    """
    validation_run = models.ForeignKey(ValidationRun, on_delete=models.CASCADE, related_name='checksums')
    entity_type = models.CharField(max_length=50)  # 'file', 'line', 'event'
    entity_id = models.CharField(max_length=100, null=True, blank=True)  # Line number or Event sequence ID
    expected_checksum = models.CharField(max_length=64)
    actual_checksum = models.CharField(max_length=64)
    is_valid = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Checksum {self.entity_type} {self.entity_id or ''}: {'Valid' if self.is_valid else 'Invalid'}"

class AgentExecutionLog(models.Model):
    """
    Logs performance and run durations for individual validator execution phases.
    """
    validation_run = models.ForeignKey(ValidationRun, on_delete=models.CASCADE, related_name='agent_logs')
    agent_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=(('success', 'Success'), ('failed', 'Failed')))
    message = models.CharField(max_length=255, null=True, blank=True)
    duration_ms = models.IntegerField()
    executed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.agent_name} in Run {self.validation_run_id}: {self.status}"

class RuleValidationResult(models.Model):
    """
    Stores individual rule validation results returned by FMCSA validation agents.
    """
    validation_run = models.ForeignKey(ValidationRun, on_delete=models.CASCADE, related_name='rule_validations')
    rule_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20)  # 'PASS' or 'FAIL'
    expected_value = models.TextField(null=True, blank=True)
    actual_value = models.TextField(null=True, blank=True)
    severity = models.CharField(max_length=20)  # 'low', 'medium', 'high', 'critical'
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Rule {self.rule_id} {self.status} for Run {self.validation_run_id}"

class DiagnosticEvent(models.Model):
    """
    Stores data diagnostic events based on FMCSA requirements (e.g., missing data, engine sync).
    """
    validation_run = models.ForeignKey(ValidationRun, on_delete=models.CASCADE, related_name='diagnostic_events')
    diagnostic_type = models.CharField(max_length=50) # e.g., 'Missing Data', 'Engine Sync', 'Timing', 'Position'
    description = models.TextField()
    severity = models.CharField(max_length=20) # 'low', 'medium', 'high', 'critical'
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Diagnostic {self.diagnostic_type} for Run {self.validation_run_id}"

class MalfunctionEvent(models.Model):
    """
    Stores critical ELD malfunctions based on FMCSA requirements and diagnostic escalations.
    """
    validation_run = models.ForeignKey(ValidationRun, on_delete=models.CASCADE, related_name='malfunction_events')
    malfunction_type = models.CharField(max_length=50) # e.g., 'Power', 'Engine Sync', 'Timing', 'Position', 'Data Transfer'
    description = models.TextField()
    escalated_from_diagnostic = models.BooleanField(default=False)
    severity = models.CharField(max_length=20, default='critical')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Malfunction {self.malfunction_type} for Run {self.validation_run_id}"

class InvestigationResult(models.Model):
    """
    Stores synthesized root causes deduced from failures, diagnostics, and malfunctions.
    """
    validation_run = models.ForeignKey(ValidationRun, on_delete=models.CASCADE, related_name='investigations')
    root_cause = models.TextField()
    evidence = models.JSONField(default=list)
    affected_records = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Investigation for Run {self.validation_run_id}: {self.root_cause[:30]}"

class CorrectionReport(models.Model):
    """
    Stores the results of the Autonomous Correction Agent including before/after metrics,
    change logs, and the path to the corrected CSV file.
    """
    validation_run = models.OneToOneField(ValidationRun, on_delete=models.CASCADE, related_name='correction_report')
    original_status = models.CharField(max_length=20)
    corrected_status = models.CharField(max_length=20)
    
    errors_before = models.IntegerField(default=0)
    errors_after = models.IntegerField(default=0)
    warnings_before = models.IntegerField(default=0)
    warnings_after = models.IntegerField(default=0)
    
    compliance_score_before = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    compliance_score_after = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    
    change_log = models.JSONField(default=list)
    before_after_comparison = models.JSONField(default=list)
    
    corrected_file_path = models.CharField(max_length=512, null=True, blank=True)
    final_verdict = models.CharField(max_length=50) # 'FMCSA COMPLIANT' or 'MANUAL REVIEW REQUIRED'
    
    # Strict Verification Workflow Fields
    verification_status = models.CharField(max_length=20, default='PENDING') # 'PASS', 'FAIL', 'PENDING'
    errors_remaining_details = models.JSONField(default=list)
    revalidated_at = models.DateTimeField(null=True, blank=True)
    validator_version = models.CharField(max_length=50, default='v1.0')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Correction Report for Run {self.validation_run_id} ({self.final_verdict})"
