"""Deterministic ASS subtitle script generator with kinetic active-word state highlights."""

import math
from pathlib import Path

import yaml

from clipforge.subtitles.models import SubtitleChunk, SubtitleStylePreset


def format_ass_centisecond(seconds: float) -> str:
    """Format seconds into ASS timestamp H:MM:SS.cc with monotonic precision."""
    total_cs = max(0, int(math.floor(seconds * 100.0 + 0.5)))
    cs = total_cs % 100
    total_sec = total_cs // 100
    sec = total_sec % 60
    total_min = total_sec // 60
    minute = total_min % 60
    hour = total_min // 60
    return f"{hour}:{minute:02d}:{sec:02d}.{cs:02d}"


def load_style_preset(preset_name: str = "classic_white") -> SubtitleStylePreset:
    """Load style preset from yaml file or fallback to classic_white."""
    preset_dir = Path(__file__).parent / "presets"
    preset_file = preset_dir / f"{preset_name}.yaml"
    if not preset_file.exists():
        preset_file = preset_dir / "classic_white.yaml"

    if preset_file.exists():
        try:
            data = yaml.safe_load(preset_file.read_text(encoding="utf-8"))
            return SubtitleStylePreset(**data)
        except Exception:
            pass

    return SubtitleStylePreset(name=preset_name)


def generate_ass_script(
    chunks: list[SubtitleChunk],
    style: SubtitleStylePreset,
    video_width: int = 1080,
    video_height: int = 1920,
    enable_pop_in: bool = True,
) -> str:
    """
    Generate complete ASS script string with one Dialogue event per active word state.
    Avoids fragile karaoke tags and guarantees cross-platform rendering precision.
    """
    lines: list[str] = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {video_width}",
        f"PlayResY: {video_height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        (
            f"Style: Default,{style.font_name},{style.font_size},{style.primary_color},"
            f"&H000000FF&,{style.outline_color},{style.back_color},"
            f"{style.bold},{style.italic},0,0,100,100,0,0,1,"
            f"{style.outline},{style.shadow},{style.alignment},90,90,{style.margin_v},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for chunk in chunks:
        words = chunk.words
        if not words:
            continue

        num_words = len(words)
        for i, target_word in enumerate(words):
            # Monotonic event start and end
            evt_start_s = target_word.start_s
            if i < num_words - 1:
                evt_end_s = words[i + 1].start_s
            else:
                evt_end_s = chunk.end_s

            # Ensure start < end
            if evt_end_s <= evt_start_s:
                evt_end_s = evt_start_s + 0.05

            start_str = format_ass_centisecond(evt_start_s)
            end_str = format_ass_centisecond(evt_end_s)

            # Build line text with target_word highlighted
            text_parts: list[str] = []
            for j, w in enumerate(words):
                if j == i:
                    # Active highlighted word
                    text_parts.append(f"{{\\c{style.active_color}}}{w.text}{{\\r}}")
                else:
                    text_parts.append(w.text)

            line_text = " ".join(text_parts)

            # Optional subtle pop-in animation on the very first word of the chunk
            prefix = ""
            if enable_pop_in and i == 0:
                prefix = "{\\fscx108\\fscy108\\t(0,80,\\fscx100\\fscy100)}"

            lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{prefix}{line_text}")

    return "\n".join(lines) + "\n"
