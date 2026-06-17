from celery import shared_task
from apps.ai_auditor.agents.supervisor import SupervisorAgent
from apps.upload.models import ELDFile

@shared_task
def run_ai_audit_task(validation_run_id: int, validation_data: dict, eld_file_id: int):
    try:
        eld_file = ELDFile.objects.get(id=eld_file_id)
        eld_file.status = 'processing'
        eld_file.progress_percent = 50
        eld_file.save()
    except Exception as e:
        print(f"Celery task: could not load ELDFile {eld_file_id}: {e}")
        return

    # --- PHASE 1: AI Executive Audit (optional, gracefully skip on LLM failure) ---
    try:
        ai_supervisor = SupervisorAgent()
        ai_supervisor.run_audit(validation_run_id, validation_data)
    except Exception as e:
        print(f"Celery task: AI Supervisor skipped (quota/error): {e}")

    # --- PHASE 2: Autonomous CSV Correction (always runs, has deterministic fallback) ---
    try:
        from apps.validations.models import ValidationRun
        from apps.validations.autonomous_correction_agent import AutonomousCorrectionAgent
        val_run = ValidationRun.objects.get(id=validation_run_id)
        correction_agent = AutonomousCorrectionAgent()
        correction_agent.execute_correction(val_run)
    except Exception as e:
        print(f"Celery task: Correction Agent error: {e}")

    # --- DONE ---
    try:
        eld_file.status = 'completed'
        eld_file.progress_percent = 100
        eld_file.save()
    except Exception as e:
        print(f"Celery task: could not update ELDFile status: {e}")

@shared_task
def generate_report_task(validation_run_id: int):
    from apps.validations.models import ValidationRun
    from apps.ai_auditor.pdf_generator import generate_audit_pdf
    import os
    
    try:
        val_run = ValidationRun.objects.get(id=validation_run_id)
        pdf_buffer = generate_audit_pdf(val_run)
        
        # Save to disk
        reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        file_path = os.path.join(reports_dir, f'report_{validation_run_id}.pdf')
        
        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
            
        return file_path
    except Exception as e:
        print(f"Failed to generate report asynchronously: {str(e)}")
        return None
