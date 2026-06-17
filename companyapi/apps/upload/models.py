"""
File: apps/upload/models.py
Why it exists:
    Defines Django MySQL models representing carriers, commercial motor vehicles,
    ingested ELD files, and parsed log events. This stores the primary telemetry data
    before or during the validation run.

Inputs:
    - Metadata and parameters representing carrier profile information and telemetric logs.

Outputs:
    - Django database models mapping to MySQL tables.

Dependencies:
    - django.db (Django Database engine)
    - django.contrib.auth.models.User (Django Auth model)
"""

from django.db import models
from django.contrib.auth.models import User

class Company(models.Model):
    """
    Represents a motor carrier fleet registered in the system.
    """
    company_name = models.CharField(max_length=100)
    company_email = models.EmailField(max_length=100)
    location = models.CharField(max_length=100)
    type = models.CharField(max_length=100, choices=(('IT', 'IT'), ('Non-IT', 'Non-IT'), ('Finance', 'Finance')))
    add_date = models.DateTimeField(auto_now_add=True)
    us_dot_number = models.CharField(max_length=15, unique=True, null=True, blank=True)

    def __str__(self) -> str:
        return self.company_name

class CMV(models.Model):
    """
    Represents a Commercial Motor Vehicle (CMV) matching FMCSA rules.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='cmvs')
    vin = models.CharField(max_length=17, unique=True)
    license_plate = models.CharField(max_length=20)
    power_unit_number = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.power_unit_number} (VIN: {self.vin})"

class ELDFile(models.Model):
    """
    Represents an uploaded and stored ELD CSV output file.
    """
    driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='eld_files')
    cmv = models.ForeignKey(CMV, on_delete=models.SET_NULL, null=True, blank=True, related_name='eld_files')
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512)
    status = models.CharField(
        max_length=20, 
        choices=(('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')), 
        default='pending'
    )
    task_id = models.CharField(max_length=255, null=True, blank=True)
    progress_percent = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    compliance_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    overall_status = models.CharField(
        max_length=20, 
        choices=(('compliant', 'Compliant'), ('non_compliant', 'Non-Compliant')), 
        default='compliant'
    )
    raw_header_json = models.JSONField(null=True, blank=True)
    error_log = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.filename} - {self.status}"

class ELDEvent(models.Model):
    """
    Represents an individual duty status event parsed from the ELD file.
    """
    eld_file = models.ForeignKey(ELDFile, on_delete=models.CASCADE, related_name='events')
    sequence_id = models.IntegerField()
    record_status = models.IntegerField()  # 1=Active, 2=Inactive
    record_origin = models.IntegerField()  # 1=Auto, 2=Driver
    event_type = models.IntegerField()    # 1=Change in Duty Status, etc.
    event_code = models.IntegerField()    # 1=Off Duty, 2=Sleeper, 3=Driving, 4=On Duty
    event_date_time = models.DateTimeField()
    accumulated_engine_hours = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True)
    elapsed_miles = models.IntegerField(null=True, blank=True)
    location_desc = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self) -> str:
        return f"File {self.eld_file_id} - Event {self.sequence_id} (Code: {self.event_code})"

class AgentJob(models.Model):
    """
    Tracks the execution of the agent pipeline for an ELD file.
    """
    job_id = models.CharField(max_length=255, unique=True)
    eld_file = models.ForeignKey(ELDFile, on_delete=models.CASCADE, related_name='jobs')
    status = models.CharField(
        max_length=20,
        choices=(('PENDING', 'Pending'), ('RUNNING', 'Running'), ('SUCCESS', 'Success'), ('FAILED', 'Failed')),
        default='PENDING'
    )
    current_agent = models.CharField(max_length=100, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Job {self.job_id} - {self.status}"

