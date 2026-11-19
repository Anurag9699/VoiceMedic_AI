# VoiceMedic AI — Voice-Controlled Consultation & Medical Report Generator

A production-grade, privacy-first healthcare AI system that converts spoken physician consultations into publication-quality structured medical reports and signed PDF records. Equipped with **deep speaker verification** (biometric authentication) and **multilingual Automatic Speech Recognition (ASR) supporting 12+ Indian regional languages**.

---

## 1. System Architecture

```
                                  ┌────────────────────────┐
                                  │   Doctor / Physician   │
                                  └───────────┬────────────┘
                                              │ Spoken Voice
                                              ▼
                                 ┌──────────────────────────┐
                                 │   Browser Frontend       │
                                 │   • Language Selector    │
                                 │   • Voice Profile State  │
                                 └────────────┬─────────────┘
                                              │ WebM / Opus Stream
                                              ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ FastAPI Backend Pipeline                                                               │
│                                                                                        │
│  [1. Audio Processor]                                                                 │
│      ffmpeg conversion → 16kHz mono 16-bit PCM WAV + SNR & clipping check              │
│                                                                                        │
│  [2. Biometric Speaker Verification] (SpeechBrain ECAPA-TDNN)                         │
│      • Segment-Level Embeddings (2.5s window / 1.5s hop)                                │
│      • Median & Min/Max Score Aggregation                                              │
│      • Dynamic Quality-Calibrated Threshold (0.45 - 0.70)                              │
│      • Anti-Spoofing: Spectral Flatness + Voice Bandwidth Analysis                     │
│      • Status: VERIFIED or FLAGGED IMPOSTOR                                            │
│                                                                                        │
│  [3. Multilingual ASR] (OpenAI Whisper / faster-whisper)                               │
│      • 12 Indian Languages: Hindi, Marathi, Tamil, Telugu, Gujarati, Kannada,         │
│        Malayalam, Bengali, Punjabi, Urdu, Odia + English & Auto-Detect                │
│      • Language-specific clinical prompts for high vocabulary precision                │
│                                                                                        │
│  [4. Clinical NLP Extraction] (Google Gemini 2.5 Flash)                                │
│      • Multilingual Prompting & Translation to Structured FHIR-aligned JSON            │
│      • Extracts: Symptoms, Vitals, Diagnosis, Prescriptions, History                   │
│                                                                                        │
│  [5. Publication-Grade PDF Engine] (ReportLab)                                         │
│      • Automated formal medical documentation with digital biometric verification stamp│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Indian Language Support

The ASR engine supports automatic speech recognition in the following Indian regional languages:

| Language | Native Script | Language Code | Clinical Bias Prompt |
|---|---|---|---|
| **Auto-Detect** | 🌐 Auto | `auto` | Adaptive |
| **English** | English | `en` | Medical consultation vocabulary |
| **Hindi** | हिन्दी | `hi` | चिकित्सीय परामर्श शब्दावली |
| **Marathi** | मराठी | `mr` | वैद्यकीय तपासणी शब्दावली |
| **Tamil** | தமிழ் | `ta` | மருத்துவ பரிசோதனை சொற்களஞ்சியம் |
| **Telugu** | తెలుగు | `te` | వైద్య సంప్రదింపుల పదజాలం |
| **Gujarati** | ગુજરાતી | `gu` | તબીબી પરામર્શ શબ્દભંડોળ |
| **Kannada** | ಕನ್ನಡ | `kn` | ವೈದ್ಯಕೀಯ ಸಮಾಲೋಚನೆ ಶಬ್ದಕೋಶ |
| **Malayalam** | മലയാളം | `ml` | മെഡിക്കൽ കൺസൾട്ടേഷൻ പദാവലി |
| **Bengali** | বাংলা | `bn` | মেডিকেল পরামর্শের পরিভাষা |
| **Punjabi** | ਪੰਜਾਬੀ | `pa` | ਡਾਕਟਰੀ ਸਲਾਹ ਸ਼ਬਦਾਵਲੀ |
| **Urdu** | اردو | `ur` | طبی مشورہ کے الفاظ |
| **Odia** | ଓଡ଼ିଆ | `or` | ଡାକ୍ତରୀ ପରାମର୍ଶ ଶବ୍ଦାବଳୀ |

---

## 3. Deep Speaker Verification Architecture

### Why earlier voice verification systems failed (and how we solved it):
1. **Single global vector vs. Segment-Level Analysis**: Previously, a single audio file yielded one embedding. A cough or noise at the start degraded the whole embedding. Now, the audio is split into overlapping 2.5-second windows. We compute cosine similarity per window and take the **statistical median**, completely filtering out transient noise.
2. **Fixed vs. Dynamic Quality-Calibrated Threshold**:
   - High SNR clean recordings: threshold relaxes by `-0.02` for seamless user convenience.
   - Low SNR noisy recordings: threshold tightens by `+0.03` to prevent impostor matches.
   - Multi-sample enrollment (5+ samples): threshold relaxes by `-0.01` due to high confidence.
3. **Enrollment Quality Score (0–100)**: Users receive immediate feedback on their voice baseline quality based on inter-sample similarity consistency and signal-to-noise ratio.
4. **Anti-Spoofing Gate**: Spectral flatness and effective bandwidth checks detect replay attacks from loudspeakers or synthesized audio.

---

## 4. Running the Project

### Prerequisites
- Python 3.10+ (macOS, Linux, or Windows)
- Node.js 18+ & npm
- `ffmpeg` installed on system (`brew install ffmpeg` on macOS, or `sudo apt install ffmpeg` on Linux)

### Backend Setup
```bash
cd voice-payment-system/backend
python3 -m pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
- Interactive API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)
- Languages API: [http://localhost:8000/api/languages](http://localhost:8000/api/languages)

### Frontend Setup
```bash
cd voice-payment-system/frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 5. Running the Test Suite

```bash
cd voice-payment-system
pytest -v
```
All **64 tests** validate audio preprocessing, speaker verification, anti-spoofing, dynamic thresholding, Indian language mappings, and report generation.
