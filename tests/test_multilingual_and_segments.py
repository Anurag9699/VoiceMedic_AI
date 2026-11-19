"""
Tests for new Multilingual Indian Languages and Segment-Level Speaker Verification.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app, SUPPORTED_LANGUAGES
from audio.speaker import (
    _get_dynamic_threshold,
    _compute_enrollment_quality_score,
    _compute_segment_embeddings,
    DEFAULT_THRESHOLD,
)
from audio.transcriber import MEDICAL_PROMPTS


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Indian Languages & Multilingual Tests
# ---------------------------------------------------------------------------

def test_get_languages_endpoint(client):
    """GET /api/languages should return supported Indian languages and auto-detect."""
    response = client.get("/api/languages")
    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    total_count = data.get("total", data.get("count", 0))
    assert total_count >= 13

    # Check key Indian languages are present
    codes = [item["code"] for item in data["languages"]]
    for expected in ["auto", "en", "hi", "mr", "ta", "te", "gu", "kn", "ml", "bn", "pa", "ur", "or"]:
        assert expected in codes


def test_medical_prompts_configured_for_indian_languages():
    """Verify medical domain prompts exist for Hindi, Marathi, Tamil, Telugu, etc."""
    for lang in ["hi", "mr", "ta", "te", "gu", "kn", "ml", "bn", "pa", "ur", "or", "en", None]:
        assert lang in MEDICAL_PROMPTS
        assert len(MEDICAL_PROMPTS[lang]) > 20


# ---------------------------------------------------------------------------
# Dynamic Threshold Tests
# ---------------------------------------------------------------------------

def test_dynamic_threshold_clean_audio():
    """High SNR audio (>15 dB) should reduce threshold for user convenience."""
    quality = {"snr_db": 22.0, "clipping_ratio": 0.0}
    thresh = _get_dynamic_threshold(quality, enrollment_sample_count=3)
    assert thresh < DEFAULT_THRESHOLD  # Should be lower/more lenient


def test_dynamic_threshold_noisy_audio():
    """Low SNR audio (<8 dB) should raise threshold for security."""
    quality = {"snr_db": 6.0, "clipping_ratio": 0.0}
    thresh = _get_dynamic_threshold(quality, enrollment_sample_count=2)
    assert thresh > DEFAULT_THRESHOLD  # Should be higher/stricter


def test_dynamic_threshold_bounds():
    """Threshold must remain strictly within [0.45, 0.70]."""
    extreme_clean = {"snr_db": 50.0, "clipping_ratio": 0.0}
    extreme_noisy = {"snr_db": -10.0, "clipping_ratio": 0.0}

    t_low = _get_dynamic_threshold(extreme_clean, enrollment_sample_count=10)
    t_high = _get_dynamic_threshold(extreme_noisy, enrollment_sample_count=1)

    assert 0.45 <= t_low <= 0.70
    assert 0.45 <= t_high <= 0.70


# ---------------------------------------------------------------------------
# Enrollment Quality Score Tests
# ---------------------------------------------------------------------------

def test_enrollment_quality_score():
    """Quality score should scale with sample count, SNR, and consistency."""
    # 3 identical unit embeddings with high SNR
    emb = np.random.randn(192).astype(np.float32)
    emb = emb / np.linalg.norm(emb)
    embeddings = [emb, emb.copy(), emb.copy()]
    snrs = [20.0, 22.0, 21.0]

    score = _compute_enrollment_quality_score(embeddings, snrs)
    assert 0 <= score <= 100
    assert score >= 75  # High quality enrollment with 3 consistent samples


def test_enrollment_quality_score_single_sample():
    """Single sample gets lower score than 3 samples."""
    emb = np.random.randn(192).astype(np.float32)
    emb = emb / np.linalg.norm(emb)

    score_1 = _compute_enrollment_quality_score([emb], [18.0])
    score_3 = _compute_enrollment_quality_score([emb, emb, emb], [18.0, 18.0, 18.0])

    assert score_1 < score_3
