import json
import logging
from typing import Dict, Any, List
from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from .models import ValidationRun, ValidationFailure, InvestigationResult, CorrectionReport
from .checksum_verifier import calculate_line_checksum, rotate_left_3

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
# FMCSA ELD CSV Auto Correction Engine

You are an expert FMCSA ELD Compliance Investigator, CSV Validation Engineer, Java Backend Engineer, and Auto-Correction Agent.

Your primary objective is:
1. Analyze uploaded ELD CSV files and validation failures.
2. Investigate root causes and explain why the failure occurred.
3. Suggest CSV-level fixes.
4. Output EXACT deterministic line replacements to automatically generate a corrected CSV.

You will be given:
- The raw CSV content (with line numbers).
- The list of validation failures and diagnostics.

---

# Mandatory Output JSON Schema
You must output ONLY valid JSON matching this schema:

```json
{{
    "root_cause_analysis": [
        {{
            "rule_id": "Rule identifier",
            "rule_name": "Name of rule",
            "severity": "CRITICAL/WARNING",
            "reason": "Why it failed",
            "root_cause": "Underlying root cause (e.g. Missing Data, Driver Behavior, Source Code Bug)",
            "technical_analysis": "Deep dive into the failure",
            "fmcsa_reference": "49 CFR Part 395 reference",
            "suggested_csv_fix": "Explanation of how to fix the CSV",
            "confidence": 95
        }}
    ],
    "csv_patches": [
        {{
            "line_number": 42,
            "old_value": "1,2,3...",
            "new_value": "1,2,4...",
            "reason": "Correcting duty status",
            "fmcsa_rule": "49 CFR 395.15"
        }}
    ],
    "final_verdict": "FMCSA COMPLIANT" or "MANUAL REVIEW REQUIRED"
}}
```

