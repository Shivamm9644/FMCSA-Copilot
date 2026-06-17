import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'companyapi.settings')

# Read .env file directly since python-dotenv might not be installed
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ[k] = v

django.setup()

from apps.upload.models import ELDFile
from apps.validations.models import ValidationRun, ValidationFailure, InvestigationResult, CorrectionReport
from apps.validations.autonomous_correction_agent import AutonomousCorrectionAgent

def run():
    print("--- 1. Fetching recent Validation Run ---")
    val_run = ValidationRun.objects.last()
    if not val_run:
        print("No Validation Run found.")
        return
        
    print(f"Using Validation Run ID: {val_run.id} for ELD {val_run.eld_file.id}")
    
    # 1. Create a dummy ValidationFailure for "Sequence ID Gap"
    print("--- 2. Injecting Validation Failure ---")
    CorrectionReport.objects.filter(validation_run=val_run).delete(); ValidationFailure.objects.filter(validation_run=val_run).delete(); ValidationFailure.objects.create(
        validation_run=val_run,
        agent_name="FMCSA Validation Layer Agent",
        check_name="RULE_EVENT_SEQUENCE_ID",
        severity="high",
        description="Gap in sequence ID. Sequence ID jumped from 7C to 7E, missing 7D.",
        raw_data={"expected_sequence": "7D", "actual_sequence": "7E"}
    )
    
    print("--- 3. Running Autonomous Correction Agent ---")
    agent = AutonomousCorrectionAgent()
    result = agent.execute_correction(val_run)
    
    print("--- 4. Result ---")
    print(result)
    
    if result:
        # Fetch the correction report
        try:
            report = val_run.correction_report
            print("\n--- Correction Report ---")
            print(f"Status: {report.status}")
            print(f"Root Cause: {report.root_cause_analysis}")
            print(f"Patches Applied: {report.patches_applied}")
            print(f"Change Log: {report.change_log}")
            print(f"Revalidated: {report.revalidation_successful}")
        except Exception as e:
            print("No correction report created.", str(e))

if __name__ == "__main__":
    run()
