"""
Whisper ASR transcription module.

Loads a Whisper model once at startup (lazy singleton pattern) and
exposes a single function to transcribe a 16kHz mono WAV file.

Supports faster-whisper (CTranslate2) as the primary backend when available,
falling back to openai-whisper. Accepts an optional language parameter to
support Indian language transcription; when None, Whisper auto-detects.
"""

import os
import json
import logging
import ssl
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv()

# ---------------------------------------------------------------------------
# Medical prompts per language
# ---------------------------------------------------------------------------

MEDICAL_PROMPTS: dict[str | None, str] = {
    None: (
        "Clinical medical consultation: Patient, symptoms, fever, cough, chest pain, "
        "headache, shortness of breath, blood pressure, BP, pulse rate, temperature, "
        "SpO2, diagnosis, prescription, tablet, syrup, mg, daily, twice daily."
    ),
    "en": (
        "Clinical medical consultation: Patient, symptoms, fever, cough, chest pain, "
        "headache, shortness of breath, blood pressure, BP, pulse rate, temperature, "
        "SpO2, diagnosis, prescription, tablet, syrup, mg, daily, twice daily."
    ),
    "hi": (
        "चिकित्सा परामर्श: रोगी, लक्षण, बुखार, खांसी, सीने में दर्द, सिरदर्द, "
        "सांस की तकलीफ, रक्तचाप, नाड़ी दर, तापमान, SpO2, निदान, नुस्खा, "
        "गोली, सिरप, मिलीग्राम, दैनिक, दिन में दो बार।"
    ),
    "mr": (
        "वैद्यकीय सल्ला: रुग्ण, लक्षणे, ताप, खोकला, छातीत दुखणे, डोकेदुखी, "
        "श्वास घेण्यास त्रास, रक्तदाब, नाडी दर, तापमान, SpO2, निदान, "
        "प्रिस्क्रिप्शन, गोळी, सिरप, मिलिग्राम, दररोज, दिवसातून दोनदा."
    ),
    "ta": (
        "மருத்துவ ஆலோசனை: நோயாளி, அறிகுறிகள், காய்ச்சல், இருமல், மார்பு வலி, "
        "தலைவலி, மூச்சு திணறல், இரத்த அழுத்தம், நாடி துடிப்பு, வெப்பநிலை, "
        "SpO2, நோய் கண்டறிதல், மருந்துச்சீட்டு, மாத்திரை, சிரப், மி.கி., தினமும், "
        "தினமும் இரண்டு முறை."
    ),
    "te": (
        "వైద్య సంప్రదింపు: రోగి, లక్షణాలు, జ్వరం, దగ్గు, ఛాతీ నొప్పి, తలనొప్పి, "
        "శ్వాస తీసుకోవడంలో ఇబ్బంది, రక్తపోటు, నాడి రేటు, ఉష్ణోగ్రత, SpO2, "
        "నిర్ధారణ, ప్రిస్క్రిప్షన్, మాత్ర, సిరప్, మి.గ్రా., రోజువారీ, రోజుకు రెండుసార్లు."
    ),
    "gu": (
        "તબીબી પરામર્શ: દર્દી, લક્ષણો, તાવ, ઉધરસ, છાતીમાં દુખાવો, માથાનો દુખાવો, "
        "શ્વાસ લેવામાં તકલીફ, બ્લડ પ્રેશર, પલ્સ રેટ, તાપમાન, SpO2, નિદાન, "
        "પ્રિસ્ક્રિપ્શન, ટેબ્લેટ, સિરપ, મિ.ગ્રા., દૈનિક, દિવસમાં બે વાર."
    ),
    "kn": (
        "ವೈದ್ಯಕೀಯ ಸಮಾಲೋಚನೆ: ರೋಗಿ, ರೋಗಲಕ್ಷಣಗಳು, ಜ್ವರ, ಕೆಮ್ಮು, ಎದೆ ನೋವು, "
        "ತಲೆನೋವು, ಉಸಿರಾಟದ ತೊಂದರೆ, ರಕ್ತದೊತ್ತಡ, ನಾಡಿ ದರ, ತಾಪಮಾನ, SpO2, "
        "ರೋಗನಿರ್ಣಯ, ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್, ಮಾತ್ರೆ, ಸಿರಪ್, ಮಿ.ಗ್ರಾ., ದೈನಂದಿನ, ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ."
    ),
    "ml": (
        "വൈദ്യ ഉപദേശം: രോഗി, ലക്ഷണങ്ങൾ, പനി, ചുമ, നെഞ്ചുവേദന, തലവേദന, "
        "ശ്വാസതടസ്സം, രക്തസമ്മർദ്ദം, നാഡി നിരക്ക്, താപനില, SpO2, രോഗനിർണ്ണയം, "
        "കുറിപ്പടി, ഗുളിക, സിറപ്പ്, മി.ഗ്രാം., ദൈനംദിനം, ദിവസേന രണ്ടുതവണ."
    ),
    "bn": (
        "চিকিৎসা পরামর্শ: রোগী, উপসর্গ, জ্বর, কাশি, বুকে ব্যথা, মাথাব্যথা, "
        "শ্বাসকষ্ট, রক্তচাপ, নাড়ির হার, তাপমাত্রা, SpO2, রোগ নির্ণয়, "
        "প্রেসক্রিপশন, ট্যাবলেট, সিরাপ, মিলিগ্রাম, প্রতিদিন, দিনে দুইবার।"
    ),
    "pa": (
        "ਡਾਕਟਰੀ ਸਲਾਹ: ਮਰੀਜ਼, ਲੱਛਣ, ਬੁਖਾਰ, ਖੰਘ, ਛਾਤੀ ਦਰਦ, ਸਿਰਦਰਦ, "
        "ਸਾਹ ਲੈਣ ਵਿੱਚ ਮੁਸ਼ਕਲ, ਬਲੱਡ ਪ੍ਰੈਸ਼ਰ, ਨਬਜ਼ ਦਰ, ਤਾਪਮਾਨ, SpO2, ਨਿਦਾਨ, "
        "ਨੁਸਖ਼ਾ, ਗੋਲੀ, ਸ਼ਰਬਤ, ਮਿਲੀਗ੍ਰਾਮ, ਰੋਜ਼ਾਨਾ, ਦਿਨ ਵਿੱਚ ਦੋ ਵਾਰ।"
    ),
    "ur": (
        "طبی مشاورت: مریض، علامات، بخار، کھانسی، سینے میں درد، سر درد، "
        "سانس کی تکلیف، بلڈ پریشر، نبض کی رفتار، درجہ حرارت، SpO2، تشخیص، "
        "نسخہ، گولی، شربت، ملی گرام، روزانہ، دن میں دو بار۔"
    ),
    "or": (
        "ଚିକିତ୍ସା ପରାମର୍ଶ: ରୋଗୀ, ଲକ୍ଷଣ, ଜ୍ୱର, କାଶ, ଛାତି ବ୍ୟଥା, ମୁଣ୍ଡ ବ୍ୟଥା, "
        "ନିଃଶ୍ୱାସ ନେବାରେ ଅସୁବିଧା, ରକ୍ତଚାପ, ନାଡ଼ି ହାର, ତାପମାତ୍ରା, SpO2, ରୋଗ ନିର୍ଣ୍ଣୟ, "
        "ପ୍ରେସ୍‌କ୍ରିପ୍ସନ, ଟ୍ୟାବ୍‌ଲେଟ, ସିରପ, ମିଲିଗ୍ରାମ, ପ୍ରତିଦିନ, ଦିନକୁ ଦୁଇ ଥର।"
    ),
}