# CSV Patching Rules
- In `csv_patches`, provide the `line_number` exactly as it appears in the input.
- `new_value` MUST NOT include the final line checksum (the 2-character hex code at the end of the line). We will recalculate and append it automatically.
- ONLY modify lines that directly cause the validation failures.
- If data is too corrupted to reconstruct safely, set `final_verdict` to "MANUAL REVIEW REQUIRED" and leave `csv_patches` empty.
"""

class AutonomousCorrectionAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.1,
            max_retries=0,  # Fail fast — deterministic fallback handles quota errors
            model_kwargs={"response_mime_type": "application/json"}
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", "CSV File Content:\n{csv_content}\n\nValidation Failures:\n{failures}")
        ])
        self.chain = self.prompt | self.llm

    def execute_correction(self, validation_run: ValidationRun) -> bool:
        eld_file = validation_run.eld_file
        with open(eld_file.file_path, 'r', encoding='utf-8') as f:
            raw_lines = f.read().splitlines()

        # Add line numbers for the LLM
        numbered_csv = "\n".join([f"Line {i+1}: {line}" for i, line in enumerate(raw_lines)])

        failures = ValidationFailure.objects.filter(validation_run=validation_run)
        failure_text = json.dumps([{
            "check": f.check_name,
            "description": f.description,
            "raw_data": f.raw_data
        } for f in failures], indent=2)

        if not failures.exists():
            return False # Nothing to correct

        try:
            logger.info(f"Invoking AutonomousCorrectionAgent for Run {validation_run.id}")

            # ----------------------------------------------------------------
            # PHASE 0: DETERMINISTIC CHECKSUM AUTO-CORRECTION
            # Recalculate and fix ALL line checksums before calling the LLM.
            # This ensures a corrected CSV is always produced for checksum
            # failures even when the Gemini API quota is exhausted.
            # ----------------------------------------------------------------
            deterministic_patches = []
            corrected_lines_det = list(raw_lines)
            for i, line in enumerate(corrected_lines_det):
                stripped = line.strip()
                if not stripped or stripped.lower().startswith("end of file"):
                    continue
                if ',' not in stripped:
                    continue
                parts = stripped.rsplit(',', 1)
                if len(parts) != 2:
                    continue
                body = parts[0]
                existing_chk = parts[1].strip()
                correct_chk = calculate_line_checksum(body)
                if existing_chk.upper() != correct_chk.upper():
                    new_full = f"{body},{correct_chk}"
                    deterministic_patches.append({
                        "line_number": i + 1,
                        "old_value": line,
                        "new_value": new_full,
                        "reason": f"Recalculated line checksum: was '{existing_chk}', should be '{correct_chk}'",
                        "fmcsa_rule": "FMCSA ELD Spec - Line Data Check Value"
                    })
                    corrected_lines_det[i] = new_full

            # Recalculate file checksum
            new_file_chk = self._recalculate_file_checksum(corrected_lines_det)
            if len(corrected_lines_det) >= 2 and corrected_lines_det[-2].lower().startswith("end of file"):
                corrected_lines_det[-1] = new_file_chk

            # Save deterministic corrected CSV immediately (LLM may fail/quota)
            orig_path = eld_file.file_path
            corrected_path = orig_path.replace(".csv", "_corrected.csv")
            with open(corrected_path, 'w', encoding='utf-8', newline='') as cf:
                cf.write("\n".join(corrected_lines_det))
                cf.write("\n")
            logger.info(f"Deterministic corrected CSV saved: {corrected_path} ({len(deterministic_patches)} patches)")

            # ----------------------------------------------------------------
            # PHASE 1: LLM ROOT CAUSE ANALYSIS & DATA-LEVEL CORRECTIONS
            # ----------------------------------------------------------------
            import os
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key or api_key == "your_gemini_api_key_here":
                logger.warning("No valid Gemini API key found. Using deterministic result only.")
                result_json = {
                    "final_verdict": "FMCSA COMPLIANT" if not deterministic_patches else "PARTIALLY CORRECTED",
                    "root_cause_analysis": [{
                        "rule_id": "CHECKSUM_AUTO_CORRECTED",
                        "rule_name": "Deterministic Checksum Auto-Correction",
                        "severity": "INFO",
                        "reason": f"{len(deterministic_patches)} line checksum(s) were recalculated and corrected automatically.",
                        "root_cause": "Incorrect checksum values in CSV file",
                        "technical_analysis": "Line and file checksums were recomputed per FMCSA spec and applied.",
                        "fmcsa_reference": "49 CFR 395.15 - ELD Line Data Check Value",
                        "suggested_csv_fix": "Use the auto-generated corrected CSV file.",
                        "confidence": 100
                    }],
                    "csv_patches": []
                }
            else:
                try:
                    response = self.chain.invoke({
                        "csv_content": numbered_csv,
                        "failures": failure_text
                    })
                    result_json = json.loads(response.content)
                except Exception as llm_err:
                    logger.warning(f"LLM call failed ({llm_err}). Falling back to deterministic result.")
                    result_json = {
                        "final_verdict": "PARTIALLY CORRECTED",
                        "root_cause_analysis": [{
                            "rule_id": "LLM_QUOTA_EXCEEDED",
                            "rule_name": "LLM Unavailable - Deterministic Correction Applied",
                            "severity": "WARNING",
                            "reason": f"LLM call failed: {str(llm_err)[:200]}",
                            "root_cause": "API quota exceeded or network error",
                            "technical_analysis": f"Checksum errors were fixed deterministically. {len(deterministic_patches)} patches applied.",
                            "fmcsa_reference": "N/A",
                            "suggested_csv_fix": "Download the corrected CSV. LLM data-level analysis unavailable due to quota.",
                            "confidence": 80
                        }],
                        "csv_patches": []
                    }

            # Save the report
            report = CorrectionReport.objects.create(
                validation_run=validation_run,
                original_status=validation_run.status,
                errors_before=failures.count(),
                final_verdict=result_json.get("final_verdict", "MANUAL REVIEW REQUIRED")
            )

            patches = result_json.get("csv_patches", [])
            # Start from deterministic corrections, then apply any LLM patches on top
            change_log = list(deterministic_patches)  # Include deterministic fixes in changelog
            
            if patches:
                # Apply LLM patches on top of deterministic corrections
                corrected_lines = list(corrected_lines_det)
                for patch in patches:
                    idx = patch["line_number"] - 1
                    if 0 <= idx < len(corrected_lines):
                        new_content = patch["new_value"]
                        # Strip any trailing checksum the LLM may have mistakenly included
                        parts_chk = new_content.rsplit(',', 1)
                        if len(parts_chk) == 2 and len(parts_chk[1].strip()) == 2:
                            try:
                                int(parts_chk[1].strip(), 16)
                                new_content = parts_chk[0]  # Remove LLM-supplied checksum
                            except ValueError:
                                pass
                        # Auto-calculate correct checksum
                        new_checksum = calculate_line_checksum(new_content)
                        new_full_line = f"{new_content},{new_checksum}"
                        
                        change_log.append({
                            "record": f"Line {patch['line_number']}",
                            "old_value": corrected_lines[idx],
                            "new_value": new_full_line,
                            "reason": patch.get("reason", ""),
                            "fmcsa_rule": patch.get("fmcsa_rule", "")
                        })
                        corrected_lines[idx] = new_full_line

                # Recalculate File Checksum
                new_file_checksum = self._recalculate_file_checksum(corrected_lines)
                if len(corrected_lines) >= 2 and corrected_lines[-2].lower().startswith("end of file"):
                    corrected_lines[-1] = new_file_checksum
                
                # Revalidation
                from django.utils import timezone
                metrics, all_errors = self._run_revalidation(corrected_lines)
                errors_after = len(all_errors)
                report.errors_after = errors_after
                report.errors_remaining_details = all_errors
                report.revalidated_at = timezone.now()
                
                if metrics.get("is_valid", False) and errors_after == 0:
                    report.verification_status = 'PASS'
                    report.final_verdict = 'FMCSA COMPLIANT'
                    report.corrected_status = 'PASS'
                else:
                    report.verification_status = 'FAIL'
                    report.final_verdict = 'MANUAL REVIEW REQUIRED'
                    report.corrected_status = 'PARTIAL'
                
                # Overwrite corrected CSV with LLM-enhanced version
                with open(corrected_path, 'w', encoding='utf-8', newline='') as f:
                    f.write("\n".join(corrected_lines))
                    f.write("\n")
                logger.info(f"LLM-enhanced corrected CSV saved: {corrected_path} | errors_after={errors_after} | verification={report.verification_status}")
            else:
                # No LLM patches — use deterministic corrections only
                from django.utils import timezone
                metrics, all_errors = self._run_revalidation(corrected_lines_det)
                errors_after = len(all_errors)
                report.errors_after = errors_after
                report.errors_remaining_details = all_errors
                report.revalidated_at = timezone.now()
                
                if metrics.get("is_valid", False) and errors_after == 0:
                    report.verification_status = 'PASS'
                    report.final_verdict = 'FMCSA COMPLIANT'
                    report.corrected_status = 'PASS'
                else:
                    report.verification_status = 'FAIL'
                    report.final_verdict = 'MANUAL REVIEW REQUIRED'
                    report.corrected_status = 'PARTIAL'
                logger.info(f"Deterministic-only correction. errors_after={errors_after} | verification={report.verification_status}")

            # Always point to the corrected file (written in Phase 0)
            report.corrected_file_path = corrected_path
                
            # Synthesize before/after
            report.change_log = change_log
            
            # Store Root Cause analysis into InvestigationResult for dashboard
            for rc in result_json.get("root_cause_analysis", []):
                InvestigationResult.objects.create(
                    validation_run=validation_run,
                    root_cause=rc.get("root_cause", ""),
                    evidence=[
                        rc.get("technical_analysis", ""),
                        f"Rule: {rc.get('rule_id', '')} - {rc.get('rule_name', '')}",
                        f"Ref: {rc.get('fmcsa_reference', '')}",
                        f"Fix: {rc.get('suggested_csv_fix', '')}"
                    ]
                )
                
            report.save()
            return True

        except Exception as e:
            logger.error(f"Correction Agent Error: {str(e)}", exc_info=True)
            # Last resort: if we have a corrected_path from deterministic phase, save a minimal report
            try:
                if 'corrected_path' in locals() and os.path.exists(corrected_path):
                    CorrectionReport.objects.get_or_create(
                        validation_run=validation_run,
                        defaults={
                            'original_status': validation_run.status,
                            'errors_before': failures.count(),
                            'final_verdict': 'PARTIALLY CORRECTED',
                            'corrected_status': 'PARTIAL',
                            'corrected_file_path': corrected_path,
                            'change_log': deterministic_patches if 'deterministic_patches' in locals() else []
                        }
                    )
            except Exception:
                pass
            return False

    def _recalculate_file_checksum(self, lines: List[str]) -> str:
        line_checksum_sum = 0
        for line in lines:
            if not line or line.lower().startswith("end of file") or len(line) <= 4:
                continue
            if ',' in line:
                chk = line.rsplit(',', 1)[1].strip()
                try:
                    line_checksum_sum += int(chk, 16)
                except ValueError:
                    pass
                    
        file_checksum_16 = line_checksum_sum & 0xFFFF
        high_rotated = rotate_left_3((file_checksum_16 >> 8) & 0xFF)
        low_rotated = rotate_left_3(file_checksum_16 & 0xFF)
        combined = (high_rotated << 8) | low_rotated
        return f"{(combined ^ 0x969C):04X}"

    def _run_revalidation(self, lines: List[str]) -> tuple:
        from apps.validations.pipeline import run_full_validation_pipeline
        csv_content = "\n".join(lines)
        metrics, all_errors = run_full_validation_pipeline(csv_content, save_to_db=False)
        return metrics, all_errors
