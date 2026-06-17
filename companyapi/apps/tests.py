"""
File: apps/tests.py
Why it exists:
    Provides comprehensive automated tests verifying:
    1. Parsing logic for FMCSA date/time formats and segment parsers (Header, User, CMV, Event).
    2. Checksum calculations (Line, Event, and File Checksums) matching the FMCSA specification.
    3. Integration testing of file uploads via DRF, using APIRequestFactory and force_authenticate
       to ensure records are written to ValidationRun, ValidationFailure, and ChecksumResult tables correctly.

Inputs:
    - Mock ELD CSV files, individual data rows, and API requests.

Outputs:
    - Test success/failure results.

Dependencies:
    - django.test.TestCase (Django testing library)
    - rest_framework.test.APIRequestFactory (DRF request builder)
    - rest_framework.test.force_authenticate (DRF force authentication helper)
    - django.contrib.auth.models.User (Django Auth)
    - apps.parser.segment_parsers (Segment parsing engine)
    - apps.validations.checksum_verifier (Checksum engine)
    - apps.upload.models (Ingestion database tables)
    - apps.validations.models (Validation database tables)
    - apps.upload.views (ELD view controller actions)
"""

import io
from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.parser.segment_parsers import (
    HeaderParser, UserListParser, CMVParser, EventParser, parse_fmcsa_datetime
)
from apps.validations.checksum_verifier import (
    calculate_line_checksum,
    calculate_event_checksum,
    verify_file_checksum,
    fmcsa_char_to_dec,
    rotate_left_3
)
from apps.upload.models import Company, CMV, ELDFile, ELDEvent
from apps.validations.models import (
    ValidationRun, ValidationFailure, ChecksumResult, AgentExecutionLog, RuleValidationResult
)
from apps.validations.rules import analyze_hos_rules
from apps.validations.fmcsa_agents import (
    HeaderValidationAgent, UserValidationAgent, CMVValidationAgent,
    EventValidationAgent, LoginLogoutValidationAgent, EngineHoursValidationAgent,
    OdometerValidationAgent
)
from apps.validations.diagnostic_agent import DiagnosticAgent
from apps.validations.malfunction_agent import MalfunctionAgent
from apps.validations.investigation_agent import InvestigationAgent
from apps.upload.views import ELDFileViewSet

