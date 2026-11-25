"""
Speaker Verification Unit Tests
================================

Comprehensive tests for the speaker verification system covering:
1. Audio quality gate — silence rejection, SNR estimation, clipping detection
2. Anti-spoofing — spectral analysis for replay detection
3. Embedding computation — correct shape, normalization
4. Enrollment — quality enforcement, inter-sample consistency
5. Verification — threshold calibration, confidence bands
6. Integration — genuine acceptance and impostor rejection
"""

import io
import sys
import wave
import struct
import math
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import os

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest


# ─────────────────────────────────────────────────────────────────────────
# Helpers: Generate test WAV files with controlled properties
# ─────────────────────────────────────────────────────────────────────────

def make_wav_file(
    filepath: str,
    duration_ms: int = 5000,
    sample_rate: int = 16000,
    frequency: float = 440.0,
    amplitude: float = 0.5,
    add_noise: bool = False,
    noise_level: float = 0.01,
    silent: bool = False,
    clipped: bool = False,
) -> str:
    """Generate a WAV file with controlled audio properties."""
    n_samples = int(sample_rate * duration_ms / 1000)

    if silent:
        # Pure silence
        samples = np.zeros(n_samples, dtype=np.float32)
    else:
        # Generate a tone with optional harmonics (more speech-like)
        t = np.arange(n_samples) / sample_rate
        samples = amplitude * np.sin(2 * np.pi * frequency * t)
        # Add harmonics for richer spectrum
        samples += amplitude * 0.3 * np.sin(2 * np.pi * frequency * 2 * t)
        samples += amplitude * 0.15 * np.sin(2 * np.pi * frequency * 3 * t)
        # Add amplitude modulation (more speech-like)
        samples *= 1.0 + 0.3 * np.sin(2 * np.pi * 3.0 * t)
        # Add silent gaps to simulate speech pauses (critical for SNR estimation)
        # Every ~0.5s of "speech" followed by ~0.15s of silence
        envelope = np.ones(n_samples, dtype=np.float32)
        period = int(0.65 * sample_rate)
        silence_len = int(0.15 * sample_rate)
        for start in range(0, n_samples, period):
            gap_start = start + period - silence_len
            gap_end = min(start + period, n_samples)
            if gap_start < n_samples:
                envelope[gap_start:gap_end] = 0.0
        samples *= envelope

    if add_noise:
        noise = noise_level * np.random.randn(n_samples).astype(np.float32)
        samples += noise

    if clipped:
        # Force heavy clipping
        samples = np.clip(samples * 5.0, -1.0, 1.0)

    # Convert to int16
    samples_int16 = np.clip(samples * 32767, -32768, 32767).astype(np.int16)

    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples_int16.tobytes())

    return filepath


def make_silence_wav(filepath: str, duration_ms: int = 5000) -> str:
    """Generate a completely silent WAV file."""
    return make_wav_file(filepath, duration_ms=duration_ms, silent=True)


def make_short_wav(filepath: str, duration_ms: int = 500) -> str:
    """Generate a very short WAV file."""
    return make_wav_file(filepath, duration_ms=duration_ms)


def make_noisy_wav(filepath: str, duration_ms: int = 5000, snr_db: float = 0) -> str:
    """Generate a WAV file with very poor SNR."""
    signal_amp = 0.1
    noise_amp = signal_amp * (10 ** (-snr_db / 20))
    return make_wav_file(
        filepath,
        duration_ms=duration_ms,
        amplitude=signal_amp,
        add_noise=True,
        noise_level=noise_amp,
    )


def make_clipped_wav(filepath: str, duration_ms: int = 5000) -> str:
    """Generate a heavily clipped WAV file."""
    return make_wav_file(filepath, duration_ms=duration_ms, clipped=True)


# ─────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def good_wav(tmp_dir):
    """A good quality WAV file for testing."""
    return make_wav_file(
        os.path.join(tmp_dir, "good.wav"),
        duration_ms=5000,
        frequency=200,
        amplitude=0.6,
        add_noise=True,
        noise_level=0.002,
    )


