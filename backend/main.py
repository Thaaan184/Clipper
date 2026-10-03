"""
Main FastAPI app — ClipForge backend.
"""
import asyncio
import io
import json
import logging
import re
import uuid
import zipfile
from typing import Any
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from db import init_db, get_db
from models import ScanRequest, ScanResponse, VideoInfo, ClipInfo, RenderRequest, RescanRequest
from services.subtitles import cues_to_srt, build_ass_from_cues
from workers.ingest import run_ingest
from workers.scout import run_scout
from workers.editor import render_clip

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="ClipForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory SSE pub/sub ───────────────────────────────────────────────────
from collections import defaultdict

_job_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_job_latest_event: dict[str, dict] = {}


class BroadcastQueue:
    def __init__(self, job_id: str):
        self.job_id = job_id

    async def put(self, event: dict):
        _job_latest_event[self.job_id] = event
        subs = list(_job_subscribers.get(self.job_id, set()))
        for sub_q in subs:
            try:
                await sub_q.put(event)
            except Exception:
                pass


# ── Concurrency semaphore for renders ────────────────────────────────────────
_render_semaphore = asyncio.Semaphore(settings.max_concurrent_renders)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await init_db()
    logger.info("ClipForge started | DB: %s | Data: %s", settings.db_path, settings.data_dir)


# ── Rate limiting helper ───────────────────────────────────────────────────────
async def check_rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    window = datetime.now(timezone.utc).strftime("%Y-%m-%d %H")

    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute_fetchall(
            "SELECT count FROM rate_limits WHERE ip = ? AND window_start = ?",
            (ip, window),
        )
        if row:
            count = row[0]["count"]
            if count >= settings.rate_limit_scans_per_hour:
                raise HTTPException(429, f"Rate limit: maks {settings.rate_limit_scans_per_hour} scan/jam")
            await db.execute(
                "UPDATE rate_limits SET count = count + 1 WHERE ip = ? AND window_start = ?",
                (ip, window),
            )
        else:
            await db.execute(
                "INSERT INTO rate_limits (ip, window_start, count) VALUES (?, ?, 1)",
                (ip, window),
            )
        await db.commit()


# ── Main scan pipeline ────────────────────────────────────────────────────────
@app.post("/api/scan", response_model=ScanResponse)
async def scan(req: ScanRequest, request: Request):
    """Start ingest + scout pipeline for a YouTube URL."""
    await check_rate_limit(request)

    video_id = str(uuid.uuid4())[:8]
    job_id = str(uuid.uuid4())

    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        # Check active scan jobs count (ignore stale jobs older than 10 minutes)
        row = await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM jobs WHERE job_type = 'scan' AND status IN ('pending','running') AND updated_at > datetime('now', '-10 minutes')"
        )
        pending_count = row[0]["c"] if row else 0
        if pending_count >= settings.max_pending_jobs:
            raise HTTPException(503, "Server sedang memproses antrean video lain. Coba beberapa menit lagi.")

        await db.execute(
            "INSERT INTO videos (id, url, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            (video_id, req.url, "pending", now, now),
        )
        await db.execute(
            "INSERT INTO jobs (id, video_id, job_type, status, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (job_id, video_id, "scan", "pending", now, now),
        )
        await db.commit()

    q = BroadcastQueue(job_id)

    # Run pipeline in background
    asyncio.create_task(_run_full_pipeline(job_id, video_id, req, q))

    return ScanResponse(job_id=job_id, video_id=video_id)


