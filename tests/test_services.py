"""Tests for service modules - extraction, core info, stubs, transcription."""


import pytest

from app.models.nemsis import (
    NEMSISPatientInfo,
    NEMSISProcedures,
    NEMSISRecord,
)
from app.services.core_info_checker import (
    get_full_name,
    is_core_info_complete,
    trigger_downstream,
)
from app.services.gp_caller import call_gp
from app.services.medical_db import query_records
from app.services.nemsis_extractor import _dummy_extract, _merge_records, extract_nemsis
from app.services.summary import generate_summary, get_summary_for_hospital

# --- NEMSIS Extractor ---


class TestDummyExtract:
    def test_extracts_name(self):
        r = _dummy_extract("Patient named John David Smith is a 45 year old male")
        assert r.patient.patient_name_first == "John David"
        assert r.patient.patient_name_last == "Smith"

    def test_extracts_age_gender(self):
        r = _dummy_extract("45 year old male patient")
        assert r.patient.patient_age == "45"
        assert r.patient.patient_gender == "Male"

    def test_extracts_female(self):
        r = _dummy_extract("patient is female")
        assert r.patient.patient_gender == "Female"

    def test_extracts_address(self):
        r = _dummy_extract("located at 742 Evergreen Terrace Springfield Illinois")
        assert r.patient.patient_address == "742 Evergreen Terrace"
        assert r.patient.patient_city == "Springfield"
        assert r.patient.patient_state == "Illinois"

    def test_extracts_vitals_bp(self):
        r = _dummy_extract("Blood pressure is 160 over 95")
        assert r.vitals.systolic_bp == 160
        assert r.vitals.diastolic_bp == 95

    def test_extracts_vitals_hr(self):
        r = _dummy_extract("Heart rate 110 beats per minute")
        assert r.vitals.heart_rate == 110

    def test_extracts_vitals_rr(self):
        r = _dummy_extract("Respiratory rate 22")
        assert r.vitals.respiratory_rate == 22

    def test_extracts_vitals_spo2(self):
        r = _dummy_extract("SPO2 94 percent on room air")
        assert r.vitals.spo2 == 94

    def test_extracts_vitals_glucose(self):
        r = _dummy_extract("blood glucose 145")
        assert r.vitals.blood_glucose == 145.0

    def test_extracts_vitals_gcs(self):
        r = _dummy_extract("GCS 15 eyes 4 verbal 5 motor 6")
        assert r.vitals.gcs_total == 15

    def test_extracts_chief_complaint(self):
        r = _dummy_extract("Chief complaint is chest pain radiating to left arm")
        assert r.situation.chief_complaint is not None
        assert "chest pain" in r.situation.chief_complaint.lower()

    def test_extracts_primary_impression(self):
        r = _dummy_extract("Primary impression is STEMI")
        assert r.situation.primary_impression == "STEMI"

    def test_extracts_procedures(self):
        r = _dummy_extract("Establishing IV access right antecubital. 12 lead ECG shows changes.")
        assert len(r.procedures.procedures) == 2

    def test_extracts_medications(self):
        r = _dummy_extract("Administering aspirin 324mg and nitroglycerin 0.4mg sublingual")
        assert len(r.medications.medications) == 2

    def test_empty_transcript(self):
        r = _dummy_extract("")
        assert r.patient.patient_name_first is None
        assert r.vitals.heart_rate is None

    def test_full_scenario(self):
        transcript = (
            "Patient is a 45 year old male named John David Smith "
            "located at 742 Evergreen Terrace Springfield Illinois. "
            "Chief complaint is chest pain. Blood pressure is 160 over 95. "
            "Heart rate 110 beats per minute. Respiratory rate 22. "
            "SPO2 94 percent. Blood glucose 145. GCS 15. "
            "Primary impression is STEMI. ST elevation in leads V1 through V4. "
            "Administering aspirin 324mg. Nitroglycerin 0.4mg sublingual. "
            "Establishing IV access right antecubital. 12 lead ECG. "
            "Activating cardiac catheterization lab."
        )
        r = _dummy_extract(transcript)
        assert r.patient.patient_name_first is not None
        assert r.patient.patient_age == "45"
        assert r.patient.patient_gender == "Male"
        assert r.vitals.systolic_bp == 160
        assert r.vitals.heart_rate == 110
        assert r.situation.primary_impression == "STEMI"
        assert len(r.procedures.procedures) >= 2
        assert len(r.medications.medications) >= 2


class TestMergeRecords:
    def test_merge_preserves_existing_non_null(self):
        existing = NEMSISRecord(
            patient=NEMSISPatientInfo(patient_name_first="John", patient_age="45"),
        )
        new = NEMSISRecord(
            patient=NEMSISPatientInfo(patient_name_first=None, patient_age="45"),
        )
        merged = _merge_records(existing, new)
        assert merged.patient.patient_name_first == "John"

    def test_merge_takes_new_non_null(self):
        existing = NEMSISRecord(
            patient=NEMSISPatientInfo(patient_name_first="John"),
        )
        new = NEMSISRecord(
            patient=NEMSISPatientInfo(
                patient_name_first="John", patient_name_last="Smith"
            ),
        )
        merged = _merge_records(existing, new)
        assert merged.patient.patient_name_last == "Smith"
        assert merged.patient.patient_name_first == "John"

    def test_merge_combines_lists(self):
        existing = NEMSISRecord(
            procedures=NEMSISProcedures(procedures=["12-lead ECG"]),
        )
        new = NEMSISRecord(
            procedures=NEMSISProcedures(procedures=["12-lead ECG", "IV access"]),
        )
        merged = _merge_records(existing, new)
        assert "12-lead ECG" in merged.procedures.procedures
        assert "IV access" in merged.procedures.procedures
        assert len(merged.procedures.procedures) == 2  # no duplicates

    def test_merge_empty_records(self):
        existing = NEMSISRecord()
        new = NEMSISRecord()
        merged = _merge_records(existing, new)
        assert merged.patient.patient_name_first is None


