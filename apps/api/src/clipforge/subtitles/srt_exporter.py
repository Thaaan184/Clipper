"""Exporter for standard SRT subtitle files from kinetic chunks."""

import math

from clipforge.subtitles.models import SubtitleChunk


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds to HH:MM:SS,mmm for SubRip files."""
    total_ms = max(0, int(math.floor(seconds * 1000.0 + 0.5)))
    ms = total_ms % 1000
    total_sec = total_ms // 1000
    sec = total_sec % 60
    total_min = total_sec // 60
    minute = total_min % 60
    hour = total_min // 60
    return f"{hour:02d}:{minute:02d}:{sec:02d},{ms:03d}"


def export_srt(chunks: list[SubtitleChunk]) -> str:
    """Export list of subtitle chunks into valid SRT text."""
    output_blocks: list[str] = []

    for idx, chunk in enumerate(chunks, start=1):
        if not chunk.words:
            continue

        start_str = format_srt_timestamp(chunk.start_s)
        end_str = format_srt_timestamp(chunk.end_s)
        text = " ".join(w.text for w in chunk.words)

        block = f"{idx}\n{start_str} --> {end_str}\n{text}\n"
        output_blocks.append(block)

    return "\n".join(output_blocks)
