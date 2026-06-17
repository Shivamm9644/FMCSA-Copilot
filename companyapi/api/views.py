import os
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.contrib.auth.models import User
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.models import (
    Company, Employee, UserProfile, CMV, ELDFile, 
    ELDEvent, DiagnosticEvent, ComplianceAudit, 
    ChatSession, ChatMessage,
    ValidationRun, ValidationFailure, ChecksumResult, AgentExecutionLog
)
from api.serlizers import (
    CompanySerializer, EmployeeSerializer, UserProfileSerializer, 
    CMVSerializer, ELDFileSerializer, ELDEventSerializer, 
    DiagnosticEventSerializer, ComplianceAuditSerializer, 
    ChatSessionSerializer, ChatMessageSerializer,
    ValidationRunSerializer, ValidationFailureSerializer,
    ChecksumResultSerializer, AgentExecutionLogSerializer
)

from api.agents.workflow import execute_copilot_audit
from api.agents.chat_agent import generate_chat_response
from api.services.pdf_generator import generate_eld_audit_pdf

class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

class CMVViewSet(viewsets.ModelViewSet):
    queryset = CMV.objects.all()
    serializer_class = CMVSerializer

class ELDFileViewSet(viewsets.ModelViewSet):
    queryset = ELDFile.objects.all().order_by('-uploaded_at')
    serializer_class = ELDFileSerializer

    @action(detail=False, methods=['post'], url_path='upload')
    def upload_eld(self, request):
        """
        Receives an ELD CSV file, runs the multi-agent supervisor graph,
        logs runs, checksums, validations, and saves all outputs.
        """
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file uploaded. Please upload a file with key 'file'."}, status=status.HTTP_400_BAD_REQUEST)
            
        # 1. Resolve Driver User (auth fallback)
        if request.user and request.user.is_authenticated:
            driver_user = request.user
        else:
            driver_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
            if not driver_user:
                driver_user = User.objects.create_user(username='guest_driver', email='driver@guest.com', password='password123', first_name='Guest', last_name='Driver')
                
        # 2. Save raw file locally
        upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file_obj.name)
        
        with open(file_path, 'wb+') as destination:
            for chunk in file_obj.chunks():
                destination.write(chunk)
                
        # 3. Read content
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                csv_content = f.read()
        except Exception as e:
            return Response({"error": f"Failed to read file: {e}"}, status=status.HTTP_400_BAD_REQUEST)
            
        # 4. Resolve company and CMV
        company = Company.objects.first() or Company.objects.create(company_name="Guest Carrier", company_email="guest@carrier.com", location="USA", type="IT")
        cmv = CMV.objects.first() or CMV.objects.create(company=company, vin="VINMOCK1234567890", license_plate="MOCKPLT", power_unit_number="UNIT-01")
            
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
        
        # 6. Execute LangGraph Supervisor StateGraph
        try:
            state = execute_copilot_audit(csv_content, file_id=eld_file.id)
            
            # Save Header information to ELDFile
            header_data = state.get("parsed_header", {})
            if hasattr(header_data, 'to_dict'):
                eld_file.raw_header_json = header_data.to_dict()
            else:
                eld_file.raw_header_json = header_data
            
            # Save events to database
            events_to_create = []
            for ev in state.get("parsed_events", []):
                events_to_create.append(ELDEvent(
                    eld_file=eld_file,
                    sequence_id=ev["sequence_id"],
                    record_status=ev["record_status"],
                    record_origin=ev["record_origin"],
                    event_type=ev["event_type"],
                    event_code=ev["event_code"],
                    event_date_time=ev["event_date_time"],
                    accumulated_engine_hours=ev.get("accumulated_engine_hours"),
                    elapsed_miles=ev.get("elapsed_miles"),
                    location_desc=ev.get("location_desc"),
                    latitude=ev.get("latitude"),
                    longitude=ev.get("longitude")
                ))
            if events_to_create:
                ELDEvent.objects.bulk_create(events_to_create)
                
            # Save diagnostics & malfunctions to database
            diagnostics_to_create = []
            for d in state.get("parsed_diagnostics", []) + state.get("parsed_malfunctions", []):
                diagnostics_to_create.append(DiagnosticEvent(
                    eld_file=eld_file,
                    event_type=d["event_type"],
                    code=d["code"],
                    description=d.get("description"),
                    event_date_time=d["event_date_time"]
                ))
            if diagnostics_to_create:
                DiagnosticEvent.objects.bulk_create(diagnostics_to_create)
                
            # Record Checksum Results
            checksum_data = state.get("checksum_results", {})
            checksums_to_create = [
                ChecksumResult(
                    validation_run=val_run,
                    entity_type="file",
                    expected_checksum=checksum_data.get("file_checksum", ""),
                    actual_checksum=checksum_data.get("file_checksum", ""),
                    is_valid=checksum_data.get("is_valid", True)
                )
            ]
            for fc in checksum_data.get("failed_lines", []):
                checksums_to_create.append(ChecksumResult(
                    validation_run=val_run,
                    entity_type="line",
                    entity_id=str(fc["line_number"]),
                    expected_checksum=fc["expected"],
                    actual_checksum=fc["actual"],
                    is_valid=False
                ))
            if checksums_to_create:
                ChecksumResult.objects.bulk_create(checksums_to_create)
                
            # Record Validation Failures
            failures_to_create = []
            for f in state.get("validation_failures", []):
                failures_to_create.append(ValidationFailure(
                    validation_run=val_run,
                    agent_name=f["agent_name"],
                    check_name=f["check_name"],
                    severity=f["severity"],
                    description=f["description"],
                    raw_data=f.get("raw_data")
                ))
            if failures_to_create:
                ValidationFailure.objects.bulk_create(failures_to_create)
                
            # Record Agent Logs
            agent_logs_to_create = []   
            for al in state.get("agent_logs", []):
                agent_logs_to_create.append(AgentExecutionLog(
                    validation_run=val_run,
                    agent_name=al["agent_name"],
                    status=al["status"],
                    message=al.get("message"),
                    duration_ms=al["duration_ms"]
                ))
            if agent_logs_to_create:
                AgentExecutionLog.objects.bulk_create(agent_logs_to_create)
                
            # Update scoring and status metrics
            metrics = state.get("compliance_score_metrics", {})
            val_run.compliance_score = metrics.get("compliance_score", 100.0)
            val_run.risk_level = metrics.get("risk", "LOW")
            val_run.severity_level = metrics.get("severity", "NONE")
            val_run.status = 'completed'
            val_run.save()
            
            eld_file.compliance_score = val_run.compliance_score
            eld_file.overall_status = "compliant" if val_run.compliance_score >= 90 else "non_compliant"
            eld_file.executive_summary = state.get("executive_summary", "")
            eld_file.status = 'completed'
            eld_file.save()
            
            # Return validation details
            run_serializer = ValidationRunSerializer(val_run)
            return Response({
                "message": "ELD file parsed and audited successfully using multi-agent supervisor graph.",
                "analysis": run_serializer.data,
                "investigation": state.get("investigation_findings", {}),
                "executive_summary": eld_file.executive_summary
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            val_run.status = 'failed'
            val_run.save()
            
            eld_file.status = 'failed'
            eld_file.error_log = str(e)
            eld_file.save()
            
            return Response({
                "error": f"ELD analysis failed: {e}",
                "file_status": "failed"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='download-report')
    def download_report(self, request, pk=None):
        """
        Generates and downloads the styled PDF compliance audit report.
        """
        eld_file = get_object_or_404(ELDFile, pk=pk)
        
        # Grab latest validation run failures and details
        latest_run = ValidationRun.objects.filter(eld_file=eld_file, status='completed').order_by('-run_at').first()
        
        violations = []
        if latest_run:
            failures = ValidationFailure.objects.filter(validation_run=latest_run)
            # Adapt validation failure shape to compliance audit structure for ReportLab
            for f in failures:
                violations.append(ComplianceAudit(
                    violation_type=f.check_name,
                    severity=f.severity,
                    regulation_reference=f.raw_data.get("regulation") if f.raw_data else None,
                    description=f.description
                ))
                
        diagnostics = DiagnosticEvent.objects.filter(eld_file=eld_file)
        summary = eld_file.executive_summary or "No executive summary available."
        
        try:
            pdf_data = generate_eld_audit_pdf(eld_file, violations, diagnostics, summary)
            response = HttpResponse(pdf_data, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="eld_audit_{eld_file.id}.pdf"'
            return response
        except Exception as e:
            return Response({"error": f"Failed to generate report: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatSessionViewSet(viewsets.ModelViewSet):
    queryset = ChatSession.objects.all().order_by('-created_at')
    serializer_class = ChatSessionSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if not user or not user.is_authenticated:
            user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        serializer.save(user=user)

    @action(detail=True, methods=['post'], url_path='message')
    def send_message(self, request, pk=None):
        session = get_object_or_404(ChatSession, pk=pk)
        content = request.data.get('content')
        if not content:
            return Response({"error": "Missing message content. Please supply a 'content' field."}, status=status.HTTP_400_BAD_REQUEST)
            
        response_text = generate_chat_response(session.id, content)
        latest_msg = ChatMessage.objects.filter(session=session, sender='assistant').last()
        serializer = ChatMessageSerializer(latest_msg)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='messages')
    def get_messages(self, request, pk=None):
        session = get_object_or_404(ChatSession, pk=pk)
        messages = ChatMessage.objects.filter(session=session).order_by('created_at')
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)