"""Pipeline stage execution implementations for Ingest, Signals, and Fusion."""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
import numpy as np
import structlog

from clipforge.asr.models import CandidateTranscript
from clipforge.asr.whisper import transcribe_candidate_slice, transcribe_clip_media
from clipforge.boundaries.snap import snap_boundaries_to_words
from clipforge.core.config import settings
from clipforge.fusion.candidates import make_candidates
from clipforge.fusion.fuse import fuse
from clipforge.fusion.presets import load_preset
from clipforge.fusion.snap import refine_boundaries
from clipforge.ingest.download import download_ingest_assets, download_video_range
from clipforge.ingest.models import VideoMetadata
from clipforge.ingest.probe import probe_video
from clipforge.llm.client import evaluate_candidate_scout
from clipforge.quality.gate import evaluate_quality_gate
from clipforge.render.engine import render_single_clip
from clipforge.signals.audio import extract_audio_features
from clipforge.signals.chat import extract_chat_features
from clipforge.signals.heatmap import extract_heatmap_features
from clipforge.signals.models import AudioFeatures, ChatFeatures, HeatmapFeatures
from clipforge.subtitles import (
    SubtitleWord,
    create_kinetic_chunks,
    export_srt,
    generate_ass_script,
    load_style_preset,
    validate_and_normalize_words,
)
from clipforge.timeline.models import TimelineResponse
from clipforge.timeline.service import get_candidates_for_job, save_timeline_artifact

logger = structlog.get_logger(__name__)


def get_job_dir(job_id: str) -> Path:
    p = settings.data_dir / "jobs" / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------
