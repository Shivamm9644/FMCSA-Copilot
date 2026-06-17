import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from apps.ai_auditor.qdrant_service import QdrantService

class ExecutiveAuditorAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.2,
            max_retries=0
        ) if os.environ.get("GOOGLE_API_KEY") else None

    def generate_audit_report(self, validation_data: dict) -> str:
        if not self.llm:
            return "Executive Audit Report: (Mocked - No Google API Key). The ELD file shows multiple compliance issues."

        # Summarize data to avoid blowing up context window
        score = validation_data.get("compliance_score")
        risk = validation_data.get("risk_level")
        failures = validation_data.get("failures", [])
        malfunctions = validation_data.get("malfunction_events", [])
        investigations = validation_data.get("investigations", [])

        # Fetch relevant FMCSA context based on findings
        search_query = "ELD compliance rules for "
        if malfunctions:
            search_query += malfunctions[0].get("malfunction_type", "") + " malfunction."
        elif investigations:
            search_query += investigations[0].get("root_cause", "")
        else:
            search_query += "general driving logs."
            
        fmcsa_context = QdrantService.retrieve_context(search_query)

        system_prompt = (
            "You are an expert FMCSA Executive Compliance Auditor. "
            "Write a concise, professional executive summary report for this ELD run. "
            "Cite the provided FMCSA rules where applicable.\n\n"
            f"Relevant FMCSA Rules:\n{fmcsa_context}"
        )

        human_prompt = (
            f"Compliance Score: {score}\n"
            f"Risk Level: {risk}\n\n"
            f"Validation Failures: {json.dumps([f.get('description') for f in failures])}\n"
            f"Malfunctions: {json.dumps([m.get('description') for m in malfunctions])}\n"
            f"Root Cause Investigations: {json.dumps([i.get('root_cause') for i in investigations])}\n\n"
            "Please provide a final Markdown executive summary."
        )

        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        
        return response.content
