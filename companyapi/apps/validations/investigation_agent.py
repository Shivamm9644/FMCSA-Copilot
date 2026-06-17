"""
File: apps/validations/investigation_agent.py
Why it exists:
    Provides deterministic investigation logic to synthesize the output of previous validation layers.
    It correlates failures, diagnostics, and malfunctions to deduce root causes.
"""

from typing import List, Dict, Any

class InvestigationAgent:
    """
    Synthesizes validation results to determine root causes.
    """
    def investigate(self, failures: List[Dict[str, Any]], diagnostics: List[Dict[str, Any]], malfunctions: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []

        # 1. Check for Persistent GPS/Sensor Failure
        # Condition: Position Malfunction + Missing Data Diagnostics
        has_pos_malf = any(m.get("malfunction_type") == "Position" for m in malfunctions)
        missing_data_diags = [d for d in diagnostics if d.get("diagnostic_type") == "Missing Data"]
        
        if has_pos_malf and len(missing_data_diags) > 0:
            affected_records = []
            for ev in events:
                if int(ev.get("record_status", 0)) == 1:
                    lat = ev.get("latitude")
                    lon = ev.get("longitude")
                    if lat is None or lon is None or str(lat).strip() == "" or str(lon).strip() == "":
                        affected_records.append(ev.get("sequence_id"))
            
            results.append({
                "root_cause": "Persistent ELD sensor failure or GPS disconnect.",
                "evidence": [
                    "Position Malfunction detected.",
                    f"{len(missing_data_diags)} Missing Data Diagnostic events recorded."
                ],
                "affected_records": affected_records
            })

        # 2. Check for Potential Tampering / Persistent Engine Sync Loss
        # Condition: Engine Sync Malfunction + Engine Sync Diagnostics
        has_engine_malf = any(m.get("malfunction_type") == "Engine Sync" for m in malfunctions)
        engine_diags = [d for d in diagnostics if d.get("diagnostic_type") == "Engine Sync"]
        
        if has_engine_malf and len(engine_diags) > 0:
            results.append({
                "root_cause": "Potential tampering or persistent ECM (Engine Control Module) disconnect.",
                "evidence": [
                    "Engine Sync Malfunction detected.",
                    f"{len(engine_diags)} Engine Sync Diagnostic events recorded."
                ],
                "affected_records": [] # Could aggregate specific sequence IDs if engine sync logic recorded them
            })

        # 3. Check for Systematic Time Drift
        has_timing_malf = any(m.get("malfunction_type") == "Timing" for m in malfunctions)
        timing_diags = [d for d in diagnostics if d.get("diagnostic_type") == "Timing"]
        
        if has_timing_malf and len(timing_diags) > 0:
            results.append({
                "root_cause": "Systematic ELD internal clock drift or failure to sync with UTC.",
                "evidence": [
                    "Timing Malfunction detected.",
                    f"{len(timing_diags)} Timing Diagnostic events recorded."
                ],
                "affected_records": []
            })
            
        # 4. Check for Power Loss Events
        has_power_malf = any(m.get("malfunction_type") == "Power" for m in malfunctions)
        if has_power_malf:
            results.append({
                "root_cause": "Unexplained power loss or device shutdown during expected active hours.",
                "evidence": [
                    "Power Malfunction detected due to >24h data gap."
                ],
                "affected_records": []
            })

        return results
