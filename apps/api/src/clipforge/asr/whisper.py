"""Targeted ASR using faster-whisper with word-level timestamps on candidate audio slices."""

import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import structlog

from clipforge.asr.models import CandidateTranscript, WordTimestamp
from clipforge.fusion.models import CandidateWindow
from clipforge.subtitles.models import SubtitleWord

logger = structlog.get_logger(__name__)

# In-memory cache for Faster-Whisper model
_CACHED_MODEL: Any = None
_CACHED_MODEL_NAME: str | None = None


def get_whisper_model(
    model_name: str = "base",
    device: str = "auto",
    compute_type: str = "auto",
) -> Any:
    """Load or return cached faster-whisper model."""
    global _CACHED_MODEL, _CACHED_MODEL_NAME

    if _CACHED_MODEL is not None and _CACHED_MODEL_NAME == model_name:
        return _CACHED_MODEL

    from faster_whisper import WhisperModel

    logger.info("loading_whisper_model", model=model_name, device=device)
    # CPU fallback settings
    dev = "cpu" if device in ("auto", "cpu") else device
    comp = "int8" if compute_type in ("auto", "int8") and dev == "cpu" else "float32"

    model = WhisperModel(model_name, device=dev, compute_type=comp)
    _CACHED_MODEL = model
    _CACHED_MODEL_NAME = model_name
    return model


def extract_audio_slice(audio_path: Path, start_s: float, end_s: float) -> np.ndarray:
    """Extract audio slice from file as 16kHz mono float32 numpy array."""
    duration = max(0.5, end_s - start_s)
    cmd = [
        "ffmpeg",
        "-ss",
        f"{max(0.0, start_s):.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(audio_path),
        "-f",
        "f32le",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-loglevel",
        "error",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        logger.error("ffmpeg_slice_failed", stderr=proc.stderr.decode("utf-8", errors="replace"))
        return np.zeros(0, dtype=np.float32)

    return np.frombuffer(proc.stdout, dtype=np.float32)


def transcribe_candidate_slice(
    audio_path: Path,
    cand: CandidateWindow,
    model_name: str = "base",
    device: str = "auto",
    compute_type: str = "auto",
    pad_s: float = 1.0,
) -> CandidateTranscript:
    """
    Transcribe a single candidate window with word-level timestamps in canonical source coordinates.
    """
    if not audio_path.exists():
        logger.warning("audio_file_missing_for_transcription", path=str(audio_path))
        return CandidateTranscript(candidate_id=cand.id)

    slice_start = max(0.0, cand.start_s - pad_s)
    slice_end = cand.end_s + pad_s

    audio_arr = extract_audio_slice(audio_path, slice_start, slice_end)
    if len(audio_arr) < 8000:  # < 0.5s audio
        return CandidateTranscript(candidate_id=cand.id)

    try:
        model = get_whisper_model(model_name, device, compute_type)
        segments, info = model.transcribe(
            audio_arr,
            word_timestamps=True,
            vad_filter=False,
            beam_size=3,
        )

        all_words: list[WordTimestamp] = []
        full_text_parts: list[str] = []
        word_idx = 0

        for seg in segments:
            full_text_parts.append(seg.text.strip())
            if seg.words:
                for w in seg.words:
                    w_start = round(slice_start + w.start, 3)
                    w_end = round(slice_start + w.end, 3)
                    # Only include words that fall reasonably within or close to window
                    all_words.append(
                        WordTimestamp(
                            idx=word_idx,
                            start_s=w_start,
                            end_s=w_end,
                            text=w.word.strip(),
                            confidence=round(w.probability, 3),
                        )
                    )
                    word_idx += 1

        return CandidateTranscript(
            candidate_id=cand.id,
            text=" ".join(full_text_parts),
            language=info.language,
            words=all_words,
        )
    except Exception as exc:
        logger.error("targeted_transcription_error", candidate_id=cand.id, error=str(exc))
        return CandidateTranscript(candidate_id=cand.id)


def transcribe_clip_media(
    media_path: Path,
    model_name: str = "base",
    device: str = "auto",
    compute_type: str = "auto",
) -> list[SubtitleWord]:
    """
    Directly transcribe a rendered/cut raw clip media file (e.g. raw.mp4)
    to produce ground-truth word-level timestamps in the clip's native timeline (0.0s = start of clip).
    """
    if not media_path.exists() or media_path.stat().st_size < 1000:
        return []

    try:
        model = get_whisper_model(model_name, device, compute_type)
        segments, _info = model.transcribe(
            str(media_path),
            word_timestamps=True,
            vad_filter=False,
            beam_size=3,
        )

        words: list[SubtitleWord] = []
        word_idx = 0
        for seg in segments:
            if seg.words:
                for w in seg.words:
                    clean_w = w.word.strip()
                    if clean_w:
                        words.append(
                            SubtitleWord(
                                idx=word_idx,
                                start_s=round(float(w.start), 3),
                                end_s=round(max(float(w.start) + 0.04, float(w.end)), 3),
                                text=clean_w,
                                confidence=round(float(w.probability), 3),
                            )
                        )
                        word_idx += 1
        return words
    except Exception as exc:
        logger.error("transcribe_clip_media_failed", path=str(media_path), error=str(exc))
        return []
