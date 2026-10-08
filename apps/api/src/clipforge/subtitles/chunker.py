"""Kinetic chunking for subtitles using pause detection and font metric wrapping."""

from pathlib import Path

from PIL import ImageFont

from clipforge.subtitles.models import SubtitleChunk, SubtitleWord

# Default font path
DEFAULT_FONT_PATH = (
    Path(__file__).parent.parent.parent.parent / "assets" / "fonts" / "LiberationSans-Bold.ttf"
)


def get_font_metric(font_path: Path | None, font_size: int = 48) -> ImageFont.FreeTypeFont | None:
    """Load Pillow ImageFont to measure text pixel width."""
    path = font_path or DEFAULT_FONT_PATH
    if path.exists():
        try:
            return ImageFont.truetype(str(path), font_size)
        except Exception:
            pass
    return None


def create_kinetic_chunks(
    words: list[SubtitleWord],
    max_words_per_chunk: int = 4,
    max_pause_s: float = 0.35,
    max_width_px: int = 864,  # 80% of 1080 canvas
    font_path: Path | None = None,
    font_size: int = 48,
    min_chunk_duration_s: float = 0.30,
) -> list[SubtitleChunk]:
    """
    Split word stream into short, punchy kinetic subtitle chunks.
    Groups words by speaker to allow independent concurrent streams,
    and breaks on pauses, punctuation, max word limits, or line width overflow.
    """
    if not words:
        return []

    font = get_font_metric(font_path, font_size)

    # Group words by speaker to preserve independent speaker streams
    words_by_speaker: dict[str, list[SubtitleWord]] = {}
    for w in words:
        spk = w.speaker or "speaker_1"
        if spk not in words_by_speaker:
            words_by_speaker[spk] = []
        words_by_speaker[spk].append(w)

    all_chunks: list[SubtitleChunk] = []

    for spk, spk_words in words_by_speaker.items():
        spk_words_sorted = sorted(spk_words, key=lambda w: (w.start_s, w.end_s, w.idx))
        current_words: list[SubtitleWord] = []
        spk_chunks: list[SubtitleChunk] = []

        for w in spk_words_sorted:
            # Decide if we need to break before adding this word
            break_before = False
            if current_words:
                # 1. Check pause since previous word
                pause = w.start_s - current_words[-1].end_s
                if pause >= max_pause_s:
                    break_before = True

                # 2. Check max words
                elif len(current_words) >= max_words_per_chunk:
                    break_before = True

                # 3. Check width overflow
                elif font:
                    test_str = " ".join([cw.text for cw in current_words] + [w.text])
                    try:
                        width = font.getlength(test_str)
                        if width > max_width_px:
                            break_before = True
                    except Exception:
                        pass

            if break_before and current_words:
                pos_y = next((cw.pos_y for cw in current_words if cw.pos_y is not None), None)
                spk_chunks.append(
                    SubtitleChunk(
                        words=list(current_words),
                        start_s=current_words[0].start_s,
                        end_s=current_words[-1].end_s,
                        speaker=spk,
                        pos_y=pos_y,
                    )
                )
                current_words = []

            current_words.append(w)

            # Break after word if it ends with strong punctuation
            if any(w.text.endswith(p) for p in [".", "!", "?", ","]):
                pos_y = next((cw.pos_y for cw in current_words if cw.pos_y is not None), None)
                spk_chunks.append(
                    SubtitleChunk(
                        words=list(current_words),
                        start_s=current_words[0].start_s,
                        end_s=current_words[-1].end_s,
                        speaker=spk,
                        pos_y=pos_y,
                    )
                )
                current_words = []

        if current_words:
            pos_y = next((cw.pos_y for cw in current_words if cw.pos_y is not None), None)
            spk_chunks.append(
                SubtitleChunk(
                    words=list(current_words),
                    start_s=current_words[0].start_s,
                    end_s=current_words[-1].end_s,
                    speaker=spk,
                    pos_y=pos_y,
                )
            )

        # Enforce minimum display duration within this speaker's stream
        for idx, ch in enumerate(spk_chunks):
            dur = ch.end_s - ch.start_s
            if dur < min_chunk_duration_s:
                max_extend = ch.start_s + min_chunk_duration_s
                if idx + 1 < len(spk_chunks):
                    next_start = spk_chunks[idx + 1].start_s
                    ch.end_s = round(min(max_extend, max(ch.end_s, next_start - 0.05)), 3)
                else:
                    ch.end_s = round(max_extend, 3)

        all_chunks.extend(spk_chunks)

    all_chunks.sort(key=lambda c: (c.start_s, c.end_s))
    return all_chunks