# ---------------------------------------------------------------------------
# Backend detection (faster-whisper preferred, openai-whisper fallback)
# ---------------------------------------------------------------------------

try:
    from faster_whisper import WhisperModel as FasterWhisperModel  # noqa: PLC0415
    _FASTER_WHISPER_AVAILABLE = True
except ImportError:
    _FASTER_WHISPER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Lazy singleton state
# ---------------------------------------------------------------------------

_whisper_model = None
_loaded_model_name: str | None = None
_model_backend: str | None = None  # "faster_whisper" | "openai_whisper"


# ---------------------------------------------------------------------------
# SSL patch (macOS Python.org installer)
# ---------------------------------------------------------------------------

def _patch_ssl_for_macos() -> None:
    """
    On macOS, the Python.org installer does not install root certificates.
    Patches urllib to use certifi's CA bundle so Whisper can download model
    weights over HTTPS without SSL errors.
    """
    try:
        import certifi  # noqa: PLC0415
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl_ctx)
        )
        urllib.request.install_opener(opener)
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Model loader (lazy singleton)
# ---------------------------------------------------------------------------

def get_whisper_model(model_name: str = "small"):
    """
    Return a loaded Whisper model, using the lazy singleton pattern.

    Tries faster-whisper (CTranslate2) first for speed; falls back to
    openai-whisper if faster-whisper is not installed.

    Supported model names: tiny, base, small, medium, large.
    """
    global _whisper_model, _loaded_model_name, _model_backend

    if _whisper_model is not None and _loaded_model_name == model_name:
        return _whisper_model

    if _FASTER_WHISPER_AVAILABLE:
        logger.info("Loading faster-whisper model '%s'…", model_name)
        _whisper_model = FasterWhisperModel(model_name, device="cpu", compute_type="int8")
        _loaded_model_name = model_name
        _model_backend = "faster_whisper"
        logger.info("faster-whisper model '%s' loaded successfully.", model_name)
    else:
        try:
            import whisper  # noqa: PLC0415
            _patch_ssl_for_macos()
            logger.info("Loading openai-whisper model '%s'…", model_name)
            _whisper_model = whisper.load_model(model_name)
            _loaded_model_name = model_name
            _model_backend = "openai_whisper"
            logger.info("openai-whisper model '%s' loaded successfully.", model_name)
        except ImportError:
            raise RuntimeError(
                "Neither faster-whisper nor openai-whisper is installed. "
                "Run: pip install faster-whisper  (or: pip install openai-whisper)"
            )

    return _whisper_model


