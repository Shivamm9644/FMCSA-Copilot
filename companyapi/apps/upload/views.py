"""
File: apps/upload/views.py
Why it exists:
    Exposes the REST API endpoint for uploading raw ELD files, triggering Phase 1 validations,
    performing segment parsing, check verifying, HOS validations, and writing the entire validation
    audit log to the MySQL databases.

Inputs:
    - Multipart HTTP POST request containing raw ELD CSV file in the 'file' field.

Outputs:
    - HTTP response returning JSON status, overall score, details, checksum outputs, and logs.

Dependencies:
    - os, csv, time (Python Standard Library)
    - rest_framework (Django REST Framework)
    - django.contrib.auth.models.User (Django Auth)
    - apps.upload.models (Company, CMV, ELDFile, ELDEvent)
    - apps.upload.serializers (ELDFileSerializer)
    - apps.validations.models (ValidationRun, ValidationFailure, ChecksumResult, AgentExecutionLog)
    - apps.validations.serializers (ValidationRunSerializer)
    - apps.parser.segment_parsers (HeaderParser, UserListParser, CMVParser, EventParser)
    - apps.validations.checksum_verifier (verify_file_checksum)
    - apps.validations.rules (analyze_hos_rules)
"""

import os
import csv
import time
import uuid
from typing import Dict, List, Any
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import User

from django.db import models
from apps.upload.models import Company, CMV, ELDFile, ELDEvent, AgentJob
from apps.upload.serializers import ELDFileSerializer
from apps.validations.models import (
    ValidationRun, ValidationFailure, ChecksumResult, AgentExecutionLog
)
from apps.validations.serializers import ValidationRunSerializer

from apps.parser.segment_parsers import (
    HeaderParser, UserListParser, CMVParser, EventParser
)
from apps.validations.checksum_verifier import verify_file_checksum
from apps.validations.rules import analyze_hos_rules

