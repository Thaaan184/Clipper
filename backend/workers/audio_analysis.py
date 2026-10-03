"""
Audio analysis — RMS energy spike detection without full video download.
Downloads audio-only stream for analysis.
"""
import asyncio
import logging
import numpy as np
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)


async def download_audio(url: str, video_id: str) -> Path | None:
    """Download audio-only stream via yt-dlp for analysis/whisper."""
    output_path = settings.raw_dir / f"{video_id}.m4a"
    if output_path.exists():
        logger.info("Audio already cached: %s", output_path)
        return output_path

    cmd = [
        "yt-dlp",
        "-f", "bestaudio[ext=m4a]/bestaudio",
        "-o", str(output_path),
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        url,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error("Audio download failed: %s", stderr.decode()[-300:])
            return None

        logger.info("Audio downloaded: %s (%.1f MB)", output_path.name, output_path.stat().st_size / 1e6)
        return output_path

    except Exception as e:
        logger.error("yt-dlp audio error: %s", e)
        return None


async def detect_energy_spikes(
    audio_path: Path,
    threshold_multiplier: float = 2.5,
    min_gap_seconds: float = 5.0,
) -> list[dict]:
    """
    Detect moments with audio energy significantly above baseline.
    Returns list of {time: float, energy: float} sorted by time.
    """
    try:
        import librosa

        loop = asyncio.get_event_loop()

        def _analyze():
            y, sr = librosa.load(str(audio_path), sr=16000, mono=True)
            hop = 8000  # 0.5s frames
            rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
            times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=hop)

            baseline = float(np.median(rms))
            if baseline < 1e-6:
                return []

            threshold = baseline * threshold_multiplier
            spikes = []
            last_spike_time = -min_gap_seconds

            for t, energy in zip(times, rms):
                if energy > threshold and (t - last_spike_time) >= min_gap_seconds:
                    spikes.append({
                        "time": round(float(t), 2),
                        "energy": round(float(energy / baseline), 2),
                    })
                    last_spike_time = t

            return spikes

        spikes = await loop.run_in_executor(None, _analyze)
        logger.info("Found %d audio spikes in %s", len(spikes), audio_path.name)
        return spikes

    except ImportError:
        logger.warning("librosa not installed, skipping audio spike detection")
        return []
    except Exception as e:
        logger.error("Audio spike detection error: %s", e)
        return []
