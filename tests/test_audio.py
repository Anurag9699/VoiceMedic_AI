import io
import sys
import wave
from pathlib import Path
from unittest.mock import patch

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient
from main import app
from audio.processor import validate_audio_content_type
from audio.parser import parse_medical_report, _parse_with_regex
from report.generator import generate_pdf_report, save_report_to_db, get_all_reports

# ---------------------------------------------------------------------------
# Test Data & Fixtures
# ---------------------------------------------------------------------------

FAKE_MEDICAL_TRANSCRIPT = {
    "text": "Patient Rahul, 45 year old male, complains of severe chest pain and fever for 3 days. BP is 130 over 85, pulse 78. Diagnosis: Acute Angina. Prescribe Tablet Aspirin 75mg daily.",
    "language": "en",
    "segments": [
        {"start": 0.0, "end": 4.5, "text": "Patient Rahul, 45 year old male, complains of severe chest pain and fever for 3 days."}
    ],
}

FAKE_VERIFICATION_SUCCESS = {
    "verified": True,
    "confidence_score": 0.88,
    "threshold_used": 0.75,
    "user_id": "default_doctor",
    "method": "speechbrain_ecapa_tdnn (embedding-averaged)",
    "message": "Voice match successful.",
}


def make_wav_bytes(duration_ms: int = 1600, sample_rate: int = 16000) -> bytes:
    """Generate a minimal valid mono WAV file in memory for testing."""
    num_samples = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    buf.seek(0)
    return buf.read()


@pytest.fixture()
def client():
    """Return a TestClient with speech models patched to avoid heavyweight model loading."""
    with patch("main.transcribe_audio", return_value=FAKE_MEDICAL_TRANSCRIPT), \
         patch("main.verify_speaker", return_value=FAKE_VERIFICATION_SUCCESS), \
         patch("main.enroll_speaker", return_value={"status": "success", "enrolled": True}), \
         patch("main.reset_enrollment", return_value=True):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# 1. Health Check & Doctor Info Tests
# ---------------------------------------------------------------------------

def test_health_endpoint(client):
    """GET /health returns 200 with status ok and VoiceMedic AI."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["system"] == "VoiceMedic AI"


def test_doctor_info_endpoint(client):
    """GET /api/doctor/info returns enrollment status and report count."""
    response = client.get("/api/doctor/info")
    assert response.status_code == 200
    data = response.json()
    assert "voice_enrolled" in data
    assert "total_reports" in data


def test_doctor_reset_voice_endpoint(client):
    """POST /api/doctor/reset-voice resets enrollment."""
    response = client.post("/api/doctor/reset-voice")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "cleared" in data


# ---------------------------------------------------------------------------
# 2. Doctor Voice Enrollment Tests
# ---------------------------------------------------------------------------

def test_doctor_enroll_valid_audio(client):
    """POST /api/audio/enroll with valid WAV should succeed."""
    wav_data = make_wav_bytes(duration_ms=2000)
    response = client.post(
        "/api/audio/enroll",
        files={"file": ("doctor_sample.wav", wav_data, "audio/wav")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["voice_enrolled"] is True


def test_doctor_enroll_missing_file(client):
    """POST /api/audio/enroll without file should return 422."""
    response = client.post("/api/audio/enroll")
    assert response.status_code == 422


def test_doctor_enroll_invalid_content_type(client):
    """POST /api/audio/enroll with invalid content type returns 415."""
    response = client.post(
        "/api/audio/enroll",
        files={"file": ("text.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 415
    assert "Unsupported media type" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Medical Report Generation Tests
# ---------------------------------------------------------------------------

def test_generate_report_valid_audio(client):
    """POST /api/report/generate should process voice and generate medical report + PDF."""
    wav_data = make_wav_bytes(duration_ms=2000)
    response = client.post(
        "/api/report/generate",
        files={"file": ("consultation.wav", wav_data, "audio/wav")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "report_id" in data
    assert "transcript" in data
    assert "medical_report" in data
    assert data["speaker_verification"]["verified"] is True
    assert data["pdf_url"] is not None


def test_generate_report_missing_file(client):
    """POST /api/report/generate without file returns 422."""
    response = client.post("/api/report/generate")
    assert response.status_code == 422


def test_generate_report_invalid_content_type(client):
    """POST /api/report/generate with text file returns 415."""
    response = client.post(
        "/api/report/generate",
        files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
    )
    assert response.status_code == 415


# ---------------------------------------------------------------------------
# 4. Report PDF Download & History Tests
# ---------------------------------------------------------------------------

def test_download_report_not_found(client):
    """GET /api/report/download/{non_existent_id} returns 404."""
    response = client.get("/api/report/download/non-existent-report-id-12345")
    assert response.status_code == 404
    assert response.json()["detail"] == "Report not found."


def test_report_history_endpoint(client):
    """GET /api/reports/history returns list of previous reports."""
    response = client.get("/api/reports/history")
    assert response.status_code == 200
    data = response.json()
    assert "reports" in data
    assert "total" in data
    assert isinstance(data["reports"], list)


# ---------------------------------------------------------------------------
# 5. Unit Tests: Audio Processor, Parser, & PDF Generator
# ---------------------------------------------------------------------------

def test_validate_audio_content_type():
    """Verify accepted and rejected audio MIME types."""
    assert validate_audio_content_type("audio/wav") is True
    assert validate_audio_content_type("audio/webm") is True
    assert validate_audio_content_type("audio/webm;codecs=opus") is True
    assert validate_audio_content_type("audio/ogg") is True
    assert validate_audio_content_type("application/json") is False
    assert validate_audio_content_type("text/plain") is False


def test_medical_parser_regex_fallback():
    """Verify regex fallback parser extracts basic patient info."""
    transcript = "Patient is a 55 year old male complaining of severe fever."
    data = _parse_with_regex(transcript)
    assert data["age"] == 55
    assert data["gender"] == "Male"
    assert data["is_valid"] is True


def test_pdf_report_generation_and_db():
    """Verify PDF creation and database insertion for reports."""
    sample_data = {
        "patient_name": "Test Patient",
        "age": 30,
        "gender": "Female",
        "symptoms": ["Headache", "Fatigue"],
        "duration": "2 days",
        "vitals": {"blood_pressure": "120/80 mmHg", "temperature": "98.6 F"},
        "suggested_diagnosis": "Mild Migraine",
        "prescription": "Tab Paracetamol 500mg SOS",
        "is_valid": True,
    }
    import uuid
    report_id = f"test-report-{uuid.uuid4().hex[:8]}"
    pdf_path = generate_pdf_report(sample_data, report_id, doctor_name="Dr. Test")
    assert Path(pdf_path).exists()
    assert Path(pdf_path).stat().st_size > 0

    # Test DB storage & retrieval
    save_report_to_db(report_id, "test_doc", sample_data, pdf_path)
    reports = get_all_reports("test_doc")
    assert len(reports) >= 1
    matching = [r for r in reports if r["id"] == report_id]
    assert len(matching) == 1
    assert matching[0]["patient_name"] == "Test Patient"
    assert "Headache" in matching[0]["symptoms"]
