import csv
import time
from typing import Dict, Any, Tuple

from apps.upload.models import ELDEvent
from apps.validations.models import (
    ValidationFailure, ChecksumResult, AgentExecutionLog,
    RuleValidationResult, DiagnosticEvent, MalfunctionEvent, InvestigationResult
)
from apps.parser.segment_parsers import (
    HeaderParser, UserListParser, CMVParser, EventParser
)
from apps.validations.checksum_verifier import verify_file_checksum
from apps.validations.rules import analyze_hos_rules

def run_full_validation_pipeline(csv_content: str, eld_file=None, validation_run=None, save_to_db: bool = True) -> Tuple[Dict[str, Any], list]:
    """
    Runs the deterministic validation pipeline (Agents 1 through 7) on the provided CSV content.
    If save_to_db is True, it persists all results to the DB using the provided validation_run and eld_file.
    Returns a tuple: (metrics_dict, errors_list)
    """
    agent_logs = []
    
    # --- AGENT 1: PARSING ---
    parse_start = time.time()
    parsed_header = None
    parsed_users = []
    parsed_cmvs = []
    parsed_events = []
    
    header_parser = HeaderParser()
    user_parser = UserListParser()
    cmv_parser = CMVParser()
    event_parser = EventParser()
    
    lines = csv_content.splitlines()
    current_section = None
    header_rows = []
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        
        # Section detection
        if "ELD File Header" in line_str:
            current_section = "header"
            if "," not in line_str:
                continue
        elif "User List" in line_str:
            current_section = "users"
            if "," not in line_str:
                continue
        elif "CMV List" in line_str or "Commercial Motor Vehicle" in line_str:
            current_section = "cmvs"
            if "," not in line_str:
                continue
        elif "ELD Event List" in line_str:
            current_section = "events"
            if "," not in line_str:
                continue
        elif any(x in line_str for x in ["Annotations", "Certification", "Malfunctions", "Login/Logout", "Engine Power-Up", "Unidentified", "End of File"]):
            current_section = "ignored"
            if "," not in line_str:
                continue
        
        if current_section == "ignored":
            continue
        
        reader = csv.reader([line_str])
        try:
            row = next(reader)
        except StopIteration:
            continue
            
        if not row:
            continue
        
        if current_section == "header":
            header_rows.append(row)
        elif current_section == "users":
            res = user_parser.parse(row)
            if res:
                parsed_users.append(res)
        elif current_section == "cmvs":
            res = cmv_parser.parse(row)
            if res:
                parsed_cmvs.append(res)
        elif current_section == "events":
            res = event_parser.parse(row)
            if res:
                parsed_events.append(res)
    
    # Compile Header
    if len(header_rows) >= 7:
        try:
            l1 = header_rows[0]
            l2 = header_rows[1]
            l3 = header_rows[2]
            l4 = header_rows[3]
            l5 = header_rows[4]
            l6 = header_rows[5]
            l7 = header_rows[6]
            
            parsed_header_dict = {
                "driver_last_name": l1[0].strip() if len(l1) > 0 else "",
                "driver_first_name": l1[1].strip() if len(l1) > 1 else "",
                "driver_username": l1[2].strip() if len(l1) > 2 else "",
                "co_driver_last_name": l2[0].strip() if len(l2) > 0 else "",
                "co_driver_first_name": l2[1].strip() if len(l2) > 1 else "",
                "co_driver_username": l2[2].strip() if len(l2) > 2 else "",
                "power_unit_number": l3[0].strip() if len(l3) > 0 else "",
                "vin": l3[1].strip() if len(l3) > 1 else "",
                "carrier_usdot": l4[0].strip() if len(l4) > 0 else "",
                "carrier_name": l4[1].strip() if len(l4) > 1 else "",
                "multi_day_basis": l4[2].strip() if len(l4) > 2 else "7",
                "start_hour": l4[3].strip() if len(l4) > 3 else "0",
                "shipping_doc": l5[0].strip() if len(l5) > 0 else "",
                "exempt_status": l5[1].strip() if len(l5) > 1 else "0",
                "eld_registration_id": l7[0].strip() if len(l7) > 0 else "",
            }
            
            class DummyHeader:
                def __init__(self, d):
                    self.d = d
                def to_dict(self):
                    return self.d
                def get(self, key, default=None):
                    return self.d.get(key, default)
            
            parsed_header = DummyHeader(parsed_header_dict)
        except Exception as e:
            parsed_header = None
    elif len(header_rows) == 1:
        res = header_parser.parse(header_rows[0])
        if res:
            parsed_header = res
    
    if save_to_db and eld_file and parsed_header:
        eld_file.raw_header_json = parsed_header.to_dict()
        eld_file.save(update_fields=['raw_header_json'])
        
    if save_to_db and eld_file:
        events_to_create = []
        for ev in parsed_events:
            events_to_create.append(ELDEvent(
                eld_file=eld_file,
                sequence_id=ev.sequence_id,
                record_status=ev.record_status,
                record_origin=ev.record_origin,
                event_type=ev.event_type,
                event_code=ev.event_code,
                event_date_time=ev.event_date_time,
                accumulated_engine_hours=ev.accumulated_engine_hours,
                elapsed_miles=ev.elapsed_miles,
                location_desc=ev.location_desc,
                latitude=ev.latitude,
                longitude=ev.longitude
            ))
        if events_to_create:
            ELDEvent.objects.bulk_create(events_to_create)
            
    if save_to_db and validation_run:
        parse_duration = int((time.time() - parse_start) * 1000)
        agent_logs.append(AgentExecutionLog(
            validation_run=validation_run,
            agent_name="Parser Agent",
            status="success",
            message=f"Parsed {len(parsed_events)} event records.",
            duration_ms=parse_duration
        ))
    
    # --- AGENT 2: CHECKSUM VERIFIER ---
    chk_start = time.time()
    checksum_res = verify_file_checksum(csv_content)
    
    if save_to_db and validation_run:
        checksums_to_create = [
            ChecksumResult(
                validation_run=validation_run,
                entity_type="file",
                expected_checksum=checksum_res["file_checksum"],
                actual_checksum=checksum_res["provided_file_checksum"] or "MISSING",
                is_valid=checksum_res["is_valid"]
            )
        ]
        for fc in checksum_res["failed_lines"]:
            checksums_to_create.append(ChecksumResult(
                validation_run=validation_run,
                entity_type="line",
                entity_id=str(fc["line_number"]),
                expected_checksum=fc["expected"],
                actual_checksum=fc["actual"],
                is_valid=False
            ))
        if checksums_to_create:
            ChecksumResult.objects.bulk_create(checksums_to_create)
            
    checksum_failures_dicts = []
    for fc in checksum_res["failed_lines"]:
        checksum_failures_dicts.append({
            "rule_id": "Incorrect Line Data Check Value",
            "status": "FAIL",
            "expected_value": fc["expected"],
            "actual_value": fc["actual"],
            "severity": "CRITICAL",
            "description": f"Line {fc['line_number']} verification of the line data check value produced a result of '{fc['expected']}'. This does not match the supplied value of '{fc['actual']}'.",
            "raw_data": {"line_content": fc["content"]}
        })
    
    if not checksum_res["is_valid"] and checksum_res["provided_file_checksum"].upper() != checksum_res["file_checksum"].upper():
        checksum_failures_dicts.append({
            "rule_id": "Incorrect File Data Check Value",
            "status": "FAIL",
            "expected_value": checksum_res["file_checksum"],
            "actual_value": checksum_res["provided_file_checksum"],
            "severity": "CRITICAL",
            "description": f"Verification of the file data check value produced a result of '{checksum_res['file_checksum']}'. This does not match the supplied file data check value of '{checksum_res['provided_file_checksum']}'.",
            "raw_data": {}
        })

    if save_to_db and validation_run and checksum_failures_dicts:
        checksum_failures_to_create = []
        for cf in checksum_failures_dicts:
            checksum_failures_to_create.append(ValidationFailure(
                validation_run=validation_run,
                agent_name="Checksum Agent",
                check_name=cf["rule_id"],
                severity=cf["severity"],
                description=cf["description"],
                raw_data=cf["raw_data"]
            ))
        ValidationFailure.objects.bulk_create(checksum_failures_to_create)

    if save_to_db and validation_run:
        chk_duration = int((time.time() - chk_start) * 1000)
        agent_logs.append(AgentExecutionLog(
            validation_run=validation_run,
            agent_name="Checksum Agent",
            status="success",
            message=f"Checksum result: {checksum_res['is_valid']}. Failed lines: {len(checksum_res['failed_lines'])}",
            duration_ms=chk_duration
        ))

    # --- AGENT 3: RULES VALIDATION ---
    rules_start = time.time()
    events_dict_list = [ev.to_dict() for ev in parsed_events]
    hos_violations = analyze_hos_rules(parsed_events)
    
    if save_to_db and validation_run and hos_violations:
        failures_to_create = []
        for v in hos_violations:
            failures_to_create.append(ValidationFailure(
                validation_run=validation_run,
                agent_name="HOS Rules Agent",
                check_name=v["violation_type"],
                severity=v["severity"],
                description=v["description"],
                raw_data={"regulation": v["regulation_reference"]}
            ))
        ValidationFailure.objects.bulk_create(failures_to_create)

    if save_to_db and validation_run:
        rules_duration = int((time.time() - rules_start) * 1000)
        agent_logs.append(AgentExecutionLog(
            validation_run=validation_run,
            agent_name="Rules Agent",
            status="success",
            message=f"Completed HOS rules check. Violations found: {len(hos_violations)}",
            duration_ms=rules_duration
        ))

    # --- AGENT 4: FMCSA VALIDATION LAYER ---
    fmcsa_start = time.time()
    from apps.validations.fmcsa_agents import (
        HeaderValidationAgent, UserValidationAgent, CMVValidationAgent,
        EventValidationAgent, LoginLogoutValidationAgent, EngineHoursValidationAgent,
        OdometerValidationAgent
    )
    
    header_dict = parsed_header.to_dict() if parsed_header else None
    users_dict_list = [u.to_dict() for u in parsed_users]
    cmvs_dict_list = [c.to_dict() for c in parsed_cmvs]
    
    header_agent = HeaderValidationAgent()
    user_agent = UserValidationAgent()
    cmv_agent = CMVValidationAgent()
    event_agent = EventValidationAgent()
    login_logout_agent = LoginLogoutValidationAgent()
    engine_hours_agent = EngineHoursValidationAgent()
    odometer_agent = OdometerValidationAgent()
    
    rule_results = []
    rule_results.extend(header_agent.validate(header_dict))
    rule_results.extend(user_agent.validate(users_dict_list))
    rule_results.extend(cmv_agent.validate(cmvs_dict_list))
    rule_results.extend(event_agent.validate(events_dict_list))
    rule_results.extend(login_logout_agent.validate(events_dict_list))
    rule_results.extend(engine_hours_agent.validate(events_dict_list))
    rule_results.extend(odometer_agent.validate(events_dict_list))
    
    fmcsa_failures_count = 0
    fmcsa_failures_dicts = []
    for r in rule_results:
        if r["status"] == "FAIL":
            fmcsa_failures_count += 1
            fmcsa_failures_dicts.append({
                "rule_id": r["rule_id"],
                "status": "FAIL",
                "expected_value": r["expected_value"],
                "actual_value": r["actual_value"],
                "severity": r["severity"],
                "description": f"Rule {r['rule_id']} failed. Expected {r['expected_value']}, got {r['actual_value']}"
            })

    if save_to_db and validation_run and rule_results:
        db_rule_results = []
        for r in rule_results:
            db_rule_results.append(RuleValidationResult(
                validation_run=validation_run,
                rule_id=r["rule_id"],
                status=r["status"],
                expected_value=r["expected_value"],
                actual_value=r["actual_value"],
                severity=r["severity"]
            ))
        RuleValidationResult.objects.bulk_create(db_rule_results)

    if save_to_db and validation_run:
        fmcsa_duration = int((time.time() - fmcsa_start) * 1000)
        agent_logs.append(AgentExecutionLog(
            validation_run=validation_run,
            agent_name="FMCSA Validation Layer Agent",
            status="success",
            message=f"Completed FMCSA validation rules. Total checks: {len(rule_results)}, Failed: {fmcsa_failures_count}",
            duration_ms=fmcsa_duration
        ))

    # --- AGENT 5: DIAGNOSTIC AGENT ---
    diag_start = time.time()
    from apps.validations.diagnostic_agent import DiagnosticAgent
    diag_agent = DiagnosticAgent()
    diag_results = diag_agent.detect(events_dict_list)

    if save_to_db and validation_run and diag_results:
        db_diag_results = []
        for d in diag_results:
            db_diag_results.append(DiagnosticEvent(
                validation_run=validation_run,
                diagnostic_type=d["diagnostic_type"],
                description=d["description"],
                severity=d["severity"]
            ))
        DiagnosticEvent.objects.bulk_create(db_diag_results)

    if save_to_db and validation_run:
        diag_duration = int((time.time() - diag_start) * 1000)
        agent_logs.append(AgentExecutionLog(
            validation_run=validation_run,
            agent_name="Diagnostic Agent",
            status="success",
            message=f"Completed Data Diagnostic checks. Events generated: {len(diag_results)}",
            duration_ms=diag_duration
        ))

    # --- AGENT 6: MALFUNCTION AGENT ---
    malf_start = time.time()
    from apps.validations.malfunction_agent import MalfunctionAgent
    malf_agent = MalfunctionAgent()
    malf_results = malf_agent.detect(events_dict_list, diag_results)

    if save_to_db and validation_run and malf_results:
        db_malf_results = []
        for m in malf_results:
            db_malf_results.append(MalfunctionEvent(
                validation_run=validation_run,
                malfunction_type=m["malfunction_type"],
                description=m["description"],
                escalated_from_diagnostic=m["escalated_from_diagnostic"],
                severity=m["severity"]
            ))
        MalfunctionEvent.objects.bulk_create(db_malf_results)

    if save_to_db and validation_run:
        malf_duration = int((time.time() - malf_start) * 1000)
        agent_logs.append(AgentExecutionLog(
            validation_run=validation_run,
            agent_name="Malfunction Agent",
            status="success",
            message=f"Completed Malfunction checks. Events generated: {len(malf_results)}",
            duration_ms=malf_duration
        ))

    # --- AGENT 7: INVESTIGATION AGENT ---
    inv_start = time.time()
    from apps.validations.investigation_agent import InvestigationAgent
    inv_agent = InvestigationAgent()
    failures_list = hos_violations + rule_results + checksum_failures_dicts
    inv_results = inv_agent.investigate(failures_list, diag_results, malf_results, events_dict_list)

    if save_to_db and validation_run and inv_results:
        db_inv_results = []
        for inv in inv_results:
            db_inv_results.append(InvestigationResult(
                validation_run=validation_run,
                root_cause=inv["root_cause"],
                evidence=inv["evidence"],
                affected_records=inv["affected_records"]
            ))
        InvestigationResult.objects.bulk_create(db_inv_results)

    if save_to_db and validation_run:
        inv_duration = int((time.time() - inv_start) * 1000)
        agent_logs.append(AgentExecutionLog(
            validation_run=validation_run,
            agent_name="Investigation Agent",
            status="success",
            message=f"Completed Investigation analysis. Root causes found: {len(inv_results)}",
            duration_ms=inv_duration
        ))

    if save_to_db and validation_run and agent_logs:
        AgentExecutionLog.objects.bulk_create(agent_logs)
        
    # --- SCORING ENGINE ---
    score = 100.0
    score -= (len(hos_violations) * 5.0)
    score -= (fmcsa_failures_count * 5.0)
    score -= (len(diag_results) * 3.0)
    score -= (len(malf_results) * 10.0)
    score -= (len(checksum_res["failed_lines"]) * 2.0)
    if not checksum_res["is_valid"]:
        score -= 10.0
    score = max(0.0, min(100.0, score))
    
    risk = "LOW"
    if score < 75.0:
        risk = "HIGH"
    elif score < 90.0:
        risk = "MEDIUM"
        
    severity = "NONE"
    if len(hos_violations) > 0 or len(checksum_res["failed_lines"]) > 0 or fmcsa_failures_count > 0 or len(diag_results) > 0 or len(malf_results) > 0:
        severity = "WARNING"
    if len(hos_violations) > 2 or not checksum_res["is_valid"] or fmcsa_failures_count > 3 or len(diag_results) > 2 or len(malf_results) > 0:
        severity = "CRITICAL"
        
    metrics = {
        "score": score,
        "risk": risk,
        "severity": severity,
        "is_valid": (len(hos_violations) == 0 and fmcsa_failures_count == 0 and len(checksum_res["failed_lines"]) == 0 and checksum_res["is_valid"] and len(diag_results) == 0 and len(malf_results) == 0)
    }

    all_errors = []
    for f in checksum_failures_dicts:
        all_errors.append(f)
    for v in hos_violations:
        all_errors.append(v)
    for f in fmcsa_failures_dicts:
        all_errors.append(f)
    for d in diag_results:
        all_errors.append(d)
    for m in malf_results:
        all_errors.append(m)

    return metrics, all_errors