# Stage 1: VALIDATE
# ---------------------------------------------------------
async def stage_validate(
    db: aiosqlite.Connection,
    job_id: str,
    stage_input: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    job_dir = get_job_dir(job_id)
    url = stage_input["source_url"]

    # 1. Probe video metadata
    metadata: VideoMetadata = await probe_video(url, max_duration_s=settings.max_vod_seconds)

    # 2. Update jobs table
    await db.execute(
        """
        UPDATE jobs
        SET video_id = ?, title = ?, duration_s = ?
        WHERE id = ?
        """,
        (metadata.video_id, metadata.title, metadata.duration_s, job_id),
    )
    await db.commit()

    # 3. Save metadata artifact
    meta_path = job_dir / "meta.json"
    meta_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")

    metrics = {
        "video_id": metadata.video_id,
        "duration_s": metadata.duration_s,
        "has_chat": metadata.has_chat,
        "has_heatmap": metadata.has_heatmap,
    }
    return [str(meta_path)], metrics


# ---------------------------------------------------------
# Stage 2: FETCH_SIGNALS
# ---------------------------------------------------------
async def stage_fetch_signals(
    db: aiosqlite.Connection,
    job_id: str,
    stage_input: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    job_dir = get_job_dir(job_id)
    meta_path = job_dir / "meta.json"
    if not meta_path.exists():
        raise RuntimeError("Missing meta.json from validate stage")

    metadata = VideoMetadata.model_validate_json(meta_path.read_text(encoding="utf-8"))

    # Download assets
    ingest_res = await download_ingest_assets(metadata, job_dir)

    outputs = [ingest_res.audio_path]
    if ingest_res.chat_path:
        outputs.append(ingest_res.chat_path)
    if ingest_res.heatmap_path:
        outputs.append(ingest_res.heatmap_path)

    metrics = {
        "audio_bytes": Path(ingest_res.audio_path).stat().st_size
        if Path(ingest_res.audio_path).exists()
        else 0,
        "chat_downloaded": ingest_res.chat_path is not None,
        "heatmap_downloaded": ingest_res.heatmap_path is not None,
        "disk_used_bytes": ingest_res.disk_used_bytes,
    }
    return outputs, metrics


# ---------------------------------------------------------
# Stage 3: ANALYZE_SIGNALS
# ---------------------------------------------------------
async def stage_analyze_signals(
    db: aiosqlite.Connection,
    job_id: str,
    stage_input: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    job_dir = get_job_dir(job_id)
    signals_dir = job_dir / "signals"
    signals_dir.mkdir(parents=True, exist_ok=True)

    meta_path = job_dir / "meta.json"
    metadata = VideoMetadata.model_validate_json(meta_path.read_text(encoding="utf-8"))

    # 1. Locate audio file
    audio_candidates = list(job_dir.glob("audio_raw.*"))
    if not audio_candidates:
        raise RuntimeError(f"Audio file missing in {job_dir}")
    audio_file = audio_candidates[0]

    # 2. Extract audio features
    audio_feats: AudioFeatures = await extract_audio_features(audio_file)
    audio_out = signals_dir / "audio_features.json"
    audio_out.write_text(audio_feats.model_dump_json(), encoding="utf-8")

    # 3. Locate and extract chat features
    chat_candidates = list(job_dir.glob("chat.*"))
    chat_file = chat_candidates[0] if chat_candidates else None
    chat_feats: ChatFeatures = extract_chat_features(chat_file, duration_s=metadata.duration_s)
    chat_out = signals_dir / "chat_features.json"
    chat_out.write_text(chat_feats.model_dump_json(), encoding="utf-8")

    # 4. Extract heatmap features
    heatmap_candidates = list(job_dir.glob("heatmap.json"))
    heatmap_file = heatmap_candidates[0] if heatmap_candidates else None
    heatmap_feats: HeatmapFeatures = extract_heatmap_features(
        heatmap_file, duration_s=metadata.duration_s
    )
    heatmap_out = signals_dir / "heatmap_features.json"
    heatmap_out.write_text(heatmap_feats.model_dump_json(), encoding="utf-8")

    metrics = {
        "audio_seconds": audio_feats.duration_s,
        "speech_segments_count": len(audio_feats.speech_segments),
        "chat_available": chat_feats.available,
        "chat_messages": chat_feats.total_messages,
        "heatmap_available": heatmap_feats.available,
    }

    outputs = [str(audio_out), str(chat_out), str(heatmap_out)]
    return outputs, metrics


# ---------------------------------------------------------
# Stage 4: FUSE_CANDIDATES
# ---------------------------------------------------------
async def stage_fuse_candidates(
    db: aiosqlite.Connection,
    job_id: str,
    stage_input: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    job_dir = get_job_dir(job_id)
    signals_dir = job_dir / "signals"

    meta_path = job_dir / "meta.json"
    metadata = VideoMetadata.model_validate_json(meta_path.read_text(encoding="utf-8"))

    audio_feats = AudioFeatures.model_validate_json(
        (signals_dir / "audio_features.json").read_text(encoding="utf-8")
    )
    chat_feats = ChatFeatures.model_validate_json(
        (signals_dir / "chat_features.json").read_text(encoding="utf-8")
    )
    heatmap_feats = HeatmapFeatures.model_validate_json(
        (signals_dir / "heatmap_features.json").read_text(encoding="utf-8")
    )

    # Load preset
    genre = stage_input.get("genre", "gaming")
    cfg = load_preset(genre)

    # Prepare signal arrays
    raw_signals: dict[str, np.ndarray | None] = {
        "loud_surge": np.array(audio_feats.loud_surge, dtype=np.float32),
        "onset_density": np.array(audio_feats.onset_density, dtype=np.float32),
        "nonspeech_loud": np.array(audio_feats.nonspeech_loud, dtype=np.float32),
        "hf_ratio": np.array(audio_feats.hf_ratio, dtype=np.float32),
        "chat_rate": np.array(chat_feats.chat_rate, dtype=np.float32)
        if chat_feats.available
        else None,
        "chat_hype": np.array(chat_feats.chat_hype, dtype=np.float32)
        if chat_feats.available
        else None,
        "clip_intent": np.array(chat_feats.clip_intent, dtype=np.float32)
        if chat_feats.available
        else None,
        "heatmap": np.array(heatmap_feats.heatmap_curve, dtype=np.float32)
        if heatmap_feats.available
        else None,
    }

    # Execute fusion
    fuse_result = fuse(
        signals=raw_signals,
        weights=cfg.weights,
        agree_thr=cfg.agreement.threshold,
        agree_min=cfg.agreement.min_modalities,
        agree_bonus=cfg.agreement.bonus,
        agree_win_s=cfg.agreement.window_s,
    )

    # Generate initial candidates
    candidates = make_candidates(
        score=fuse_result.score,
        total_duration_s=metadata.duration_s,
        cfg=cfg.candidate_generation,
        hop_s=1.0,
        per_signal_norm=fuse_result.per_signal,
    )

    # Refine candidate boundaries using VAD speech segments
    for cand in candidates:
        snapped_start, snapped_end = refine_boundaries(
            start_s=cand.start_s,
            end_s=cand.end_s,
            speech_segments=audio_feats.speech_segments,
            total_duration_s=metadata.duration_s,
            min_duration_s=cfg.candidate_generation.min_duration_s,
            max_duration_s=cfg.candidate_generation.max_duration_s,
        )
        cand.start_s = snapped_start
        cand.end_s = snapped_end
        cand.duration_s = round(snapped_end - snapped_start, 2)

    # Clear old candidates for this job and insert new candidates into DB
    await db.execute("DELETE FROM candidates WHERE job_id = ?", (job_id,))
    for cand in candidates:
        await db.execute(
            """
            INSERT INTO candidates (
                id, job_id, rank, start_s, end_s, peak_s, signal_score, final_score,
                category, title, hook_text, reason, evidence_json, flags_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cand.id,
                job_id,
                cand.rank,
                cand.start_s,
                cand.end_s,
                cand.peak_s,
                cand.signal_score,
                cand.final_score,
                cand.category,
                cand.title,
                cand.hook_text,
                cand.reason,
                json.dumps(cand.evidence),
                json.dumps(cand.flags),
                cand.status,
            ),
        )
    await db.commit()

    # Build and save timeline artifact
    signal_curves_dict = {
        "fused_score": [float(x) for x in fuse_result.score],
        "loud_surge": audio_feats.loud_surge,
        "onset_density": audio_feats.onset_density,
        "speech_prob": audio_feats.speech_prob,
    }
    if chat_feats.available:
        signal_curves_dict["chat_rate"] = chat_feats.chat_rate
        signal_curves_dict["chat_hype"] = chat_feats.chat_hype
    if heatmap_feats.available:
        signal_curves_dict["heatmap"] = heatmap_feats.heatmap_curve

    timeline_resp = TimelineResponse(
        job_id=job_id,
        duration_s=metadata.duration_s,
        hop_s=1.0,
        signals=signal_curves_dict,
        candidates=candidates,
        metadata={"title": metadata.title, "genre": genre},
    )
    timeline_path = save_timeline_artifact(job_dir, timeline_resp)

    metrics = {
        "candidates_count": len(candidates),
        "signals_used": fuse_result.used,
        "preset_used": genre,
    }
    return [str(timeline_path)], metrics


# ---------------------------------------------------------
# Stage 5: TARGETED_ASR
# ---------------------------------------------------------
async def stage_targeted_asr(
    db: aiosqlite.Connection,
    job_id: str,
    stage_input: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    job_dir = get_job_dir(job_id)
    signals_dir = job_dir / "signals"
    transcripts_dir = job_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    genre = stage_input.get("genre", "gaming")

    # Locate audio file
    audio_candidates = list(job_dir.glob("audio_raw.*"))
    if not audio_candidates:
        raise RuntimeError(f"Audio file missing in {job_dir}")
    audio_file = audio_candidates[0]

    # Load audio and chat features
    audio_feats = AudioFeatures.model_validate_json(
        (signals_dir / "audio_features.json").read_text(encoding="utf-8")
    )
    chat_feats = ChatFeatures.model_validate_json(
        (signals_dir / "chat_features.json").read_text(encoding="utf-8")
    )

    # Fetch candidates from DB
    cands_resp = await get_candidates_for_job(job_id, db)
    candidates = cands_resp.candidates

    output_files: list[str] = []
    transcribed_count = 0
    rejected_talking_count = 0

    for cand in candidates:
        # Pre-ASR heuristic quality gate
        gate_res = evaluate_quality_gate(cand, audio_feats, chat_feats, genre=genre)
        cand.flags = list(set(cand.flags + gate_res.flags))

        if not gate_res.passed:
            rejected_talking_count += 1
            cand.status = "rejected"
            cand.reason = gate_res.reason
            cand.final_score = round(cand.signal_score * (1.0 - gate_res.score_penalty), 4)
            # Update DB
            await db.execute(
                """
                UPDATE candidates
                SET status = ?, reason = ?, flags_json = ?, final_score = ?
                WHERE id = ? AND job_id = ?
                """,
                (
                    cand.status,
                    cand.reason,
                    json.dumps(cand.flags),
                    cand.final_score,
                    cand.id,
                    job_id,
                ),
            )
            continue

        # Targeted ASR transcription on candidate window
        transcript: CandidateTranscript = transcribe_candidate_slice(
            audio_path=audio_file,
            cand=cand,
            model_name=settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute,
        )

        # Word boundary snapping if words were detected
        if transcript.words:
            cand = snap_boundaries_to_words(cand, transcript.words)

        # Save transcript artifact
        tr_path = transcripts_dir / f"{cand.id}.json"
        tr_path.write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
        output_files.append(str(tr_path))
        transcribed_count += 1

        # Update candidate boundaries in DB
        await db.execute(
            """
            UPDATE candidates
            SET start_s = ?, end_s = ?, flags_json = ?
            WHERE id = ? AND job_id = ?
            """,
            (cand.start_s, cand.end_s, json.dumps(cand.flags), cand.id, job_id),
        )

    await db.commit()

    metrics = {
        "transcribed_count": transcribed_count,
        "rejected_talking_count": rejected_talking_count,
    }
    return output_files, metrics


# ---------------------------------------------------------
# Stage 6: SCOUT_RERANK
# ---------------------------------------------------------
async def stage_scout_rerank(
    db: aiosqlite.Connection,
    job_id: str,
    stage_input: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    job_dir = get_job_dir(job_id)
    signals_dir = job_dir / "signals"
    transcripts_dir = job_dir / "transcripts"

    genre = stage_input.get("genre", "gaming")

    meta_path = job_dir / "meta.json"
    metadata = VideoMetadata.model_validate_json(meta_path.read_text(encoding="utf-8"))

    audio_feats = AudioFeatures.model_validate_json(
        (signals_dir / "audio_features.json").read_text(encoding="utf-8")
    )
    chat_feats = ChatFeatures.model_validate_json(
        (signals_dir / "chat_features.json").read_text(encoding="utf-8")
    )

    cands_resp = await get_candidates_for_job(job_id, db)
    candidates = cands_resp.candidates

    approved_count = 0
    rejected_count = 0

    for cand in candidates:
        # Load transcript if exists
        tr_file = transcripts_dir / f"{cand.id}.json"
        if tr_file.exists():
            transcript = CandidateTranscript.model_validate_json(
                tr_file.read_text(encoding="utf-8")
            )
        else:
            transcript = CandidateTranscript(candidate_id=cand.id)

        # Call LLM Scout or fallback heuristic
        verdict = await evaluate_candidate_scout(
            cand=cand,
            transcript=transcript,
            meta=metadata,
            audio_feats=audio_feats,
            chat_feats=chat_feats,
            genre=genre,
        )

        cand.title = verdict.title
        cand.hook_text = verdict.hook_text
        cand.category = verdict.category
        cand.reason = verdict.reason
        cand.llm_score = verdict.confidence
        cand.flags = list(set(cand.flags + verdict.flags))

        if verdict.verdict == "REJECT":
            cand.status = "rejected"
            cand.final_score = round(cand.signal_score * 0.3, 4)
            rejected_count += 1
        else:
            cand.status = "proposed"
            cand.final_score = round(cand.signal_score * verdict.confidence, 4)
            approved_count += 1

    # Re-rank: Sort proposed/approved first by final_score desc, then rejected
    valid_cands = [c for c in candidates if c.status != "rejected"]
    rejected_cands = [c for c in candidates if c.status == "rejected"]

    valid_cands.sort(key=lambda c: c.final_score, reverse=True)
    rejected_cands.sort(key=lambda c: c.final_score, reverse=True)

    reranked = valid_cands + rejected_cands
    for rank_idx, c in enumerate(reranked, start=1):
        c.rank = rank_idx
        await db.execute(
            """
            UPDATE candidates
            SET rank = ?, final_score = ?, llm_score = ?, category = ?,
                title = ?, hook_text = ?, reason = ?, flags_json = ?, status = ?
            WHERE id = ? AND job_id = ?
            """,
            (
                c.rank,
                c.final_score,
                c.llm_score,
                c.category,
                c.title,
                c.hook_text,
                c.reason,
                json.dumps(c.flags),
                c.status,
                c.id,
                job_id,
            ),
        )

    await db.commit()

    # Update timeline artifact with re-ranked candidates
    timeline_file = job_dir / "timeline.json"
    if timeline_file.exists():
        tl_data = json.loads(timeline_file.read_text(encoding="utf-8"))
        tl_data["candidates"] = [c.model_dump() for c in reranked]
        timeline_file.write_text(json.dumps(tl_data, indent=2), encoding="utf-8")

    metrics = {
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "top_title": valid_cands[0].title if valid_cands else "None",
    }
    return [str(timeline_file)], metrics


# ---------------------------------------------------------
# Stage 7: RENDER_CLIPS
# ---------------------------------------------------------
async def stage_render_clips(
    db: aiosqlite.Connection,
    job_id: str,
    stage_input: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    job_dir = get_job_dir(job_id)
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    transcripts_dir = job_dir / "transcripts"

    source_url = stage_input.get("source_url", "")
    target_count = int(stage_input.get("clip_count", 5))
    reframe_mode = stage_input.get("reframe_mode", "blur")
    subtitle_style = stage_input.get("subtitle_style", "classic_white")

    # Fetch kept, specific, or top candidates from DB
    cand_ids = stage_input.get("candidate_ids")
    if cand_ids and isinstance(cand_ids, list) and len(cand_ids) > 0:
        placeholders = ",".join("?" for _ in cand_ids)
        query = f"""
            SELECT id, rank, COALESCE(user_start_s, start_s), COALESCE(user_end_s, end_s), title, category
            FROM candidates
            WHERE job_id = ? AND id IN ({placeholders})
            ORDER BY rank ASC, final_score DESC
        """
        params: tuple[Any, ...] = (job_id, *cand_ids)
    else:
        async with db.execute(
            "SELECT COUNT(*) FROM candidates WHERE job_id = ? AND status = 'kept'", (job_id,)
        ) as cur:
            row = await cur.fetchone()
            kept_count = row[0] if row else 0

        if kept_count > 0:
            query = """
                SELECT id, rank, COALESCE(user_start_s, start_s), COALESCE(user_end_s, end_s), title, category
                FROM candidates
                WHERE job_id = ? AND status = 'kept'
                ORDER BY rank ASC, final_score DESC
            """
            params = (job_id,)
        else:
            query = """
                SELECT id, rank, COALESCE(user_start_s, start_s), COALESCE(user_end_s, end_s), title, category
                FROM candidates
                WHERE job_id = ? AND status != 'rejected'
                ORDER BY rank ASC, final_score DESC
                LIMIT ?
            """
            params = (job_id, target_count)

    candidates_to_render = []
    async with db.execute(query, params) as cur:
        async for r in cur:
            st = float(r[2])
            en = float(r[3])
            dur = max(1.0, round(en - st, 3))
            candidates_to_render.append(
                {
                    "id": r[0],
                    "rank": r[1],
                    "start_s": st,
                    "end_s": en,
                    "duration_s": dur,
                    "title": r[4],
                    "category": r[5],
                }
            )

    rendered_files: list[str] = []
    qa_passed_count = 0
    style_preset = load_style_preset(subtitle_style)
    total_candidates = len(candidates_to_render)
    last_render_error = "Unknown error"

    for idx, cand in enumerate(candidates_to_render):
        # Progressively update job render percentage: 0.80 -> 0.98
        current_pct = round(0.80 + 0.18 * (idx / max(1, total_candidates)), 2)
        await db.execute(
            "UPDATE jobs SET progress = ?, updated_at = ? WHERE id = ?",
            (current_pct, datetime.now(UTC).isoformat(), job_id),
        )
        cand_id = cand["id"]
        # Mark candidate as rendering
        await db.execute(
            "UPDATE candidates SET status = 'rendering' WHERE id = ?",
            (cand_id,),
        )
        await db.commit()

        clip_id = str(uuid.uuid4())
        clip_folder = clips_dir / clip_id
        clip_folder.mkdir(parents=True, exist_ok=True)

        raw_video = clip_folder / "raw.mp4"

        # 1. Download or trim raw video segment
        try:
            await download_video_range(
                source_url=source_url,
                start_s=cand["start_s"],
                end_s=cand["end_s"],
                out_path=raw_video,
                cookies_path=settings.cookies_file,
            )
        except Exception as exc:
            logger.error(
                "failed_to_download_clip_range",
                clip_id=clip_id,
                candidate_id=cand_id,
                error=str(exc),
            )
            last_render_error = f"Download range failed for {cand_id}: {exc}"
            await db.execute(
                "UPDATE candidates SET status = 'render_failed' WHERE id = ?",
                (cand_id,),
            )
            await db.commit()
            continue

        # 2. Extract ground-truth word timestamps directly from raw_video
        raw_words: list[SubtitleWord] = []
        try:
            raw_words = await asyncio.to_thread(
                transcribe_clip_media,
                raw_video,
                settings.whisper_model,
                settings.whisper_device,
                settings.whisper_compute,
            )
        except Exception as exc:
            logger.warning("transcribe_raw_video_failed", clip_id=clip_id, error=str(exc))

        words_for_clip: list[SubtitleWord] = []
        if raw_words:
            words_for_clip = raw_words
        else:
            # Fallback to candidate transcript if raw_video had no words or transcription failed
            tr_file = transcripts_dir / f"{cand_id}.json"
            if tr_file.exists():
                try:
                    tr_data = CandidateTranscript.model_validate_json(
                        tr_file.read_text(encoding="utf-8")
                    )
                    c_start = cand["start_s"]
                    c_end = cand["end_s"]
                    for w in tr_data.words:
                        # Exclude words completely outside clip
                        if w.end_s <= c_start or w.start_s >= c_end:
                            continue
                        rel_start = max(0.0, round(w.start_s - c_start, 3))
                        rel_end = min(
                            cand["duration_s"],
                            max(rel_start + 0.04, round(w.end_s - c_start, 3)),
                        )
                        words_for_clip.append(
                            SubtitleWord(
                                idx=len(words_for_clip),
                                start_s=rel_start,
                                end_s=rel_end,
                                text=w.text,
                                confidence=w.confidence,
                            )
                        )
                except Exception as exc:
                    logger.warning(
                        "fallback_transcript_parse_failed", clip_id=clip_id, error=str(exc)
                    )

        val_words = validate_and_normalize_words(words_for_clip, clip_duration_s=cand["duration_s"])
        chunks = create_kinetic_chunks(val_words)
        ass_content = generate_ass_script(chunks, style=style_preset)

        ass_file = clip_folder / "subs.ass"
        ass_file.write_text(ass_content, encoding="utf-8")

        srt_file = clip_folder / "clip.srt"
        srt_file.write_text(export_srt(chunks), encoding="utf-8")

        has_subtitles = subtitle_style.lower() not in (
            "none",
            "off",
            "disable",
            "no_subtitles",
            "tanpa_subtitle",
        )

        # 3. Render clip via engine
        try:
            render_res = render_single_clip(
                clip_dir=clip_folder,
                raw_video=raw_video,
                ass_path=ass_file if has_subtitles else None,
                mode=reframe_mode,
                expected_duration_s=cand["duration_s"],
            )
        except Exception as exc:
            logger.error(
                "render_single_clip_failed", clip_id=clip_id, candidate_id=cand_id, error=str(exc)
            )
            last_render_error = f"FFmpeg render failed for {cand_id}: {exc}"
            await db.execute(
                "UPDATE candidates SET status = 'render_failed' WHERE id = ?",
                (cand_id,),
            )
            await db.commit()
            continue

        now_iso = datetime.now(UTC).isoformat()
        clip_status = "done" if render_res["success"] else "failed"
        if render_res["success"]:
            qa_passed_count += 1
            if render_res["final_path"]:
                rendered_files.append(render_res["final_path"])

        # 4. Insert clip into DB
        r_params_json = json.dumps({"reframe_mode": reframe_mode, "subtitle_style": subtitle_style})
        qa_json_str = json.dumps(render_res["qa"])

        await db.execute(
            """
            INSERT INTO clips (
                id, candidate_id, job_id, status, video_path, thumb_path, srt_path,
                width, height, duration_s, render_params_json, qa_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1080, 1920, ?, ?, ?, ?)
            """,
            (
                clip_id,
                cand_id,
                job_id,
                clip_status,
                render_res["final_path"],
                render_res["thumb_path"],
                str(srt_file),
                cand["duration_s"],
                r_params_json,
                qa_json_str,
                now_iso,
            ),
        )

        # 5. Insert subtitle track & words into DB
        track_id = str(uuid.uuid4())
        await db.execute(
            """
            INSERT INTO subtitle_tracks (id, clip_id, revision, source, language, style_json, created_at)
            VALUES (?, ?, 1, 'asr', 'id', ?, ?)
            """,
            (track_id, clip_id, json.dumps({"preset": subtitle_style}), now_iso),
        )

        for subw in val_words:
            await db.execute(
                """
                INSERT INTO subtitle_words (track_id, idx, start_s, end_s, text, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (track_id, subw.idx, subw.start_s, subw.end_s, subw.text, subw.confidence),
            )

        # Mark candidate as rendered
        await db.execute("UPDATE candidates SET status = 'rendered' WHERE id = ?", (cand_id,))
        await db.commit()

    if not rendered_files and candidates_to_render:
        raise RuntimeError(
            f"Gagal me-render klip: 0 dari {len(candidates_to_render)} kandidat berhasil dirender. "
            f"Penyebab terakhir: {last_render_error}"
        )

    metrics = {
        "clips_rendered": len(rendered_files),
        "qa_passed_count": qa_passed_count,
    }
    return rendered_files, metrics
