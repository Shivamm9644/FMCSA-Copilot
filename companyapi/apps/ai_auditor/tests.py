import os
from unittest.mock import patch
from django.test import TestCase
from apps.validations.models import ValidationRun
from apps.upload.models import ELDFile, Company
from apps.ai_auditor.models import ExecutiveAuditReport
from apps.ai_auditor.agents.supervisor import SupervisorAgent

from django.contrib.auth.models import User

class AIAuditorTests(TestCase):
    def setUp(self):
        user = User.objects.create(username="testuser")
        eld_file = ELDFile.objects.create(driver=user, filename="test.csv")
        self.val_run = ValidationRun.objects.create(
            eld_file=eld_file,
            compliance_score=85.0,
            risk_level="MEDIUM",
            severity_level="WARNING"
        )
        self.mock_data = {
            "compliance_score": 85.0,
            "risk_level": "MEDIUM",
            "failures": [],
            "malfunction_events": [],
            "investigations": []
        }

    @patch("apps.ai_auditor.agents.executive_auditor.ExecutiveAuditorAgent.generate_audit_report")
    def test_supervisor_agent_execution(self, mock_generate):
        mock_generate.return_value = "MOCKED AUDIT REPORT"
        
        supervisor = SupervisorAgent()
        result = supervisor.run_audit(self.val_run.id, self.mock_data)
        
        self.assertEqual(result, "MOCKED AUDIT REPORT")
        
        # Verify it was saved to DB
        report = ExecutiveAuditReport.objects.get(validation_run_id=self.val_run.id)
        self.assertEqual(report.summary, "MOCKED AUDIT REPORT")
