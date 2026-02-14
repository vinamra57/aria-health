"""Tests for Pydantic models - NEMSIS, case, and transcript schemas."""

from app.models.case import CaseCreate, CaseListItem, CaseResponse, CaseStatusUpdate
from app.models.nemsis import (
    NEMSISMedications,
    NEMSISPatientInfo,
    NEMSISProcedures,
    NEMSISRecord,
    NEMSISSituation,
    NEMSISVitals,
)
from app.models.transcript import TranscriptResponse, TranscriptSegment

# --- NEMSIS Models ---


class TestNEMSISPatientInfo:
    def test_defaults_all_none(self):
        p = NEMSISPatientInfo()
        assert p.patient_name_first is None
        assert p.patient_name_last is None
        assert p.patient_address is None
        assert p.patient_age is None
        assert p.patient_gender is None

    def test_set_fields(self):
        p = NEMSISPatientInfo(
            patient_name_first="John",
            patient_name_last="Smith",
            patient_age="45",
            patient_gender="Male",
            patient_address="742 Evergreen Terrace",
            patient_city="Springfield",
            patient_state="Illinois",
            patient_zip="62704",
        )
        assert p.patient_name_first == "John"
        assert p.patient_city == "Springfield"

    def test_serialization_roundtrip(self):
        p = NEMSISPatientInfo(patient_name_first="Jane", patient_age="30")
        json_str = p.model_dump_json()
        restored = NEMSISPatientInfo.model_validate_json(json_str)
        assert restored.patient_name_first == "Jane"
        assert restored.patient_age == "30"
        assert restored.patient_name_last is None


class TestNEMSISVitals:
    def test_defaults(self):
        v = NEMSISVitals()
        assert v.systolic_bp is None
        assert v.heart_rate is None
        assert v.spo2 is None

    def test_full_vitals(self):
        v = NEMSISVitals(
            systolic_bp=120,
            diastolic_bp=80,
            heart_rate=72,
            respiratory_rate=16,
            spo2=98,
            blood_glucose=100.0,
            gcs_total=15,
        )
        assert v.systolic_bp == 120
        assert v.gcs_total == 15


class TestNEMSISRecord:
    def test_default_record(self):
        r = NEMSISRecord()
        assert r.patient is not None
        assert r.vitals is not None
        assert r.situation is not None
        assert r.procedures is not None
        assert r.medications is not None

    def test_independent_defaults(self):
        """Verify each NEMSISRecord gets independent sub-model instances."""
        r1 = NEMSISRecord()
        r2 = NEMSISRecord()
        r1.patient.patient_name_first = "Alice"
        assert r2.patient.patient_name_first is None

    def test_full_record_serialization(self):
        r = NEMSISRecord(
            patient=NEMSISPatientInfo(patient_name_first="Bob", patient_age="55"),
            vitals=NEMSISVitals(heart_rate=80, spo2=96),
            situation=NEMSISSituation(chief_complaint="Chest pain"),
            procedures=NEMSISProcedures(procedures=["12-lead ECG"]),
            medications=NEMSISMedications(medications=["Aspirin 324mg"]),
        )
        data = r.model_dump()
        assert data["patient"]["patient_name_first"] == "Bob"
        assert data["vitals"]["heart_rate"] == 80
        assert data["situation"]["chief_complaint"] == "Chest pain"
        assert "12-lead ECG" in data["procedures"]["procedures"]
        assert "Aspirin 324mg" in data["medications"]["medications"]

    def test_json_roundtrip(self):
        original = NEMSISRecord(
            patient=NEMSISPatientInfo(patient_name_first="Test"),
            vitals=NEMSISVitals(systolic_bp=140),
        )
        json_str = original.model_dump_json()
        restored = NEMSISRecord.model_validate_json(json_str)
        assert restored.patient.patient_name_first == "Test"
        assert restored.vitals.systolic_bp == 140

    def test_empty_lists_default(self):
        r = NEMSISRecord()
        assert r.procedures.procedures == []
        assert r.medications.medications == []


# --- Case Models ---


class TestCaseModels:
    def test_case_create_empty(self):
        c = CaseCreate()
        assert c is not None

    def test_case_status_update(self):
        u = CaseStatusUpdate(status="completed")
        assert u.status == "completed"

    def test_case_list_item(self):
        item = CaseListItem(
            id="abc-123",
            created_at="2026-01-01T00:00:00Z",
            status="active",
            core_info_complete=False,
        )
        assert item.patient_name is None
        assert item.chief_complaint is None

    def test_case_response(self):
        resp = CaseResponse(
            id="abc",
            created_at="2026-01-01T00:00:00Z",
            status="active",
            full_transcript="Hello",
            nemsis_data=NEMSISRecord(),
            core_info_complete=True,
        )
        assert resp.core_info_complete is True
        assert resp.nemsis_data.patient.patient_name_first is None


# --- Transcript Models ---


class TestTranscriptModels:
    def test_transcript_segment(self):
        seg = TranscriptSegment(
            case_id="case-1",
            segment_text="Patient is having chest pain",
            timestamp="2026-01-01T00:00:00Z",
            segment_type="committed",
        )
        assert seg.id is None
        assert seg.segment_type == "committed"

    def test_transcript_response(self):
        resp = TranscriptResponse(
            segments=[
                TranscriptSegment(
                    case_id="case-1",
                    segment_text="Test",
                    timestamp="2026-01-01T00:00:00Z",
                    segment_type="committed",
                )
            ],
            total=1,
        )
        assert resp.total == 1
        assert len(resp.segments) == 1