class RestructuredParserTests(TestCase):
    
    def test_parse_fmcsa_datetime(self):
        dt = parse_fmcsa_datetime("061026", "154536")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 6)
        self.assertEqual(dt.day, 10)
        self.assertEqual(dt.hour, 15)
        self.assertEqual(dt.minute, 45)
        self.assertEqual(dt.second, 36)

    def test_header_parser_typed(self):
        row = ["ELD File Header", "ELDREG123", "Doe", "John", "johndoe", "Smith", "Jane", "janesmith", "1234567", "Test Carrier Inc", "7", "0", "SHIP987", "0", "F7"]
        parser = HeaderParser()
        record = parser.parse(row)
        self.assertIsNotNone(record)
        self.assertEqual(record.eld_registration_id, "ELDREG123")
        self.assertEqual(record.driver_last_name, "Doe")
        self.assertEqual(record.driver_first_name, "John")
        self.assertEqual(record.driver_username, "johndoe")
        self.assertEqual(record.carrier_usdot, "1234567")
        self.assertEqual(record.carrier_name, "Test Carrier Inc")
        self.assertEqual(record.multi_day_basis, 7)
        self.assertEqual(record.start_hour, 0)
        self.assertEqual(record.shipping_doc, "SHIP987")
        self.assertEqual(record.exempt_status, "0")
        
        # Dictionary-like access mixin check
        self.assertEqual(record["eld_registration_id"], "ELDREG123")
        self.assertEqual(record.get("driver_username"), "johndoe")

    def test_user_list_parser_typed(self):
        row = ["User List", "johndoe", "Doe", "John", "CA", "DL98765", "97"]
        parser = UserListParser()
        record = parser.parse(row)
        self.assertIsNotNone(record)
        self.assertEqual(record.username, "johndoe")
        self.assertEqual(record.last_name, "Doe")
        self.assertEqual(record.first_name, "John")
        self.assertEqual(record.license_state, "CA")
        self.assertEqual(record.license_number, "DL98765")

    def test_cmv_parser_typed(self):
        row = ["Commercial Motor Vehicle (CMV) List", "UNIT01", "VIN12345678901234", "CA", "PLATE99", "13"]
        parser = CMVParser()
        record = parser.parse(row)
        self.assertIsNotNone(record)
        self.assertEqual(record.power_unit_number, "UNIT01")
        self.assertEqual(record.vin, "VIN12345678901234")
        self.assertEqual(record.license_plate_state, "CA")
        self.assertEqual(record.license_plate, "PLATE99")

    def test_event_parser_typed(self):
        row = ["ELD Event List", "1", "1", "1", "1", "1", "061026", "080000", "100.5", "1000", "Los Angeles CA", "34.0522", "-118.2437", "UNIT01", "VIN12345678901234", "BF"]
        parser = EventParser()
        record = parser.parse(row)
        self.assertIsNotNone(record)
        self.assertEqual(record.sequence_id, 1)
        self.assertEqual(record.record_status, 1)
        self.assertEqual(record.record_origin, 1)
        self.assertEqual(record.event_type, 1)
        self.assertEqual(record.event_code, 1)
        self.assertEqual(record.accumulated_engine_hours, Decimal("100.5"))
        self.assertEqual(record.elapsed_miles, 1000)
        self.assertEqual(record.location_desc, "Los Angeles CA")
        self.assertEqual(record.latitude, Decimal("34.0522"))
        self.assertEqual(record.longitude, Decimal("-118.2437"))
        self.assertEqual(record.cmv_id, "UNIT01")
        self.assertEqual(record.cmv_vin, "VIN12345678901234")

class RestructuredChecksumTests(TestCase):
    
    def test_char_to_dec(self):
        self.assertEqual(fmcsa_char_to_dec("0"), 0)
        self.assertEqual(fmcsa_char_to_dec("A"), 17)
        self.assertEqual(fmcsa_char_to_dec("j"), 58)
        self.assertEqual(fmcsa_char_to_dec(","), 0)

    def test_rotate_left(self):
        self.assertEqual(rotate_left_3(0x0F), 0x78)

    def test_line_checksum(self):
        line = "User List,johndoe,Doe,John,CA,DL98765,97"
        chk = calculate_line_checksum(line)
        self.assertEqual(chk, "97")

    def test_event_checksum(self):
        chk = calculate_event_checksum(
            event_type="1",
            event_code="1",
            event_date="061026",
            event_time="080000",
            vehicle_miles="1000",
            engine_hours="100.5",
            latitude="34.0522",
            longitude="-118.2437",
            cmv_number="UNIT01",
            username="johndoe"
        )
        self.assertEqual(len(chk), 2)

    def test_verify_file_checksum_valid(self):
        file_content = (
            "ELD File Header,ELDREG123,Doe,John,johndoe,Smith,Jane,janesmith,1234567,Test Carrier Inc,7,0,SHIP987,0,F7\n"
            "User List,johndoe,Doe,John,CA,DL98765,97\n"
            "Commercial Motor Vehicle (CMV) List,UNIT01,VIN12345678901234,CA,PLATE99,13\n"
            "End of File:\n"
            "9E91"
        )
        res = verify_file_checksum(file_content)
        self.assertTrue(res["is_valid"])

class RestructuredRulesTests(TestCase):
    
    def test_hos_11_hour_driving(self):
        base_time = datetime(2026, 6, 10, 8, 0, 0)
        events = [
            {"event_code": 4, "event_date_time": base_time},
            {"event_code": 3, "event_date_time": base_time + timedelta(minutes=10)},
            {"event_code": 4, "event_date_time": base_time + timedelta(hours=12, minutes=10)}
        ]
        violations = analyze_hos_rules(events)
        self.assertTrue(any(v["violation_type"] == "11_hour_driving" for v in violations))

