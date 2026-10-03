"""Unit tests for chat signals extraction and lag compensation."""

import json
from pathlib import Path

from clipforge.signals.chat import extract_chat_features


def test_chat_unavailable(tmp_path: Path):
    non_existent = tmp_path / "chat.json"
    feats = extract_chat_features(non_existent, duration_s=60.0)
    assert not feats.available
    assert feats.total_messages == 0
    assert len(feats.chat_rate) == 60


def test_chat_extraction_and_lag_compensation(tmp_path: Path):
    chat_file = tmp_path / "chat.live_chat.json"

    # Suppose audience reacts at video second 16 (16000 ms) with "WKWK GILA ANJIR CLIP THIS"
    messages = [
        {
            "replayChatItemAction": {
                "videoOffsetTimeMsec": "16000",
                "actions": [
                    {
                        "addChatItemAction": {
                            "item": {
                                "liveChatTextMessageRenderer": {
                                    "message": {"runs": [{"text": "wkwk gila anjir gg"}]}
                                }
                            }
                        }
                    }
                ],
            }
        },
        {
            "replayChatItemAction": {
                "videoOffsetTimeMsec": "16500",
                "actions": [
                    {
                        "addChatItemAction": {
                            "item": {
                                "liveChatTextMessageRenderer": {
                                    "message": {"runs": [{"text": "clip this bang!"}]}
                                }
                            }
                        }
                    }
                ],
            }
        },
    ]

    with chat_file.open("w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m) + "\n")

    # With chat_lag_s = 6.0, an event reacting at second 16 should be shifted back to second 10!
    feats = extract_chat_features(chat_file, duration_s=30.0, chat_lag_s=6.0)

    assert feats.available
    assert feats.total_messages == 2
    assert len(feats.chat_rate) == 30

    # At shifted second 10:
    assert feats.chat_rate[10] >= 1.0
    assert feats.chat_hype[10] > 0.0
    assert feats.clip_intent[10] > 0.0