async def _run_full_pipeline(job_id: str, video_id: str, req: ScanRequest, q: Any):
    """Full pipeline: ingest → scout → editor (parallel clips)."""
    db_path = str(settings.db_path)
    try:
        # Phase 1: Ingest
        result = await run_ingest(job_id, video_id, req.url, req.subtitle_lang, q, db_path)

        # Phase 2: Scout
        clip_ids = await run_scout(
            job_id=job_id,
            video_id=video_id,
            transcript_text=result["transcript_text"],
            audio_spikes=result["spikes"],
            video_duration=result["duration"],
            clip_count=req.clip_count,
            duration_target=req.duration_target,
            subtitle_lang=req.subtitle_lang,
            layout=req.layout,
            progress_queue=q,
            db_path=db_path,
            content_type=req.content_type,
        )

        # Phase 3: Editor — render all clips concurrently (capped by semaphore)
        render_tasks = []
        for clip_id in clip_ids:
            # Get clip info
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                rows = await db.execute_fetchall("SELECT * FROM clips WHERE id = ?", (clip_id,))
                if not rows:
                    continue
                c = rows[0]

            render_job_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    "INSERT INTO jobs (id, video_id, clip_id, job_type, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                    (render_job_id, video_id, clip_id, "render", "pending", now, now),
                )
                await db.commit()

            render_tasks.append(_render_with_semaphore(
                render_job_id, clip_id, video_id, req.url,
                c["start_time"], c["end_time"], c["layout"], c["subtitle_lang"],
                q, db_path,
            ))

        await asyncio.gather(*render_tasks, return_exceptions=True)

        # Update main scan job to done
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE jobs SET status = 'done', phase = 'done', progress = 100, message = 'Semua klip selesai diproses', updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), job_id),
            )
            await db.commit()

        # Fetch final clip list for "done" event
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            clips = await db.execute_fetchall("SELECT * FROM clips WHERE video_id = ? ORDER BY score DESC", (video_id,))

        clips_data = [_clip_row_to_dict(c) for c in clips]
        await q.put({"event": "done", "job_id": job_id, "clips": clips_data})

    except Exception as e:
        logger.error("Pipeline error: %s", e)
        await q.put({"event": "error", "job_id": job_id, "error": str(e)})


async def _render_with_semaphore(job_id, clip_id, video_id, url, start, end, layout, lang, q, db_path):
    async with _render_semaphore:
        await render_clip(job_id, clip_id, video_id, url, start, end, layout, lang, q, db_path)


def _clip_row_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["hashtags"] = json.loads(d.get("hashtags") or "[]")
    except Exception:
        d["hashtags"] = []
    return d


# ── SSE progress stream & Job status ──────────────────────────────────────────
@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not rows:
            raise HTTPException(404, "Job tidak ditemukan")
        return dict(rows[0])