class RestructuredIntegrationTests(TestCase):
    
    def setUp(self):
        self.company = Company.objects.create(
            company_name="Restructured Carrier",
            company_email="rest@carrier.com",
            location="Dallas TX",
            type="IT",
            us_dot_number="1234567"
        )
        self.driver = User.objects.create_user(
            username="test_driver",
            email="test@driver.com",
            password="secure_password"
        )
        self.cmv = CMV.objects.create(
            company=self.company,
            vin="VIN12345678901234",
            license_plate="PLT99",
            power_unit_number="UNIT01"
        )
        
        self.mock_csv_content = (
            "ELD File Header,ELDREG123,Doe,John,johndoe,Smith,Jane,janesmith,1234567,Test Carrier Inc,7,0,SHIP987,0,F7\n"
            "User List,johndoe,Doe,John,CA,DL98765,97\n"
            "Commercial Motor Vehicle (CMV) List,UNIT01,VIN12345678901234,CA,PLATE99,13\n"
            "ELD Event List,1,1,1,1,1,061026,080000,100.5,1000,Los Angeles CA,34.0522,-118.2437,UNIT01,VIN12345678901234,A0\n"
            "ELD Event List,2,1,1,1,3,061026,093000,102.0,1080,Barstow CA,34.8958,-117.0173,UNIT01,VIN12345678901234,A5\n"
            "End of File:\n"
            "9E81"  # Correct checksum for this exact set of lines
        )

    def test_api_upload_writes_validation_tables(self):
        factory = APIRequestFactory()
        file_data = io.BytesIO(self.mock_csv_content.encode('utf-8'))
        file_data.name = 'restructured_eld.csv'
        
        request = factory.post(
            '/api/v1/eld/upload/',
            {'file': file_data},
            format='multipart'
        )
        force_authenticate(request, user=self.driver)
        
        view = ELDFileViewSet.as_view({'post': 'upload_eld'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("job_status", response.data)
        
        # Verify db models
        eld_file = ELDFile.objects.filter(filename='restructured_eld.csv').first()
        self.assertIsNotNone(eld_file)
        self.assertIn(eld_file.status, ['pending', 'completed'])
        
        val_run = ValidationRun.objects.filter(eld_file=eld_file).first()
        self.assertIsNotNone(val_run)
        self.assertEqual(val_run.status, 'completed')
        
        checksum_results = ChecksumResult.objects.filter(validation_run=val_run)
        self.assertTrue(checksum_results.filter(entity_type='file').exists())
        
        # Verify RuleValidationResult records were written to MySQL database
        rule_results = RuleValidationResult.objects.filter(validation_run=val_run)
        self.assertTrue(rule_results.exists())
        # The test payload has valid data, so the rules should pass
        self.assertTrue(rule_results.filter(status='PASS').exists())

class RestructuredValidationAgentTests(TestCase):

    def test_header_validation_agent(self):
        agent = HeaderValidationAgent()
        
        # Valid header
        valid_header = {
            "eld_registration_id": "REG1",
            "carrier_usdot": "1234567",
            "driver_username": "driver1",
            "driver_first_name": "John",
            "driver_last_name": "Doe",
            "multi_day_basis": 7,
            "start_hour": 0
        }
        results = agent.validate(valid_header)
        for r in results:
            self.assertEqual(r["status"], "PASS", f"Failed rule: {r['rule_id']}")

        # Invalid header
        invalid_header = {
            "eld_registration_id": "RE", # too short
            "carrier_usdot": "abc", # non-numeric
            "driver_username": "",
            "driver_first_name": "John",
            "driver_last_name": "",
            "multi_day_basis": 10, # invalid
            "start_hour": 25 # invalid
        }
        results = agent.validate(invalid_header)
        fails = [r["rule_id"] for r in results if r["status"] == "FAIL"]
        self.assertIn("RULE_HEADER_REG_ID", fails)
        self.assertIn("RULE_HEADER_USDOT", fails)
        self.assertIn("RULE_HEADER_DRIVER_USERNAME", fails)
        self.assertIn("RULE_HEADER_DRIVER_NAME", fails)
        self.assertIn("RULE_HEADER_MULTI_DAY", fails)
        self.assertIn("RULE_HEADER_START_HOUR", fails)

    def test_user_validation_agent(self):
        agent = UserValidationAgent()
        
        valid_users = [
            {"username": "driver1", "license_state": "CA", "license_number": "LIC123"}
        ]
        results = agent.validate(valid_users)
        for r in results:
            self.assertEqual(r["status"], "PASS")

        invalid_users = [
            {"username": "", "license_state": "CAL", "license_number": ""}
        ]
        results = agent.validate(invalid_users)
        fails = [r["rule_id"] for r in results if r["status"] == "FAIL"]
        self.assertTrue(any("RULE_USER_USERNAME" in f for f in fails))
        self.assertTrue(any("RULE_USER_LICENSE_STATE" in f for f in fails))
        self.assertTrue(any("RULE_USER_LICENSE_NUMBER" in f for f in fails))

    def test_cmv_validation_agent(self):
        agent = CMVValidationAgent()
        
        valid_cmvs = [
            {"vin": "V1N12345678901234", "license_plate_state": "TX", "license_plate": "PLT123", "power_unit_number": "UNIT1"}
        ]
        results = agent.validate(valid_cmvs)
        for r in results:
            self.assertEqual(r["status"], "PASS")

        invalid_cmvs = [
            {"vin": "VIN123", "license_plate_state": "TEX", "license_plate": "", "power_unit_number": ""}
        ]
        results = agent.validate(invalid_cmvs)
        fails = [r["rule_id"] for r in results if r["status"] == "FAIL"]
        self.assertTrue(any("RULE_CMV_VIN" in f for f in fails))
        self.assertTrue(any("RULE_CMV_PLATE_STATE" in f for f in fails))
        self.assertTrue(any("RULE_CMV_PLATE" in f for f in fails))
        self.assertTrue(any("RULE_CMV_UNIT_NUMBER" in f for f in fails))

    def test_event_validation_agent(self):
        agent = EventValidationAgent()
        
        valid_events = [{
            "sequence_id": 1,
            "record_status": 1,
            "record_origin": 1,
            "event_type": 1,
            "event_code": 1,
            "latitude": Decimal("34.05"),
            "longitude": Decimal("-118.24")
        }]
        results = agent.validate(valid_events)
        for r in results:
            self.assertEqual(r["status"], "PASS")

        invalid_events = [{
            "sequence_id": -1,
            "record_status": 3,
            "record_origin": 5,
            "event_type": 7,
            "event_code": 9,
            "latitude": Decimal("95.0"),
            "longitude": Decimal("-190.0")
        }]
        results = agent.validate(invalid_events)
        fails = [r["rule_id"] for r in results if r["status"] == "FAIL"]
        self.assertTrue(any("RULE_EVENT_SEQUENCE_ID" in f for f in fails))
        self.assertTrue(any("RULE_EVENT_RECORD_STATUS" in f for f in fails))
        self.assertTrue(any("RULE_EVENT_RECORD_ORIGIN" in f for f in fails))
        self.assertTrue(any("RULE_EVENT_TYPE" in f for f in fails))
        self.assertTrue(any("RULE_EVENT_CODE" in f for f in fails))
        self.assertTrue(any("RULE_EVENT_COORDINATES" in f for f in fails))

    def test_login_logout_validation_agent(self):
        agent = LoginLogoutValidationAgent()
        base_time = datetime(2026, 6, 10, 8, 0, 0)
        
        # Valid sequence: Alternating login and logout
        valid_seq = [
            {"event_type": 5, "event_code": 1, "event_date_time": base_time},
            {"event_type": 5, "event_code": 2, "event_date_time": base_time + timedelta(hours=4)},
            {"event_type": 5, "event_code": 1, "event_date_time": base_time + timedelta(hours=6)},
            {"event_type": 5, "event_code": 2, "event_date_time": base_time + timedelta(hours=10)}
        ]
        results = agent.validate(valid_seq)
        for r in results:
            self.assertEqual(r["status"], "PASS")

        # Invalid sequence: Consecutive logins
        invalid_seq = [
            {"event_type": 5, "event_code": 1, "event_date_time": base_time},
            {"event_type": 5, "event_code": 1, "event_date_time": base_time + timedelta(hours=4)}
        ]
        results = agent.validate(invalid_seq)
        fails = [r["rule_id"] for r in results if r["status"] == "FAIL"]
        self.assertIn("RULE_LOGIN_LOGOUT_SEQUENCE", fails)

    def test_engine_hours_validation_agent(self):
        agent = EngineHoursValidationAgent()
        base_time = datetime(2026, 6, 10, 8, 0, 0)
        
        # Valid monotonic engine hours
        valid_hours = [
            {"record_status": 1, "event_date_time": base_time, "accumulated_engine_hours": Decimal("100.0")},
            {"record_status": 1, "event_date_time": base_time + timedelta(hours=2), "accumulated_engine_hours": Decimal("101.5")}
        ]
        results = agent.validate(valid_hours)
        for r in results:
            self.assertEqual(r["status"], "PASS")

        # Invalid descending engine hours
        descending_hours = [
            {"record_status": 1, "event_date_time": base_time, "accumulated_engine_hours": Decimal("100.0")},
            {"record_status": 1, "event_date_time": base_time + timedelta(hours=2), "accumulated_engine_hours": Decimal("99.0")}
        ]
        results = agent.validate(descending_hours)
        fails = [r["rule_id"] for r in results if r["status"] == "FAIL"]
        self.assertIn("RULE_ENGINE_HOURS_MONOTONIC", fails)

        # Impossible engine hours rate (e.g. +200 hours over 1 hour)
        rate_hours = [
            {"record_status": 1, "event_date_time": base_time, "accumulated_engine_hours": Decimal("100.0")},
            {"record_status": 1, "event_date_time": base_time + timedelta(hours=1), "accumulated_engine_hours": Decimal("300.0")}
        ]
        results = agent.validate(rate_hours)
        fails = [r["rule_id"] for r in results if r["status"] == "FAIL"]
        self.assertIn("RULE_ENGINE_HOURS_RATE", fails)

    def test_odometer_validation_agent(self):
        agent = OdometerValidationAgent()
        base_time = datetime(2026, 6, 10, 8, 0, 0)
        
        # Valid odometer
        valid_odo = [
            {"record_status": 1, "event_date_time": base_time, "elapsed_miles": 1000},
            {"record_status": 1, "event_date_time": base_time + timedelta(hours=2), "elapsed_miles": 1100}
        ]
        results = agent.validate(valid_odo)
        for r in results:
            self.assertEqual(r["status"], "PASS")

        # Invalid descending odometer
        descending_odo = [
            {"record_status": 1, "event_date_time": base_time, "elapsed_miles": 1000},
            {"record_status": 1, "event_date_time": base_time + timedelta(hours=2), "elapsed_miles": 900}
        ]
        results = agent.validate(descending_odo)
        fails = [r["rule_id"] for r in results if r["status"] == "FAIL"]
        self.assertIn("RULE_ODOMETER_MONOTONIC", fails)

        # Impossible speed check (e.g. 150 miles over 1 hour)
        speed_odo = [
            {"record_status": 1, "event_date_time": base_time, "elapsed_miles": 1000},
            {"record_status": 1, "event_date_time": base_time + timedelta(hours=1), "elapsed_miles": 1150}
        ]
        results = agent.validate(speed_odo)
        fails = [r["rule_id"] for r in results if r["status"] == "FAIL"]
        self.assertIn("RULE_ODOMETER_SPEED", fails)

class DiagnosticAgentTests(TestCase):
    def test_missing_data_diagnostic(self):
        agent = DiagnosticAgent()
        base_time = datetime(2026, 6, 10, 8, 0, 0)
        events = [
            {"record_status": 1, "event_date_time": base_time, "latitude": "", "longitude": ""}
        ]
        diagnostics = agent.detect(events)
        self.assertTrue(any(d["diagnostic_type"] == "Missing Data" for d in diagnostics))

    def test_engine_sync_diagnostic(self):
        agent = DiagnosticAgent()
        base_time = datetime(2026, 6, 10, 8, 0, 0)
        events = [
            {"record_status": 1, "event_date_time": base_time, "elapsed_miles": 1000, "accumulated_engine_hours": 100.0},
            {"record_status": 1, "event_date_time": base_time + timedelta(hours=2), "elapsed_miles": 1060, "accumulated_engine_hours": 100.0}
        ]
        diagnostics = agent.detect(events)
        self.assertTrue(any(d["diagnostic_type"] == "Engine Sync" for d in diagnostics))

    def test_timing_diagnostic(self):
        agent = DiagnosticAgent()
        base_time = datetime(2026, 6, 10, 8, 0, 0)
        events = [
            {"record_status": 1, "event_date_time": base_time},
            {"record_status": 1, "event_date_time": base_time},
            {"record_status": 1, "event_date_time": base_time},
            {"record_status": 1, "event_date_time": base_time}
        ]
        diagnostics = agent.detect(events)
        self.assertTrue(any(d["diagnostic_type"] == "Timing" for d in diagnostics))

    def test_position_diagnostic(self):
        agent = DiagnosticAgent()
        base_time = datetime(2026, 6, 10, 8, 0, 0)
        events = [
            {"record_status": 1, "event_date_time": base_time, "elapsed_miles": 1000, "latitude": Decimal("34.05"), "longitude": Decimal("-118.24")},
            {"record_status": 1, "event_date_time": base_time + timedelta(hours=1), "elapsed_miles": 1200, "latitude": Decimal("35.05"), "longitude": Decimal("-119.24")}
        ]
        diagnostics = agent.detect(events)
        self.assertTrue(any(d["diagnostic_type"] == "Position" for d in diagnostics))

class MalfunctionAgentTests(TestCase):
    def test_power_malfunction(self):
        agent = MalfunctionAgent()
        diagnostic_events = [
            {"diagnostic_type": "Power Diagnostic"},
            {"diagnostic_type": "Power Diagnostic"},
            {"diagnostic_type": "Power Diagnostic"},
            {"diagnostic_type": "Power Diagnostic"}
        ]
        malfunctions = agent.detect([], diagnostic_events)
        self.assertTrue(any(m["malfunction_type"] == "Power" for m in malfunctions))

    def test_escalation_logic(self):
        agent = MalfunctionAgent()
        diagnostic_events = [
            {"diagnostic_type": "Missing Data"},
            {"diagnostic_type": "Missing Data"},
            {"diagnostic_type": "Missing Data"},
            {"diagnostic_type": "Missing Data"},
            {"diagnostic_type": "Missing Data"},
            {"diagnostic_type": "Missing Data"} # 6 occurrences
        ]
        malfunctions = agent.detect([], diagnostic_events)
        self.assertTrue(any(m["malfunction_type"] == "Position" and m["escalated_from_diagnostic"] for m in malfunctions))

class InvestigationAgentTests(TestCase):
    def test_investigation_sensor_disconnect(self):
        agent = InvestigationAgent()
        diagnostics = [{"diagnostic_type": "Missing Data"}]
        malfunctions = [{"malfunction_type": "Position"}]
        events = [
            {"sequence_id": "1", "record_status": "1", "latitude": "", "longitude": ""},
            {"sequence_id": "2", "record_status": "1", "latitude": "40.0", "longitude": "-74.0"}
        ]
        results = agent.investigate([], diagnostics, malfunctions, events)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["root_cause"], "Persistent ELD sensor failure or GPS disconnect.")
        self.assertIn("1", results[0]["affected_records"])
        self.assertNotIn("2", results[0]["affected_records"])

