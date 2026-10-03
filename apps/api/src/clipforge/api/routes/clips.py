"""API routes for clip retrieval, video streaming, subtitle editing, and WYSIWYG preview."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from clipforge.core.config import settings
from clipforge.db.connection import get_db
from clipforge.render.engine import render_single_clip
from clipforge.render.preview import render_subtitle_preview_frame
from clipforge.subtitles import (
    SubtitleWord,
    create_kinetic_chunks,
    export_srt,
    generate_ass_script,
    load_style_preset,
    validate_and_normalize_words,
)

router = APIRouter(prefix="/api/clips", tags=["Clips"])


class ClipResponse(BaseModel):
    id: str
    candidate_id: str
    job_id: str
    status: str
    video_path: str | None = None
    thumb_path: str | None = None
    srt_path: str | None = None
    width: int = 1080
    height: int = 1920
    duration_s: float | None = None
    render_params: dict[str, Any] = Field(default_factory=dict)
    qa: dict[str, Any] | None = None
    created_at: str


class SubtitlesUpdatePayload(BaseModel):
    words: list[SubtitleWord]
    style_preset: str = "classic_white"


class SubtitlesPreviewPayload(BaseModel):
    t_s: float = 1.0
    style_preset: str = "classic_white"
    reframe_mode: str = "blur"
    words: list[SubtitleWord] | None = None


@router.get("/{clip_id}", response_model=ClipResponse)
async def get_clip(clip_id: str, db: aiosqlite.Connection = Depends(get_db)) -> ClipResponse:
    """Fetch clip metadata and QA report."""
    query = """
        SELECT id, candidate_id, job_id, status, video_path, thumb_path, srt_path,
               width, height, duration_s, render_params_json, qa_json, created_at
        FROM clips
        WHERE id = ?
    """
    async with db.execute(query, (clip_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Clip not found")

        render_params = json.loads(row[10]) if row[10] else {}
        qa = json.loads(row[11]) if row[11] else None

        return ClipResponse(
            id=row[0],
            candidate_id=row[1],
            job_id=row[2],
            status=row[3],
            video_path=row[4],
            thumb_path=row[5],
            srt_path=row[6],
            width=row[7] or 1080,
            height=row[8] or 1920,
            duration_s=row[9],
            render_params=render_params,
            qa=qa,
            created_at=row[12],
        )


@router.get("/{clip_id}/video")
async def stream_clip_video(
    clip_id: str, db: aiosqlite.Connection = Depends(get_db)
) -> FileResponse:
    """Stream final rendered MP4 video with HTTP Range support."""
    async with db.execute("SELECT video_path FROM clips WHERE id = ?", (clip_id,)) as cursor:
        row = await cursor.fetchone()
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Clip video not found")

    video_path = Path(row[0])
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file missing on disk")

    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"{clip_id}.mp4",
    )


@router.get("/{clip_id}/subtitles")
async def get_clip_subtitles(
    clip_id: str, db: aiosqlite.Connection = Depends(get_db)
) -> dict[str, Any]:
    """Retrieve the latest subtitle track and words for a clip."""
    # Find latest track
    q_track = """
        SELECT id, revision, style_json, language
        FROM subtitle_tracks
        WHERE clip_id = ?
        ORDER BY revision DESC
        LIMIT 1
    """
    async with db.execute(q_track, (clip_id,)) as cursor:
        track_row = await cursor.fetchone()
        if not track_row:
            return {"clip_id": clip_id, "revision": 0, "words": [], "style": "classic_white"}

        track_id, revision, style_json, language = (
            track_row[0],
            track_row[1],
            track_row[2],
            track_row[3],
        )

    # Fetch words
    q_words = """
        SELECT idx, start_s, end_s, text, confidence
        FROM subtitle_words
        WHERE track_id = ?
        ORDER BY idx ASC
    """
    words = []
    async with db.execute(q_words, (track_id,)) as cursor:
        async for r in cursor:
            words.append(
                {
                    "idx": r[0],
                    "start_s": r[1],
                    "end_s": r[2],
                    "text": r[3],
                    "confidence": r[4],
                }
            )

    return {
        "clip_id": clip_id,
        "track_id": track_id,
        "revision": revision,
        "language": language,
        "style": json.loads(style_json) if style_json else {},
        "words": words,
    }


@router.put("/{clip_id}/subtitles")
async def update_clip_subtitles(
    clip_id: str,
    payload: SubtitlesUpdatePayload,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, Any]:
    """
    Update words for a clip subtitle track, creating a new revision.
    """
    async with db.execute("SELECT job_id, duration_s FROM clips WHERE id = ?", (clip_id,)) as cur:
        c_row = await cur.fetchone()
        if not c_row:
            raise HTTPException(status_code=404, detail="Clip not found")
        job_id, clip_dur = c_row[0], c_row[1] or 30.0

    # Get max revision
    async with db.execute(
        "SELECT COALESCE(MAX(revision), 0) FROM subtitle_tracks WHERE clip_id = ?", (clip_id,)
    ) as cur:
        rev_row = await cur.fetchone()
        next_rev = (rev_row[0] if rev_row else 0) + 1

    track_id = str(uuid.uuid4())
    now_iso = datetime.now(UTC).isoformat()
    style_json = json.dumps({"preset": payload.style_preset})

    # Validate words
    val_words = validate_and_normalize_words(payload.words, clip_duration_s=clip_dur)

    await db.execute(
        """
        INSERT INTO subtitle_tracks (id, clip_id, revision, source, language, style_json, created_at)
        VALUES (?, ?, ?, 'user_edit', 'id', ?, ?)
        """,
        (track_id, clip_id, next_rev, style_json, now_iso),
    )

    for w in val_words:
        await db.execute(
            """
            INSERT INTO subtitle_words (track_id, idx, start_s, end_s, text, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (track_id, w.idx, w.start_s, w.end_s, w.text, w.confidence),
        )

    await db.commit()

    # Re-generate subs.ass in clip folder
    clip_dir = settings.data_dir / "jobs" / job_id / "clips" / clip_id
    if clip_dir.exists():
        style_preset = load_style_preset(payload.style_preset)
        chunks = create_kinetic_chunks(val_words)
        ass_content = generate_ass_script(chunks, style=style_preset)
        (clip_dir / "subs.ass").write_text(ass_content, encoding="utf-8")
        (clip_dir / "clip.srt").write_text(export_srt(chunks), encoding="utf-8")

    return {
        "status": "updated",
        "clip_id": clip_id,
        "track_id": track_id,
        "revision": next_rev,
        "words_count": len(val_words),
    }


