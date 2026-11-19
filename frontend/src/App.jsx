
import { useEffect, useRef, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || (
  window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? `http://${window.location.hostname}:8000`
    : ''
);

const MIN_ENROLL_SECS = 5;
const MIN_RECORD_SECS = 3;

const getBestMimeType = () => {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/ogg',
    'audio/mp4',
  ];
  return types.find(t => MediaRecorder.isTypeSupported(t)) || '';
};

const fmt = s =>
  `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

const INDIAN_LANGUAGES = [
  { code: 'auto', label: '🌐 Auto-Detect', nativeLabel: 'Auto' },
  { code: 'en',   label: '🇬🇧 English',  nativeLabel: 'English' },
  { code: 'hi',   label: '🇮🇳 Hindi',    nativeLabel: 'हिन्दी' },
  { code: 'mr',   label: '🇮🇳 Marathi',  nativeLabel: 'मराठी' },
  { code: 'ta',   label: '🇮🇳 Tamil',    nativeLabel: 'தமிழ்' },
  { code: 'te',   label: '🇮🇳 Telugu',   nativeLabel: 'తెలుగు' },
  { code: 'gu',   label: '🇮🇳 Gujarati', nativeLabel: 'ગુજરાતી' },
  { code: 'kn',   label: '🇮🇳 Kannada',  nativeLabel: 'ಕನ್ನಡ' },
  { code: 'ml',   label: '🇮🇳 Malayalam',nativeLabel: 'മലയാളം' },
  { code: 'bn',   label: '🇮🇳 Bengali',  nativeLabel: 'বাংলা' },
  { code: 'pa',   label: '🇮🇳 Punjabi',  nativeLabel: 'ਪੰਜਾਬੀ' },
  { code: 'ur',   label: '🇮🇳 Urdu',     nativeLabel: 'اردو' },
  { code: 'or',   label: '🇮🇳 Odia',     nativeLabel: 'ଓଡ଼ିଆ' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Premium Grayscale Theme Tokens (Obsidian / Silver / Titanium)
// ─────────────────────────────────────────────────────────────────────────────
const G = {
  bg: '#09090b',
  surface: '#121214',
  surface2: '#18181b',
  surface3: '#222226',
  surfaceHover: '#2a2a2f',

  borderSubtle: 'rgba(255, 255, 255, 0.08)',
  borderDefault: 'rgba(255, 255, 255, 0.14)',
  borderStrong: 'rgba(255, 255, 255, 0.28)',

  white: '#ffffff',
  silverHigh: '#f4f4f5',
  silverMid: '#d4d4d8',
  silverMuted: '#a1a1aa',
  silverFaint: '#71717a',
  charcoal: '#27272a',
  pitchBlack: '#09090b',

  glowSubtle: '0 0 20px rgba(255, 255, 255, 0.04)',
  glowHover: '0 0 28px rgba(255, 255, 255, 0.08)',
  shadowCard: '0 10px 30px -10px rgba(0, 0, 0, 0.7)',
};

// ─────────────────────────────────────────────────────────────────────────────
// Reusable Grayscale UI Components
// ─────────────────────────────────────────────────────────────────────────────
const Card = ({ children, style = {}, className = '' }) => (
  <div
    className={className}
    style={{
      background: G.surface,
      border: `1px solid ${G.borderSubtle}`,
      borderRadius: 14,
      padding: '24px',
      boxShadow: G.shadowCard,
      transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
      ...style,
    }}
  >
    {children}
  </div>
);

const SectionLabel = ({ children, style = {} }) => (
  <div
    style={{
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: '1.2px',
      textTransform: 'uppercase',
      color: G.silverFaint,
      fontFamily: "'JetBrains Mono', monospace",
      ...style,
    }}
  >
    {children}
  </div>
);

const Badge = ({ children, active = false, style = {} }) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      background: active ? 'rgba(255, 255, 255, 0.09)' : 'rgba(255, 255, 255, 0.04)',
      border: `1px solid ${active ? G.borderStrong : G.borderSubtle}`,
      color: active ? G.white : G.silverMuted,
      borderRadius: 999,
      padding: '4px 12px',
      fontSize: 12,
      fontWeight: 600,
      letterSpacing: '0.2px',
      ...style,
    }}
  >
    <span
      style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: active ? G.white : G.silverFaint,
        boxShadow: active ? '0 0 8px rgba(255, 255, 255, 0.8)' : 'none',
        display: 'inline-block',
      }}
    />
    {children}
  </span>
);

const Tag = ({ children, style = {} }) => (
  <span
    style={{
      background: G.surface2,
      border: `1px solid ${G.borderSubtle}`,
      color: G.silverHigh,
      borderRadius: 6,
      padding: '4px 10px',
      fontSize: 12,
      fontWeight: 500,
      display: 'inline-block',
      ...style,
    }}
  >
    {children}
  </span>
);

const DataPill = ({ label, value }) => (
  <div
    style={{
      background: G.surface2,
      border: `1px solid ${G.borderSubtle}`,
      borderRadius: 10,
      padding: '12px 16px',
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
    }}
  >
    <div
      style={{
        fontSize: 11,
        color: G.silverFaint,
        textTransform: 'uppercase',
        letterSpacing: '0.8px',
        fontWeight: 600,
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      {label}
    </div>
    <div
      style={{
        color: value ? G.white : G.silverFaint,
        fontWeight: 600,
        fontSize: 14,
        fontStyle: value ? 'normal' : 'italic',
      }}
    >
      {value || 'Not specified'}
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// Main Application Component
// ─────────────────────────────────────────────────────────────────────────────
export default function App() {
  const [selectedLanguage, setSelectedLanguage] = useState('auto');
  const [doctorInfo, setDoctorInfo] = useState(null);
  const [enrollMode, setEnrollMode] = useState(false);
  const [enrollState, setEnrollState] = useState('idle');
  const [enrollError, setEnrollError] = useState(null);
  const [enrollElapsed, setEnrollElapsed] = useState(0);
  const enrollRecorderRef = useRef(null);
  const enrollChunksRef = useRef([]);
  const enrollTimerRef = useRef(null);

  const [recState, setRecState] = useState('idle');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  const fetchDoctorInfo = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/doctor/info`);
      if (r.ok) setDoctorInfo(await r.json());
    } catch { }
  };

  const fetchHistory = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/reports/history`);
      if (r.ok) {
        const d = await r.json();
        setHistory(d.reports || []);
      }
    } catch { }
  };

  useEffect(() => {
    fetchDoctorInfo();
    fetchHistory();
  }, []);

  // ── Voice Enrollment ───────────────────────────────────────────────────────
  const startEnroll = async (resetBaseline = false) => {
    setEnrollError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      const mime = getBestMimeType();
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
      enrollRecorderRef.current = rec;
      enrollChunksRef.current = [];

      rec.ondataavailable = e => {
        if (e.data?.size > 0) enrollChunksRef.current.push(e.data);
      };

      rec.onstop = () => {
        const m = rec.mimeType || 'audio/webm';
        const blob = new Blob(enrollChunksRef.current, { type: m });
        stream.getTracks().forEach(t => t.stop());
        if (blob.size < 1000) {
          setEnrollError('Audio sample too short or silent. Speak clearly for 5+ seconds.');
          setEnrollState('idle');
          return;
        }
        uploadEnroll(blob, m, resetBaseline);
      };

      rec.start();
      setEnrollElapsed(0);
      setEnrollState('recording');
      enrollTimerRef.current = setInterval(() => setEnrollElapsed(s => s + 1), 1000);
    } catch (err) {
      setEnrollError(err.name === 'NotAllowedError' ? 'Microphone permission denied.' : err.message);
    }
  };

  const stopEnroll = () => {
    clearInterval(enrollTimerRef.current);
    const rec = enrollRecorderRef.current;
    if (rec?.state === 'recording') {
      rec.requestData();
      setTimeout(() => {
        if (rec.state !== 'inactive') rec.stop();
      }, 150);
    }
  };

  const uploadEnroll = async (blob, mime, isReset = false) => {
    setEnrollState('uploading');
    const ext = (mime || blob.type).includes('ogg')
      ? 'ogg'
      : (mime || blob.type).includes('mp4')
        ? 'mp4'
        : 'webm';
    const fd = new FormData();
    fd.append('file', blob, `enroll.${ext}`);
    if (isReset) fd.append('reset', 'true');

    try {
      const r = await fetch(`${API_BASE}/api/audio/enroll`, { method: 'POST', body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
      setEnrollState('success');
      fetchDoctorInfo();
      setTimeout(() => {
        setEnrollMode(false);
        setEnrollState('idle');
      }, 2000);
    } catch (err) {
      setEnrollError(`Enrollment failed: ${err.message}`);
      setEnrollState('idle');
    }
  };

  const resetVoiceProfile = async () => {
    if (!window.confirm('Reset your registered voice baseline? You will need to re-enroll.'))
      return;
    try {
      const r = await fetch(`${API_BASE}/api/doctor/reset-voice`, { method: 'POST' });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Reset failed');
      fetchDoctorInfo();
      setEnrollState('idle');
      setEnrollError(null);
    } catch (err) {
      setEnrollError(`Reset failed: ${err.message}`);
    }
  };

  // ── Report Recording ───────────────────────────────────────────────────────
  const startRecording = async () => {
    setError(null);
    setResult(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      const mime = getBestMimeType();
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
      mediaRecorderRef.current = rec;
      chunksRef.current = [];

      rec.ondataavailable = e => {
        if (e.data?.size > 0) chunksRef.current.push(e.data);
      };

      rec.onstop = () => {
        const m = rec.mimeType || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type: m });
        stream.getTracks().forEach(t => t.stop());
        if (blob.size < 500) {
          setError('Empty recording detected. Check your microphone.');
          setRecState('idle');
          return;
        }
        uploadAudio(blob, m);
      };

      rec.start();
      setElapsed(0);
      setRecState('recording');
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    } catch (err) {
      setError(err.name === 'NotAllowedError' ? 'Microphone access denied.' : err.message);
    }
  };

  const stopRecording = () => {
    clearInterval(timerRef.current);
    const rec = mediaRecorderRef.current;
    if (rec?.state === 'recording') {
      rec.requestData();
      setTimeout(() => {
        if (rec.state !== 'inactive') rec.stop();
        setRecState('uploading');
      }, 150);
    } else {
      setRecState('uploading');
    }
  };

  const resetRecorder = () => {
    clearInterval(timerRef.current);
    setRecState('idle');
    setResult(null);
    setError(null);
    setElapsed(0);
  };

  const uploadAudio = async (blob, mime) => {
    const ext = (mime || blob.type).includes('ogg')
      ? 'ogg'
      : (mime || blob.type).includes('mp4')
        ? 'mp4'
        : 'webm';
    const fd = new FormData();
    fd.append('file', blob, `recording.${ext}`);
    fd.append('language', selectedLanguage);

    try {
      const r = await fetch(`${API_BASE}/api/report/generate`, { method: 'POST', body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
      setResult(d);
      setRecState('done');
      fetchDoctorInfo();
      fetchHistory();
    } catch (err) {
      setError(`Processing failed: ${err.message}`);
      setRecState('idle');
    }
  };

  const enrolled = Boolean(doctorInfo?.voice_enrolled);
  const sv = result?.speaker_verification;

  return (
    <div style={{ minHeight: '100vh', background: G.bg, color: G.white, width: '100%' }}>
      {/* ── TOP NAV BAR ──────────────────────────────────────────────────────── */}
      <nav
        style={{
          borderBottom: `1px solid ${G.borderSubtle}`,
          background: 'rgba(18, 18, 20, 0.85)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          padding: '0 24px',
          minHeight: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            style={{
              width: 26,
              height: 26,
              borderRadius: 6,
              background: G.surface3,
              border: `1px solid ${G.borderDefault}`,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 13,
              color: G.white,
              fontWeight: 800,
            }}
          >
            ✚
          </span>
          <span style={{ fontWeight: 700, fontSize: 14, letterSpacing: '-0.3px', color: G.white }}>
            VoiceMedic
          </span>
          <span
            style={{
              color: G.silverFaint,
              fontSize: 11,
              fontFamily: "'JetBrains Mono', monospace",
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
            }}
          >
            AI Clinical Suite
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          {doctorInfo && (
            <Badge active={enrolled}>
              {enrolled ? 'Doctor Verified' : 'No Baseline'}
            </Badge>
          )}

          <button
            id="re-enroll-toggle-btn"
            onClick={() => setEnrollMode(p => !p)}
            style={{
              background: enrollMode ? G.white : G.surface2,
              color: enrollMode ? G.pitchBlack : G.silverMid,
              border: `1px solid ${enrollMode ? G.white : G.borderDefault}`,
              borderRadius: 8,
              padding: '6px 14px',
              fontSize: 12,
              cursor: 'pointer',
              fontWeight: 600,
              transition: 'all 0.15s ease',
            }}
          >
            {enrolled ? 'Re-enroll' : 'Enroll Voice'}
          </button>

          {doctorInfo && (
            <span
              style={{
                fontSize: 11,
                color: G.silverFaint,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {doctorInfo.total_reports} {doctorInfo.total_reports === 1 ? 'report' : 'reports'}
            </span>
          )}
        </div>
      </nav>

      {/* ── MAIN CONTENT CONTAINER ──────────────────────────────────────────── */}
      <main
        style={{
          maxWidth: 820,
          margin: '0 auto',
          padding: '36px 20px 60px',
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
        }}
      >
        {/* ── HERO HEADER ───────────────────────────────────────────────────── */}
        <header style={{ textAlign: 'center', padding: '10px 0 10px' }}>
          <h1
            style={{
              margin: 0,
              fontSize: 28,
              fontWeight: 800,
              letterSpacing: '-0.6px',
              color: G.white,
            }}
          >
            Voice Medical Report Generator
          </h1>
          <p
            style={{
              margin: '8px auto 0',
              color: G.silverMuted,
              fontSize: 13,
              maxWidth: 580,
              lineHeight: 1.6,
            }}
          >
            Speak clinical consultation naturally · ECAPA-TDNN speaker biometric verification ·
            Whisper ASR transcription · Gemini clinical entity extraction
          </p>
        </header>

        {/* ── ENROLLMENT PANEL (TOGGLED) ─────────────────────────────────────── */}
        {enrollMode && (
          <Card
            style={{
              border: `1px solid ${G.borderStrong}`,
              background: 'linear-gradient(180deg, #161619 0%, #111113 100%)',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 10,
                marginBottom: 16,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <SectionLabel>🔐 Doctor Biometric Voice Enrollment</SectionLabel>
                {enrolled ? (
                  <Tag style={{ background: G.surface3, border: `1px solid ${G.borderStrong}` }}>
                    Active Baseline · {doctorInfo?.sample_count || 1} sample(s) · Threshold{' '}
                    {Math.round((doctorInfo?.threshold || 0.45) * 100)}%
                  </Tag>
                ) : (
                  <Tag style={{ color: G.silverMuted }}>No Profile Saved</Tag>
                )}
              </div>
              {doctorInfo?.enrollment_quality_score != null && (
                <span
                  style={{
                    background: G.surface3,
                    border: `1px solid ${G.borderSubtle}`,
                    color: G.silverMid,
                    borderRadius: 6,
                    padding: '3px 10px',
                    fontSize: 11,
                    fontWeight: 600,
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  Voice Profile Quality: {doctorInfo.enrollment_quality_score}/100
                </span>
              )}
              <button
                onClick={() => {
                  setEnrollMode(false);
                  setEnrollState('idle');
                  setEnrollError(null);
                }}
                style={{
                  background: 'transparent',
                  border: `1px solid ${G.borderSubtle}`,
                  borderRadius: 6,
                  color: G.silverMuted,
                  cursor: 'pointer',
                  fontSize: 12,
                  padding: '4px 8px',
                }}
              >
                Close ✕
              </button>
            </div>

            <p style={{ margin: '0 0 14px', color: G.silverMid, fontSize: 13, lineHeight: 1.6 }}>
              Read the verification sentence aloud naturally for at least 5 seconds. This calibrates
              your ECAPA-TDNN acoustic vector.
            </p>

            <div
              style={{
                background: G.surface2,
                border: `1px solid ${G.borderDefault}`,
                borderRadius: 8,
                padding: '14px 18px',
                marginBottom: 18,
                textAlign: 'center',
              }}
            >
              <span
                style={{
                  color: G.white,
                  fontStyle: 'italic',
                  fontSize: 13,
                  lineHeight: 1.7,
                  letterSpacing: '0.2px',
                }}
              >
                "I am the authorized doctor. My voice grants access to the medical report system."
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
              {enrollState === 'idle' && (
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
                  {enrolled ? (
                    <>
                      <button
                        onClick={() => startEnroll(true)}
                        style={{
                          background: G.white,
                          color: G.pitchBlack,
                          border: 'none',
                          borderRadius: 8,
                          padding: '10px 22px',
                          fontSize: 13,
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        🎙 Reset & Record Fresh Voice
                      </button>
                      <button
                        onClick={() => startEnroll(false)}
                        style={{
                          background: G.surface3,
                          color: G.white,
                          border: `1px solid ${G.borderDefault}`,
                          borderRadius: 8,
                          padding: '10px 18px',
                          fontSize: 13,
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        ➕ Add 2nd Calibration Sample
                      </button>
                      <button
                        onClick={resetVoiceProfile}
                        style={{
                          background: 'transparent',
                          color: G.silverMuted,
                          border: `1px solid ${G.borderSubtle}`,
                          borderRadius: 8,
                          padding: '10px 14px',
                          fontSize: 13,
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        🗑 Clear Profile
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => startEnroll(true)}
                      style={{
                        background: G.white,
                        color: G.pitchBlack,
                        border: 'none',
                        borderRadius: 8,
                        padding: '10px 26px',
                        fontSize: 14,
                        fontWeight: 700,
                        cursor: 'pointer',
                      }}
                    >
                      🎙 Start Enrollment (5s)
                    </button>
                  )}
                </div>
              )}

              {enrollState === 'recording' && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: enrollElapsed >= MIN_ENROLL_SECS ? G.white : G.silverFaint,
                        display: 'inline-block',
                        animation: 'blink 1s infinite',
                      }}
                    />
                    <span
                      style={{
                        fontWeight: 700,
                        fontSize: 18,
                        fontVariantNumeric: 'tabular-nums',
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {fmt(enrollElapsed)}
                    </span>
                    <span style={{ fontSize: 12, color: G.silverMuted }}>
                      {enrollElapsed < MIN_ENROLL_SECS
                        ? `Speak continuously… ${MIN_ENROLL_SECS - enrollElapsed}s remaining`
                        : 'Minimum length achieved ✓ Tap stop to save'}
                    </span>
                  </div>

                  {/* Equalizer bars */}
                  <div style={{ display: 'flex', gap: 4, height: 32, alignItems: 'center' }}>
                    {[...Array(14)].map((_, i) => (
                      <div
                        key={i}
                        style={{
                          width: 3,
                          background: enrollElapsed >= MIN_ENROLL_SECS ? G.white : G.silverFaint,
                          borderRadius: 2,
                          animation: `wave 0.8s ${i * 0.06}s infinite ease-in-out alternate`,
                        }}
                      />
                    ))}
                  </div>

                  <button
                    onClick={stopEnroll}
                    disabled={enrollElapsed < MIN_ENROLL_SECS}
                    style={{
                      background: enrollElapsed >= MIN_ENROLL_SECS ? G.white : G.surface3,
                      color: enrollElapsed >= MIN_ENROLL_SECS ? G.pitchBlack : G.silverFaint,
                      border: `1px solid ${enrollElapsed >= MIN_ENROLL_SECS ? G.white : G.borderSubtle}`,
                      borderRadius: 8,
                      padding: '8px 24px',
                      cursor: enrollElapsed >= MIN_ENROLL_SECS ? 'pointer' : 'not-allowed',
                      fontWeight: 700,
                      fontSize: 13,
                    }}
                  >
                    ⏹ Stop & Register Voice
                  </button>
                </div>
              )}

              {enrollState === 'uploading' && (
                <div style={{ color: G.silverMid, fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>◌</span>
                  Computing 192-dimensional ECAPA-TDNN embedding vector…
                </div>
              )}

              {enrollState === 'success' && (
                <div style={{ color: G.white, fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
                  ✓ Voice profile enrolled and calibrated successfully!
                </div>
              )}

              {enrollError && (
                <div
                  style={{
                    background: G.surface2,
                    border: `1px solid ${G.borderStrong}`,
                    borderRadius: 8,
                    padding: '10px 16px',
                    color: G.silverMid,
                    fontSize: 12,
                    width: '100%',
                    textAlign: 'center',
                  }}
                >
                  ⚠ {enrollError}
                </div>
              )}
            </div>
          </Card>
        )}

        {/* ── NOT ENROLLED BANNER ────────────────────────────────────────────── */}
        {!enrolled && !enrollMode && doctorInfo && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: G.surface,
              border: `1px solid ${G.borderDefault}`,
              borderRadius: 10,
              padding: '12px 18px',
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <span style={{ fontSize: 13, color: G.silverMid }}>
              <strong style={{ color: G.white }}>No Voice Baseline Found: </strong>
              Please register your doctor voice sample once to enable automatic clinical report generation.
            </span>
            <button
              onClick={() => setEnrollMode(true)}
              style={{
                background: G.white,
                color: G.pitchBlack,
                border: 'none',
                borderRadius: 7,
                padding: '7px 16px',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              Enroll Voice Baseline
            </button>
          </div>
        )}

        {/* ── RECORDER CARD ──────────────────────────────────────────────────── */}
        <Card>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 16,
              flexWrap: 'wrap',
              gap: 8,
            }}
          >
            <SectionLabel>🎙 Patient Consultation Dictation</SectionLabel>
            <span
              style={{
                fontSize: 11,
                color: G.silverFaint,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              Whisper · Gemini 2.5
            </span>
          </div>

          {/* Language Selector */}
          <div style={{ marginBottom: 16 }}>
            <SectionLabel style={{ marginBottom: 10 }}>LANGUAGE / भाषा</SectionLabel>
            <div
              style={{
                display: 'flex',
                gap: 8,
                overflowX: 'auto',
                paddingBottom: 6,
                scrollbarWidth: 'thin',
                scrollbarColor: `${G.borderSubtle} transparent`,
              }}
            >
              {INDIAN_LANGUAGES.map(lang => {
                const isSelected = selectedLanguage === lang.code;
                return (
                  <button
                    key={lang.code}
                    onClick={() => setSelectedLanguage(lang.code)}
                    style={{
                      flexShrink: 0,
                      background: isSelected ? G.surface3 : G.surface2,
                      border: `1px solid ${isSelected ? G.borderStrong : G.borderSubtle}`,
                      color: isSelected ? G.white : G.silverMuted,
                      borderRadius: 999,
                      padding: '5px 13px',
                      fontSize: 12,
                      fontWeight: isSelected ? 700 : 500,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      transition: 'all 0.15s ease',
                      fontFamily: 'inherit',
                    }}
                  >
                    {lang.nativeLabel} <span style={{ opacity: 0.6, fontSize: 10 }}>({lang.code})</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* IDLE STATE */}
          {recState === 'idle' && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20, padding: '16px 0' }}>
              <button
                id="start-record-btn"
                onClick={startRecording}
                style={{
                  width: 92,
                  height: 92,
                  borderRadius: '50%',
                  background: 'radial-gradient(circle at 35% 35%, #2c2c31 0%, #151517 75%)',
                  border: `2px solid ${G.borderStrong}`,
                  color: G.white,
                  fontSize: '2.1rem',
                  cursor: 'pointer',
                  boxShadow: `0 0 0 8px rgba(255, 255, 255, 0.03), 0 12px 28px rgba(0, 0, 0, 0.6)`,
                  transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.18s ease, border-color 0.18s ease',
                  outline: 'none',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.transform = 'scale(1.06)';
                  e.currentTarget.style.boxShadow = '0 0 0 14px rgba(255, 255, 255, 0.06), 0 16px 36px rgba(0, 0, 0, 0.8)';
                  e.currentTarget.style.borderColor = G.white;
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.transform = 'scale(1)';
                  e.currentTarget.style.boxShadow = '0 0 0 8px rgba(255, 255, 255, 0.03), 0 12px 28px rgba(0, 0, 0, 0.6)';
                  e.currentTarget.style.borderColor = G.borderStrong;
                }}
              >
                🎤
              </button>

              <div style={{ textAlign: 'center' }}>
                <p style={{ color: G.silverMid, margin: '0 0 6px', fontSize: 13, fontWeight: 500 }}>
                  Click the mic and speak patient details naturally
                </p>
                <p style={{ color: G.silverFaint, margin: 0, fontSize: 12 }}>
                  Mention: patient name, age, symptoms, duration, vitals, diagnosis, and prescription.
                </p>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', maxWidth: 660 }}>
                {[
                  '"Patient Rahul, 45 male, chest pain 3 days, BP 140/90, ECG normal"',
                  '"Mrs. Priya, 32, acute fever 5 days, temp 102F, paracetamol 650mg"',
                  '"60 year old diabetic male, shortness of breath, SpO2 94%"',
                ].map(ex => (
                  <span
                    key={ex}
                    style={{
                      background: G.surface2,
                      border: `1px solid ${G.borderSubtle}`,
                      borderRadius: 20,
                      padding: '5px 12px',
                      fontSize: 11,
                      color: G.silverMuted,
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {ex}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* RECORDING STATE */}
          {recState === 'recording' && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: '16px 0' }}>
              <button
                onClick={elapsed >= MIN_RECORD_SECS ? stopRecording : undefined}
                style={{
                  width: 92,
                  height: 92,
                  borderRadius: '50%',
                  background: elapsed >= MIN_RECORD_SECS ? G.white : G.surface3,
                  border: `2px solid ${G.white}`,
                  color: elapsed >= MIN_RECORD_SECS ? G.pitchBlack : G.white,
                  fontSize: '2rem',
                  cursor: elapsed >= MIN_RECORD_SECS ? 'pointer' : 'default',
                  animation: elapsed >= MIN_RECORD_SECS ? 'pulse-ring 1.5s infinite' : 'none',
                  outline: 'none',
                  transition: 'all 0.2s ease',
                }}
              >
                {elapsed >= MIN_RECORD_SECS ? '⏹' : '🎤'}
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: G.white,
                    display: 'inline-block',
                    animation: 'blink 1s infinite',
                  }}
                />
                <span
                  style={{
                    fontWeight: 700,
                    fontSize: 22,
                    fontVariantNumeric: 'tabular-nums',
                    fontFamily: "'JetBrains Mono', monospace",
                    color: G.white,
                  }}
                >
                  {fmt(elapsed)}
                </span>
                <span style={{ fontSize: 12, color: G.silverMuted }}>
                  {elapsed < MIN_RECORD_SECS
                    ? `Keep speaking… ${MIN_RECORD_SECS - elapsed}s`
                    : 'Tap ⏹ to finish consultation'}
                </span>
              </div>

              {/* Sound visualizer wave */}
              <div style={{ display: 'flex', gap: 4, height: 36, alignItems: 'center' }}>
                {[...Array(16)].map((_, i) => (
                  <div
                    key={i}
                    style={{
                      width: 3,
                      background: G.white,
                      borderRadius: 2,
                      animation: `wave 0.75s ${i * 0.05}s infinite ease-in-out alternate`,
                    }}
                  />
                ))}
              </div>

              <button
                onClick={resetRecorder}
                style={{
                  background: 'transparent',
                  border: `1px solid ${G.borderSubtle}`,
                  color: G.silverMuted,
                  borderRadius: 7,
                  padding: '6px 18px',
                  fontSize: 12,
                  cursor: 'pointer',
                }}
              >
                Cancel Recording
              </button>
            </div>
          )}

          {/* UPLOADING / PROCESSING STATE */}
          {recState === 'uploading' && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, padding: '28px 0' }}>
              <div
                style={{
                  width: 44,
                  height: 44,
                  border: `3px solid ${G.borderSubtle}`,
                  borderTop: `3px solid ${G.white}`,
                  borderRadius: '50%',
                  animation: 'spin 0.85s linear infinite',
                }}
              />
              <div
                style={{
                  color: G.silverMid,
                  fontSize: 13,
                  textAlign: 'center',
                  lineHeight: 2.2,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                <div>[1/4] ECAPA-TDNN Speaker Biometric Verification…</div>
                <div>[2/4] Whisper Automatic Speech Recognition…</div>
                <div>[3/4] Gemini 2.5 Flash Clinical Extraction…</div>
                <div>[4/4] Generating Standard Medical PDF…</div>
              </div>
            </div>
          )}

          {/* DONE / RESULTS STATE */}
          {recState === 'done' && result && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              {/* Speaker verification alert bar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 10,
                  background: sv?.verified ? 'rgba(255, 255, 255, 0.06)' : G.surface2,
                  border: `1px solid ${sv?.verified ? G.borderStrong : G.borderDefault}`,
                  borderRadius: 10,
                  padding: '14px 18px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 16 }}>{sv?.verified ? '✓' : '✕'}</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13, color: G.white }}>
                      {sv?.verified ? 'Doctor Biometric Authenticated' : 'Voice Biometric Not Verified'}
                      {sv?.confidence_band && (
                        <span
                          style={{
                            marginLeft: 8,
                            fontSize: 10,
                            fontWeight: 600,
                            letterSpacing: '0.5px',
                            textTransform: 'uppercase',
                            color: sv.confidence_band === 'high' ? G.white
                              : sv.confidence_band === 'medium' ? G.silverMid
                                : G.silverFaint,
                            background: G.surface3,
                            border: `1px solid ${G.borderSubtle}`,
                            borderRadius: 4,
                            padding: '2px 6px',
                          }}
                        >
                          {sv.confidence_band}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: G.silverFaint, marginTop: 2 }}>
                      {sv?.message || (sv?.verified
                        ? 'Speech acoustic centroid matched enrolled doctor baseline.'
                        : 'Audio signature does not match enrolled profile. Report was not saved to database.')}
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    display: 'flex',
                    gap: 12,
                    fontSize: 12,
                    color: G.silverMid,
                    fontFamily: "'JetBrains Mono', monospace",
                    flexWrap: 'wrap',
                  }}
                >
                  <span>
                    Confidence:{' '}
                    <strong style={{ color: G.white }}>
                      {((sv?.confidence_score || 0) * 100).toFixed(1)}%
                    </strong>
                  </span>
                  <span>
                    Threshold:{' '}
                    <strong style={{ color: G.white }}>
                      {((sv?.threshold_used || 0.55) * 100).toFixed(0)}%
                    </strong>
                  </span>
                  {sv?.audio_quality?.snr_db != null && (
                    <span>
                      SNR:{' '}
                      <strong style={{ color: G.white }}>
                        {sv.audio_quality.snr_db}dB
                      </strong>
                    </span>
                  )}
                  {sv?.anti_spoof && !sv.anti_spoof.passed && (
                    <span style={{ color: '#ff6b6b' }}>⚠ Spoof detected</span>
                  )}
                </div>
              </div>

              {!sv?.verified && (
                <div
                  style={{
                    background: G.surface2,
                    border: `1px solid ${G.borderSubtle}`,
                    borderRadius: 8,
                    padding: '12px 16px',
                    fontSize: 12,
                    color: G.silverMuted,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: 10,
                  }}
                >
                  <span>
                    {sv?.anti_spoof && !sv?.anti_spoof?.passed
                      ? 'Potential replay attack detected. Please speak directly into the microphone.'
                      : `Score ${((sv?.confidence_score || 0) * 100).toFixed(1)}% is below threshold ${((sv?.threshold_used || 0.55) * 100).toFixed(0)}%. Re-enroll your voice if you changed microphones.`}
                  </span>
                  <button
                    onClick={() => setEnrollMode(true)}
                    style={{
                      background: G.white,
                      color: G.pitchBlack,
                      border: 'none',
                      borderRadius: 6,
                      padding: '5px 12px',
                      fontSize: 11,
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    Open Re-enrollment
                  </button>
                </div>
              )}

              {/* Multilingual transcript box */}
              <div
                style={{
                  background: G.surface2,
                  border: `1px solid ${G.borderSubtle}`,
                  borderLeft: `3px solid ${G.white}`,
                  borderRadius: 8,
                  padding: '16px 20px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 6 }}>
                  <SectionLabel>Multilingual Clinical Transcript</SectionLabel>
                  {result.model_used && (
                    <span
                      style={{
                        background: G.surface3,
                        border: `1px solid ${G.borderSubtle}`,
                        color: G.silverMid,
                        borderRadius: 4,
                        padding: '2px 8px',
                        fontSize: 10,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      ⚡ {result.model_used}
                    </span>
                  )}
                </div>

                {result.language && (
                  <div style={{ fontSize: 12, color: G.silverMuted, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>🗣️ Detected:</span>
                    <strong style={{ color: G.white }}>
                      {INDIAN_LANGUAGES.find(l => l.code === result.language)?.nativeLabel || result.language}
                    </strong>
                    <span style={{ color: G.silverFaint }}>({result.language})</span>
                  </div>
                )}

                <div
                  style={{
                    color: result.transcript ? G.white : G.silverFaint,
                    fontSize: 15,
                    lineHeight: 1.7,
                    fontWeight: 500,
                    fontStyle: result.transcript ? 'normal' : 'italic',
                  }}
                >
                  {result.transcript ? `"${result.transcript}"` : 'No recognizable speech detected'}
                </div>

                {result.english_translation && result.english_translation !== result.transcript && (
                  <div
                    style={{
                      marginTop: 12,
                      paddingTop: 12,
                      borderTop: `1px solid ${G.borderSubtle}`,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 11,
                        color: G.silverFaint,
                        textTransform: 'uppercase',
                        letterSpacing: '0.8px',
                        fontFamily: "'JetBrains Mono', monospace",
                        marginBottom: 4,
                      }}
                    >
                      🌐 English Clinical Translation
                    </div>
                    <div style={{ color: G.silverMid, fontSize: 13.5, lineHeight: 1.6, fontStyle: 'italic' }}>
                      "{result.english_translation}"
                    </div>
                  </div>
                )}
              </div>

              {/* Extracted medical data */}
              {result.medical_report && (
                <div>
                  <SectionLabel style={{ marginBottom: 12 }}>Extracted Medical Data (Gemini 2.5)</SectionLabel>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                      gap: 10,
                    }}
                  >
                    <DataPill label="Patient Name" value={result.medical_report.patient_name} />
                    <DataPill
                      label="Age / Gender"
                      value={
                        result.medical_report.age
                          ? `${result.medical_report.age} yrs / ${result.medical_report.gender || '—'}`
                          : null
                      }
                    />
                    <DataPill label="Symptoms Duration" value={result.medical_report.duration} />
                    <DataPill label="Diagnosis" value={result.medical_report.suggested_diagnosis} />
                  </div>

                  {/* Symptoms */}
                  {result.medical_report.symptoms?.length > 0 && (
                    <div style={{ marginTop: 14 }}>
                      <div
                        style={{
                          fontSize: 11,
                          color: G.silverFaint,
                          marginBottom: 8,
                          fontWeight: 700,
                          letterSpacing: '1px',
                          textTransform: 'uppercase',
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        Identified Symptoms
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
                        {result.medical_report.symptoms.map((s, i) => (
                          <Tag key={i}>{s}</Tag>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Recommended Tests */}
                  {result.medical_report.recommended_tests?.length > 0 && (
                    <div style={{ marginTop: 14 }}>
                      <div
                        style={{
                          fontSize: 11,
                          color: G.silverFaint,
                          marginBottom: 8,
                          fontWeight: 700,
                          letterSpacing: '1px',
                          textTransform: 'uppercase',
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        Recommended Diagnostic Tests
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
                        {result.medical_report.recommended_tests.map((t, i) => (
                          <Tag key={i} style={{ background: G.surface3 }}>
                            {t}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Prescription */}
                  {result.medical_report.prescription && (
                    <div
                      style={{
                        marginTop: 14,
                        background: G.surface2,
                        border: `1px solid ${G.borderSubtle}`,
                        borderRadius: 8,
                        padding: '12px 16px',
                      }}
                    >
                      <div
                        style={{
                          fontSize: 11,
                          color: G.silverFaint,
                          marginBottom: 6,
                          fontWeight: 700,
                          letterSpacing: '1px',
                          textTransform: 'uppercase',
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        Prescribed Medication
                      </div>
                      <div
                        style={{
                          color: G.white,
                          fontSize: 13,
                          lineHeight: 1.6,
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        {result.medical_report.prescription}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Action buttons */}
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
                {result.pdf_url ? (
                  <a
                    href={`${API_BASE}${result.pdf_url}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      flex: '1 1 240px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                      background: G.white,
                      color: G.pitchBlack,
                      borderRadius: 8,
                      padding: '12px 20px',
                      fontWeight: 700,
                      fontSize: 14,
                      textDecoration: 'none',
                      transition: 'opacity 0.15s ease',
                    }}
                  >
                    📄 Download Clinical PDF Report ↓
                  </a>
                ) : sv?.verified ? (
                  <div
                    style={{
                      width: '100%',
                      background: G.surface2,
                      border: `1px solid ${G.borderSubtle}`,
                      borderRadius: 8,
                      padding: '12px 16px',
                      color: G.silverMuted,
                      fontSize: 13,
                    }}
                  >
                    ⚠ Transcript did not contain enough clinical structure to generate a PDF.
                  </div>
                ) : null}

                <button
                  id="record-again-btn"
                  onClick={resetRecorder}
                  style={{
                    flex: '1 1 180px',
                    background: G.surface2,
                    color: G.silverMid,
                    border: `1px solid ${G.borderDefault}`,
                    borderRadius: 8,
                    padding: '12px 20px',
                    fontWeight: 600,
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  🎤 Record Another Patient
                </button>
              </div>
            </div>
          )}

          {error && (
            <div
              style={{
                marginTop: 14,
                background: G.surface2,
                border: `1px solid ${G.borderStrong}`,
                borderRadius: 8,
                padding: '12px 16px',
                color: G.white,
                fontSize: 13,
              }}
            >
              ⚠ {error}
            </div>
          )}
        </Card>

        {/* ── REPORT HISTORY CARD ────────────────────────────────────────────── */}
        <Card>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 10,
              marginBottom: showHistory ? 16 : 0,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <SectionLabel>Clinical Report History</SectionLabel>
              <Tag>{history.length}</Tag>
            </div>
            <button
              onClick={() => setShowHistory(p => !p)}
              style={{
                background: G.surface2,
                border: `1px solid ${G.borderDefault}`,
                color: G.silverMid,
                borderRadius: 7,
                padding: '6px 14px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {showHistory ? 'Hide History' : 'Show History'}
            </button>
          </div>

          {showHistory && history.length === 0 && (
            <p
              style={{
                color: G.silverFaint,
                textAlign: 'center',
                margin: '16px 0 6px',
                fontSize: 13,
              }}
            >
              No verified patient reports on file yet.
            </p>
          )}

          {showHistory && (
            <div
              className="history-scroller"
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                maxHeight: 380,
                overflowY: 'auto',
                overflowX: 'hidden',
                paddingRight: 6,
              }}
            >
              {history.map(r => (
                <div
                  key={r.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: G.surface2,
                    border: `1px solid ${G.borderSubtle}`,
                    borderRadius: 8,
                    padding: '12px 16px',
                    flexWrap: 'wrap',
                    gap: 12,
                  }}
                >
                  <div style={{ flex: '1 1 200px', minWidth: 0 }}>
                    <div
                      style={{
                        fontWeight: 600,
                        fontSize: 13.5,
                        color: G.white,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {r.patient_name || 'Anonymous Patient'}
                      {r.age && (
                        <span style={{ color: G.silverFaint, fontWeight: 400 }}> · {r.age} yrs</span>
                      )}
                      {r.gender && (
                        <span style={{ color: G.silverFaint, fontWeight: 400 }}> ({r.gender})</span>
                      )}
                    </div>
                    <div
                      style={{
                        color: G.silverFaint,
                        fontSize: 11,
                        marginTop: 3,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {new Date(r.timestamp).toLocaleString()}
                    </div>
                    {r.diagnosis && (
                      <div style={{ color: G.silverMid, fontSize: 11, marginTop: 4 }}>
                        Dx: {r.diagnosis}
                      </div>
                    )}
                  </div>
                  <a
                    href={`${API_BASE}/api/report/download/${r.id}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      background: G.surface3,
                      border: `1px solid ${G.borderDefault}`,
                      color: G.white,
                      borderRadius: 6,
                      padding: '6px 14px',
                      fontSize: 12,
                      textDecoration: 'none',
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    Download PDF ↗
                  </a>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* ── FOOTER ────────────────────────────────────────────────────────── */}
        <footer style={{ textAlign: 'center', marginTop: 10 }}>
          <p
            style={{
              color: G.silverFaint,
              fontSize: 11,
              fontFamily: "'JetBrains Mono', monospace",
              letterSpacing: '0.3px',
              margin: 0,
            }}
          >
            VoiceMedic AI · Whisper ASR · ECAPA-TDNN Biometrics · Gemini 2.5 Flash · ReportLab · FastAPI
          </p>
        </footer>
      </main>
    </div>
  );
}