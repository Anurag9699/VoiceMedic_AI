"""
Audio processing utilities for the Voice-Controlled Payment System.
Handles file saving, format validation, and conversion to 16kHz mono WAV
using the system ffmpeg binary (required by ASR models like Whisper).
"""

import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import UploadFile

# Accepted MIME types from browser MediaRecorder
ALLOWED_CONTENT_TYPES = {
    "audio/webm",
    "audio/webm;codecs=opus",
    "audio/ogg",
    "audio/ogg;codecs=opus",
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/mp4",
    "audio/mpeg",
}

MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB


def validate_audio_content_type(content_type: str) -> bool:
    """Return True if the MIME type is an accepted audio format."""
    ct = content_type.lower().strip()
    return any(ct.startswith(allowed.split(";")[0]) for allowed in ALLOWED_CONTENT_TYPES)


async def save_upload_file(file: UploadFile, target_dir: Path) -> tuple[Path, int]:
    """
    Stream the uploaded file to disk inside target_dir.
    Returns (saved_path, size_in_bytes).
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "audio.webm").suffix or ".webm"
    unique_name = f"{uuid.uuid4().hex}{suffix}"
    dest_path = target_dir / unique_name

    size = 0
    with dest_path.open("wb") as out:
        while chunk := await file.read(8192):
            if size + len(chunk) > MAX_FILE_SIZE_BYTES:
                dest_path.unlink(missing_ok=True)
                raise ValueError(
                    f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB."
                )
            out.write(chunk)
            size += len(chunk)

    return dest_path, size


def convert_to_16k_mono_wav(source_path: Path, output_dir: Path) -> tuple[Path, float]:
    """
    Convert any audio file to 16kHz, mono-channel, 16-bit PCM WAV using ffmpeg.
    This is the standard format expected by Whisper and most ASR models.

    Uses a 3-attempt fallback strategy to handle Chrome on macOS which records
    WebM files with incomplete EBML headers that confuse FFmpeg's auto-detection.

    Returns (converted_wav_path, duration_seconds).
    Raises RuntimeError if ffmpeg is not found or all attempts fail.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError(
            "ffmpeg is not installed or not on PATH. "
            "Install it via: brew install ffmpeg"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    wav_path = output_dir / (source_path.stem + "_16k.wav")

    # Shared output args
    out_args = ["-ar", "16000", "-ac", "1", "-sample_fmt", "s16", "-y", str(wav_path)]

    # ── Detect actual format from magic bytes (don't trust the extension) ──────
    # Chrome on macOS sometimes writes audio/mp4 data with a .webm extension.
    MAGIC_FMT = {
        b"\x1a\x45\xdf\xa3": "webm",   # EBML — real WebM/Matroska
        b"ftyp":             "mp4",    # MP4/M4A (bytes 4-7)
        b"OggS":             "ogg",    # Ogg container
        b"RIFF":             "wav",    # WAV
    }
    fmt_hint = None
    try:
        with open(source_path, "rb") as f:
            header = f.read(12)
        if header[:4] == b"\x1a\x45\xdf\xa3":
            fmt_hint = "webm"
        elif header[4:8] == b"ftyp":
            fmt_hint = "mp4"
        elif header[:4] == b"OggS":
            fmt_hint = "ogg"
        elif header[:4] == b"RIFF":
            fmt_hint = "wav"
        else:
            # Fall back to extension
            EXT_FMT = {".webm": "webm", ".ogg": "ogg", ".mp4": "mp4", ".m4a": "mp4"}
            fmt_hint = EXT_FMT.get(source_path.suffix.lower())
    except OSError:
        pass

    # Attempt 1: explicit format + error tolerance (fixes Chrome EBML issue)
    attempts = []
    if fmt_hint:
        attempts.append([
            ffmpeg_bin,
            "-fflags", "+discardcorrupt+genpts",
            "-err_detect", "ignore_err",
            "-f", fmt_hint,
            "-i", str(source_path),
        ] + out_args)

    # Attempt 2: error tolerance only, no format hint
    attempts.append([
        ffmpeg_bin,
        "-fflags", "+discardcorrupt+genpts",
        "-err_detect", "ignore_err",
        "-i", str(source_path),
    ] + out_args)

    # Attempt 3: plain vanilla
    attempts.append([ffmpeg_bin, "-y", "-i", str(source_path)] + out_args[:-2] + [out_args[-1]])

    last_code, last_stderr = -1, ""
    for cmd in attempts:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        last_code, last_stderr = res.returncode, res.stderr
        if res.returncode == 0 and wav_path.exists() and wav_path.stat().st_size > 100:
            return wav_path, _get_audio_duration(wav_path)

    raise RuntimeError(f"ffmpeg conversion failed (exit code {last_code}):\n{last_stderr}")


def _get_audio_duration(wav_path: Path) -> float:
    """Use ffprobe to read audio duration in seconds. Returns 0.0 on failure."""
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        return 0.0

    try:
        result = subprocess.run(
            [
                ffprobe_bin,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(wav_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return round(float(result.stdout.strip()), 2)
    except (ValueError, subprocess.TimeoutExpired):
        return 0.0