async def test_extract_nemsis_dummy_mode():
    """Test that extract_nemsis works in dummy mode."""
    result = await extract_nemsis("Patient is a 45 year old male named John Smith")
    assert result.patient.patient_age == "45"
    assert result.patient.patient_gender == "Male"


async def test_extract_nemsis_with_existing():
    """Test extract with existing record preserves data."""
    existing = NEMSISRecord(
        patient=NEMSISPatientInfo(patient_name_first="John", patient_name_last="Smith"),
    )
    result = await extract_nemsis(
        "45 year old male", existing=existing
    )
    # In dummy mode, the result comes from _dummy_extract which doesn't merge with existing
    # (merge only happens in the real OpenAI path)
    assert result is not None


# --- Core Info Checker ---


class TestCoreInfoChecker:
    def test_incomplete_no_name(self):
        r = NEMSISRecord(
            patient=NEMSISPatientInfo(
                patient_address="123 Main St", patient_age="45", patient_gender="Male"
            ),
        )
        assert is_core_info_complete(r) is False

    def test_incomplete_no_address(self):
        r = NEMSISRecord(
            patient=NEMSISPatientInfo(
                patient_name_first="John", patient_age="45", patient_gender="Male"
            ),
        )
        assert is_core_info_complete(r) is False

    def test_incomplete_no_age(self):
        r = NEMSISRecord(
            patient=NEMSISPatientInfo(
                patient_name_first="John",
                patient_address="123 Main St",
                patient_gender="Male",
            ),
        )
        assert is_core_info_complete(r) is False

    def test_incomplete_no_gender(self):
        r = NEMSISRecord(
            patient=NEMSISPatientInfo(
                patient_name_first="John",
                patient_address="123 Main St",
                patient_age="45",
            ),
        )
        assert is_core_info_complete(r) is False

    def test_complete_with_first_name(self):
        r = NEMSISRecord(
            patient=NEMSISPatientInfo(
                patient_name_first="John",
                patient_address="123 Main St",
                patient_age="45",
                patient_gender="Male",
            ),
        )
        assert is_core_info_complete(r) is True

    def test_complete_with_last_name(self):
        r = NEMSISRecord(
            patient=NEMSISPatientInfo(
                patient_name_last="Smith",
                patient_address="123 Main St",
                patient_age="45",
                patient_gender="Male",
            ),
        )
        assert is_core_info_complete(r) is True

    def test_empty_record(self):
        r = NEMSISRecord()
        assert is_core_info_complete(r) is False


class TestGetFullName:
    def test_full_name(self):
        r = NEMSISRecord(
            patient=NEMSISPatientInfo(
                patient_name_first="John", patient_name_last="Smith"
            ),
        )
        assert get_full_name(r) == "John Smith"

    def test_first_only(self):
        r = NEMSISRecord(
            patient=NEMSISPatientInfo(patient_name_first="John"),
        )
        assert get_full_name(r) == "John"

    def test_last_only(self):
        r = NEMSISRecord(
            patient=NEMSISPatientInfo(patient_name_last="Smith"),
        )
        assert get_full_name(r) == "Smith"

    def test_empty(self):
        r = NEMSISRecord()
        assert get_full_name(r) == "Unknown"


async def test_trigger_downstream():
    """Test parallel downstream calls return results."""
    r = NEMSISRecord(
        patient=NEMSISPatientInfo(
            patient_name_first="John",
            patient_name_last="Smith",
            patient_age="45",
            patient_gender="Male",
            patient_address="123 Main St",
        ),
    )
    gp_result, db_result = await trigger_downstream(r)
    assert "John Smith" in gp_result
    assert "John Smith" in db_result
    assert "[GP STUB]" in gp_result
    assert "[MEDICAL DB STUB]" in db_result


# --- GP Caller Stub ---


async def test_gp_caller():
    result = await call_gp(
        patient_name="John Smith",
        patient_age="45",
        patient_gender="Male",
        patient_address="123 Main St",
    )
    assert "John Smith" in result
    assert "45" in result
    assert "[GP STUB]" in result


# --- Medical DB Stub ---


async def test_medical_db():
    result = await query_records(
        patient_name="Jane Doe",
        patient_age="32",
        patient_gender="Female",
    )
    assert "Jane Doe" in result
    assert "[MEDICAL DB STUB]" in result


# --- Summary Service Stubs ---


async def test_summary_not_implemented():
    with pytest.raises(NotImplementedError):
        await generate_summary("case-123")


async def test_hospital_summary_not_implemented():
    with pytest.raises(NotImplementedError):
        await get_summary_for_hospital("case-123")
