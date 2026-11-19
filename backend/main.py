import os
import json
import uuid
import logging

from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from audio.processor import (
    convert_to_16k_mono_wav,
    save_upload_file,
    validate_audio_content_type,
)
from audio.transcriber import transcribe_audio
from audio.parser import parse_medical_report
from audio.speaker import verify_speaker, reset_enrollment, enroll_speaker, DEFAULT_THRESHOLD
from report.generator import generate_pdf_report, save_report_to_db, get_all_reports

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
RAW_AUDIO_DIR = BASE_DIR / "data" / "audio" / "raw"
WAV_AUDIO_DIR = BASE_DIR / "data" / "audio" / "wav_16k"

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

app = FastAPI(
    title="VoiceMedic AI — Medical Report Generator",
    description="Voice-powered medical report generation using Whisper ASR + ECAPA-TDNN + Gemini AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Supported language catalogue
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: list[dict] = [
    {"code": "auto", "display_name": "Auto-detect"},
    {"code": "en",   "display_name": "English"},
    {"code": "hi",   "display_name": "Hindi"},
    {"code": "mr",   "display_name": "Marathi"},
    {"code": "ta",   "display_name": "Tamil"},
    {"code": "te",   "display_name": "Telugu"},
    {"code": "gu",   "display_name": "Gujarati"},
    {"code": "kn",   "display_name": "Kannada"},
    {"code": "ml",   "display_name": "Malayalam"},
    {"code": "bn",   "display_name": "Bengali"},
    {"code": "pa",   "display_name": "Punjabi"},
    {"code": "ur",   "display_name": "Urdu"},
    {"code": "or",   "display_name": "Odia"},
]


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
def get_health():
    """Simple health-check endpoint."""
    return {"status": "ok", "system": "VoiceMedic AI"}


# ---------------------------------------------------------------------------
# Supported Languages
# ---------------------------------------------------------------------------

@app.get("/api/languages", tags=["System"])
def get_supported_languages():
    """
    Return the list of languages supported by the ASR transcription engine,
    including Indian regional languages and auto-detect.
    """
    return {
        "languages": SUPPORTED_LANGUAGES,
        "total": len(SUPPORTED_LANGUAGES),
    }


# ---------------------------------------------------------------------------
# Doctor Voice Enrollment
# ---------------------------------------------------------------------------

@app.post("/api/audio/enroll", tags=["Auth"])
async def enroll_voice(
    file: UploadFile = File(...),
    reset: bool = Form(False),
):
    """
    Enroll the doctor's voice as the biometric baseline.
    Only enrolled doctor can generate reports.
    """
    content_type = file.content_type or ""
    if not validate_audio_content_type(content_type):
        raise HTTPException(status_code=415, detail=f"Unsupported media type: '{content_type}'.")

    try:
        raw_path, size_bytes = await save_upload_file(file, RAW_AUDIO_DIR)
        wav_path, duration_seconds = convert_to_16k_mono_wav(raw_path, WAV_AUDIO_DIR)
        res = enroll_speaker(str(wav_path), user_id="default_doctor", reset=reset)
        return {
            "status": "success",
            "message": "Doctor voice profile enrolled successfully!",
            "duration_seconds": duration_seconds,
            "voice_enrolled": True,
            **res
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Generate Medical Report from Voice
# ---------------------------------------------------------------------------

@app.post("/api/report/generate", tags=["Report"])
async def generate_report(
    file: UploadFile = File(...),
    language: str = Form("auto"),
):
    """
    Main endpoint: Doctor speaks patient details → AI generates structured medical report + PDF.

    Pipeline:
    1. Validate & save audio
    2. Convert to 16kHz WAV (ffmpeg)
    3. Verify doctor's voice (ECAPA-TDNN)
    4. Transcribe speech to text (Whisper)
    5. Extract medical data (Gemini LLM)
    6. Generate PDF report (reportlab)
    7. Save to database (SQLite)
    8. Return report data + PDF download link

    Form fields:
        file     – audio file (any format supported by ffmpeg)
        language – BCP-47 language code (e.g. 'hi', 'ta') or 'auto' for
                   automatic language detection (default: 'auto')
    """
    content_type = file.content_type or ""
    if not validate_audio_content_type(content_type):
        raise HTTPException(status_code=415, detail=f"Unsupported media type: '{content_type}'.")

    # Step 1 & 2: Save & convert audio
    try:
        raw_path, size_bytes = await save_upload_file(file, RAW_AUDIO_DIR)
        wav_path, duration_seconds = convert_to_16k_mono_wav(raw_path, WAV_AUDIO_DIR)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Step 3: Verify doctor's voice
    speaker_data = verify_speaker(str(wav_path), user_id="default_doctor")

    # Step 4: Transcribe speech to text
    # Map "auto" sentinel to None so the transcriber triggers language auto-detection
    whisper_language: str | None = None if language == "auto" else language
    try:
        transcription = transcribe_audio(
            wav_path,
            model_name=WHISPER_MODEL,
            language=whisper_language,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {e}")

    transcript_text = transcription["text"].strip()
    english_translation = transcription.get("english_translation", transcript_text).strip()
    detected_lang = transcription.get("language", "en")

    # Step 5: Extract medical data using Gemini LLM
    # If spoken in a regional language, provide both native transcript and English translation for clinical precision
    parse_input = (
        f"{transcript_text}\n(English Translation: {english_translation})"
        if english_translation and english_translation != transcript_text
        else transcript_text
    )
    medical_data = parse_medical_report(parse_input, language=detected_lang)
    medical_data["transcript"] = transcript_text
    medical_data["english_translation"] = english_translation

    # Step 6 & 7: Generate PDF and save to DB only if doctor is verified
    report_id = str(uuid.uuid4())
    pdf_url = None

    if speaker_data.get("verified") and medical_data.get("is_valid"):
        try:
            pdf_path = generate_pdf_report(medical_data, report_id, doctor_name="Dr. Attending Physician")
            save_report_to_db(report_id, "default_doctor", medical_data, pdf_path)
            pdf_url = f"/api/report/download/{report_id}"
        except Exception as e:
            logging.error(f"PDF/DB error: {e}")

    return {
        "status":              "success",
        "report_id":           report_id,
        "transcript":          transcript_text,
        "english_translation": english_translation,
        "language":            transcription["language"],
        "language_name":       transcription.get("language_name"),
        "language_requested":  language,
        "model_used":          transcription.get("model_used"),
        "duration_seconds":    duration_seconds,
        "speaker_verification": speaker_data,
        "medical_report":      medical_data,
        "pdf_url":             pdf_url,
    }


# ---------------------------------------------------------------------------
# Download PDF Report
# ---------------------------------------------------------------------------

@app.get("/api/report/download/{report_id}", tags=["Report"])
def download_report(report_id: str):
    """Download a generated PDF report by its ID."""
    pdf_path = BASE_DIR / "data" / "reports" / f"{report_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"medical_report_{report_id[:8]}.pdf"
    )


# ---------------------------------------------------------------------------
# Report History
# ---------------------------------------------------------------------------

@app.get("/api/reports/history", tags=["Report"])
def get_report_history():
    """Fetch all past medical reports."""
    reports = get_all_reports("default_doctor")
    return {"reports": reports, "total": len(reports)}


# ---------------------------------------------------------------------------
# Doctor Info (enrollment status)
# ---------------------------------------------------------------------------

@app.get("/api/doctor/info", tags=["Auth"])
def get_doctor_info():
    """Check doctor enrollment status and report count."""
    enrollment_dir = BASE_DIR / "data" / "audio" / "enrollment"
    enrollment_file = enrollment_dir / "default_doctor_embedding.npy"
    samples = list(enrollment_dir.glob("default_doctor_sample_*.wav"))
    reports = get_all_reports("default_doctor")
    return {
        "voice_enrolled": enrollment_file.exists(),
        "sample_count":   len(samples),
        "threshold":      DEFAULT_THRESHOLD,
        "total_reports":  len(reports),
    }


@app.post("/api/doctor/reset-voice", tags=["Auth"])
def reset_voice_profile():
    """Reset doctor voice biometric baseline for re-enrollment."""
    cleared = reset_enrollment("default_doctor")
    return {"status": "success", "cleared": cleared, "message": "Voice baseline reset. Please re-enroll."}
