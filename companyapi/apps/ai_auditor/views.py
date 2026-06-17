from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from apps.validations.models import ValidationRun
from apps.ai_auditor.pdf_generator import generate_audit_pdf
from apps.ai_auditor.models import ExecutiveAuditReport
from rest_framework import viewsets
from rest_framework.decorators import action

class ReportViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk=None):
        val_run = get_object_or_404(ValidationRun, eld_file_id=pk)
        data = {
            "validation_run_id": val_run.id,
            "status": val_run.status,
            "compliance_score": val_run.eld_file.compliance_score,
            "risk_level": val_run.risk_level,
            "severity_level": val_run.severity_level,
        }
        if hasattr(val_run, 'executive_audit'):
            data["summary"] = val_run.executive_audit.summary
            data["remediation_plan"] = val_run.executive_audit.remediation_plan
            
        return Response(data)
        
    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        val_run = get_object_or_404(ValidationRun, eld_file_id=pk)
        
        try:
            pdf_buffer = generate_audit_pdf(val_run)
            response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="compliance_report_{pk}.pdf"'
            return response
        except Exception as e:
            return Response({"error": f"Failed to generate PDF: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
import os
import json
import base64
import tempfile
import csv
from PyPDF2 import PdfReader
from docx import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from apps.ai_auditor.qdrant_service import QdrantService
from dotenv import load_dotenv

class ChatViewSet(viewsets.ViewSet):
    def create(self, request):
        query = request.data.get('query')
        if not query:
            return Response({"error": "No query provided."}, status=status.HTTP_400_BAD_REQUEST)
            
        file_context = ""
        b64_images = []
        
        # Handle file attachments
        files = request.FILES.getlist('attachments')
        for f in files:
            ext = f.name.lower().split('.')[-1]
            try:
                if ext in ['png', 'jpg', 'jpeg']:
                    img_data = f.read()
                    b64 = base64.b64encode(img_data).decode('utf-8')
                    b64_images.append((ext, b64))
                elif ext == 'pdf':
                    reader = PdfReader(f)
                    text = []
                    for page in reader.pages:
                        text.append(page.extract_text())
                    file_context += f"\n--- PDF File ({f.name}) ---\n" + "\n".join(text)
                elif ext == 'docx':
                    doc = Document(f)
                    text = [p.text for p in doc.paragraphs]
                    file_context += f"\n--- Word Document ({f.name}) ---\n" + "\n".join(text)
                elif ext in ['csv', 'txt']:
                    text = f.read().decode('utf-8', errors='ignore')
                    file_context += f"\n--- Text/CSV File ({f.name}) ---\n" + text
            except Exception as e:
                file_context += f"\n[Error reading file {f.name}: {str(e)}]"

        # 1. Retrieve REAL context from Qdrant via fastembed
        raw_sources = QdrantService.retrieve_context(query, limit=2)
        
        if not raw_sources or max([s["score"] for s in raw_sources] + [0]) < 0.2:
            # Keyword fallback: search seeded docs directly
            raw_sources = QdrantService.keyword_fallback(query)

        # Build context text
        if raw_sources:
            context_text = "\n\n".join([f"Source: {s['source']} ({s['regulation']})\nText: {s['text']}" for s in raw_sources])
        else:
            context_text = "No specific FMCSA rules found in the database. Rely on general knowledge."

        # Dynamically reload environment variables
        load_dotenv(override=True)
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        
        if not api_key or api_key == "your_gemini_api_key_here":
            # LOCAL DETERMINISTIC RAG (No API Key Required)
            return Response({
                "summary": "Offline Mode. I can only answer direct keywords about ELDs or Hours of Service.",
                "detected_issues": "N/A",
                "root_cause": "N/A",
                "fmcsa_reference": "N/A",
                "suggested_fix": "None",
                "confidence_score": 0.0
            })
            
        # GEMINI LLM RAG
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.1,
            api_key=api_key,
            max_retries=0
        )
        
        prompt_text = f"""You are an expert FMCSA compliance consultant and an intelligent assistant. 
If the user's query is about FMCSA regulations, ELDs, or Hours of Service, answer it using ONLY the provided context and uploaded files.
If the user's query is a general knowledge question, you MUST answer it politely based on your general knowledge.
If an image or file is uploaded, analyze it thoroughly to detect errors, non-compliance, or required fixes.

Context from FMCSA Rulebook:
{context_text}

Additional Uploaded Files Content:
{file_context}

User Query: {query}

You MUST return your response as a valid JSON object strictly matching this exact schema:
{{
  "summary": "A detailed explanation addressing the query and file contents.",
  "detected_issues": "Bullet points of detected issues, or 'None detected'.",
  "root_cause": "The root cause of the issues, or 'N/A'.",
  "fmcsa_reference": "The specific regulation citation from the context, or 'N/A'.",
  "suggested_fix": "Any recommended corrective action based on the rules, or 'None'.",
  "confidence_score": 95
}}
"""

        message_content = [{"type": "text", "text": prompt_text}]
        for ext, b64 in b64_images:
            mime_type = f"image/{'jpeg' if ext in ['jpg', 'jpeg'] else 'png'}"
            message_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}})

        msg = HumanMessage(content=message_content)
        
        try:
            response = llm.invoke([msg])
            
            # Parse JSON
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]
                
            data = json.loads(content)
            # Ensure all keys exist
            defaults = ["summary", "detected_issues", "root_cause", "fmcsa_reference", "suggested_fix", "confidence_score"]
            for d in defaults:
                if d not in data:
                    data[d] = "N/A"
            return Response(data)
        except Exception as e:
            return Response({
                "summary": f"Failed to generate AI response: {str(e)}",
                "detected_issues": "N/A",
                "root_cause": "System Error",
                "fmcsa_reference": "N/A",
                "suggested_fix": "Retry request",
                "confidence_score": 0.0
            })
