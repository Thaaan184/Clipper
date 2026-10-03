"""Extract chat features from YouTube live chat replay with lag compensation."""

import json
import math
import re
from pathlib import Path

import numpy as np
import structlog

from clipforge.signals.models import ChatFeatures

logger = structlog.get_logger(__name__)

LEXICON_DIR = Path(__file__).parent / "lexicon"


def load_lexicon(filename: str) -> set[str]:
    path = LEXICON_DIR / filename
    if not path.exists():
        return set()
    words = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            words.add(line)
    return words


def _extract_chat_items_from_file(chat_path: Path) -> list[tuple[float, str]]:
    """
    Parse live chat JSON or JSONL file into list of (offset_s, text).
    """
    items: list[tuple[float, str]] = []
    if not chat_path.exists():
        return items

    with chat_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue

            # Check replayChatItemAction structure
            action = data.get("replayChatItemAction") or data
            actions = action.get("actions", [])
            offset_ms_raw = action.get("videoOffsetTimeMsec")

            if offset_ms_raw is None:
                continue

            try:
                offset_s = float(offset_ms_raw) / 1000.0
            except (ValueError, TypeError):
                continue

            for sub_act in actions:
                item_container = sub_act.get("addChatItemAction", {}).get(
                    "item", {}
                ) or sub_act.get("item", {})
                renderer = item_container.get("liveChatTextMessageRenderer") or item_container.get(
                    "liveChatPaidMessageRenderer"
                )
                if not renderer:
                    continue

                message_obj = renderer.get("message", {})
                runs = message_obj.get("runs", [])
                text_parts = [r.get("text", "") for r in runs if "text" in r]
                full_text = " ".join(text_parts).strip().lower()

                if full_text:
                    items.append((offset_s, full_text))

    return items


def extract_chat_features(
    chat_path: Path | None,
    duration_s: float,
    chat_lag_s: float = 6.0,
) -> ChatFeatures:
    """
    Process chat events into 1-second time series with chat lag compensation.
    """
    num_secs = max(1, int(math.ceil(duration_s)))

    if not chat_path or not chat_path.exists():
        return ChatFeatures(
            available=False,
            duration_s=duration_s,
            chat_rate=list(np.zeros(num_secs, dtype=float)),
            chat_hype=list(np.zeros(num_secs, dtype=float)),
            clip_intent=list(np.zeros(num_secs, dtype=float)),
            total_messages=0,
        )

    items = _extract_chat_items_from_file(chat_path)
    if not items:
        return ChatFeatures(
            available=False,
            duration_s=duration_s,
            chat_rate=list(np.zeros(num_secs, dtype=float)),
            chat_hype=list(np.zeros(num_secs, dtype=float)),
            clip_intent=list(np.zeros(num_secs, dtype=float)),
            total_messages=0,
        )

    hype_lexicon = load_lexicon("hype.txt") | load_lexicon("laughter.txt")
    clip_lexicon = load_lexicon("clip_intent.txt")

    # Word boundary regex for matching words
    def matches_lexicon(text: str, lexicon: set[str]) -> bool:
        tokens = set(re.findall(r"\b\w+\b", text))
        if tokens & lexicon:
            return True
        for phrase in lexicon:
            if " " in phrase and phrase in text:
                return True
        return False

    raw_rate = np.zeros(num_secs + int(chat_lag_s) + 60, dtype=np.float32)
    raw_hype_count = np.zeros_like(raw_rate)
    raw_clip_count = np.zeros_like(raw_rate)

    for offset_s, text in items:
        sec = int(offset_s)
        if 0 <= sec < len(raw_rate):
            raw_rate[sec] += 1.0
            if matches_lexicon(text, hype_lexicon):
                raw_hype_count[sec] += 1.0
            if matches_lexicon(text, clip_lexicon):
                raw_clip_count[sec] += 1.0

    # Lag compensation: shift backward by chat_lag_s
    lag_bins = int(round(chat_lag_s))
    rate_shifted = np.zeros(num_secs, dtype=np.float32)
    hype_shifted = np.zeros(num_secs, dtype=np.float32)
    clip_shifted = np.zeros(num_secs, dtype=np.float32)

    for t in range(num_secs):
        source_idx = t + lag_bins
        if source_idx < len(raw_rate):
            rate_val = raw_rate[source_idx]
            rate_shifted[t] = rate_val
            if rate_val > 0:
                hype_shifted[t] = raw_hype_count[source_idx] / rate_val
                clip_shifted[t] = raw_clip_count[source_idx] / rate_val

    return ChatFeatures(
        available=True,
        duration_s=duration_s,
        chat_rate=[float(x) for x in rate_shifted],
        chat_hype=[float(x) for x in hype_shifted],
        clip_intent=[float(x) for x in clip_shifted],
        total_messages=len(items),
    )
