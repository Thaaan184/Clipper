"""LLM Scout client for evidence-based candidate verification and metadata generation."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import structlog
from openai import AsyncOpenAI

from clipforge.asr.models import CandidateTranscript
from clipforge.core.config import settings
from clipforge.fusion.models import CandidateWindow
from clipforge.ingest.models import VideoMetadata
from clipforge.llm.models import ScoutVerdict
from clipforge.signals.models import AudioFeatures, ChatFeatures

logger = structlog.get_logger(__name__)

PROMPT_FILE = Path(__file__).parent / "prompts" / "scout_v1.md"


def _build_heuristic_verdict(
    cand: CandidateWindow,
    transcript: CandidateTranscript,
    audio_feats: AudioFeatures,
    chat_feats: ChatFeatures,
) -> ScoutVerdict:
    """Deterministic heuristic scout fallback when LLM is unavailable or unconfigured."""
    start_i = max(0, int(cand.start_s))
    end_i = min(len(audio_feats.speech_prob), int(np.ceil(cand.end_s)))

    max_surge = (
        float(np.max(audio_feats.loud_surge[start_i:end_i]))
        if len(audio_feats.loud_surge) > start_i
        else 0.0
    )
    mean_onset = (
        float(np.mean(audio_feats.onset_density[start_i:end_i]))
        if len(audio_feats.onset_density) > start_i
        else 0.0
    )

    has_hype_chat = False
    if chat_feats.available and len(chat_feats.chat_hype) > start_i:
        hype_slice = chat_feats.chat_hype[start_i:end_i]
        if len(hype_slice) > 0 and np.max(hype_slice) > 0.0:
            has_hype_chat = True

    text_lower = transcript.text.lower()
    has_text_laugh = any(w in text_lower for w in ["wkwk", "haha", "ngakak", "lol", "anjir"])
    has_text_hype = any(
        w in text_lower for w in ["mati", "squad", "rata", "clutch", "gila", "nice", "gas"]
    )

    if "talking_only" in cand.flags:
        return ScoutVerdict(
            verdict="REJECT",
            category="talking_only",
            title="Sesi Ngobrol Santai",
            hook_text="Lagi bahas sesuatu...",
            reason="Percakapan tanpa aksi gameplay atau reaksi penonton yang menonjol.",
            confidence=0.85,
            flags=["talking_only"],
        )

    if has_text_laugh:
        return ScoutVerdict(
            verdict="KEEP",
            category="funny_fail",
            title="Momen Kocak & Reaksi Penonton",
            hook_text="Bisa-bisanya kejadian kayak gini...",
            reason="Terdapat indikasi tawa penonton/streamer pada momen ini.",
            confidence=0.88,
            flags=["funny_moment"],
        )

    if max_surge > 0.35 or mean_onset > 1.0 or has_hype_chat or has_text_hype:
        return ScoutVerdict(
            verdict="KEEP",
            category="gameplay_highlight",
            title="Aksi Intens Gameplay",
            hook_text="Detik-detik pertempuran sengit...",
            reason="Lonjakan audio dan aktivitas onset tinggi menandakan momen pertarungan.",
            confidence=0.90,
            flags=["combat_action"],
        )

    return ScoutVerdict(
        verdict="KEEP",
        category="gameplay_highlight",
        title="Highlight Momen Gameplay",
        hook_text="Lihat apa yang terjadi selanjutnya!",
        reason="Kandidat memiliki skor sinyal di atas ambang batas deteksi.",
        confidence=0.75,
        flags=[],
    )


async def evaluate_candidate_scout(
    cand: CandidateWindow,
    transcript: CandidateTranscript,
    meta: VideoMetadata,
    audio_feats: AudioFeatures,
    chat_feats: ChatFeatures,
    genre: str = "gaming",
) -> ScoutVerdict:
    """
    Evaluate candidate using LLM with structured evidence, or fallback to heuristic verifier.
    """
    # Fallback if LLM is not configured
    if not settings.llm_base_url and not settings.llm_api_key:
        logger.info(
            "llm_not_configured_using_heuristic_scout",
            candidate_id=cand.id,
        )
        return _build_heuristic_verdict(cand, transcript, audio_feats, chat_feats)

    system_prompt = (
        PROMPT_FILE.read_text(encoding="utf-8")
        if PROMPT_FILE.exists()
        else "Kamu adalah Short-Form Video Scout."
    )

    start_i = max(0, int(cand.start_s))
    end_i = min(len(audio_feats.speech_prob), int(np.ceil(cand.end_s)))
    max_surge = (
        float(np.max(audio_feats.loud_surge[start_i:end_i]))
        if len(audio_feats.loud_surge) > start_i
        else 0.0
    )
    mean_speech = (
        float(np.mean(audio_feats.speech_prob[start_i:end_i]))
        if len(audio_feats.speech_prob) > start_i
        else 0.0
    )

    evidence: dict[str, Any] = {
        "video_title": meta.title,
        "genre": genre,
        "candidate": {
            "id": cand.id,
            "start_s": cand.start_s,
            "end_s": cand.end_s,
            "duration_s": cand.duration_s,
            "fused_score": cand.final_score or cand.signal_score,
            "max_loud_surge": round(max_surge, 3),
            "mean_speech_prob": round(mean_speech, 3),
            "flags": cand.flags,
        },
        "transcript": transcript.text[:500] if transcript.text else "(Tidak ada transkrip)",
    }

    user_prompt = f"Analisis bukti berikut dan berikan penilaian JSON:\n{json.dumps(evidence, indent=2, ensure_ascii=False)}"

    try:
        client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "sk-dummy",
            timeout=30.0,
        )
        model_name = settings.llm_model or "gpt-4o-mini"
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return ScoutVerdict(**parsed)
    except Exception as exc:
        logger.warning(
            "llm_scout_failed_falling_back_to_heuristic",
            candidate_id=cand.id,
            error=str(exc),
        )
        return _build_heuristic_verdict(cand, transcript, audio_feats, chat_feats)
