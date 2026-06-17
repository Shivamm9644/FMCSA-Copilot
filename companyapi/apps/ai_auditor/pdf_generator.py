import os
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from apps.validations.models import ValidationRun

def generate_audit_pdf(validation_run: ValidationRun) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = styles['Title']
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    elements = []
    
    # Title
    elements.append(Paragraph(f"FMCSA ELD Compliance Audit Report", title_style))
    elements.append(Spacer(1, 12))
    
    # Summary Table
    elements.append(Paragraph("Executive Summary", heading_style))
    eld_file = validation_run.eld_file
    summary_data = [
        ["File Name", eld_file.filename],
        ["Upload Date", eld_file.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')],
        ["Compliance Score", f"{eld_file.compliance_score}/100"],
        ["Risk Level", validation_run.risk_level],
        ["Severity", validation_run.severity_level]
    ]
    t = Table(summary_data, colWidths=[150, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 24))
    
    # AI Summary
    if hasattr(validation_run, 'executive_audit'):
        elements.append(Paragraph("AI Auditor Summary", heading_style))
        elements.append(Paragraph(validation_run.executive_audit.summary, normal_style))
        elements.append(Spacer(1, 12))
        
        elements.append(Paragraph("Remediation Plan", heading_style))
        elements.append(Paragraph(validation_run.executive_audit.remediation_plan or "None", normal_style))
        elements.append(Spacer(1, 24))
        
    # Validation Failures
    elements.append(Paragraph("Validation Failures", heading_style))
    failures = validation_run.failures.all()
    if failures:
        fail_data = [["Check Name", "Severity", "Description"]]
        for f in failures:
            fail_data.append([f.check_name, f.severity, f.description[:100] + "..."])
        ft = Table(fail_data, colWidths=[150, 80, 270])
        ft.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(ft)
    else:
        elements.append(Paragraph("No validation failures detected.", normal_style))
        
    doc.build(elements)
    buffer.seek(0)
    return buffer
