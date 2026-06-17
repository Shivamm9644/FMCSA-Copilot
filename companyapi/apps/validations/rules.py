"""
File: apps/validations/rules.py
Why it exists:
    Executes deterministic safety checks on duty status logs to evaluate compliance
    with Federal Motor Carrier Safety Administration (FMCSA) Hours of Service (HOS) rules:
    - 11-Hour Driving Rule (395.3(a)(3)(i))
    - 14-Hour Shift Limit Rule (395.3(a)(2))
    - 30-Minute Rest Break Rule (395.3(a)(3)(ii))

Inputs:
    - events (List[Dict[str, Any]]): List of parsed ELD event records containing event_code and event_date_time.

Outputs:
    - List[Dict[str, Any]]: A list of detected HOS violations.

Dependencies:
    - datetime, timedelta (Python Standard Library)
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any

def analyze_hos_rules(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Evaluates ELD event records against FMCSA HOS rules.
    """
    violations = []
    if not events:
        return violations

    # Sort events chronologically
    sorted_events = sorted(events, key=lambda x: x.get("event_date_time"))
    
    # 1. 30-Minute Break Rule Check
    # A driver must take a 30-minute consecutive break if more than 8 hours have elapsed since the end of the last 30-minute break
    last_break_end = sorted_events[0].get("event_date_time")
    consecutive_off_duty_duration = timedelta()
    
    for idx, event in enumerate(sorted_events):
        curr_time = event.get("event_date_time")
        code = event.get("event_code")
        
        # Calculate time elapsed since last break end
        elapsed_since_break = curr_time - last_break_end
        
        if code in [1, 2]:  # Off Duty or Sleeper Berth (qualifies for break)
            # Find next event time to determine duration
            if idx + 1 < len(sorted_events):
                next_time = sorted_events[idx + 1].get("event_date_time")
                duration = next_time - curr_time
                consecutive_off_duty_duration += duration
            else:
                consecutive_off_duty_duration += timedelta(minutes=30)  # assume break continues
                
            if consecutive_off_duty_duration >= timedelta(minutes=30):
                last_break_end = curr_time + consecutive_off_duty_duration
                consecutive_off_duty_duration = timedelta()
        else:
            consecutive_off_duty_duration = timedelta()
            if elapsed_since_break > timedelta(hours=8) and code == 3:  # Driving after 8 hours without 30m break
                violations.append({
                    "violation_type": "30_min_break",
                    "severity": "medium",
                    "regulation_reference": "395.3(a)(3)(ii)",
                    "description": f"Driver drove at {curr_time.isoformat()} which is more than 8 hours since the last 30-minute break."
                })

    # 2. 11-Hour Driving Rule & 14-Hour Shift Limit Check
    # Within a 14-hour window from shift start, a driver can drive up to 11 hours.
    # A shift starts when transitioning from 10 consecutive hours off-duty to on-duty/driving.
    shift_start = None
    accumulated_driving = timedelta()
    consecutive_off_duty = timedelta()
    
    # Initialize shift_start to the first event's time as a default fallback
    if sorted_events:
        shift_start = sorted_events[0].get("event_date_time")

    for idx, event in enumerate(sorted_events):
        curr_time = event.get("event_date_time")
        code = event.get("event_code")
        
        # Determine transition out of off-duty
        if code in [1, 2]:  # Off Duty / Sleeper
            if idx + 1 < len(sorted_events):
                next_time = sorted_events[idx + 1].get("event_date_time")
                duration = next_time - curr_time
                consecutive_off_duty += duration
            else:
                consecutive_off_duty += timedelta(hours=10)
        else:
            # Transition out of off-duty
            if consecutive_off_duty >= timedelta(hours=10):
                # Reset shift parameters
                shift_start = curr_time
                accumulated_driving = timedelta()
            consecutive_off_duty = timedelta()

        if shift_start:
            # Check if current event is within the shift window
            shift_elapsed = curr_time - shift_start
            
            # 14-Hour Shift violation
            if shift_elapsed > timedelta(hours=14) and code == 3:
                violations.append({
                    "violation_type": "14_hour_duty",
                    "severity": "high",
                    "regulation_reference": "395.3(a)(2)",
                    "description": f"Driving event at {curr_time.isoformat()} occurred after the 14-hour shift limit."
                })
                
            # Accumulate driving hours
            if code == 3:
                if idx + 1 < len(sorted_events):
                    next_time = sorted_events[idx + 1].get("event_date_time")
                    drive_duration = next_time - curr_time
                    accumulated_driving += drive_duration
                else:
                    accumulated_driving += timedelta(hours=1)  # assume driving continues for an hour
                    
                # 11-Hour Driving violation
                if accumulated_driving > timedelta(hours=11):
                    violations.append({
                        "violation_type": "11_hour_driving",
                        "severity": "high",
                        "regulation_reference": "395.3(a)(3)(i)",
                        "description": f"Driver exceeded 11 hours of driving on shift starting at {shift_start.isoformat()}."
                    })

    return violations
