"""Extract audio features using FFmpeg streaming and pure NumPy/SciPy."""

import asyncio
import math
import subprocess
from pathlib import Path

import numpy as np
import scipy.ndimage
import scipy.signal
import structlog

from clipforge.signals.models import AudioFeatures, SpeechSegment
from clipforge.signals.vad import compute_vad

logger = structlog.get_logger(__name__)

SAMPLE_RATE = 16000
CHUNK_SECONDS = 60
BYTES_PER_SAMPLE = 4  # float32


def _compute_chunk_metrics(
    chunk: np.ndarray,
    sr: int = SAMPLE_RATE,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute per-second raw metrics for a 1D audio chunk.

    Returns:
        (loud_db, onset_density, hf_ratio, crest_db)
    """
    num_secs = max(1, int(math.ceil(len(chunk) / sr)))
    loud_db = np.zeros(num_secs, dtype=np.float32)
    onset_density = np.zeros(num_secs, dtype=np.float32)
    hf_ratio = np.zeros(num_secs, dtype=np.float32)
    crest_db = np.zeros(num_secs, dtype=np.float32)

    # Pre-pad chunk to full seconds if needed
    target_len = num_secs * sr
    if len(chunk) < target_len:
        padded = np.zeros(target_len, dtype=np.float32)
        padded[: len(chunk)] = chunk
    else:
        padded = chunk[:target_len]

    # Reshape to (num_secs, sr) for vectorized time-domain metrics
    secs_matrix = padded.reshape((num_secs, sr))

    # 1. RMS and loud_db
    rms = np.sqrt(np.mean(secs_matrix**2, axis=1) + 1e-12)
    loud_db = 20.0 * np.log10(rms)

    # 2. Crest factor in dB: peak_db - loud_db
    peak_val = np.max(np.abs(secs_matrix), axis=1)
    peak_db = 20.0 * np.log10(peak_val + 1e-12)
    crest_db = np.maximum(0.0, peak_db - loud_db)

    # 3. Spectral metrics per second (STFT)
    n_fft = 512
    hop_length = 256
    # 2kHz to 8kHz corresponds to bins:
    # bin_freq = k * (sr / n_fft) = k * 31.25 Hz
    # 2000 / 31.25 = 64
    # 8000 / 31.25 = 256
    hf_bin_start = 64
    hf_bin_end = 256

    for s in range(num_secs):
        sec_audio = secs_matrix[s]
        f, t, Zxx = scipy.signal.stft(sec_audio, fs=sr, nperseg=n_fft, noverlap=n_fft - hop_length)
        mag = np.abs(Zxx)  # shape: (n_fft // 2 + 1, n_frames)

        # High frequency energy ratio: energy(2kHz-8kHz) / total_energy
        total_energy = float(np.sum(mag**2) + 1e-9)
        hf_energy = float(np.sum(mag[hf_bin_start : hf_bin_end + 1, :] ** 2))
        hf_ratio[s] = float(np.clip(hf_energy / total_energy, 0.0, 1.0))

        # Spectral flux: half-wave rectified difference across frames
        diff = np.diff(mag, axis=1)
        pos_diff = np.maximum(0.0, diff)
        flux_per_frame = np.sum(pos_diff, axis=0)

        # Detect onsets: peaks in spectral flux
        if len(flux_per_frame) > 4:
            flux_mean = float(np.mean(flux_per_frame))
            flux_std = float(np.std(flux_per_frame))
            threshold = flux_mean + 1.2 * flux_std
            peaks, _ = scipy.signal.find_peaks(flux_per_frame, height=threshold, distance=2)
            onset_density[s] = float(len(peaks))
        else:
            onset_density[s] = 0.0

    return loud_db, onset_density, hf_ratio, crest_db


def extract_features_from_array(
    audio: np.ndarray,
    sr: int = SAMPLE_RATE,
) -> AudioFeatures:
    """Extract audio features and VAD from in-memory numpy array (for testing or short clips)."""
    duration_s = len(audio) / sr
    loud_db, onset_density, hf_ratio, crest_db = _compute_chunk_metrics(audio, sr=sr)

    # Rolling median for loud_surge (45s window)
    window_size = min(45, len(loud_db))
    if window_size % 2 == 0:
        window_size = max(1, window_size - 1)
    rolling_med = scipy.ndimage.median_filter(loud_db, size=window_size, mode="reflect")
    loud_surge = np.maximum(0.0, loud_db - rolling_med)

    # VAD
    speech_prob, speech_segments = compute_vad(audio, sr=sr)

    # Ensure speech_prob matches length of loud_db
    if len(speech_prob) < len(loud_db):
        padded_prob = np.zeros(len(loud_db), dtype=np.float32)
        padded_prob[: len(speech_prob)] = speech_prob
        speech_prob = padded_prob
    elif len(speech_prob) > len(loud_db):
        speech_prob = speech_prob[: len(loud_db)]

    # Nonspeech loudness: loud events without speech
    nonspeech_loud = loud_db * (1.0 - speech_prob)

    return AudioFeatures(
        duration_s=round(duration_s, 2),
        loud_db=[float(x) for x in loud_db],
        loud_surge=[float(x) for x in loud_surge],
        onset_density=[float(x) for x in onset_density],
        hf_ratio=[float(x) for x in hf_ratio],
        crest_db=[float(x) for x in crest_db],
        nonspeech_loud=[float(x) for x in nonspeech_loud],
        speech_prob=[float(x) for x in speech_prob],
        speech_segments=speech_segments,
    )


def extract_features_from_file_sync(
    audio_path: Path,
    sr: int = SAMPLE_RATE,
    chunk_seconds: int = CHUNK_SECONDS,
) -> AudioFeatures:
    """
    Stream audio file via FFmpeg pipe into fixed chunks and compute features without loading full file into RAM.
    """
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(audio_path),
        "-f",
        "f32le",
        "-ac",
        "1",
        "-ar",
        str(sr),
        "pipe:1",
    ]

    bytes_per_chunk = chunk_seconds * sr * BYTES_PER_SAMPLE

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.stdout is None:
        raise RuntimeError("Failed to open FFmpeg stdout pipe")

    loud_db_chunks: list[np.ndarray] = []
    onset_density_chunks: list[np.ndarray] = []
    hf_ratio_chunks: list[np.ndarray] = []
    crest_db_chunks: list[np.ndarray] = []
    speech_prob_chunks: list[np.ndarray] = []
    all_speech_segments: list[SpeechSegment] = []

    elapsed_s = 0.0

    try:
        while True:
            raw_bytes = proc.stdout.read(bytes_per_chunk)
            if not raw_bytes:
                break

            chunk_samples = np.frombuffer(raw_bytes, dtype=np.float32)
            if len(chunk_samples) == 0:
                break

            c_loud, c_onset, c_hf, c_crest = _compute_chunk_metrics(chunk_samples, sr=sr)
            loud_db_chunks.append(c_loud)
            onset_density_chunks.append(c_onset)
            hf_ratio_chunks.append(c_hf)
            crest_db_chunks.append(c_crest)

            # VAD on chunk
            c_sp_prob, c_sp_segs = compute_vad(chunk_samples, sr=sr)
            speech_prob_chunks.append(c_sp_prob)
            for seg in c_sp_segs:
                all_speech_segments.append(
                    SpeechSegment(
                        start_s=round(seg.start_s + elapsed_s, 3),
                        end_s=round(seg.end_s + elapsed_s, 3),
                        confidence=seg.confidence,
                    )
                )

            elapsed_s += len(chunk_samples) / sr

        proc.stdout.close()
        proc.wait()

    except Exception as exc:
        proc.kill()
        raise RuntimeError(f"Error during audio stream extraction: {exc}") from exc

    if not loud_db_chunks:
        return AudioFeatures(
            duration_s=0.0,
            loud_db=[],
            loud_surge=[],
            onset_density=[],
            hf_ratio=[],
            crest_db=[],
            nonspeech_loud=[],
            speech_prob=[],
            speech_segments=[],
        )

    loud_db_all = np.concatenate(loud_db_chunks)
    onset_density_all = np.concatenate(onset_density_chunks)
    hf_ratio_all = np.concatenate(hf_ratio_chunks)
    crest_db_all = np.concatenate(crest_db_chunks)
    speech_prob_all = np.concatenate(speech_prob_chunks)

    # Align lengths
    total_len = len(loud_db_all)
    if len(speech_prob_all) < total_len:
        pad = np.zeros(total_len - len(speech_prob_all), dtype=np.float32)
        speech_prob_all = np.concatenate([speech_prob_all, pad])
    else:
        speech_prob_all = speech_prob_all[:total_len]

    # Rolling median for loud_surge across the whole video (45s window)
    window_size = min(45, total_len)
    if window_size % 2 == 0:
        window_size = max(1, window_size - 1)
    rolling_med = scipy.ndimage.median_filter(loud_db_all, size=window_size, mode="reflect")
    loud_surge_all = np.maximum(0.0, loud_db_all - rolling_med)

    nonspeech_loud_all = loud_db_all * (1.0 - speech_prob_all)

    return AudioFeatures(
        duration_s=round(elapsed_s, 2),
        loud_db=[float(x) for x in loud_db_all],
        loud_surge=[float(x) for x in loud_surge_all],
        onset_density=[float(x) for x in onset_density_all],
        hf_ratio=[float(x) for x in hf_ratio_all],
        crest_db=[float(x) for x in crest_db_all],
        nonspeech_loud=[float(x) for x in nonspeech_loud_all],
        speech_prob=[float(x) for x in speech_prob_all],
        speech_segments=all_speech_segments,
    )


async def extract_audio_features(
    audio_path: Path,
    sr: int = SAMPLE_RATE,
    chunk_seconds: int = CHUNK_SECONDS,
) -> AudioFeatures:
    return await asyncio.to_thread(
        extract_features_from_file_sync,
        audio_path,
        sr,
        chunk_seconds,
    )