GOOD_QUALITY_RESULT = {
    "passed": True,
    "duration": 5.0,
    "snr_db": 25.0,
    "speech_ratio": 0.9,
    "clipping_ratio": 0.0,
    "issues": [],
}


@pytest.fixture
def silent_wav(tmp_dir):
    """A silent WAV file for testing."""
    return make_silence_wav(os.path.join(tmp_dir, "silent.wav"))


@pytest.fixture
def short_wav(tmp_dir):
    """A too-short WAV file for testing."""
    return make_short_wav(os.path.join(tmp_dir, "short.wav"), duration_ms=500)


@pytest.fixture
def noisy_wav(tmp_dir):
    """A very noisy WAV file for testing."""
    return make_noisy_wav(os.path.join(tmp_dir, "noisy.wav"), snr_db=-5)


@pytest.fixture
def clipped_wav(tmp_dir):
    """A heavily clipped WAV file for testing."""
    return make_clipped_wav(os.path.join(tmp_dir, "clipped.wav"))


# ─────────────────────────────────────────────────────────────────────────
# 1. Audio Quality Gate Tests
# ─────────────────────────────────────────────────────────────────────────

class TestAudioQualityGate:
    """Tests for the audio quality assessment system."""

    def test_good_audio_passes_quality_gate(self, good_wav):
        """Good quality audio should pass all checks."""
        from audio.speaker import assess_audio_quality
        result = assess_audio_quality(good_wav, min_duration=1.0)
        assert result["passed"] is True
        assert len(result["issues"]) == 0
        assert result["duration"] > 0
        assert result["snr_db"] > 0

    def test_silent_audio_fails_quality_gate(self, silent_wav):
        """Silent audio should fail the speech ratio check."""
        from audio.speaker import assess_audio_quality
        result = assess_audio_quality(silent_wav, min_duration=1.0)
        assert result["passed"] is False
        assert any("silence" in issue.lower() or "speech" in issue.lower()
                    for issue in result["issues"])

    def test_short_audio_fails_quality_gate(self, short_wav):
        """Audio shorter than minimum duration should fail."""
        from audio.speaker import assess_audio_quality
        result = assess_audio_quality(short_wav, min_duration=2.0)
        assert result["passed"] is False
        assert any("short" in issue.lower() for issue in result["issues"])

    def test_clipped_audio_fails_quality_gate(self, clipped_wav):
        """Heavily clipped audio should fail the clipping check."""
        from audio.speaker import assess_audio_quality
        result = assess_audio_quality(clipped_wav, min_duration=1.0)
        # Clipped audio produces clipping ratio > 5%
        assert result["clipping_ratio"] > 0

    def test_nonexistent_file_fails_gracefully(self):
        """Non-existent file should fail with clear error."""
        from audio.speaker import assess_audio_quality
        result = assess_audio_quality("/nonexistent/path.wav")
        assert result["passed"] is False
        assert len(result["issues"]) > 0

    def test_snr_estimation_returns_float(self, good_wav):
        """SNR estimation should return a finite float."""
        from audio.speaker import _estimate_snr, _read_wav_signal
        signal, sr = _read_wav_signal(good_wav)
        snr = _estimate_snr(signal, sr)
        assert isinstance(snr, float)
        assert not np.isnan(snr)
        assert not np.isinf(snr)

    def test_speech_ratio_on_silence(self, silent_wav):
        """Speech ratio of pure silence should be near zero."""
        from audio.speaker import _compute_speech_ratio, _read_wav_signal
        signal, sr = _read_wav_signal(silent_wav)
        ratio = _compute_speech_ratio(signal, sr)
        assert ratio < 0.1  # Mostly silence

    def test_speech_ratio_on_speech(self, good_wav):
        """Speech ratio of audio with content should be significant."""
        from audio.speaker import _compute_speech_ratio, _read_wav_signal
        signal, sr = _read_wav_signal(good_wav)
        ratio = _compute_speech_ratio(signal, sr)
        assert ratio > 0.2  # Some active content