@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """Server-Sent Events stream for job progress."""
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not rows:
            raise HTTPException(404, "Job tidak ditemukan")
        job = dict(rows[0])

    # If job is already finished, return immediate state
    if job.get("status") == "done":
        async def done_gen():
            yield f"data: {json.dumps({'event': 'done', 'job_id': job_id, 'progress': 100, 'message': job.get('message') or 'Selesai', 'video_id': job.get('video_id')})}\n\n"
        return StreamingResponse(
            done_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    if job.get("status") == "error":
        async def err_gen():
            yield f"data: {json.dumps({'event': 'error', 'job_id': job_id, 'error': job.get('error_msg') or 'Job gagal'})}\n\n"
        return StreamingResponse(
            err_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    sub_q: asyncio.Queue = asyncio.Queue()
    _job_subscribers[job_id].add(sub_q)

    async def event_generator():
        try:
            # Yield latest event if available, or construct from DB
            latest = _job_latest_event.get(job_id)
            if latest:
                yield f"data: {json.dumps(latest)}\n\n"
            else:
                initial_event = {
                    "event": "progress",
                    "job_id": job_id,
                    "phase": job.get("phase", "ingest"),
                    "progress": job.get("progress", 0),
                    "message": job.get("message", "Memulai proses..."),
                }
                yield f"data: {json.dumps(initial_event)}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(sub_q.get(), timeout=10)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("event") in ("done", "error"):
                        break
                except asyncio.TimeoutError:
                    # Cloudflare keep-alive comment
                    yield ": keep-alive\n\n"
        finally:
            _job_subscribers[job_id].discard(sub_q)
            if not _job_subscribers[job_id]:
                _job_subscribers.pop(job_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Video & clip endpoints ────────────────────────────────────────────────────
@app.get("/api/videos/{video_id}")
async def get_video(video_id: str):
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        videos = await db.execute_fetchall("SELECT * FROM videos WHERE id = ?", (video_id,))
        if not videos:
            raise HTTPException(404, "Video not found")
        clips = await db.execute_fetchall(
            "SELECT * FROM clips WHERE video_id = ? ORDER BY score DESC", (video_id,)
        )
    v = dict(videos[0])
    v["clips"] = [_clip_row_to_dict(c) for c in clips]
    return v


@app.get("/api/projects")
async def list_projects():
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        videos = await db.execute_fetchall(
            "SELECT v.*, COUNT(c.id) as clip_count FROM videos v "
            "LEFT JOIN clips c ON c.video_id = v.id "
            "GROUP BY v.id ORDER BY v.created_at DESC LIMIT 20"
        )
    return [dict(v) for v in videos]


@app.api_route("/api/clips/{clip_id}/download", methods=["GET", "HEAD"])
async def download_clip(clip_id: str):
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM clips WHERE id = ?", (clip_id,))
        if not rows:
            raise HTTPException(404, "Clip not found")
        clip = dict(rows[0])

    if clip["status"] != "done" or not clip.get("file_path"):
        raise HTTPException(400, f"Clip belum selesai (status: {clip['status']})")

    file_path = Path(clip["file_path"])
    if not file_path.exists():
        raise HTTPException(404, "File tidak ditemukan di disk")

    filename = f"clipforge_{clip_id[:8]}_{clip.get('hook_title', 'clip')[:30].replace(' ', '_')}.mp4"
    return FileResponse(
        str(file_path),
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.api_route("/api/clips/{clip_id}/preview", methods=["GET", "HEAD"])
async def preview_clip(clip_id: str):
    """Stream video for inline browser playback."""
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM clips WHERE id = ?", (clip_id,))
        if not rows:
            raise HTTPException(404, "Clip tidak ditemukan")
        clip = dict(rows[0])

    if clip["status"] != "done" or not clip.get("file_path"):
        raise HTTPException(400, f"Clip belum selesai (status: {clip['status']})")

    file_path = Path(clip["file_path"])
    if not file_path.exists():
        raise HTTPException(404, "File tidak ditemukan di disk")

    return FileResponse(
        str(file_path),
        media_type="video/mp4",
        headers={
            "Content-Disposition": "inline",
            "Accept-Ranges": "bytes",
        },
    )


async def _run_rescan_pipeline(job_id: str, video_id: str, video: dict, req: ScanRequest, q: Any):
    """Rescan pipeline: uses existing transcript/audio spikes, re-runs scout + editor."""
    db_path = str(settings.db_path)
    try:
        raw_spikes = video.get("audio_spikes") or "[]"
        try:
            spikes = json.loads(raw_spikes)
        except Exception:
            spikes = []

        await q.put({
            "event": "progress",
            "job_id": job_id,
            "phase": "scout",
            "progress": 20,
            "message": "Menganalisis ulang transkrip dan hook momen...",
        })

        clip_ids = await run_scout(
            job_id=job_id,
            video_id=video_id,
            transcript_text=video.get("transcript", ""),
            audio_spikes=spikes,
            video_duration=video.get("duration", 0),
            clip_count=req.clip_count,
            duration_target=req.duration_target,
            subtitle_lang=req.subtitle_lang,
            layout=req.layout,
            progress_queue=q,
            db_path=db_path,
            content_type=req.content_type,
        )

        render_tasks = []
        for clip_id in clip_ids:
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                rows = await db.execute_fetchall("SELECT * FROM clips WHERE id = ?", (clip_id,))
                if not rows:
                    continue
                c = rows[0]

            render_job_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    "INSERT INTO jobs (id, video_id, clip_id, job_type, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                    (render_job_id, video_id, clip_id, "render", "pending", now, now),
                )
                await db.commit()

            render_tasks.append(_render_with_semaphore(
                render_job_id, clip_id, video_id, video["url"],
                c["start_time"], c["end_time"], c["layout"], c["subtitle_lang"],
                q, db_path,
            ))

        await asyncio.gather(*render_tasks, return_exceptions=True)

        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE jobs SET status = 'done', phase = 'done', progress = 100, message = 'Semua klip selesai diproses ulang', updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), job_id),
            )
            await db.execute(
                "UPDATE videos SET status = 'done', updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), video_id),
            )
            await db.commit()

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            clips = await db.execute_fetchall("SELECT * FROM clips WHERE video_id = ? ORDER BY score DESC", (video_id,))

        clips_data = [_clip_row_to_dict(c) for c in clips]
        await q.put({"event": "done", "job_id": job_id, "clips": clips_data})

    except Exception as e:
        logger.error("Rescan pipeline error: %s", e)
        await q.put({"event": "error", "job_id": job_id, "error": str(e)})


