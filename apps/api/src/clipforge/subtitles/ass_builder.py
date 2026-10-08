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


# Consistent speaker color palette in ASS format (&HAABBGGRR&)
SPEAKER_PALETTE = [
    None,            # Slot 0 / Speaker 1 -> style.primary_color
    "&H00008CFF&",   # Slot 1 / Speaker 2 -> Fire Orange (B:00, G:8C, R:FF)
    "&H00FFFF00&",   # Slot 2 / Speaker 3 -> Electric Cyan (B:FF, G:FF, R:00)
    "&H0000FF7F&",   # Slot 3 / Speaker 4 -> Lime Green (B:00, G:FF, R:7F)
    "&H00B400FF&",   # Slot 4 / Speaker 5 -> Vivid Magenta / Pink (B:B4, G:00, R:FF)
    "&H0000FFFF&",   # Slot 5 / Speaker 6 -> Gold / Yellow (B:00, G:FF, R:FF)
]


def get_speaker_color_mapping(
    chunks: list[SubtitleChunk],
    default_primary: str,
) -> dict[str, str]:
    """Map speaker IDs to consistent distinctive colors across the video."""
    mapping: dict[str, str] = {}
    palette_idx = 0
    for ch in chunks:
        spk = ch.speaker or "speaker_1"
        if spk not in mapping:
            spk_lower = spk.lower()
            if spk_lower in ("speaker_1", "spk_1", "spk1", "speaker1", "default"):
                mapping[spk] = default_primary
            elif spk_lower in ("speaker_2", "spk_2", "spk2", "speaker2"):
                mapping[spk] = SPEAKER_PALETTE[1]
            elif spk_lower in ("speaker_3", "spk_3", "spk3", "speaker3"):
                mapping[spk] = SPEAKER_PALETTE[2]
            elif spk_lower in ("speaker_4", "spk_4", "spk4", "speaker4"):
                mapping[spk] = SPEAKER_PALETTE[3]
            elif spk_lower in ("speaker_5", "spk_5", "spk5", "speaker5"):
                mapping[spk] = SPEAKER_PALETTE[4]
            else:
                color = SPEAKER_PALETTE[palette_idx % len(SPEAKER_PALETTE)]
                mapping[spk] = color if color else default_primary
                palette_idx += 1
    return mapping


def assign_chunk_vertical_positions(
    chunks: list[SubtitleChunk],
    base_y: int = 1680,
    step_y: int = 140,
    direction: str = "up",
) -> dict[int, int]:
    """
    Assign vertical Y positions to chunks.
    If chunk has explicit pos_y (user dragged), use it.
    If overlapping chunks appear at the same time, stack them vertically (atas-bawah)
    so they never collide.
    direction: 'up' (base_y - slot*step_y) for bottom placement.
               'down' (base_y + slot*step_y) for top placement (Shorts Safe Zone).
    """
    positions: dict[int, int] = {}
    active_slots: list[tuple[float, int]] = []

    for i, c in enumerate(chunks):
        if c.pos_y is not None:
            positions[i] = c.pos_y
            continue

        # Expire slots whose end_time <= c.start_s
        active_slots = [(end, slot) for (end, slot) in active_slots if end > c.start_s]
        used_slots = {slot for (_, slot) in active_slots}

        # Find lowest available slot index
        slot = 0
        while slot in used_slots:
            slot += 1

        active_slots.append((c.end_s, slot))
        if direction == "down":
            positions[i] = min(1740, base_y + slot * step_y)
        else:
            positions[i] = max(180, base_y - slot * step_y)

    return positions


def generate_ass_script(
    chunks: list[SubtitleChunk],
    style: SubtitleStylePreset,
    video_width: int = 1080,
    video_height: int = 1920,
    enable_pop_in: bool = True,
    subtitle_position: str = "bottom",
) -> str:
    """
    Generate complete ASS script string with one Dialogue event per active word state.
    Supports overlapping subtitles with multi-speaker distinction, custom vertical drag positioning,
    and subtitle location presets ('bottom' or 'top' for YT Shorts safe zone).
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

    if style.name.lower() in ("none", "off", "disable", "no_subtitles", "tanpa_subtitle"):
        return "\n".join(lines) + "\n"

    center_x = video_width // 2
    is_top = str(subtitle_position).lower() in ("top", "atas", "top_safe", "safe_top")
    if is_top:
        base_y = 420
        direction = "down"
    else:
        base_y = max(200, video_height - style.margin_v)
        direction = "up"
    step_y = max(90, int(style.font_size * 2.2 + 20))

    speaker_colors = get_speaker_color_mapping(chunks, style.primary_color)
    chunk_positions = assign_chunk_vertical_positions(
        chunks, base_y=base_y, step_y=step_y, direction=direction
    )

    for chunk_idx, chunk in enumerate(chunks):
        words = chunk.words
        if not words:
            continue

        pos_y = chunk_positions.get(chunk_idx, base_y)
        spk_color = speaker_colors.get(chunk.speaker or "speaker_1", style.primary_color)
        pos_tag = f"\\an2\\pos({center_x},{pos_y})"

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
                if j == i and style.active_color != style.primary_color:
                    # Active highlighted word with distinct accent color
                    if spk_color == style.primary_color:
                        text_parts.append(f"{{\\c{style.active_color}}}{w.text}{{\\r}}")
                    else:
                        text_parts.append(f"{{\\c{style.active_color}}}{w.text}{{\\r\\c{spk_color}}}")
                else:
                    text_parts.append(w.text)

            line_text = " ".join(text_parts)

            # Optional subtle pop-in animation on the very first word of the chunk
            prefix = ""
            if enable_pop_in and i == 0:
                prefix = "\\fscx108\\fscy108\\t(0,80,\\fscx100\\fscy100)"

            tags = f"{{{pos_tag}\\c{spk_color}{prefix}}}"
            lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{tags}{line_text}")

    return "\n".join(lines) + "\n"