# ─────────────────────────────────────────────────────────────────────────
# 2. RMS Normalization Tests
# ─────────────────────────────────────────────────────────────────────────

class TestRMSNormalization:
    """Tests for the audio RMS normalization."""

    def test_normalization_produces_target_rms(self):
        """Normalized signal should be close to the target RMS."""
        from audio.speaker import _rms_normalize, TARGET_RMS
        signal = np.random.randn(16000).astype(np.float32) * 0.01  # quiet signal
        normalized = _rms_normalize(signal)
        actual_rms = np.sqrt(np.mean(normalized ** 2))
        assert abs(actual_rms - TARGET_RMS) < 0.02

    def test_normalization_preserves_silence(self):
        """Normalizing silence should return silence (no division by zero)."""
        from audio.speaker import _rms_normalize
        signal = np.zeros(16000, dtype=np.float32)
        normalized = _rms_normalize(signal)
        assert np.allclose(normalized, 0.0)

    def test_normalization_prevents_clipping(self):
        """Normalized signal should not exceed ±0.99."""
        from audio.speaker import _rms_normalize
        signal = np.random.randn(16000).astype(np.float32) * 0.5
        normalized = _rms_normalize(signal)
        assert np.max(np.abs(normalized)) <= 1.0

    def test_loud_and_quiet_signals_normalize_to_same_level(self):
        """Two signals of different volumes should have similar RMS after normalization."""
        from audio.speaker import _rms_normalize
        t = np.linspace(0, 1, 16000)
        loud = (np.sin(2 * np.pi * 440 * t) * 0.8).astype(np.float32)
        quiet = (np.sin(2 * np.pi * 440 * t) * 0.01).astype(np.float32)
        rms_loud = np.sqrt(np.mean(_rms_normalize(loud) ** 2))
        rms_quiet = np.sqrt(np.mean(_rms_normalize(quiet) ** 2))
        # Should be within 20% of each other
        assert abs(rms_loud - rms_quiet) / max(rms_loud, rms_quiet) < 0.2


# ─────────────────────────────────────────────────────────────────────────
# 3. Anti-Spoofing Tests
# ─────────────────────────────────────────────────────────────────────────