@router.post("/{clip_id}/subtitles/preview")
async def preview_subtitle_frame(
    clip_id: str,
    payload: SubtitlesPreviewPayload,
    db: aiosqlite.Connection = Depends(get_db),
) -> FileResponse:
    """
    Render a single WYSIWYG preview frame at t_s using the real FFmpeg ASS filter pipeline.
    """
    async with db.execute("SELECT job_id, video_path FROM clips WHERE id = ?", (clip_id,)) as cur:
        c_row = await cur.fetchone()
        if not c_row:
            raise HTTPException(status_code=404, detail="Clip not found")
        job_id = c_row[0]

    clip_dir = settings.data_dir / "jobs" / job_id / "clips" / clip_id
    raw_video = clip_dir / "raw.mp4"
    if not raw_video.exists():
        # Fallback to final video or raw
        if c_row[1] and Path(c_row[1]).exists():
            raw_video = Path(c_row[1])
        else:
            raise HTTPException(status_code=404, detail="Source video for preview not found")

    style_preset = load_style_preset(payload.style_preset)

    if payload.words is not None:
        words = validate_and_normalize_words(payload.words, clip_duration_s=60.0)
    else:
        # Load from current subs.ass if exists or DB
        words = []

    chunks = create_kinetic_chunks(words)
    ass_content = generate_ass_script(chunks, style=style_preset)

    preview_ass = clip_dir / "preview.ass"
    preview_ass.write_text(ass_content, encoding="utf-8")

    out_png = clip_dir / "preview.png"
    success = render_subtitle_preview_frame(
        raw_video=raw_video,
        ass_path=preview_ass,
        output_png=out_png,
        t_s=payload.t_s,
        mode=payload.reframe_mode,
        fonts_dir=clip_dir / "fonts",
    )

    if not success or not out_png.exists():
        raise HTTPException(status_code=500, detail="Failed to render preview frame")

    return FileResponse(path=str(out_png), media_type="image/png")


@router.post("/{clip_id}/rerender", response_model=ClipResponse)
async def rerender_clip(
    clip_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> ClipResponse:
    """Re-render clip with current subs.ass and reframe configuration."""
    async with db.execute(
        "SELECT job_id, render_params_json FROM clips WHERE id = ?", (clip_id,)
    ) as cur:
        c_row = await cur.fetchone()
        if not c_row:
            raise HTTPException(status_code=404, detail="Clip not found")
        job_id, r_params_str = c_row[0], c_row[1]

    clip_dir = settings.data_dir / "jobs" / job_id / "clips" / clip_id
    raw_video = clip_dir / "raw.mp4"
    ass_file = clip_dir / "subs.ass"

    if not raw_video.exists() or not ass_file.exists():
        raise HTTPException(status_code=400, detail="Missing raw.mp4 or subs.ass for re-render")

    r_params = json.loads(r_params_str) if r_params_str else {}
    mode = r_params.get("reframe_mode", "blur")

    render_result = render_single_clip(
        clip_dir=clip_dir,
        raw_video=raw_video,
        ass_path=ass_file,
        mode=mode,
    )

    status_str = "done" if render_result["success"] else "failed"

    await db.execute(
        """
        UPDATE clips
        SET status = ?, video_path = ?, thumb_path = ?, qa_json = ?
        WHERE id = ?
        """,
        (
            status_str,
            render_result["final_path"],
            render_result["thumb_path"],
            json.dumps(render_result["qa"]),
            clip_id,
        ),
    )
    await db.commit()

    return await get_clip(clip_id, db)


@router.get("/{clip_id}/subtitles.srt")
async def download_clip_srt(
    clip_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> FileResponse:
    """Download standard SRT subtitle file for this clip."""
    async with db.execute("SELECT srt_path FROM clips WHERE id = ?", (clip_id,)) as cur:
        row = await cur.fetchone()
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="SRT file not found")

    srt_file = Path(row[0])
    if not srt_file.exists():
        raise HTTPException(status_code=404, detail="SRT file missing on disk")

    return FileResponse(
        path=str(srt_file),
        media_type="text/plain",
        filename=f"{clip_id}.srt",
    )
