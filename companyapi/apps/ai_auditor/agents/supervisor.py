import logging
from typing import TypedDict, Any
from langgraph.graph import StateGraph, END
from apps.ai_auditor.agents.executive_auditor import ExecutiveAuditorAgent
from apps.ai_auditor.models import ExecutiveAuditReport

logger = logging.getLogger(__name__)

class AuditState(TypedDict):
    validation_run_id: int
    validation_data: dict
    audit_report: str
    remediation_plan: str

class SupervisorAgent:
    def __init__(self):
        self.workflow = StateGraph(AuditState)
        
        # Define nodes
        self.workflow.add_node("executive_auditor", self._run_executive_auditor)
        self.workflow.add_node("remediation_agent", self._run_remediation_agent)
        self.workflow.add_node("save_report", self._save_report)
        
        # Define edges
        self.workflow.set_entry_point("executive_auditor")
        self.workflow.add_edge("executive_auditor", "remediation_agent")
        self.workflow.add_edge("remediation_agent", "save_report")
        self.workflow.add_edge("save_report", END)
        
        self.app = self.workflow.compile()

    def _run_executive_auditor(self, state: AuditState):
        logger.info(f"Running Executive Auditor for Run {state['validation_run_id']}")
        agent = ExecutiveAuditorAgent()
        report = agent.generate_audit_report(state["validation_data"])
        return {"audit_report": report}

    def _run_remediation_agent(self, state: AuditState):
        logger.info(f"Running Remediation Agent for Run {state['validation_run_id']}")
        from apps.ai_auditor.agents.remediation_agent import RemediationAgent
        agent = RemediationAgent()
        # Pass investigation results or the whole validation_data
        investigation_data = state["validation_data"].get("investigations", [])
        plan = agent.generate_plan(investigation_data)
        return {"remediation_plan": plan}

    def _save_report(self, state: AuditState):
        logger.info(f"Saving Audit Report for Run {state['validation_run_id']}")
        try:
            ExecutiveAuditReport.objects.create(
                validation_run_id=state["validation_run_id"],
                summary=state["audit_report"],
                remediation_plan=state.get("remediation_plan", ""),
                llm_raw_response=state["audit_report"]
            )
        except Exception as e:
            logger.error(f"Failed to save Executive Audit Report: {e}")
        return state

    def run_audit(self, validation_run_id: int, validation_data: dict) -> str:
        state = {
            "validation_run_id": validation_run_id,
            "validation_data": validation_data,
            "audit_report": ""
        }
        result = self.app.invoke(state)
        return result["audit_report"]
