# Legacy v1 Audit (ClipForge v1)

| Metadata | Details |
|---|---|
| Date | 2026-10-04 |
| Target Snapshot | Commit `5cded7c` (tag: `legacy-v1-final`, branch: `legacy/v1`) |
| Auditor | Senior Full-stack Agent |

---

## 1. Overview & Architecture

ClipForge v1 was designed as a monolith FastAPI service serving a pre-built React/Vite single-page application (SPA). It implements a 3-phase pipeline (`ingest` -> `scout` -> `editor`) communicating with the client over Server-Sent Events (SSE).

### Pipeline Flow in v1
1. **Ingest (`workers/ingest.py`)**:
   - Fetches video metadata using `yt_dlp.YoutubeDL(download=False)`.
   - Attempts subtitle retrieval: `yt-dlp` auto-subs first, then `youtube_transcript_api`.
   - If captions missing and video <= 1800s: downloads full audio via `download_audio()` and transcribes using `faster-whisper`.
   - If captions missing and video > 1800s: skips audio transcription entirely, setting transcript to empty string (`""`).
   - If video <= 3600s: downloads audio and calculates RMS energy spikes via `librosa`.
   - If video > 3600s: skips audio download, leaving spikes empty (`[]`).
2. **Scout (`workers/scout.py` & `services/llm.py`)**:
   - Sends formatted transcript (first 80,000 characters) + top 20 audio spikes to an OpenAI-compatible endpoint (9Router/Gemini/OpenAI).
   - If transcript is empty and spikes are empty (VOD > 3600s without CC), sends only title and total duration to LLM, causing blind halluncination of timestamps.
   - If LLM fails, falls back to `_generate_fallback_moments` (evenly spaced timestamps across video span).
3. **Editor (`workers/editor.py` & `services/reframe.py` & `services/subtitles.py`)**:
   - Downloads each clip time range using `yt-dlp.utils.download_range_func`.
   - Runs `faster-whisper` on each cut video segment with `vad_filter=False`.
   - Generates `.ass` subtitles with hardcoded 4-word chunks and inline `\fscx114\fscy114\c&H0000A8FF&` tags without measuring font bounds.
   - Burns subtitles into 9:16 vertical canvas (`scale=1080:1920`) using FFmpeg filter complex.
   - Runs `loudnorm` filter with `-c:v copy`.

---

## 2. Inventory of Modules & Disposition Matrix

| Path | Purpose | Lines / Size | Disposition | Justification |
|---|---|---|---|---|
| `backend/config.py` | `pydantic-settings` configuration loader | 48 lines | **Rewrite** | Hardcodes specific paths, lacks robust validation, lacks model independence. |
| `backend/db.py` | SQLite schema and initialization | 80 lines | **Rewrite** | No migration runner; resets unfinished jobs to error on startup instead of checkpoint resumption; lacks candidate evidence tables. |
| `backend/models.py` | Pydantic v1/v2 request/response schemas | 120 lines | **Rewrite** | Weak validation; mixed responsibilities; lack RFC 7807 problem details. |
| `backend/main.py` | FastAPI application endpoints & background orchestration | 780 lines | **Rewrite** | Massive god-file handling routing, process orchestration, DB queries, static serving, and zip bundling in single module. |
| `backend/services/transcript.py` | Transcript retrieval (yt-dlp, api, whisper) | 165 lines | **Rewrite** | Subprocess calls with `shell=False` but brittle VTT regex parsing; lacks word timestamp normalization; blocks loop. |
| `backend/services/llm.py` | LLM client and prompt templates | 230 lines | **Rewrite** | Hallucinates on empty transcript; injects raw un-normalized spikes; regex-based JSON extraction; prompt lacks anti-injection fences. |
| `backend/services/reframe.py` | FFmpeg command generation for 9:16 layouts | 185 lines | **Keep concept / Rewrite** | Filter graph concepts (`blur`, `center`, `stacked`) are solid, but escape logic is naive (`_escape_filter_path`), missing font directory bounding and safe margins. |
| `backend/services/subtitles.py` | ASS and SRT subtitle generator | 225 lines | **Drop / Rewrite** | Instantiates `WhisperModel` inside loop; `vad_filter=False`; ASS generation lacks text wrapping metrics; unescaped `{}` characters. |
| `backend/workers/ingest.py` | Phase 1 worker | 145 lines | **Drop / Rewrite** | Transcript-first bias; skips audio on >1800s; skips spikes on >3600s; not resumable. |
| `backend/workers/scout.py` | Phase 2 worker | 110 lines | **Drop / Rewrite** | Thin wrapper around `llm.py`; no candidate ranking fusion. |
| `backend/workers/audio_analysis.py` | Audio download & RMS energy calculation | 130 lines | **Keep concept / Rewrite** | Librosa STFT loads full audio into memory; must be rewritten for chunked streaming PCM. |
| `backend/workers/editor.py` | Phase 3 worker (range download & render) | 220 lines | **Rewrite** | Direct range download without keyframe cut re-sync causes A/V drift; missing QA gates. |
| `frontend/` | React 18 + Vite + Tailwind UI | ~2500 lines | **Rewrite in Phase 6** | UI lacks timeline explorer, evidence cards, and server-side preview frames. |

---

## 3. Database Schema Audit

v1 uses SQLite with WAL mode. Tables:
- `videos`: Tracks metadata, raw transcript string, audio spikes JSON.
- `clips`: Stores candidate timing, score, ASS subtitle JSON, status.
- `jobs`: Tracks execution phase and integer percentage (0-100).
- `rate_limits`: Basic IP-based sliding window rate limiter.

### Deficiencies in v1 DB Schema
1. **No Evidence Trail**: Does not store which signal contributed what weight to a candidate.
2. **No Review Phase State**: Candidates are immediately converted into renderable clips without a formal human-in-the-loop review state (`proposed` -> `kept` / `rejected` / `retimed`).
3. **No Resumability / Checkpoints**: Any container restart executes `UPDATE jobs SET status = 'error'`, abandoning partially completed work.
4. **No Word-Level Timestamps Store**: Subtitles are stored as JSON blobs rather than structured word-level relational records.

---

## 4. Dependencies & Toolchain Audit

v1 `requirements.txt`:
```text
fastapi==0.115.0
uvicorn[standard]==0.30.6
aiosqlite==0.20.0
pydantic==2.8.2
pydantic-settings==2.5.2
python-multipart==0.0.9
httpx==0.27.2
openai==1.51.0
yt-dlp>=2025.1.1
youtube-transcript-api==0.6.2
faster-whisper==1.0.3
librosa==0.10.2
soundfile>=0.12.1
numpy==1.26.4
python-dotenv==1.0.1
aiofiles==24.1.0
```

### Toolchain Findings
- `numpy==1.26.4` and `librosa==0.10.2`: Memory intensive when analyzing 3+ hour files.
- `faster-whisper==1.0.3`: CPU execution with `compute_type="int8"` works reliably, but initializing per clip in v1 wastes 5-10s per clip.
- FFmpeg on host: `4.4.2` with `libass` support enabled.
- Docker environment: Root privileges restricted; local execution must rely on direct Python virtual environments (`uv`).