@app.post("/api/videos/{video_id}/rescan")
async def rescan_video(video_id: str, req: RescanRequest):
    """Re-scout and re-render an already saved video with new settings without re-downloading."""
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM videos WHERE id = ?", (video_id,))
        if not rows:
            raise HTTPException(404, "Video tidak ditemukan")
        video = dict(rows[0])

    if not video.get("transcript"):
        raise HTTPException(400, "Video belum memiliki transkrip, tidak dapat di-rescan")

    # Delete previous clips and files
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        old_clips = await db.execute_fetchall("SELECT file_path FROM clips WHERE video_id = ?", (video_id,))
        for c in old_clips:
            if c["file_path"] and Path(c["file_path"]).exists():
                try:
                    Path(c["file_path"]).unlink()
                except OSError:
                    pass
        await db.execute("DELETE FROM clips WHERE video_id = ?", (video_id,))
        await db.commit()

    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(str(settings.db_path)) as db:
        await db.execute(
            "INSERT INTO jobs (id, video_id, job_type, status, phase, progress, message, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (job_id, video_id, "scan", "pending", "scout", 10, "Menyiapkan rescan klip...", now, now),
        )
        await db.execute("UPDATE videos SET status = 'scouting', updated_at = ? WHERE id = ?", (now, video_id))
        await db.commit()

    q = BroadcastQueue(job_id)
    scan_req = ScanRequest(
        url=video["url"],
        clip_count=req.clip_count,
        duration_target=req.duration_target,
        content_type=req.content_type,
        subtitle_lang=req.subtitle_lang,
        layout=req.layout,
    )
    asyncio.create_task(_run_rescan_pipeline(job_id, video_id, video, scan_req, q))
    return {"job_id": job_id, "video_id": video_id}


@app.post("/api/clips/{clip_id}/retry")
async def retry_clip(clip_id: str, req: RenderRequest):
    """Re-render an individual clip with modified timings, layout, or title."""
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT c.*, v.url FROM clips c JOIN videos v ON v.id = c.video_id WHERE c.id = ?", (clip_id,)
        )
        if not rows:
            raise HTTPException(404, "Klip tidak ditemukan")
        clip = dict(rows[0])

    start_time = float(req.start_time) if req.start_time is not None else float(clip["start_time"])
    end_time = float(req.end_time) if req.end_time is not None else float(clip["end_time"])
    duration = round(max(1.0, end_time - start_time), 2)
    hook_title = req.hook_title.strip() if req.hook_title else clip["hook_title"]
    layout = req.layout or clip.get("layout", "blur")
    subtitle_lang = req.subtitle_lang or clip.get("subtitle_lang", "id")

    if clip.get("file_path") and Path(clip["file_path"]).exists():
        try:
            Path(clip["file_path"]).unlink()
        except OSError:
            pass

    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    q = BroadcastQueue(job_id)

    async with aiosqlite.connect(str(settings.db_path)) as db:
        await db.execute(
            "INSERT INTO jobs (id, video_id, clip_id, job_type, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (job_id, clip["video_id"], clip_id, "render", "pending", now, now),
        )
        await db.execute(
            "UPDATE clips SET start_time=?, end_time=?, duration=?, hook_title=?, layout=?, subtitle_lang=?, status='pending', error_msg=NULL, updated_at=? WHERE id=?",
            (start_time, end_time, duration, hook_title, layout, subtitle_lang, now, clip_id),
        )
        await db.commit()

    asyncio.create_task(render_clip(
        job_id, clip_id, clip["video_id"], clip["url"],
        start_time, end_time,
        layout, subtitle_lang, q, str(settings.db_path),
        custom_subtitles=req.custom_subtitles,
        custom_transcript=req.custom_transcript,
        subtitle_style=req.subtitle_style or "popin",
    ))

    return {"job_id": job_id, "clip_id": clip_id}


@app.get("/api/clips/{clip_id}/subtitles")
async def get_clip_subtitles(clip_id: str):
    """Retrieve subtitle cues and transcript for editing."""
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT c.*, v.transcript as video_transcript FROM clips c JOIN videos v ON v.id = c.video_id WHERE c.id = ?",
            (clip_id,),
        )
        if not rows:
            raise HTTPException(404, "Klip tidak ditemukan")
        clip = dict(rows[0])

    cues = []
    # 1. Stored subtitles_json
    if clip.get("subtitles_json"):
        try:
            raw_cues = json.loads(clip["subtitles_json"])
            for c in raw_cues:
                start = float(c.get("start", 0))
                end = float(c.get("end", start + c.get("duration", 3.0)))
                cues.append({
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "text": c.get("text", "").strip(),
                })
        except Exception:
            cues = []

    # 2. If no subtitles_json, slice from video transcript
    if not cues and clip.get("video_transcript"):
        clip_start = float(clip["start_time"])
        clip_end = float(clip["end_time"])
        v_lines = clip["video_transcript"].splitlines()
        pattern = re.compile(r"^\[(\d+):(\d+\.?\d*)\]\s*(.*)$")
        for line in v_lines:
            m = pattern.match(line.strip())
            if m:
                mins, secs, txt = int(m.group(1)), float(m.group(2)), m.group(3).strip()
                t_sec = mins * 60 + secs
                if clip_start <= t_sec <= clip_end:
                    rel_start = max(0.0, round(t_sec - clip_start, 2))
                    cues.append({
                        "start": rel_start,
                        "end": min(round(clip["duration"], 2), round(rel_start + 3.0, 2)),
                        "text": txt,
                    })

    # 3. Fallback placeholder
    if not cues:
        cues = [{
            "start": 0.0,
            "end": round(float(clip.get("duration", 30.0)), 2),
            "text": clip.get("transcript") or clip.get("hook_title") or "",
        }]

    return {
        "clip_id": clip_id,
        "subtitle_lang": clip.get("subtitle_lang", "id"),
        "transcript": clip.get("transcript") or " ".join(c["text"] for c in cues if c.get("text")),
        "cues": cues,
    }


