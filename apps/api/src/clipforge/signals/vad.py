"""Voice Activity Detection (VAD) via faster-whisper Silero VAD with energy fallback."""

import math
from typing import Any

import numpy as np
import structlog

from clipforge.signals.models import SpeechSegment

logger = structlog.get_logger(__name__)


def compute_energy_vad(
    audio: np.ndarray,
    sr: int = 16000,
    frame_ms: int = 30,
    threshold_db: float = -38.0,
) -> tuple[np.ndarray, list[SpeechSegment]]:
    """
    Fallback energy-based VAD with hysteresis.

    Returns:
        speech_prob (1s grid), list of SpeechSegment
    """
    frame_len = int(sr * frame_ms / 1000)
    n_frames = len(audio) // frame_len
    if n_frames == 0:
        return np.zeros(1, dtype=np.float32), []

    frames = audio[: n_frames * frame_len].reshape((n_frames, frame_len))
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-9)
    db = 20.0 * np.log10(rms)

    is_speech_frame = db > threshold_db

    duration_s = int(math.ceil(len(audio) / sr))
    speech_prob = np.zeros(duration_s, dtype=np.float32)

    frames_per_sec = 1000.0 / frame_ms
    for sec in range(duration_s):
        f_start = int(sec * frames_per_sec)
        f_end = min(n_frames, int((sec + 1) * frames_per_sec))
        if f_end > f_start:
            speech_prob[sec] = float(np.mean(is_speech_frame[f_start:f_end]))

    # Merge contiguous frames into speech segments
    segments: list[SpeechSegment] = []
    in_speech = False
    seg_start = 0.0

    for i, active in enumerate(is_speech_frame):
        t = i * (frame_ms / 1000.0)
        if active and not in_speech:
            in_speech = True
            seg_start = t
        elif not active and in_speech:
            in_speech = False
            if t - seg_start >= 0.3:  # minimum 300ms
                segments.append(
                    SpeechSegment(start_s=round(seg_start, 3), end_s=round(t, 3), confidence=0.8)
                )

    if in_speech:
        t_end = n_frames * (frame_ms / 1000.0)
        if t_end - seg_start >= 0.3:
            segments.append(
                SpeechSegment(start_s=round(seg_start, 3), end_s=round(t_end, 3), confidence=0.8)
            )

    return speech_prob, segments


def compute_vad(
    audio: np.ndarray,
    sr: int = 16000,
) -> tuple[np.ndarray, list[SpeechSegment]]:
    """
    Run Silero VAD from faster-whisper.

    Returns:
        speech_prob (1s grid np.ndarray), list of SpeechSegment
    """
    duration_s = max(1, int(math.ceil(len(audio) / sr)))

    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        vad_opts = VadOptions(
            threshold=0.5,
            min_speech_duration_ms=250,
            max_speech_duration_s=float("inf"),
            min_silence_duration_ms=2000,
            speech_pad_ms=400,
        )
        # get_speech_timestamps accepts 1D float32 audio
        raw_segs: list[dict[str, Any]] = get_speech_timestamps(audio, vad_opts)

        segments = [
            SpeechSegment(
                start_s=round(s["start"] / sr, 3),
                end_s=round(s["end"] / sr, 3),
                confidence=1.0,
            )
            for s in raw_segs
        ]

        # Project segments into 1-second grid
        speech_prob = np.zeros(duration_s, dtype=np.float32)
        for seg in segments:
            idx_start = max(0, int(seg.start_s))
            idx_end = min(duration_s, int(math.ceil(seg.end_s)))
            for sec in range(idx_start, idx_end):
                overlap = min(seg.end_s, sec + 1.0) - max(seg.start_s, float(sec))
                if overlap > 0:
                    speech_prob[sec] = min(1.0, speech_prob[sec] + overlap)

        return speech_prob, segments

    except Exception as exc:
        logger.warning("silero_vad_failed_using_energy_fallback", error=str(exc))
        return compute_energy_vad(audio, sr=sr)
