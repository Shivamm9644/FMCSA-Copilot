"""
File: apps/validations/diagnostic_agent.py
Why it exists:
    Provides deterministic data diagnostic detection per FMCSA specifications.
    It checks for missing required data elements, engine synchronization issues,
    timing anomalies, and impossible position jumps.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any

class DiagnosticAgent:
    """
    Analyzes ELD events for data diagnostic issues.
    """
    def detect(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        diagnostics = []
        if not events:
            return diagnostics

        # Sort all events chronologically
        sorted_events = sorted(
            events, 
            key=lambda x: x.get("event_date_time") if isinstance(x.get("event_date_time"), datetime) else datetime.fromisoformat(str(x.get("event_date_time")))
        )

        # 1. Missing Data Diagnostic
        missing_data_issues = self._check_missing_data(sorted_events)
        diagnostics.extend(missing_data_issues)

        # 2. Engine Sync Diagnostic
        engine_sync_issues = self._check_engine_sync(sorted_events)
        diagnostics.extend(engine_sync_issues)

        # 3. Timing Diagnostic
        timing_issues = self._check_timing(sorted_events)
        diagnostics.extend(timing_issues)

        # 4. Position Diagnostic
        position_issues = self._check_position(sorted_events)
        diagnostics.extend(position_issues)

        return diagnostics

    def _check_missing_data(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        issues = []
        # Check if latitude/longitude are missing when event is active (status=1)
        for idx, ev in enumerate(events):
            try:
                status = int(ev.get("record_status", 0))
            except (ValueError, TypeError):
                status = 0
            
            if status == 1:
                lat = ev.get("latitude")
                lon = ev.get("longitude")
                if lat is None or lon is None or str(lat).strip() == "" or str(lon).strip() == "":
                    issues.append({
                        "diagnostic_type": "Missing Data",
                        "description": f"Missing latitude/longitude for active event at sequence ID {ev.get('sequence_id', idx)}.",
                        "severity": "medium"
                    })
        return issues

    def _check_engine_sync(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        issues = []
        # Engine sync fails if hours/miles don't make sense over time
        last_miles = None
        last_hours = None

        for ev in events:
            try:
                miles_val = ev.get("elapsed_miles")
                hours_val = ev.get("accumulated_engine_hours")
                if miles_val is None or hours_val is None:
                    continue
                miles = int(miles_val)
                hours = Decimal(str(hours_val))
            except Exception:
                continue
            
            if miles >= 0 and hours >= 0:
                if last_miles is not None and last_hours is not None:
                    miles_diff = miles - last_miles
                    hours_diff = hours - last_hours
                    
                    if miles_diff > 50 and hours_diff <= 0:
                        issues.append({
                            "diagnostic_type": "Engine Sync",
                            "description": f"Significant mileage increase ({miles_diff} miles) without engine hours increase.",
                            "severity": "high"
                        })
                last_miles = miles
                last_hours = hours
        return issues

    def _check_timing(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        issues = []
        # Check for multiple events sharing the exact same timestamp (more than 3).
        if not events:
            return issues
            
        timestamp_counts = {}
        for ev in events:
            ts = ev.get("event_date_time")
            if ts:
                ts_str = ts.isoformat() if isinstance(ts, datetime) else str(ts)
                timestamp_counts[ts_str] = timestamp_counts.get(ts_str, 0) + 1
                
        for ts, count in timestamp_counts.items():
            if count > 3:
                issues.append({
                    "diagnostic_type": "Timing",
                    "description": f"Unusual timing: {count} events share the exact same timestamp ({ts}).",
                    "severity": "low"
                })
        return issues

    def _check_position(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        issues = []
        # Detect impossible speeds > 150 mph or invalid lat/lon
        last_time = None
        last_miles = None

        for ev in events:
            try:
                miles_val = ev.get("elapsed_miles")
                lat_val = ev.get("latitude")
                lon_val = ev.get("longitude")
                
                if miles_val is not None:
                    miles = int(miles_val)
                else:
                    miles = -1
                    
                if lat_val is not None and lon_val is not None:
                    lat = Decimal(str(lat_val))
                    lon = Decimal(str(lon_val))
                    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                        issues.append({
                            "diagnostic_type": "Position",
                            "description": f"Invalid coordinates detected: Lat {lat}, Lon {lon}.",
                            "severity": "medium"
                        })
            except Exception:
                pass # invalid format already caught by normal agents
            
            try:
                raw_time = ev.get("event_date_time")
                if not raw_time:
                    continue
                curr_time = raw_time if isinstance(raw_time, datetime) else datetime.fromisoformat(str(raw_time))

                if last_time is not None and last_miles is not None and miles >= 0:
                    time_diff = curr_time - last_time
                    elapsed_hours = time_diff.total_seconds() / 3600.0
                    miles_diff = miles - last_miles
                    
                    if elapsed_hours > 0 and miles_diff > 0:
                        avg_speed = miles_diff / elapsed_hours
                        if avg_speed > 150.0:
                            issues.append({
                                "diagnostic_type": "Position",
                                "description": f"Impossible position jump detected: average speed of {avg_speed:.2f} mph.",
                                "severity": "high"
                            })
                
                last_time = curr_time
                if miles >= 0:
                    last_miles = miles
            except Exception:
                continue

        return issues