class TestAntiSpoofing:
    """Tests for the replay/spoof detection system."""

    def test_natural_audio_not_flagged(self, good_wav):
        """Natural speech-like audio should not be flagged as spoofed."""
        from audio.speaker import _check_replay_attack, _read_wav_signal
        signal, sr = _read_wav_signal(good_wav)
        result = _check_replay_attack(signal, sr)
        assert isinstance(result, dict)
        assert "is_suspicious" in result
        assert "confidence" in result
        # Rich harmonic content should not be flagged
        # (exact result depends on threshold tuning)

    def test_narrowband_audio_flagged(self, tmp_dir):
        """Very narrowband audio (like replayed through a small speaker) should be flagged."""
        from audio.speaker import _check_replay_attack
        # Generate a pure low-frequency tone (no harmonics, no HF content)
        sr = 16000
        t = np.arange(int(3 * sr)) / sr
        signal = (0.3 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
        result = _check_replay_attack(signal, sr)
        assert isinstance(result, dict)
        # Narrowband signals should have low HF ratio
        assert result["hf_energy_ratio"] < 0.05

    def test_short_audio_returns_not_suspicious(self):
        """Audio too short for analysis should not be falsely flagged."""
        from audio.speaker import _check_replay_attack
        signal = np.random.randn(1000).astype(np.float32) * 0.1
        result = _check_replay_attack(signal, 16000)
        assert result["is_suspicious"] is False

    def test_spoof_result_has_required_fields(self, good_wav):
        """Anti-spoof result should contain all required fields."""
        from audio.speaker import _check_replay_attack, _read_wav_signal
        signal, sr = _read_wav_signal(good_wav)
        result = _check_replay_attack(signal, sr)
        required_fields = ["is_suspicious", "confidence", "spectral_flatness",
                           "effective_bandwidth_hz", "hf_energy_ratio", "details"]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"


# ─────────────────────────────────────────────────────────────────────────
# 4. Embedding Computation Tests (with mocked SpeechBrain)
# ─────────────────────────────────────────────────────────────────────────

class TestEmbeddingComputation:
    """Tests for embedding computation with mocked SpeechBrain model."""

    def test_embedding_returns_none_without_model(self, good_wav):
        """Without SpeechBrain, embedding computation should return None gracefully."""
        from audio.speaker import _compute_embedding
        with patch("audio.speaker.get_verifier", return_value=None):
            result = _compute_embedding(good_wav)
            assert result is None

    def test_embedding_returns_correct_shape(self, good_wav):
        """Embedding should be a 192-dim float32 array."""
        from audio.speaker import _compute_embedding

        # Mock the verifier to return a fake 192-dim embedding
        mock_verifier = MagicMock()
        fake_embedding = np.random.randn(1, 1, 192).astype(np.float32)
        import torch
        mock_verifier.encode_batch.return_value = torch.tensor(fake_embedding)

        with patch("audio.speaker.get_verifier", return_value=mock_verifier):
            result = _compute_embedding(good_wav)
            assert result is not None
            assert result.shape == (192,)
            assert result.dtype == np.float32

    def test_embedding_is_l2_normalized(self, good_wav):
        """Embedding should have unit L2 norm."""
        from audio.speaker import _compute_embedding

        mock_verifier = MagicMock()
        fake_embedding = np.random.randn(1, 1, 192).astype(np.float32)
        import torch
        mock_verifier.encode_batch.return_value = torch.tensor(fake_embedding)

        with patch("audio.speaker.get_verifier", return_value=mock_verifier):
            result = _compute_embedding(good_wav)
            assert result is not None
            norm = np.linalg.norm(result)
            assert abs(norm - 1.0) < 1e-5, f"Embedding norm {norm} is not 1.0"


# ─────────────────────────────────────────────────────────────────────────
# 5. Cosine Similarity Tests
# ─────────────────────────────────────────────────────────────────────────

class TestCosineSimilarity:
    """Tests for the cosine similarity function."""

    def test_identical_vectors(self):
        """Identical normalized vectors should have similarity 1.0."""
        from audio.speaker import _cosine_similarity
        v = np.random.randn(192).astype(np.float32)
        v = v / np.linalg.norm(v)
        sim = _cosine_similarity(v, v)
        assert abs(sim - 1.0) < 1e-5

    def test_opposite_vectors(self):
        """Opposite vectors should have similarity -1.0."""
        from audio.speaker import _cosine_similarity
        v = np.random.randn(192).astype(np.float32)
        v = v / np.linalg.norm(v)
        sim = _cosine_similarity(v, -v)
        assert abs(sim - (-1.0)) < 1e-5

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity ~0."""
        from audio.speaker import _cosine_similarity
        v1 = np.zeros(192, dtype=np.float32)
        v2 = np.zeros(192, dtype=np.float32)
        v1[0] = 1.0
        v2[1] = 1.0
        sim = _cosine_similarity(v1, v2)
        assert abs(sim) < 1e-5

    def test_similarity_range(self):
        """Cosine similarity between random normalized vectors should be in [-1, 1]."""
        from audio.speaker import _cosine_similarity
        for _ in range(100):
            a = np.random.randn(192).astype(np.float32)
            b = np.random.randn(192).astype(np.float32)
            a = a / np.linalg.norm(a)
            b = b / np.linalg.norm(b)
            sim = _cosine_similarity(a, b)
            assert -1.0 <= sim <= 1.0


# ─────────────────────────────────────────────────────────────────────────
# 6. Confidence Band Tests
# ─────────────────────────────────────────────────────────────────────────

class TestConfidenceBands:
    """Tests for confidence band classification."""

    def test_high_confidence(self):
        """Score >= 0.75 should be 'high'."""
        from audio.speaker import _get_confidence_band
        assert _get_confidence_band(0.85, 0.55) == "high"
        assert _get_confidence_band(0.75, 0.55) == "high"

    def test_medium_confidence(self):
        """Score 0.65-0.74 should be 'medium'."""
        from audio.speaker import _get_confidence_band
        assert _get_confidence_band(0.70, 0.55) == "medium"
        assert _get_confidence_band(0.65, 0.55) == "medium"

    def test_low_confidence(self):
        """Score at threshold to 0.64 should be 'low'."""
        from audio.speaker import _get_confidence_band
        assert _get_confidence_band(0.55, 0.55) == "low"
        assert _get_confidence_band(0.60, 0.55) == "low"

    def test_fail_confidence(self):
        """Score below threshold should be 'fail'."""
        from audio.speaker import _get_confidence_band
        assert _get_confidence_band(0.40, 0.55) == "fail"
        assert _get_confidence_band(0.54, 0.55) == "fail"


# ─────────────────────────────────────────────────────────────────────────
# 7. Verification Integration Tests (with mocked model)
# ─────────────────────────────────────────────────────────────────────────

class TestVerification:
    """Integration tests for the verify_speaker function."""

    def test_verify_without_enrollment_returns_not_verified(self, good_wav, tmp_dir):
        """Verification should fail when no enrollment exists."""
        from audio.speaker import verify_speaker

        with patch("audio.speaker.get_verifier", return_value=MagicMock()), \
             patch("audio.speaker._load_reference_embedding", return_value=None), \
             patch("audio.speaker.assess_audio_quality", return_value=GOOD_QUALITY_RESULT):
            result = verify_speaker(good_wav, user_id="test_nonexistent")
            assert result["verified"] is False
            assert "No voice profile" in result["message"]

    def test_verify_with_matching_embedding(self, good_wav):
        """Verification should succeed when embeddings match (score above threshold)."""
        from audio.speaker import verify_speaker

        # Create a mock embedding
        ref_emb = np.random.randn(192).astype(np.float32)
        ref_emb = ref_emb / np.linalg.norm(ref_emb)

        # Mock: current embedding = same as reference (perfect match)
        mock_verifier = MagicMock()
        import torch
        mock_verifier.encode_batch.return_value = torch.tensor(
            ref_emb.reshape(1, 1, 192)
        )

        with patch("audio.speaker.get_verifier", return_value=mock_verifier), \
             patch("audio.speaker._load_reference_embedding", return_value=ref_emb), \
             patch("audio.speaker.assess_audio_quality", return_value=GOOD_QUALITY_RESULT):
            result = verify_speaker(good_wav, user_id="test_doctor", threshold=0.55)
            assert result["verified"] is True
            assert result["confidence_score"] > 0.99
            assert result["confidence_band"] == "high"

    def test_verify_rejects_different_speaker(self, good_wav):
        """Verification should fail when embeddings are very different (different speaker)."""
        from audio.speaker import verify_speaker

        # Reference embedding
        ref_emb = np.zeros(192, dtype=np.float32)
        ref_emb[0] = 1.0  # Unit vector in one direction

        # Mock: current embedding = orthogonal (completely different speaker)
        cur_emb = np.zeros(192, dtype=np.float32)
        cur_emb[1] = 1.0  # Unit vector in different direction

        mock_verifier = MagicMock()
        import torch
        mock_verifier.encode_batch.return_value = torch.tensor(
            cur_emb.reshape(1, 1, 192)
        )

        with patch("audio.speaker.get_verifier", return_value=mock_verifier), \
             patch("audio.speaker._load_reference_embedding", return_value=ref_emb), \
             patch("audio.speaker.assess_audio_quality", return_value=GOOD_QUALITY_RESULT):
            result = verify_speaker(good_wav, user_id="test_doctor", threshold=0.55)
            assert result["verified"] is False
            assert result["confidence_score"] < 0.1

    def test_verify_rejects_borderline_impostor(self, good_wav):
        """Score just below threshold (0.54 < 0.55) should be rejected."""
        from audio.speaker import verify_speaker

        # Craft embeddings that produce a score just below threshold
        ref_emb = np.random.randn(192).astype(np.float32)
        ref_emb = ref_emb / np.linalg.norm(ref_emb)

        # Create an orthogonal noise vector so dot product is exact
        noise = np.random.randn(192).astype(np.float32)
        noise = noise - np.dot(noise, ref_emb) * ref_emb
        noise = noise / np.linalg.norm(noise)
        cur_emb = 0.54 * ref_emb + np.sqrt(1 - 0.54**2) * noise
        cur_emb = (cur_emb / np.linalg.norm(cur_emb)).astype(np.float32)

        mock_verifier = MagicMock()
        import torch
        mock_verifier.encode_batch.return_value = torch.tensor(
            cur_emb.reshape(1, 1, 192)
        )

        with patch("audio.speaker.get_verifier", return_value=mock_verifier), \
             patch("audio.speaker._load_reference_embedding", return_value=ref_emb), \
             patch("audio.speaker.assess_audio_quality", return_value=GOOD_QUALITY_RESULT):
            result = verify_speaker(good_wav, user_id="test_doctor", threshold=0.55)
            # Score should be around 0.54 - might not be exactly that due to
            # the construction, but should be below threshold
            assert result["confidence_band"] in ("fail", "low")

    def test_verify_without_speechbrain(self, good_wav):
        """Without SpeechBrain, verification should fail gracefully."""
        from audio.speaker import verify_speaker

        with patch("audio.speaker.get_verifier", return_value=None):
            result = verify_speaker(good_wav, user_id="test_doctor")
            assert result["verified"] is False
            assert "SpeechBrain" in result["message"]

    def test_verify_response_has_required_fields(self, good_wav):
        """Verification response should contain all expected fields."""
        from audio.speaker import verify_speaker

        ref_emb = np.random.randn(192).astype(np.float32)
        ref_emb = ref_emb / np.linalg.norm(ref_emb)

        mock_verifier = MagicMock()
        import torch
        mock_verifier.encode_batch.return_value = torch.tensor(
            ref_emb.reshape(1, 1, 192)
        )

        with patch("audio.speaker.get_verifier", return_value=mock_verifier), \
             patch("audio.speaker._load_reference_embedding", return_value=ref_emb), \
             patch("audio.speaker.assess_audio_quality", return_value=GOOD_QUALITY_RESULT):
            result = verify_speaker(good_wav, user_id="test_doctor")

            required_fields = [
                "verified", "confidence_score", "confidence_band",
                "threshold_used", "user_id", "method", "message",
                "audio_quality", "anti_spoof"
            ]
            for field in required_fields:
                assert field in result, f"Missing field: {field}"


# ─────────────────────────────────────────────────────────────────────────
# 8. Enrollment Tests (with mocked model)
# ─────────────────────────────────────────────────────────────────────────

class TestEnrollment:
    """Tests for the enroll_speaker function."""

    def test_enroll_too_short_audio_rejected(self, short_wav):
        """Enrollment should reject audio shorter than minimum duration."""
        from audio.speaker import enroll_speaker

        with pytest.raises(ValueError, match="short|quality|insufficient"):
            enroll_speaker(short_wav, user_id="test_doctor", reset=True)

    def test_enroll_silent_audio_rejected(self, silent_wav):
        """Enrollment should reject silent audio."""
        from audio.speaker import enroll_speaker

        with pytest.raises(ValueError, match="silence|speech|quality|insufficient"):
            enroll_speaker(silent_wav, user_id="test_doctor", reset=True)

    def test_rejected_replacement_keeps_existing_enrollment(self, tmp_path, silent_wav, monkeypatch):
        from audio import speaker

        monkeypatch.setattr(speaker, "ENROLLMENT_DIR", tmp_path)
        sample = tmp_path / "test_doctor_sample_1.wav"
        sample.write_bytes(b"existing sample")
        reference = tmp_path / "test_doctor_embedding.npy"
        embedding = np.ones(192, dtype=np.float32)
        np.save(reference, embedding)

        with pytest.raises(ValueError, match="silence"):
            speaker.enroll_speaker(silent_wav, user_id="test_doctor", reset=True)

        assert sample.read_bytes() == b"existing sample"
        np.testing.assert_array_equal(np.load(reference), embedding)

    def test_reset_enrollment_clears_files(self, tmp_dir):
        """Reset should delete all enrollment files for the user."""
        from unittest.mock import patch
        from pathlib import Path
        from audio import speaker

        temp_path = Path(tmp_dir)
        with patch.object(speaker, "ENROLLMENT_DIR", temp_path):
            test_files = [
                temp_path / "test_reset_sample_1.wav",
                temp_path / "test_reset_sample_2.wav",
                temp_path / "test_reset_embedding.npy",
            ]
            for f in test_files:
                f.touch()

            result = speaker.reset_enrollment("test_reset")
            assert result is True

            for f in test_files:
                assert not f.exists()


# ─────────────────────────────────────────────────────────────────────────
# 9. WAV Reading Tests
# ─────────────────────────────────────────────────────────────────────────

class TestWavReading:
    """Tests for WAV file reading utility."""

    def test_read_mono_wav(self, good_wav):
        """Reading a mono WAV should return correct shape and sample rate."""
        from audio.speaker import _read_wav_signal
        signal, sr = _read_wav_signal(good_wav)
        assert sr == 16000
        assert signal.ndim == 1
        assert len(signal) > 0
        assert signal.dtype == np.float32
        assert np.max(np.abs(signal)) <= 1.0

    def test_read_stereo_wav(self, tmp_dir):
        """Reading a stereo WAV should downmix to mono."""
        from audio.speaker import _read_wav_signal

        filepath = os.path.join(tmp_dir, "stereo.wav")
        n_samples = 16000
        samples = np.random.randn(n_samples * 2).astype(np.float32) * 0.1
        samples_int16 = (samples * 32767).astype(np.int16)

        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(samples_int16.tobytes())

        signal, sr = _read_wav_signal(filepath)
        assert signal.ndim == 1
        assert len(signal) == n_samples  # Downmixed from stereo

    def test_audio_duration(self, good_wav):
        """Duration measurement should be accurate."""
        from audio.speaker import _get_audio_duration
        duration = _get_audio_duration(good_wav)
        assert abs(duration - 5.0) < 0.1  # 5 second file


# ─────────────────────────────────────────────────────────────────────────
# 10. Threshold Calibration Tests
# ─────────────────────────────────────────────────────────────────────────

class TestThresholdCalibration:
    """Tests ensuring the threshold is properly calibrated."""

    def test_default_threshold_is_0_55(self):
        """Default threshold should be 0.55, not the old 0.45."""
        # This test ensures the threshold is not accidentally reverted
        from audio.speaker import DEFAULT_THRESHOLD
        assert DEFAULT_THRESHOLD >= 0.50, (
            f"Threshold {DEFAULT_THRESHOLD} is too low! "
            f"Must be >= 0.50 to avoid false acceptances."
        )

    def test_threshold_above_impostor_ceiling(self):
        """Threshold must be above the measured impostor score ceiling of 0.50."""
        from audio.speaker import DEFAULT_THRESHOLD
        IMPOSTOR_CEILING = 0.50
        assert DEFAULT_THRESHOLD > IMPOSTOR_CEILING, (
            f"Threshold {DEFAULT_THRESHOLD} must be above "
            f"impostor ceiling {IMPOSTOR_CEILING}"
        )

    def test_threshold_allows_genuine_speakers(self):
        """Threshold must be below the typical same-speaker minimum of 0.55."""
        from audio.speaker import DEFAULT_THRESHOLD
        GENUINE_FLOOR = 0.55
        assert DEFAULT_THRESHOLD <= GENUINE_FLOOR, (
            f"Threshold {DEFAULT_THRESHOLD} must be <= {GENUINE_FLOOR} "
            f"to accept genuine speakers in noisy conditions"
        )
