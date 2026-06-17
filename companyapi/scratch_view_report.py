import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'companyapi.settings')

with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ[k] = v

django.setup()

from apps.validations.models import ValidationRun, InvestigationResult

val_run = ValidationRun.objects.last()
report = val_run.correction_report
inv = InvestigationResult.objects.filter(validation_run=val_run)

out = f'''Validation Run ID: {val_run.id}
Original Status: {report.original_status}
Corrected Status: {report.corrected_status}
Errors Before: {report.errors_before}
Errors After: {report.errors_after}
Final Verdict: {report.final_verdict}
Change Log: {report.change_log}
Corrected File: {report.corrected_file_path}

Investigation Results:
'''

for i in inv:
    out += f'Root Cause: {i.root_cause}\nEvidence: {i.evidence}\n\n'

with open('correction_report_output.txt', 'w') as f:
    f.write(out)
print("Done")
