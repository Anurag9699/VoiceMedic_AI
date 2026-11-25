import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

from . import GEMINI_MODELS

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv()

# Initialize Gemini client lazily
_gemini_client = None

LANGUAGE_NAMES = {
    "hi": "Hindi",
    "mr": "Marathi",
    "ta": "Tamil",
    "te": "Telugu",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "bn": "Bengali",
    "pa": "Punjabi",
    "ur": "Urdu",
    "or": "Odia",
    "en": "English",
}

def get_gemini_client():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            _gemini_client = genai.Client(api_key=api_key)
    except Exception as e:
        logging.warning(f"Could not initialize Gemini client: {e}")
        _gemini_client = None
    return _gemini_client


def _parse_with_regex(transcript: str) -> Dict[str, Any]:
    """Fallback regex parser for basic medical data extraction."""
    t = transcript.lower().strip()

    # Try to find age
    age = None
    age_match = re.search(r'\b(\d+)[\s-]*(?:years?|yrs?)\b', t)
    if age_match:
        age = int(age_match.group(1))

    # Gender
    gender = None
    if re.search(r'\b(?:male|man|boy|mr)\b', t):
        gender = 'Male'
    elif re.search(r'\b(?:female|woman|girl|mrs|ms)\b', t):
        gender = 'Female'

    return {
        "patient_name": None,
        "age": age,
        "gender": gender,
        "symptoms": [],
        "duration": None,
        "vitals": {},
        "medical_history": None,
        "suggested_diagnosis": None,
        "recommended_tests": [],
        "prescription": None,
        "notes": transcript,
        "is_valid": bool(age or gender),
        "method": "regex_fallback"
    }


def parse_medical_report(transcript: str, language: str = "en") -> Dict[str, Any]:
    """
    Parses a doctor's voice transcript to extract structured medical report data.
    Uses Gemini LLM if configured, otherwise falls back to Regex.

    Args:
        transcript: The voice transcript text.
        language: BCP-47 language code of the transcript (e.g. 'en', 'hi', 'mr').
    """
    if not transcript or not transcript.strip():
        return {
            "patient_name": None, "age": None, "gender": None,
            "symptoms": [], "duration": None, "vitals": {},
            "medical_history": None, "suggested_diagnosis": None,
            "recommended_tests": [], "prescription": None,
            "notes": "", "is_valid": False, "method": "empty_transcript"
        }

    lang_name = LANGUAGE_NAMES.get(language, "English")

    # Build language-aware instruction
    if language == "en" or language not in LANGUAGE_NAMES:
        language_instruction = ""
    else:
        language_instruction = (
            f"The transcript is in {lang_name}. Extract medical information and return JSON "
            f"with English field names but values can be in {lang_name} or English."
        )

    client = get_gemini_client()
    if client:
        try:
            from google.genai import types

            lang_header = (
                f"Transcript Language: {lang_name}. "
                f"Please extract medical information from the following {lang_name} medical transcript."
            )

            prompt = f"""\
You are a senior medical AI assistant helping a doctor generate a structured patient consultation report from a voice transcript.

{lang_header}
{language_instruction}

TASK: Extract ALL medical information from the voice transcript below and return it as a strict JSON object.

Transcript:
"{transcript}"

EXTRACTION RULES (CRITICAL — follow precisely):
1. PATIENT NAME: Look for any person's name mentioned as a patient. Even partial names like "Anura", "Rahul", "Priya" should be captured. Do NOT return null if any name is present.
2. AGE: Look for any number followed by "year", "yr", "वर्षे", "साल", "வயது", "ವರ್ಷ" or similar age indicators in ANY language. Also look for numbers like "25 year old", "28 yrs". Return as integer.
3. GENDER: Detect from pronouns (he/she/his/her), titles (Mr/Mrs/Ms), or explicit words (male/female/पुरुष/महिला). Return "Male", "Female", or "Other".
4. SYMPTOMS: Extract ALL physical complaints — fever, cold, cough, pain, nausea, vomiting, headache, dizziness etc. in ANY language. If the English translation mentions symptoms, always capture them. Return as array of strings in English.
5. DURATION: Look for any time reference — "3 days", "since a week", "7 दिवसांपासून", "2 hours", "for a month". Return as a readable string like "7 days".
6. VITALS: Extract blood pressure (e.g. 120/80), temperature (e.g. 101°F, 38°C), pulse (bpm), SpO2 (%), weight (kg/lbs) if mentioned.
7. DIAGNOSIS: If the doctor states a diagnosis or impression, extract it. Common: "viral fever", "URTI", "hypertension", "dengue".
8. PRESCRIPTION: Extract any medicines — tablet names, dosages, frequency (OD/BD/TDS), duration of course.
9. TESTS: Extract any lab tests or investigations ordered — CBC, LFT, chest X-ray, ECG, etc.
10. NOTES: Any additional clinical notes or instructions.

IMPORTANT: If the transcript contains BOTH a native-language original AND an English Translation (marked with "English Translation:"), use BOTH for extraction — the English translation is authoritative for symptom names and clinical terms.

Return ONLY this JSON (no markdown, no explanation):
{{
    "patient_name": "<full name string, or null if truly not mentioned>",
    "age": <integer age, or null if not mentioned>,
    "gender": "<Male/Female/Other, or null if not determinable>",
    "symptoms": ["<symptom in English>"],
    "duration": "<duration string like '3 days' or '1 week', or null>",
    "vitals": {{
        "blood_pressure": "<value with units or null>",
        "temperature": "<value with units or null>",
        "pulse": "<value with units or null>",
        "spo2": "<value with units or null>",
        "weight": "<value with units or null>"
    }},
    "medical_history": "<past medical history string or null>",
    "suggested_diagnosis": "<clinical diagnosis or null>",
    "recommended_tests": ["<test name>"],
    "prescription": "<full prescription text or null>",
    "notes": "<additional notes or null>",
    "is_valid": <true if ANY useful clinical info found — name, symptoms, age, or diagnosis — else false>
}}
"""
            response = None
            last_err = None
            for m in GEMINI_MODELS:
                try:
                    response = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                        ),
                    )
                    if response and response.text:
                        break
                except Exception as me:
                    last_err = me
                    logging.warning(f"Gemini parser with {m} failed: {me}")

            if not response or not response.text:
                raise last_err or RuntimeError("No response from Gemini LLM parser")

            resp_text = response.text.strip()
            if resp_text.startswith("```"):
                lines = resp_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                resp_text = "\n".join(lines).strip()

            data = json.loads(resp_text)
            data["method"] = "gemini_llm"
            # Ensure array fields are lists
            data["symptoms"] = data.get("symptoms") or []
            data["recommended_tests"] = data.get("recommended_tests") or []
            data["vitals"] = data.get("vitals") or {}
            return data

        except Exception as e:
            logging.error(f"Gemini medical parsing failed: {e}. Falling back to Regex.")

    return _parse_with_regex(transcript)