@app.get("/api/clips/{clip_id}/export-subtitles")
async def export_clip_subtitles(clip_id: str, format: str = "srt"):
    """Export subtitles in SRT or ASS format for external NLE editing."""
    res = await get_clip_subtitles(clip_id)
    cues = res["cues"]
    if format.lower() == "ass":
        content = build_ass_from_cues(cues, style_preset="popin")
        media_type = "text/x-ssa"
        filename = f"clip_{clip_id[:8]}.ass"
    else:
        content = cues_to_srt(cues)
        media_type = "text/plain"
        filename = f"clip_{clip_id[:8]}.srt"

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/videos/{video_id}/bundle")
async def download_video_bundle(video_id: str):
    """Package all ready clips and copywriting into a single ZIP archive."""
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        video_rows = await db.execute_fetchall("SELECT * FROM videos WHERE id = ?", (video_id,))
        if not video_rows:
            raise HTTPException(404, "Proyek tidak ditemukan")
        video = dict(video_rows[0])

        clip_rows = await db.execute_fetchall(
            "SELECT * FROM clips WHERE video_id = ? ORDER BY clip_index ASC", (video_id,)
        )
        clips = [dict(c) for c in clip_rows]

    ready_clips = [c for c in clips if c.get("file_path") and Path(c["file_path"]).exists()]
    if not ready_clips:
        raise HTTPException(400, "Belum ada klip yang selesai dirender")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for c in ready_clips:
            file_path = Path(c["file_path"])
            arcname = f"Clip_{c['clip_index']:02d}_{c['id'][:8]}.mp4"
            zip_file.write(file_path, arcname=arcname)

        copy_lines = [
            "=" * 60,
            "CLIPFORGE // METADATA & COPYWRITING READY TO POST",
            f"Proyek : {video.get('title', 'Video')}",
            f"URL    : {video.get('url', '')}",
            "=" * 60,
            "",
        ]
        for c in clips:
            tags = []
            try:
                tags = json.loads(c.get("hashtags") or "[]")
            except Exception:
                pass
            tag_str = " ".join(f"#{t}" if not t.startswith("#") else t for t in tags)

            copy_lines.extend([
                f"[KLIP {c['clip_index']:02d}] {c.get('hook_title', 'Untitled')}",
                f"Durasi : {round(c['duration'])} detik ({c['start_time']}s – {c['end_time']}s)",
                f"Layout : {c.get('layout', 'blur').upper()}",
                "",
                "Caption:",
                c.get("caption") or c.get("hook_title") or "",
                "",
                "Hashtags:",
                tag_str,
                "-" * 60,
                "",
            ])
        zip_file.writestr("copywriting_dan_hashtags.txt", "\n".join(copy_lines))

    zip_buffer.seek(0)
    safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', video.get("title", "clipforge"))[:30]
    filename = f"{safe_title}_clips.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: str):
    async with aiosqlite.connect(str(settings.db_path)) as db:
        db.row_factory = aiosqlite.Row
        clips = await db.execute_fetchall("SELECT file_path FROM clips WHERE video_id = ?", (video_id,))
        for c in clips:
            if c["file_path"] and Path(c["file_path"]).exists():
                try:
                    Path(c["file_path"]).unlink()
                except OSError:
                    pass
        for f in settings.raw_dir.glob(f"{video_id}.*"):
            try:
                f.unlink()
            except OSError:
                pass
        await db.execute("DELETE FROM clips WHERE video_id = ?", (video_id,))
        await db.execute("DELETE FROM jobs WHERE video_id = ?", (video_id,))
        await db.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        await db.commit()
    return {"deleted": video_id}


# ── Serve frontend static files with SPA fallback ────────────────────────────
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    if (frontend_dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_spa(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=False)