# ---------------------------------------------------------------------------
# SOTA Multilingual ASR (Gemini 2.5 Flash Multimodal Audio)
# ---------------------------------------------------------------------------

def _transcribe_with_gemini(
    wav_path: Path,
    language: str | None = None,
) -> dict | None:
    """
    State-of-the-art multilingual ASR using Gemini 2.5 Flash multimodal audio.
    Provides human-grade accuracy for Indic regional languages (Marathi, Hindi,
    Tamil, Telugu, Gujarati, Kannada, Malayalam, Bengali, Punjabi, Urdu, Odia)
    and Indian English, where standard Whisper models suffer high word error rates.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        with open(wav_path, "rb") as f:
            audio_bytes = f.read()

        lang_hint = (
            f"Expected Spoken Language: {language}"
            if language
            else "Expected Spoken Language: Auto-detect (Indian regional language such as Marathi, Hindi, Tamil, Telugu, or Indian English)"
        )

        prompt = f"""You are a state-of-the-art multilingual Automatic Speech Recognition (ASR) engine specializing in Indian languages and clinical medical consultations.
{lang_hint}

Instructions:
1. Accurately transcribe the spoken voice verbatim into its authentic native script without hallucinations.
2. If Marathi (mr): Use authentic Marathi grammar, verbs ('आहे', 'नाही', 'झाला', 'आला', 'पाहिजे'), nouns, and Devanagari script (e.g. "माझं नाव...", "ताप", "डोकेदुखी", "दिवसांपासून"). Do NOT convert Marathi into Hindi or phonetic distortion.
3. If Hindi (hi): Use accurate Hindi Devanagari script.
4. If Tamil (ta), Telugu (te), Kannada (kn), Malayalam (ml), Bengali (bn), Gujarati (gu), Punjabi (pa), Urdu (ur), Odia (or): Use their respective authentic native scripts.
5. If English (en): Transcribe in clean, standard English.
6. Provide an accurate English translation if the spoken audio is in an Indian regional language.
7. Return confidence score (0.0 to 1.0).

Return ONLY a valid JSON object matching this schema:
{{
  "text": "<verbatim transcript in native script>",
  "language": "<language code: mr, hi, ta, te, kn, ml, bn, gu, pa, ur, or, en>",
  "language_name": "<full language name>",
  "english_translation": "<translation into English>",
  "confidence": <float between 0.0 and 1.0>
}}
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                prompt,
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        data = json.loads(response.text)
        text = (data.get("text") or "").strip()
        if not text:
            return None

        detected_lang = data.get("language") or language or "unknown"
        english_trans = (data.get("english_translation") or text).strip()

        return {
            "text": text,
            "language": detected_lang,
            "language_name": data.get("language_name", detected_lang),
            "english_translation": english_trans,
            "segments": [{"start": 0.0, "end": 0.0, "text": text}],
            "model_used": "gemini-2.5-flash (multimodal ASR)",
            "confidence": float(data.get("confidence", 0.95)),
        }
    except Exception as e:
        logger.warning(f"Gemini multimodal ASR unavailable/failed: {e}. Falling back to Whisper.")
        return None


