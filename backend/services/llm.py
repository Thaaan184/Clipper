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

SCOUT_BASE_PROMPT = """Kamu adalah video clip scout profesional untuk short-form vertikal (TikTok, Reels, YouTube Shorts).
Analisis transkrip dan metadata audio berikut, lalu temukan momen-momen paling potensial untuk viral.

Kriteria penilaian (skor 0–100):
1. Hook Strength (0–25): Apakah 3–5 detik pertama langsung memancing rasa penasaran / atensi tinggi?
2. Content Density (0–25): Apakah padat dan bebas filler / jeda hampa?
3. Standalone Value (0–25): Apakah penonton langsung paham tanpa menonton video utuh?
4. Viral / Share Potential (0–25): Apakah memicu dorongan komentar, share ke teman, atau save?

Output WAJIB berupa JSON array saja (tanpa markdown wrap atau teks pendahuluan):
[
  {
    "start_time": <detik float, contoh: 120.5>,
    "end_time": <detik float>,
    "hook_title": "<judul hook ≤10 kata bahasa Indonesia>",
    "score": <integer 0-100>,
    "reason": "<1 kalimat alasan momen ini viral>",
    "caption": "<caption media sosial catchy, ≤150 karakter>",
    "hashtags": ["#tag1", "#tag2", "#tag3"],
    "content_type": "<gaming|reaction|clutch|podcast|tutorial|comedy|motivation>"
  }
]"""

CONTENT_TYPE_GUIDES = {
    "gaming": """TIPE FOKUS: GAMING & STREAMING
- Prioritas Utama: Reaksi vokal keras (teriakan kaget, tawa ngakak, rage quit, selebrasi kemenangan) dan aksi clutch/blunder.
- Manfaatkan data AUDIO ENERGY SPIKES di bawah untuk menandai detik-detik teriakan/hype streamer!
- Timing klip: Mulai 3–5 detik sebelum aksi/kill/blunder agar ada build-up tensi, tahan sampai reaksi streamer reda.
- Hook Title: Format khas gaming TikTok/Reels (misal: "Duelist Beban", "Detik-detik Kena Jumpscare", "1 HP Clutch Mustahil", "Rage Quit Terkonyol").""",

    "podcast": """TIPE FOKUS: PODCAST & TALKSHOW
- Prioritas Utama: Contrarian statement / hot take yang menantang opini umum di 3 detik pertama.
- Insight atau rahasia yang aplikatif dan berdiri sendiri (self-contained).
- Cerita personal atau debat tajam yang memancing emosi dan diskusi di kolom komentar.
- Timing klip: Selesaikan satu ide atau premis argumen secara tuntas tanpa terpotong di tengah nafas.""",

    "education": """TIPE FOKUS: EDUKASI, TUTORIAL & TECH
- Prioritas Utama: Hook berbasis masalah ("Capek ngerjain X manual?", "Trik rahasia yang jarang orang tahu...").
- Langkah konkret atau tool rekomendasi yang langsung bisa ditiru.
- Hilangkan intro basa-basi, langsung ke poin solusi.""",

    "comedy": """TIPE FOKUS: KOMEDI & HIBURAN
- Prioritas Utama: Punchline timing, celetukan spontan, roasting, reaksi absurd atau awkward.
- Setup singkat yang langsung disambar punchline tak terduga.""",

    "motivation": """TIPE FOKUS: MOTIVASI & CERITA INSPIRATIF
- Prioritas Utama: Pembuka emosional yang menyentuh ("Waktu gue di titik terendah...", "Jangan pernah menyerah kalau...").
- Momen titik balik perjuangan dan kalimat pamungkas yang layak di-save penonton.""",

    "auto": """TIPE FOKUS: DETEKSI OTOMATIS
- Analisis transkrip dan audio spike untuk mengenali jenis konten (Gaming, Podcast, Edukasi, dsb.) secara dinamis.
- Sesuaikan standar klip terbaik sesuai genre yang paling dominan."""
}


async def scout_moments(
    transcript_text: str,
    audio_spikes: list[dict],
    duration_target: str,
    clip_count: int,
    video_duration: int,
    content_type: str = "auto",
) -> list[dict]:
    """Call LLM to find best moments in transcript based on content type."""

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

    guide = CONTENT_TYPE_GUIDES.get(content_type, CONTENT_TYPE_GUIDES["auto"])
    system_prompt = f"{SCOUT_BASE_PROMPT}\n\n{guide}"

    logger.info("Calling LLM scout [type: %s], transcript length: %d chars", content_type, len(transcript_text))

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=4096,
        )

        raw = (response.choices[0].message.content or "").strip()

        # Extract JSON array robustly
        import re
        match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", raw)
        if match:
            moments = json.loads(match.group(0))
        else:
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            moments = json.loads(raw.strip())
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
