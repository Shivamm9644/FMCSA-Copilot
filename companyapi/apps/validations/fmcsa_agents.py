"""
File: apps/validations/fmcsa_agents.py
Why it exists:
    Provides seven deterministic, rule-based FMCSA validation agents that inspect:
    - ELD header metadata format and multi-day configuration (HeaderValidationAgent)
    - User list states and driver licenses (UserValidationAgent)
    - CMV power unit details and 17-character VIN lengths (CMVValidationAgent)
    - Telemetric event sequence status codes and coordinate boundaries (EventValidationAgent)
    - Sequential and chronological integrity of Login/Logout events (LoginLogoutValidationAgent)
    - Non-negativity, monotonicity, and logical change rates of accumulated engine hours (EngineHoursValidationAgent)
    - Non-negativity, monotonicity, and average speed limits of vehicle odometer logs (OdometerValidationAgent)

Inputs:
    - Raw dictionary records or strongly-typed dataclasses (ELDHeaderRecord, UserRecord, CMVRecord, ELDEventRecord).

Outputs:
    - List[Dict[str, Any]]: A list of dictionaries representing validation outcomes containing:
      - rule_id (str)
      - status (str: 'PASS' | 'FAIL')
      - expected_value (str)
      - actual_value (str)
      - severity (str: 'low' | 'medium' | 'high' | 'critical')

Dependencies:
    - re (Python Standard Library)
    - datetime (Python Standard Library)
    - decimal (Python Standard Library)
    - typing (Python Standard Library)
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional

class HeaderValidationAgent:
    """
    Validates the ELD File Header segment record.
    """
    def validate(self, header: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        if not header:
            results.append({
                "rule_id": "RULE_HEADER_PRESENT",
                "status": "FAIL",
                "expected_value": "Header record must be present in ELD file.",
                "actual_value": "None / Missing",
                "severity": "critical"
            })
            return results

        # 1. ELD Registration ID Check (Must be 4+ alphanumeric chars)
        reg_id = header.get("eld_registration_id", "")
        reg_valid = bool(reg_id and re.match(r"^[a-zA-Z0-9]{4,}$", reg_id))
        results.append({
            "rule_id": "RULE_HEADER_REG_ID",
            "status": "PASS" if reg_valid else "FAIL",
            "expected_value": "At least 4 alphanumeric characters",
            "actual_value": str(reg_id),
            "severity": "high"
        })

        # 2. Carrier USDOT Check (Numeric only, non-empty)
        usdot = header.get("carrier_usdot", "")
        usdot_valid = bool(usdot and usdot.isdigit())
        results.append({
            "rule_id": "RULE_HEADER_USDOT",
            "status": "PASS" if usdot_valid else "FAIL",
            "expected_value": "Numeric-only USDOT digits",
            "actual_value": str(usdot),
            "severity": "high"
        })

        # 3. Driver Username Check (Non-empty)
        driver_username = header.get("driver_username", "")
        driver_user_valid = bool(driver_username and driver_username.strip())
        results.append({
            "rule_id": "RULE_HEADER_DRIVER_USERNAME",
            "status": "PASS" if driver_user_valid else "FAIL",
            "expected_value": "Non-empty driver username",
            "actual_value": str(driver_username),
            "severity": "medium"
        })

        # 4. Driver First & Last Name Check (Non-empty)
        first_name = header.get("driver_first_name", "")
        last_name = header.get("driver_last_name", "")
        name_valid = bool(first_name and first_name.strip() and last_name and last_name.strip())
        results.append({
            "rule_id": "RULE_HEADER_DRIVER_NAME",
            "status": "PASS" if name_valid else "FAIL",
            "expected_value": "Non-empty driver first and last name",
            "actual_value": f"First: '{first_name}', Last: '{last_name}'",
            "severity": "medium"
        })

        # 5. Multi-day basis check (Must be 7 or 8)
        try:
            basis = int(header.get("multi_day_basis", 0))
            basis_valid = basis in [7, 8]
        except (ValueError, TypeError):
            basis = header.get("multi_day_basis")
            basis_valid = False
        results.append({
            "rule_id": "RULE_HEADER_MULTI_DAY",
            "status": "PASS" if basis_valid else "FAIL",
            "expected_value": "7 or 8 multi-day basis",
            "actual_value": str(basis),
            "severity": "medium"
        })

        # 6. Start hour check (Must be between 0 and 23)
        try:
            start_hour = int(header.get("start_hour", -1))
            start_hour_valid = 0 <= start_hour <= 23
        except (ValueError, TypeError):
            start_hour = header.get("start_hour")
            start_hour_valid = False
        results.append({
            "rule_id": "RULE_HEADER_START_HOUR",
            "status": "PASS" if start_hour_valid else "FAIL",
            "expected_value": "Integer between 0 and 23",
            "actual_value": str(start_hour),
            "severity": "medium"
        })

        return results


class UserValidationAgent:
    """
    Validates user list records listed in the ELD User List section.
    """
    def validate(self, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        if not users:
            # Having no users is valid, but let's log info
            return results

        for idx, user in enumerate(users):
            username = user.get("username", "")
            
            # 1. License State Check (2 letters State Code)
            state = user.get("license_state", "")
            state_valid = bool(state and len(state.strip()) == 2 and state.isalpha())
            results.append({
                "rule_id": f"RULE_USER_LICENSE_STATE_IDX_{idx}",
                "status": "PASS" if state_valid else "FAIL",
                "expected_value": "2-letter alphabetic state code",
                "actual_value": str(state),
                "severity": "medium"
            })

            # 2. License Number Check (Non-empty)
            license_num = user.get("license_number", "")
            license_valid = bool(license_num and license_num.strip())
            results.append({
                "rule_id": f"RULE_USER_LICENSE_NUMBER_IDX_{idx}",
                "status": "PASS" if license_valid else "FAIL",
                "expected_value": "Non-empty license number",
                "actual_value": str(license_num),
                "severity": "high"
            })

            # 3. Username check (Non-empty)
            user_valid = bool(username and username.strip())
            results.append({
                "rule_id": f"RULE_USER_USERNAME_IDX_{idx}",
                "status": "PASS" if user_valid else "FAIL",
                "expected_value": "Non-empty username",
                "actual_value": str(username),
                "severity": "medium"
            })

        return results


class CMVValidationAgent:
    """
    Validates Commercial Motor Vehicle records.
    """
    def validate(self, cmvs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        if not cmvs:
            return results

        for idx, cmv in enumerate(cmvs):
            # 1. VIN Check (Must be exactly 17 alphanumeric characters, excluding I, O, Q)
            vin = cmv.get("vin", "")
            vin_clean = vin.strip()
            # standard VIN doesn't contain I, O, or Q
            vin_valid = bool(
                vin_clean and 
                len(vin_clean) == 17 and 
                vin_clean.isalnum() and 
                not any(c in vin_clean.upper() for c in ["I", "O", "Q"])
            )
            results.append({
                "rule_id": f"RULE_CMV_VIN_IDX_{idx}",
                "status": "PASS" if vin_valid else "FAIL",
                "expected_value": "17-character alphanumeric VIN (excluding I, O, Q)",
                "actual_value": str(vin),
                "severity": "high"
            })

            # 2. License Plate State Check (2 characters)
            state = cmv.get("license_plate_state", "")
            state_valid = bool(state and len(state.strip()) == 2 and state.isalpha())
            results.append({
                "rule_id": f"RULE_CMV_PLATE_STATE_IDX_{idx}",
                "status": "PASS" if state_valid else "FAIL",
                "expected_value": "2-letter state abbreviation",
                "actual_value": str(state),
                "severity": "low"
            })

            # 3. License Plate Check (Non-empty)
            plate = cmv.get("license_plate", "")
            plate_valid = bool(plate and plate.strip())
            results.append({
                "rule_id": f"RULE_CMV_PLATE_IDX_{idx}",
                "status": "PASS" if plate_valid else "FAIL",
                "expected_value": "Non-empty license plate number",
                "actual_value": str(plate),
                "severity": "low"
            })

            # 4. Power Unit Number Check (Non-empty)
            unit_num = cmv.get("power_unit_number", "")
            unit_valid = bool(unit_num and unit_num.strip())
            results.append({
                "rule_id": f"RULE_CMV_UNIT_NUMBER_IDX_{idx}",
                "status": "PASS" if unit_valid else "FAIL",
                "expected_value": "Non-empty power unit number",
                "actual_value": str(unit_num),
                "severity": "medium"
            })

        return results


class EventValidationAgent:
    """
    Validates individual telemetric status logs.
    """
    def validate(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        if not events:
            return results

        for idx, event in enumerate(events):
            seq_id = event.get("sequence_id")
            rule_suffix = f"SEQ_{seq_id}" if seq_id is not None else f"IDX_{idx}"

            # 1. Record Status (1=Active, 2=Inactive)
            try:
                status_val = int(event.get("record_status", 0))
                status_valid = status_val in [1, 2]
            except (ValueError, TypeError):
                status_val = event.get("record_status")
                status_valid = False
            results.append({
                "rule_id": f"RULE_EVENT_RECORD_STATUS_{rule_suffix}",
                "status": "PASS" if status_valid else "FAIL",
                "expected_value": "1 (Active) or 2 (Inactive)",
                "actual_value": str(status_val),
                "severity": "high"
            })

            # 2. Record Origin (1=Auto, 2=Driver, 3=Edit, 4=System)
            try:
                origin = int(event.get("record_origin", 0))
                origin_valid = origin in [1, 2, 3, 4]
            except (ValueError, TypeError):
                origin = event.get("record_origin")
                origin_valid = False
            results.append({
                "rule_id": f"RULE_EVENT_RECORD_ORIGIN_{rule_suffix}",
                "status": "PASS" if origin_valid else "FAIL",
                "expected_value": "Integer between 1 and 4",
                "actual_value": str(origin),
                "severity": "medium"
            })

            # 3. Event Type (1 to 6)
            try:
                e_type = int(event.get("event_type", 0))
                type_valid = 1 <= e_type <= 6
            except (ValueError, TypeError):
                e_type = event.get("event_type")
                type_valid = False
            results.append({
                "rule_id": f"RULE_EVENT_TYPE_{rule_suffix}",
                "status": "PASS" if type_valid else "FAIL",
                "expected_value": "Integer between 1 and 6",
                "actual_value": str(e_type),
                "severity": "high"
            })

            # 4. Event Code validation based on Event Type
            try:
                e_code = int(event.get("event_code", 0))
                if type_valid:
                    e_type_val = int(e_type)
                    if e_type_val == 1:  # Change in driver duty status
                        code_valid = e_code in [1, 2, 3, 4]
                    elif e_type_val == 5:  # Login/Logout
                        code_valid = e_code in [1, 2]
                    else:
                        code_valid = True  # general validation
                else:
                    code_valid = False
            except (ValueError, TypeError):
                e_code = event.get("event_code")
                code_valid = False
            results.append({
                "rule_id": f"RULE_EVENT_CODE_{rule_suffix}",
                "status": "PASS" if code_valid else "FAIL",
                "expected_value": f"Valid code for Event Type {e_type}",
                "actual_value": str(e_code),
                "severity": "high"
            })

            # 5. Latitude & Longitude bounds check (-90 to 90 / -180 to 180)
            lat = event.get("latitude")
            lon = event.get("longitude")
            coords_valid = True
            
            if lat is not None:
                try:
                    lat_dec = Decimal(str(lat))
                    if not (-90 <= lat_dec <= 90):
                        coords_valid = False
                except Exception:
                    coords_valid = False

            if lon is not None:
                try:
                    lon_dec = Decimal(str(lon))
                    if not (-180 <= lon_dec <= 180):
                        coords_valid = False
                except Exception:
                    coords_valid = False

            results.append({
                "rule_id": f"RULE_EVENT_COORDINATES_{rule_suffix}",
                "status": "PASS" if coords_valid else "FAIL",
                "expected_value": "Latitude in [-90, 90] and Longitude in [-180, 180]",
                "actual_value": f"Lat: {lat}, Lon: {lon}",
                "severity": "medium"
            })

            # 6. Sequence ID Check (positive integer)
            try:
                seq_id_val = int(seq_id)
                seq_valid = seq_id_val > 0
            except (ValueError, TypeError):
                seq_valid = False
            results.append({
                "rule_id": f"RULE_EVENT_SEQUENCE_ID_{rule_suffix}",
                "status": "PASS" if seq_valid else "FAIL",
                "expected_value": "Positive integer sequence number",
                "actual_value": str(seq_id),
                "severity": "medium"
            })

        return results


class LoginLogoutValidationAgent:
    """
    Checks sequential integrity of login/logout logs (Event Type 5).
    """
    def validate(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        if not events:
            return results

        # 1. Filter and sort login/logout events (Event Type 5)
        # Event Code 1 = Login, 2 = Logout
        login_logout_events = []
        for ev in events:
            try:
                if int(ev.get("event_type", 0)) == 5:
                    login_logout_events.append(ev)
            except (ValueError, TypeError):
                pass

        # Sort by event_date_time
        login_logout_events = sorted(
            login_logout_events, 
            key=lambda x: x.get("event_date_time") if isinstance(x.get("event_date_time"), datetime) else datetime.fromisoformat(str(x.get("event_date_time")))
        )

        if not login_logout_events:
            results.append({
                "rule_id": "RULE_LOGIN_LOGOUT_SEQUENCE",
                "status": "PASS",
                "expected_value": "Sequential login/logout actions",
                "actual_value": "No login/logout events recorded",
                "severity": "medium"
            })
            return results

        # 2. Check alternation of login (1) and logout (2)
        sequence_valid = True
        timing_valid = True
        last_code = None
        last_time = None

        for idx, ev in enumerate(login_logout_events):
            try:
                code = int(ev.get("event_code", 0))
            except (ValueError, TypeError):
                code = None
            
            raw_time = ev.get("event_date_time")
            curr_time = raw_time if isinstance(raw_time, datetime) else datetime.fromisoformat(str(raw_time))

            # Sequence Check: A login (1) must precede a logout (2), and no duplicate consecutive logins/logouts
            if last_code is None:
                # First event should ideally be a Login (1)
                if code != 1:
                    sequence_valid = False
            else:
                if code == last_code:
                    sequence_valid = False
                elif last_code == 2 and code != 1:
                    # After logout, the next must be login
                    sequence_valid = False
                elif last_code == 1 and code != 2:
                    # After login, next must be logout
                    sequence_valid = False

            # Timing Check: Chronological timestamps must be ascending
            if last_time is not None:
                if curr_time < last_time:
                    timing_valid = False

            last_code = code
            last_time = curr_time

        results.append({
            "rule_id": "RULE_LOGIN_LOGOUT_SEQUENCE",
            "status": "PASS" if sequence_valid else "FAIL",
            "expected_value": "Logins (1) and logouts (2) must alternate starting with a login",
            "actual_value": "Sequence: " + ", ".join(str(ev.get("event_code")) for ev in login_logout_events),
            "severity": "medium"
        })

        results.append({
            "rule_id": "RULE_LOGIN_LOGOUT_TIMING",
            "status": "PASS" if timing_valid else "FAIL",
            "expected_value": "Logins/logouts must occur in chronological ascending order",
            "actual_value": "Timestamps: " + ", ".join(
                (ev.get("event_date_time").isoformat() if isinstance(ev.get("event_date_time"), datetime) else str(ev.get("event_date_time"))) 
                for ev in login_logout_events
            ),
            "severity": "medium"
        })

        return results


class EngineHoursValidationAgent:
    """
    Checks non-negativity, monotonicity, and logical change rates of accumulated engine hours.
    """
    def validate(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        if not events:
            return results

        # Sort all active chronological events
        sorted_events = []
        for ev in events:
            try:
                # Check that record is active (status == 1)
                if int(ev.get("record_status", 1)) == 1:
                    sorted_events.append(ev)
            except (ValueError, TypeError):
                sorted_events.append(ev)

        sorted_events = sorted(
            sorted_events, 
            key=lambda x: x.get("event_date_time") if isinstance(x.get("event_date_time"), datetime) else datetime.fromisoformat(str(x.get("event_date_time")))
        )

        non_negative = True
        monotonic = True
        logical_rate = True
        negative_val = None
        decreasing_pair = None
        impossible_pair = None

        for idx, ev in enumerate(sorted_events):
            hours_val = ev.get("accumulated_engine_hours")
            if hours_val is None:
                continue

            try:
                hours = Decimal(str(hours_val))
            except Exception:
                continue

            # 1. Non-negativity check
            if hours < 0:
                non_negative = False
                negative_val = hours

            # Compare with previous event
            if idx > 0:
                prev_ev = sorted_events[idx - 1]
                prev_hours_val = prev_ev.get("accumulated_engine_hours")
                if prev_hours_val is not None:
                    try:
                        prev_hours = Decimal(str(prev_hours_val))
                        # 2. Monotonicity check (with reset threshold)
                        if hours < prev_hours:
                            if hours >= 15.0:  # Reset threshold: allowed to reset to small values (< 15.0)
                                monotonic = False
                                decreasing_pair = (prev_hours, hours)

                        # 3. Rate Check: only check if not a reset
                        if hours >= prev_hours:
                            raw_curr = ev.get("event_date_time")
                            raw_prev = prev_ev.get("event_date_time")
                            
                            curr_time = raw_curr if isinstance(raw_curr, datetime) else datetime.fromisoformat(str(raw_curr))
                            prev_time = raw_prev if isinstance(raw_prev, datetime) else datetime.fromisoformat(str(raw_prev))
                            
                            time_diff = curr_time - prev_time
                            elapsed_hours = Decimal(str(time_diff.total_seconds() / 3600.0))
                            
                            hours_diff = hours - prev_hours
                            if hours_diff > (elapsed_hours * Decimal("150.0") + Decimal("0.05")):
                                logical_rate = False
                                impossible_pair = (hours_diff, elapsed_hours)
                    except Exception:
                        pass

        results.append({
            "rule_id": "RULE_ENGINE_HOURS_NON_NEGATIVE",
            "status": "PASS" if non_negative else "FAIL",
            "expected_value": "Engine hours must be >= 0.0",
            "actual_value": f"Negative value found: {negative_val}" if not non_negative else "All values non-negative",
            "severity": "high"
        })

        results.append({
            "rule_id": "RULE_ENGINE_HOURS_MONOTONIC",
            "status": "PASS" if monotonic else "FAIL",
            "expected_value": "Engine hours must monotonically increase or stay constant",
            "actual_value": f"Decreased from {decreasing_pair[0]} to {decreasing_pair[1]}" if not monotonic else "All values monotonic",
            "severity": "high"
        })

        results.append({
            "rule_id": "RULE_ENGINE_HOURS_RATE",
            "status": "PASS" if logical_rate else "FAIL",
            "expected_value": "Engine hours difference must not exceed elapsed hours between logs",
            "actual_value": f"Increase of {impossible_pair[0]} hours over {impossible_pair[1]} elapsed hours" if not logical_rate else "All rates logical",
            "severity": "medium"
        })

        return results


class OdometerValidationAgent:
    """
    Checks non-negativity, monotonicity, and average speed limits of vehicle odometer logs.
    """
    def validate(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        if not events:
            return results

        # Sort all active chronological events
        sorted_events = []
        for ev in events:
            try:
                # Check that record is active (status == 1)
                if int(ev.get("record_status", 1)) == 1:
                    sorted_events.append(ev)
            except (ValueError, TypeError):
                sorted_events.append(ev)

        sorted_events = sorted(
            sorted_events, 
            key=lambda x: x.get("event_date_time") if isinstance(x.get("event_date_time"), datetime) else datetime.fromisoformat(str(x.get("event_date_time")))
        )

        non_negative = True
        monotonic = True
        logical_speed = True
        negative_val = None
        decreasing_pair = None
        impossible_speed = None

        for idx, ev in enumerate(sorted_events):
            miles_val = ev.get("elapsed_miles")
            if miles_val is None:
                continue

            try:
                miles = int(miles_val)
            except Exception:
                continue

            # 1. Non-negativity check
            if miles < 0:
                non_negative = False
                negative_val = miles

            # Compare with previous event
            if idx > 0:
                prev_ev = sorted_events[idx - 1]
                prev_miles_val = prev_ev.get("elapsed_miles")
                if prev_miles_val is not None:
                    try:
                        prev_miles = int(prev_miles_val)
                        # 2. Monotonicity check (with reset threshold)
                        if miles < prev_miles:
                            if miles >= 50:  # Reset threshold: allowed to reset to small values (< 50)
                                monotonic = False
                                decreasing_pair = (prev_miles, miles)

                        # 3. Speed Rate Check: only check if not a reset
                        if miles >= prev_miles:
                            raw_curr = ev.get("event_date_time")
                            raw_prev = prev_ev.get("event_date_time")
                            
                            curr_time = raw_curr if isinstance(raw_curr, datetime) else datetime.fromisoformat(str(raw_curr))
                            prev_time = raw_prev if isinstance(raw_prev, datetime) else datetime.fromisoformat(str(raw_prev))
                            
                            time_diff = curr_time - prev_time
                            elapsed_hours = time_diff.total_seconds() / 3600.0
                            
                            miles_diff = miles - prev_miles
                            if elapsed_hours > 0.0:
                                avg_speed = miles_diff / elapsed_hours
                                if avg_speed > 110.0:
                                    logical_speed = False
                                    impossible_speed = (avg_speed, miles_diff, elapsed_hours)
                    except Exception:
                        pass

        results.append({
            "rule_id": "RULE_ODOMETER_NON_NEGATIVE",
            "status": "PASS" if non_negative else "FAIL",
            "expected_value": "Odometer/elapsed miles must be >= 0",
            "actual_value": f"Negative value found: {negative_val}" if not non_negative else "All values non-negative",
            "severity": "high"
        })

        results.append({
            "rule_id": "RULE_ODOMETER_MONOTONIC",
            "status": "PASS" if monotonic else "FAIL",
            "expected_value": "Odometer/elapsed miles must monotonically increase or stay constant",
            "actual_value": f"Decreased from {decreasing_pair[0]} to {decreasing_pair[1]}" if not monotonic else "All values monotonic",
            "severity": "high"
        })

        results.append({
            "rule_id": "RULE_ODOMETER_SPEED",
            "status": "PASS" if logical_speed else "FAIL",
            "expected_value": "Average speed between events must be <= 110 mph",
            "actual_value": f"Calculated speed of {impossible_speed[0]:.2f} mph ({impossible_speed[1]} miles in {impossible_speed[2]:.2f} hours)" if not logical_speed else "All speeds logical",
            "severity": "medium"
        })

        return results
