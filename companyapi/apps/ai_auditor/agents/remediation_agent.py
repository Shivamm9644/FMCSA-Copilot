from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from apps.ai_auditor.qdrant_service import QdrantService
from django.conf import settings
import os

class RemediationAgent:
    def __init__(self):
        # We assume GOOGLE_API_KEY is in environment
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.2,
            max_retries=0,
        ) if os.environ.get("GOOGLE_API_KEY") else None
        self.prompt = PromptTemplate(
            input_variables=["investigation_data", "fmcsa_rules"],
            template="""You are an expert FMCSA compliance consultant and mechanic.
Review the following root cause investigation findings:
{investigation_data}

Using the official FMCSA rules below, generate a step-by-step remediation plan for the fleet manager to fix these issues. 
Format as actionable bullet points.

FMCSA Rules Context:
{fmcsa_rules}

Remediation Plan:"""
        )

    def generate_plan(self, investigation_data: dict) -> str:
        if not self.llm:
            return "1. Ensure GOOGLE_API_KEY is set to generate real remediation plans.\n2. Contact support."
            
        # Get context filtered for hardware since investigations usually deal with malfunctions/diagnostics
        fmcsa_rules = QdrantService.retrieve_context("How to fix ELD malfunctions and timing issues", limit=3, category="hardware")
        
        chain = self.prompt | self.llm
        response = chain.invoke({
            "investigation_data": str(investigation_data),
            "fmcsa_rules": fmcsa_rules
        })
        return response.content
