import asyncio
import os
import json
import uuid
import logging

from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from audio.processor import (
    convert_to_16k_mono_wav,
    save_upload_file,
    validate_audio_content_type,
)
from audio.transcriber import SpeechServiceUnavailable, transcribe_audio
from audio.parser import parse_medical_report
from audio.speaker import (
    DEFAULT_THRESHOLD, enroll_speaker, enrollment_sample_count,
    is_voice_enrolled, reset_enrollment, verify_speaker,
)
from report.generator import count_reports, generate_pdf_report, get_all_reports, report_pdf_path, save_report_to_db

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
RAW_AUDIO_DIR = BASE_DIR / "data" / "audio" / "raw"
WAV_AUDIO_DIR = BASE_DIR / "data" / "audio" / "wav_16k"

# Default to "tiny" model in cloud environments to avoid OOM memory crashes on 512MB RAM instances
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")

app = FastAPI(
    title="VoiceMedic AI — Medical Report Generator",
    description="Voice-powered medical report generation using Whisper ASR + ECAPA-TDNN + Gemini AI",
    version="1.0.0",
)

# Robust CORS middleware allowing all web origins, Vercel preview domains, and standard REST methods
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"https?://.*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Ensure CORS headers are always returned even when an unhandled 500 error occurs."""
    logging.error(f"Global unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}", "status": "error"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Ensure CORS headers are present on all HTTPExceptions (400, 404, 415, 500)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
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

@app.get("/", tags=["System"])
def root():
    """Root health check for cloud load balancers and deployment verification."""
    return {"status": "ok", "system": "VoiceMedic AI", "docs": "/docs"}


@app.get("/health", tags=["System"])
def get_health():
    """Simple health-check endpoint reporting system status and environment readiness."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    return {
        "status": "ok",
        "system": "VoiceMedic AI",
        "gemini_configured": bool(gemini_key),
    }


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logging.exception("Voice enrollment failed")
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

    Transcribe and extract the report while checking the speaker.
    Save a PDF and history entry after both checks pass.

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
        raw_path, _ = await save_upload_file(file, RAW_AUDIO_DIR)
        wav_path, duration_seconds = await run_in_threadpool(convert_to_16k_mono_wav, raw_path, WAV_AUDIO_DIR)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Overlap the remote request with speaker inference for an enrolled user.
    verification = None
    if (os.getenv("GEMINI_API_KEY") or "").strip() and is_voice_enrolled("default_doctor"):
        verification = asyncio.create_task(
            asyncio.to_thread(verify_speaker, str(wav_path), user_id="default_doctor")
        )
    whisper_language: str | None = None if language == "auto" else language
    try:
        transcription = await run_in_threadpool(
            transcribe_audio,
            wav_path,
            model_name=WHISPER_MODEL,
            language=whisper_language,
            include_report=True,
        )
        transcript_text = transcription["text"].strip()
        if not transcript_text:
            raise HTTPException(
                status_code=422,
                detail="No intelligible speech was detected. Please record again and speak clearly.",
            )
        english_translation = transcription.get("english_translation", transcript_text).strip()
        detected_lang = transcription.get("language", "en")
        if verification is None:
            verification = asyncio.create_task(
                asyncio.to_thread(verify_speaker, str(wav_path), user_id="default_doctor")
            )

        medical_data = transcription.get("medical_report")
        if medical_data is None:
            parse_input = (
                f"{transcript_text}\n(English Translation: {english_translation})"
                if english_translation and english_translation != transcript_text
                else transcript_text
            )
            medical_data = await run_in_threadpool(parse_medical_report, parse_input, language=detected_lang)
        speaker_data = await verification
    except SpeechServiceUnavailable as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": str(e), "code": "transcription_unavailable"},
        )
    finally:
        if verification is not None:
            if not verification.done():
                verification.cancel()
            await asyncio.gather(verification, return_exceptions=True)

    medical_data["transcript"] = transcript_text
    medical_data["english_translation"] = english_translation

    # Step 6 & 7: Generate PDF and save to DB only if doctor is verified
    report_id = str(uuid.uuid4())
    pdf_url = None
    history_entry = None
    report_status = "unverified"

    if speaker_data.get("verified"):
        report_status = "incomplete"
        if medical_data.get("is_valid"):
            try:
                history_entry = await run_in_threadpool(save_verified_report, report_id, medical_data)
                pdf_url = f"/api/report/download/{report_id}"
                report_status = "saved"
            except Exception:
                report_status = "save_failed"
                logging.exception("Failed to save verified report %s", report_id)

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
        "report_status":       report_status,
        "history_entry":       history_entry,
    }


def save_verified_report(report_id: str, medical_data: dict) -> dict:
    try:
        pdf_path = generate_pdf_report(medical_data, report_id, doctor_name="Dr. Attending Physician")
        return save_report_to_db(report_id, "default_doctor", medical_data, pdf_path)
    except Exception:
        report_pdf_path(report_id).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Download PDF Report
# ---------------------------------------------------------------------------

@app.get("/api/report/download/{report_id}", tags=["Report"])
def download_report(report_id: str):
    """Download a generated PDF report by its ID."""
    pdf_path = report_pdf_path(report_id)
    if not pdf_path.is_file():
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
    return {
        "voice_enrolled": is_voice_enrolled("default_doctor"),
        "sample_count":   enrollment_sample_count("default_doctor"),
        "threshold":      DEFAULT_THRESHOLD,
        "total_reports":  count_reports("default_doctor"),
    }


@app.post("/api/doctor/reset-voice", tags=["Auth"])
def reset_voice_profile():
    """Reset doctor voice biometric baseline for re-enrollment."""
    cleared = reset_enrollment("default_doctor")
    return {"status": "success", "cleared": cleared, "message": "Voice baseline reset. Please re-enroll."}
