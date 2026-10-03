"""Word timestamp validation, clamping, and text normalization."""

import re
import unicodedata

from clipforge.subtitles.models import SubtitleWord


def normalize_subtitle_text(text: str, uppercase: bool = False) -> str:
    """Normalize text: Unicode NFC, strip brackets, escape characters, remove zero-width chars."""
    if not text:
        return ""

    # 1. Unicode NFC
    s = unicodedata.normalize("NFC", text)

    # 2. Remove zero-width characters and control chars
    s = re.sub(r"[\u200B-\u200D\uFEFF\x00-\x1F\x7F]", "", s)

    # 3. Strip ASS special characters that would corrupt subtitle rendering
    s = s.replace("{", "").replace("}", "").replace("\\", "")

    # 4. Remove emojis (Liberation Sans OFL lacks color emoji glyphs)
    s = re.sub(
        r"[\U00010000-\U0010ffff]",
        "",
        s,
        flags=re.UNICODE,
    )

    s = re.sub(r"\s+", " ", s).strip()
    if uppercase:
        s = s.upper()
    return s


def validate_and_normalize_words(
    words: list[SubtitleWord],
    clip_duration_s: float,
    uppercase: bool = False,
) -> list[SubtitleWord]:
    """
    Ensure word timestamps are monotonic, strictly within [0.0, clip_duration_s],
    non-overlapping, and meet minimum duration thresholds.
    """
    if not words:
        return []

    # Sort monotonically
    sorted_words = sorted(words, key=lambda w: (w.start_s, w.end_s))
    validated: list[SubtitleWord] = []

    for w in sorted_words:
        clean_text = normalize_subtitle_text(w.text, uppercase=uppercase)
        if not clean_text:
            continue

        # Clamp to clip boundaries
        start = max(0.0, min(w.start_s, clip_duration_s))
        end = max(start + 0.04, min(w.end_s, clip_duration_s))

        # Resolve overlap with previous word
        if validated:
            prev = validated[-1]
            if start < prev.end_s:
                # If current starts before previous ends, truncate previous
                prev.end_s = start
                if prev.end_s - prev.start_s < 0.04:
                    prev.start_s = max(0.0, prev.end_s - 0.04)

        validated.append(
            SubtitleWord(
                idx=len(validated),
                start_s=round(start, 3),
                end_s=round(end, 3),
                text=clean_text,
                confidence=w.confidence,
            )
        )

    return validated
