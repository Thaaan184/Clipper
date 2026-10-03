"""FFmpeg filtergraph builders for 9:16 vertical video reframing."""


def build_reframe_filtergraph(
    mode: str = "blur",
    ass_file: str = "subs.ass",
    fonts_dir: str = "fonts",
    width: int = 1080,
    height: int = 1920,
    game_roi: tuple[float, float, float, float] | None = None,
    face_roi: tuple[float, float, float, float] | None = None,
) -> str:
    """
    Construct FFmpeg filtergraph for 9:16 vertical layout (1080x1920).
    Modes:
      - blur: Game centered 16:9, background blurred & dimmed (standard gaming).
      - center: Centered crop 1080x1920.
      - stacked: Game ROI on top, facecam ROI on bottom.
    """
    ass_filter = f"ass={ass_file}:fontsdir={fonts_dir}"

    if mode == "center":
        return f"[0:v]scale=-2:{height},crop={width}:{height},format=yuv420p,{ass_filter}[v]"

    elif mode == "stacked" and game_roi and face_roi:
        # Normalized coordinates: x, y, w, h in [0.0, 1.0]
        # Top game: height 1200px, Bottom facecam: height 720px
        gx, gy, gw, gh = game_roi
        fx, fy, fw, fh = face_roi
        return (
            f"[0:v]split=2[game_raw][face_raw];"
            f"[game_raw]crop=iw*{gw:.3f}:ih*{gh:.3f}:iw*{gx:.3f}:ih*{gy:.3f},scale={width}:1200:flags=lanczos[game];"
            f"[face_raw]crop=iw*{fw:.3f}:ih*{fh:.3f}:iw*{fx:.3f}:ih*{fy:.3f},scale={width}:720:flags=lanczos[face];"
            f"[game][face]vstack=inputs=2,format=yuv420p,{ass_filter}[v]"
        )

    else:
        # Default: "blur" mode
        return (
            f"[0:v]split=2[bg_src][fg_src];"
            f"[bg_src]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},gblur=sigma=30,eq=brightness=-0.08[bg];"
            f"[fg_src]scale={width}:-2:flags=lanczos[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p,{ass_filter}[v]"
        )
