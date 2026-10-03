"""
LLM service — wraps 9Router (OpenAI-compatible) for moment scouting.
"""
import json
import logging
from openai import AsyncOpenAI
from config import settings

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    base_url=settings.llm_api_base,
    api_key=settings.llm_api_key,
)

SCOUT_SYSTEM_PROMPT = """Kamu adalah video clip scout profesional. Analisis transkrip video berikut dan temukan momen terbaik untuk dijadikan short-form video vertikal (konten game, podcast, tutorial, atau umum).

Kriteria scoring (0–100):
- Hook strength (0–25): 5 detik pertama apakah langsung menarik / bikin penasaran?
- Content density (0–25): Padat tanpa filler / jeda panjang?
- Standalone value (0–25): Bisa dipahami tanpa konteks video penuh?
- Viral potential (0–25): Orang akan share / save / komentar?

Prioritas konten GAME:
- Momen reaksi keras (teriakan, tawa, shock)
- Clutch play / epic fail / plot twist
- Tutorial singkat yang self-contained
- Momen lucu / unexpected

Prioritas konten PODCAST / TALK:
- Pernyataan kontroversial atau mengejutkan
- Insight dense yang berdiri sendiri
- Momen emosional atau personal

Output WAJIB: JSON array saja, tanpa teks lain sebelum atau sesudah.
Setiap item:
{
  "start_time": <detik float, contoh: 842.5>,
  "end_time": <detik float>,
  "hook_title": "<judul hook ≤10 kata bahasa Indonesia>",
  "score": <integer 0-100>,
  "reason": "<1 kalimat kenapa momen ini bagus>",
  "caption": "<caption media sosial, ≤150 karakter>",
  "hashtags": ["#tag1", "#tag2", "#tag3"],
  "content_type": "<reaction|clutch|tutorial|funny|insight|emotional|controversy>"
}"""


async def scout_moments(
    transcript_text: str,
    audio_spikes: list[dict],
    duration_target: str,
    clip_count: int,
    video_duration: int,
) -> list[dict]:
    """Call LLM to find best moments in transcript."""

    # Build duration guidance
    dur_map = {
        "15-30": "15 hingga 30 detik",
        "30-60": "30 hingga 60 detik",
        "60-90": "60 hingga 90 detik",
    }
    dur_text = dur_map.get(duration_target, "30 hingga 60 detik")

    spike_text = ""
    if audio_spikes:
        spike_list = [f"  - {s['time']:.1f}s (energi {s['energy']:.1f}x baseline)" for s in audio_spikes[:20]]
        spike_text = "\n\nAUDIO ENERGY SPIKES (momen reaksi keras / hype):\n" + "\n".join(spike_list)

    user_content = f"""Video duration: {video_duration} detik
Jumlah klip yang dicari: {clip_count}
Durasi target tiap klip: {dur_text}
{spike_text}

TRANSKRIP (format: [detik_mulai] teks):
{transcript_text[:80000]}

Temukan tepat {clip_count} momen terbaik. Output JSON array saja."""

    logger.info("Calling LLM scout, transcript length: %d chars", len(transcript_text))

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SCOUT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=4096,
        )

        raw = (response.choices[0].message.content or "").strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        moments = json.loads(raw)
        if not isinstance(moments, list):
            raise ValueError("LLM returned non-list")

        # Validate and clamp timestamps
        valid = []
        for m in moments:
            start = float(m.get("start_time", 0))
            end = float(m.get("end_time", start + 30))
            # Clamp to video bounds
            start = max(0, min(start, video_duration - 5))
            end = max(start + 5, min(end, video_duration))
            # Enforce duration target
            target_max = int(duration_target.split("-")[1]) if "-" in duration_target else 60
            if end - start > target_max + 10:
                end = start + target_max
            m["start_time"] = round(start, 3)
            m["end_time"] = round(end, 3)
            m["score"] = max(0, min(100, int(m.get("score", 50))))
            valid.append(m)

        # Sort by score descending
        valid.sort(key=lambda x: x["score"], reverse=True)
        return valid[:clip_count]

    except json.JSONDecodeError as e:
        logger.error("LLM returned invalid JSON: %s | raw: %s", e, raw[:500] if 'raw' in dir() else "N/A")
        raise
    except Exception as e:
        logger.error("LLM scout error: %s", e)
        raise