# ---------------------------------------------------------------------------
# Public transcription function
# ---------------------------------------------------------------------------

def transcribe_audio(
    wav_path: Path,
    model_name: str = "tiny",
    language: str | None = None,
    force_whisper: bool = False,
) -> dict:
    """
    Transcribe the given WAV file using the premier available ASR model.

    Pipeline:
      1. SOTA Primary: Gemini 2.5 Flash Multimodal Audio (superior for Indic languages)
      2. Fallback: Local Whisper (faster-whisper or openai-whisper)

    Parameters
    ----------
    wav_path      : Path to the 16kHz mono WAV file.
    model_name   : Whisper fallback model size (tiny, base, small, medium, large).
    language     : BCP-47 language code (e.g. 'hi', 'mr', 'ta', 'en') or None for auto.
    force_whisper: If True, skips Gemini and uses Whisper directly.

    Returns
    -------
    dict with keys:
        text                – full transcript string (in native script)
        language            – detected/specified language code
        english_translation – translation in English
        segments            – list of {start, end, text} dicts
        model_used          – identifier of engine used
    """
    if not wav_path.exists():
        raise FileNotFoundError(f"Audio file not found: {wav_path}")

    # Step 1: Premier SOTA Indic model (Gemini 2.5 Flash)
    if not force_whisper:
        gemini_result = _transcribe_with_gemini(wav_path, language=language)
        if gemini_result is not None:
            logger.info("Transcription completed with Gemini 2.5 Flash multimodal ASR.")
            return gemini_result

    # Step 2: Fallback to local Whisper
    logger.info("Using Whisper ASR engine (fallback or forced).")
    model = get_whisper_model(model_name)
    initial_prompt = MEDICAL_PROMPTS.get(language, MEDICAL_PROMPTS[None])

    try:
        if _model_backend == "faster_whisper":
            res = _transcribe_faster_whisper(model, wav_path, language, initial_prompt)
        else:
            res = _transcribe_openai_whisper(model, wav_path, language, initial_prompt)
        # Ensure english_translation is populated
        if "english_translation" not in res:
            res["english_translation"] = res["text"]
        return res
    except Exception as e:
        raise RuntimeError(f"Whisper transcription failed: {e}") from e


# ---------------------------------------------------------------------------
# Backend-specific transcription helpers
# ---------------------------------------------------------------------------

def _transcribe_faster_whisper(
    model,
    wav_path: Path,
    language: str | None,
    initial_prompt: str,
) -> dict:
    """Run transcription with faster-whisper and normalise the output."""
    kwargs: dict = {
        "initial_prompt": initial_prompt,
        "temperature": 0.0,
        "condition_on_previous_text": False,
        "beam_size": 5,
        "vad_filter": True,
    }
    if language is not None:
        kwargs["language"] = language

    segments_gen, info = model.transcribe(str(wav_path), **kwargs)

    segments_list = []
    full_text_parts = []
    for seg in segments_gen:
        text = seg.text.strip()
        full_text_parts.append(text)
        segments_list.append({
            "start": round(seg.start, 2),
            "end":   round(seg.end,   2),
            "text":  text,
        })

    detected_language = language if language is not None else info.language

    return {
        "text":       " ".join(full_text_parts).strip(),
        "language":   detected_language,
        "segments":   segments_list,
        "model_used": "faster_whisper",
    }


def _transcribe_openai_whisper(
    model,
    wav_path: Path,
    language: str | None,
    initial_prompt: str,
) -> dict:
    """Run transcription with openai-whisper and normalise the output."""
    kwargs: dict = {
        "fp16":                     False,
        "initial_prompt":           initial_prompt,
        "temperature":              0.0,
        "condition_on_previous_text": False,
    }
    if language is not None:
        kwargs["language"] = language

    result = model.transcribe(str(wav_path), **kwargs)

    detected_language = language if language is not None else result.get("language", "unknown")

    return {
        "text":     result.get("text", "").strip(),
        "language": detected_language,
        "segments": [
            {
                "start": round(seg["start"], 2),
                "end":   round(seg["end"],   2),
                "text":  seg["text"].strip(),
            }
            for seg in result.get("segments", [])
        ],
        "model_used": "openai_whisper",
    }