class ELDFileViewSet(viewsets.ModelViewSet):
    queryset = ELDFile.objects.all().order_by('-uploaded_at')
    serializer_class = ELDFileSerializer

    @action(detail=False, methods=['post'], url_path='upload')
    def upload_eld(self, request) -> Response:
        """
        Ingests ELD CSV file, performs parsing and mathematical verifications,
        records validations and errors, and registers results.
        """
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response(
                {
                    "status": "error",
                    "category": "Validation Error",
                    "reason": "Missing file payload in request.",
                    "root_cause": "The request payload did not contain a 'file' key.",
                    "suggested_fix": "Ensure the multipart/form-data request contains a valid CSV file mapped to the 'file' parameter."
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # 1. Resolve Driver User (auth fallback)
        if request.user and request.user.is_authenticated:
            driver_user = request.user
        else:
            driver_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
            if not driver_user:
                driver_user = User.objects.create_user(
                    username='guest_driver', 
                    email='driver@guest.com', 
                    password='password123', 
                    first_name='Guest', 
                    last_name='Driver'
                )
                
        # 2. Save raw file locally inside the project uploads folder
        upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file_obj.name)
        
        try:
            with open(file_path, 'wb+') as destination:
                for chunk in file_obj.chunks():
                    destination.write(chunk)
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "category": "System Error",
                    "reason": "Failed to save the uploaded file to disk.",
                    "root_cause": f"IOError during file write: {str(e)}",
                    "suggested_fix": "Check backend storage permissions and available disk space."
                }, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
                
        # 3. Read content
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                csv_content = f.read()
            if not csv_content.strip():
                raise ValueError("The uploaded CSV file is empty.")
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "category": "Validation Error",
                    "reason": "The uploaded file could not be read or is empty.",
                    "root_cause": str(e),
                    "suggested_fix": "Ensure the file contains valid text data and is not 0 bytes."
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # 4. Resolve company and CMV details
        company = Company.objects.first() or Company.objects.create(
            company_name="Guest Carrier", 
            company_email="guest@carrier.com", 
            location="USA", 
            type="IT"
        )
        cmv = CMV.objects.first() or CMV.objects.create(
            company=company, 
            vin="1V9M1234567890123", 
            license_plate="MOCKPLT", 
            power_unit_number="UNIT-01"
        )
            
        eld_file = ELDFile.objects.create(
            driver=driver_user,
            cmv=cmv,
            filename=file_obj.name,
            file_path=file_path,
            status='processing'
        )
        
        # 5. Initialize Validation Run Record
        val_run = ValidationRun.objects.create(
            eld_file=eld_file,
            status='processing'
        )
        
        try:
            from apps.validations.pipeline import run_full_validation_pipeline
            metrics, all_errors = run_full_validation_pipeline(csv_content, eld_file=eld_file, validation_run=val_run, save_to_db=True)
            
            # Update Validation Run
            val_run.compliance_score = metrics["score"]
            val_run.risk_level = metrics["risk"]
            val_run.severity_level = metrics["severity"]
            val_run.status = 'completed'
            val_run.save()
            
            # Update ELDFile
            eld_file.compliance_score = metrics["score"]
            eld_file.overall_status = 'compliant' if metrics["score"] >= 90.0 else 'non_compliant'
            eld_file.status = 'completed'

            # Prepare data payload for AI Auditor
            from apps.validations.serializers import ValidationRunSerializer
            validation_data_for_ai = ValidationRunSerializer(val_run).data

            # Trigger background job using Celery
            from apps.ai_auditor.tasks import run_ai_audit_task
            
            eld_file.status = 'pending'
            eld_file.progress_percent = 25
            eld_file.save()
            
            # Dispatch Celery task
            task = run_ai_audit_task.delay(val_run.id, validation_data_for_ai, eld_file.id)
            task_id = task.id
            
            eld_file.refresh_from_db()
            eld_file.task_id = task_id
            eld_file.save()

            val_run.refresh_from_db()
            response_serializer = ValidationRunSerializer(val_run)
            response_data = response_serializer.data
            response_data['job_status'] = 'processing'
            response_data['task_id'] = task_id

            # --- EMBED CORRECTED CSV IN RESPONSE ---
            try:
                val_run.refresh_from_db()
                if hasattr(val_run, 'correction_report'):
                    report = val_run.correction_report
                    if report.verification_status == 'PASS':
                        corrected_path = report.corrected_file_path
                        if corrected_path and os.path.exists(corrected_path):
                            with open(corrected_path, 'r', encoding='utf-8') as cf:
                                corrected_csv_text = cf.read()
                            response_data['corrected_csv_available'] = True
                            response_data['corrected_csv_content'] = corrected_csv_text
                            response_data['corrected_csv_filename'] = os.path.basename(corrected_path)
                            response_data['corrected_csv_download_url'] = f"/api/v1/eld/{eld_file.id}/corrected-csv/"
                            response_data['verification'] = {
                                "status": "PASS",
                                "score": 100,
                                "timestamp": report.revalidated_at,
                                "version": report.validator_version
                            }
                        else:
                            response_data['corrected_csv_available'] = False
                            response_data['corrected_csv_content'] = None
                    else:
                        response_data['corrected_csv_available'] = False
                        response_data['corrected_csv_content'] = None
                        response_data['verification'] = {
                            "status": "FAIL",
                            "remaining_errors": report.errors_remaining_details,
                            "reason": "Manual Review Required"
                        }
                else:
                    response_data['corrected_csv_available'] = False
                    response_data['corrected_csv_content'] = None
            except Exception as csv_err:
                response_data['corrected_csv_available'] = False
                response_data['corrected_csv_content'] = None
                response_data['corrected_csv_error'] = str(csv_err)
            
            return Response(response_data, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            val_run.status = 'failed'
            val_run.save()
            return Response({
                "status": "error",
                "category": "Pipeline Failure",
                "reason": "Pipeline failed during deterministic validation layer.",
                "root_cause": str(e),
                "suggested_fix": "Review the CSV structure for critical formatting errors or contact support."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='corrected-csv')
    def corrected_csv(self, request, pk=None):
        """Returns the corrected CSV as a downloadable file attachment if strictly verified."""
        try:
            eld_file = self.get_object()
            val_run = eld_file.validation_runs.order_by('-id').first()
            if not val_run or not hasattr(val_run, 'correction_report'):
                return Response({"status": "error", "category": "Not Found", "reason": "No correction report generated.", "root_cause": "Pipeline may not have completed or correction failed.", "suggested_fix": "Wait for pipeline to finish."}, status=404)

            report = val_run.correction_report
            if report.verification_status != 'PASS':
                return Response({
                    "status": "error",
                    "category": "Verification Failed",
                    "reason": "Manual Review Required.",
                    "root_cause": "The generated corrected CSV did not pass internal revalidation.",
                    "remaining_errors": report.errors_remaining_details
                }, status=403)

            if not report.corrected_file_path or not os.path.exists(report.corrected_file_path):
                return Response({"status": "error", "category": "Not Found", "reason": "Corrected CSV file not found on disk.", "root_cause": "File may have been deleted.", "suggested_fix": "Re-run the audit pipeline."}, status=404)

            from django.http import FileResponse
            filename = f"corrected_{eld_file.filename}"
            return FileResponse(
                open(report.corrected_file_path, 'rb'),
                as_attachment=True,
                filename=filename,
                content_type='text/csv'
            )
        except Exception as e:
            return Response({"status": "error", "category": "System Error", "reason": "Failed to serve corrected CSV.", "root_cause": str(e), "suggested_fix": "Check backend server logs."}, status=500)

    @action(detail=True, methods=['get'], url_path='download-corrected')
    def download_corrected(self, request, pk=None):
        """Alias kept for backward compatibility — delegates to corrected_csv."""
        return self.corrected_csv(request, pk=pk)
            
    @action(detail=True, methods=['get'], url_path='download-changelog')
    def download_changelog(self, request, pk=None):
        try:
            eld_file = self.get_object()
            val_run = eld_file.validation_runs.order_by('-id').first()
            if not val_run or not hasattr(val_run, 'correction_report'):
                return Response({"status": "error", "category": "Not Found", "reason": "No correction report generated.", "root_cause": "The pipeline may not have completed or correction failed.", "suggested_fix": "Wait for pipeline to finish."}, status=404)
                
            report = val_run.correction_report
            if not report.change_log:
                return Response({"status": "error", "category": "Not Found", "reason": "Change log is empty.", "root_cause": "No deterministic patches were applied.", "suggested_fix": "None."}, status=404)
                
            import json
            from django.http import HttpResponse
            response = HttpResponse(json.dumps(report.change_log, indent=2), content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="changelog_{eld_file.filename}.json"'
            return response
        except Exception as e:
            return Response({"status": "error", "category": "System Error", "reason": "Failed to serve download.", "root_cause": str(e), "suggested_fix": "Check backend server logs."}, status=500)

class DashboardViewSet(viewsets.ViewSet):
    def list(self, request):
        total_files = ELDFile.objects.count()
        avg_score = ELDFile.objects.aggregate(avg=models.Avg('compliance_score'))['avg'] or 0
        total_failures = ValidationFailure.objects.count()
        critical_failures = ValidationFailure.objects.filter(severity='critical').count()
        
        recent_files = ELDFile.objects.order_by('-uploaded_at')[:5]
        recent_data = []
        for f in recent_files:
            recent_data.append({
                "id": f.id,
                "filename": f.filename,
                "score": f.compliance_score,
                "status": f.overall_status,
                "date": f.uploaded_at
            })
            
        return Response({
            "metrics": {
                "total_files_analyzed": total_files,
                "average_compliance_score": float(avg_score),
                "total_violations_detected": total_failures,
                "critical_violations": critical_failures
            },
            "recent_activity": recent_data
        })

    @action(detail=False, methods=['get'], url_path='compliance-summary')
    def compliance_summary(self, request):
        total_files = ELDFile.objects.count()
        avg_score = ELDFile.objects.aggregate(avg=models.Avg('compliance_score'))['avg'] or 0
        
        # Count failures
        total_failures = ValidationFailure.objects.count()
        critical_failures = ValidationFailure.objects.filter(severity='critical').count()
        
        return Response({
            "total_files_analyzed": total_files,
            "average_compliance_score": float(avg_score),
            "total_violations_detected": total_failures,
            "critical_violations": critical_failures
        })
        
    @action(detail=False, methods=['get'], url_path='analytics')
    def analytics(self, request):
        # We can group violations by type
        from django.db.models import Count
        violations_by_type = list(ValidationFailure.objects.values('check_name').annotate(count=Count('id')).order_by('-count')[:10])
        
        return Response({
            "top_violations": violations_by_type
        })
        
    @action(detail=False, methods=['get'], url_path='recent-runs')
    def recent_runs(self, request):
        recent_files = ELDFile.objects.order_by('-uploaded_at')[:10]
        recent_data = []
        for f in recent_files:
            recent_data.append({
                "id": f.id,
                "filename": f.filename,
                "score": f.compliance_score,
                "status": f.overall_status,
                "date": f.uploaded_at
            })
            
        return Response({
            "recent_activity": recent_data
        })

class AgentViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'], url_path='start/(?P<file_id>[^/.]+)')
    def start_job(self, request, file_id=None):
        try:
            eld_file = ELDFile.objects.get(id=file_id)
        except ELDFile.DoesNotExist:
            return Response({"error": "File not found."}, status=status.HTTP_404_NOT_FOUND)
        
        job_id = str(uuid.uuid4())
        job = AgentJob.objects.create(
            job_id=job_id,
            eld_file=eld_file,
            status='PENDING'
        )
        return Response({"jobId": job_id, "status": "PENDING"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['get'], url_path='status/(?P<job_id>[^/.]+)')
    def job_status(self, request, job_id=None):
        try:
            job = AgentJob.objects.get(job_id=job_id)
        except AgentJob.DoesNotExist:
            return Response({"error": "Job not found."}, status=status.HTTP_404_NOT_FOUND)
            
        return Response({
            "jobId": job.job_id,
            "status": job.status,
            "current_agent": job.current_agent,
            "started_at": job.started_at,
            "completed_at": job.completed_at
        })

    @action(detail=False, methods=['get'], url_path='result/(?P<job_id>[^/.]+)')
    def job_result(self, request, job_id=None):
        try:
            job = AgentJob.objects.get(job_id=job_id)
        except AgentJob.DoesNotExist:
            return Response({"error": "Job not found."}, status=status.HTTP_404_NOT_FOUND)
        
        if job.status != 'SUCCESS':
            return Response({"error": "Job not yet completed or failed."}, status=status.HTTP_400_BAD_REQUEST)
            
        val_run = ValidationRun.objects.filter(eld_file=job.eld_file).order_by('-id').first()
        if not val_run:
            return Response({"error": "Validation run not found for this file."}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = ValidationRunSerializer(val_run)
        return Response(serializer.data)
