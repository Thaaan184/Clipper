"""Checkpoint management with atomic writes and input hashing."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clipforge.core.config import settings


def compute_hash(data: Any) -> str:
    """Compute deterministic SHA256 hex digest for structured data or bytes."""
    if isinstance(data, (bytes, bytearray)):
        return hashlib.sha256(data).hexdigest()
    serialized = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


class CheckpointManager:
    """Manages stage checkpoints for resumable pipeline execution."""

    def __init__(self, job_id: str, data_dir: Path | None = None):
        self.job_id = job_id
        base_dir = data_dir or settings.data_dir
        self.job_dir = (base_dir / "jobs" / job_id).resolve()
        self.checkpoint_dir = self.job_dir / ".checkpoint"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def get_checkpoint_path(self, stage: str) -> Path:
        return self.checkpoint_dir / f"{stage}.json"

    def is_stage_completed(self, stage: str, input_hash: str) -> bool:
        """Check if stage checkpoint exists, input_hash matches, and all recorded output files exist."""
        ckpt_path = self.get_checkpoint_path(stage)
        if not ckpt_path.exists():
            return False

        try:
            data = json.loads(ckpt_path.read_text(encoding="utf-8"))
            if data.get("input_hash") != input_hash:
                return False

            outputs = data.get("outputs", [])
            if stage == "render_clips" and not outputs:
                return False

            for rel_output in outputs:
                out_path = self.job_dir / rel_output
                if not out_path.exists():
                    return False

            return True
        except Exception:
            return False

    def save_checkpoint(
        self,
        stage: str,
        input_hash: str,
        outputs: list[str],
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Atomically persist a stage checkpoint using a temporary file and atomic rename."""
        ckpt_path = self.get_checkpoint_path(stage)
        tmp_path = ckpt_path.with_suffix(".tmp")

        payload = {
            "stage": stage,
            "input_hash": input_hash,
            "outputs": outputs,
            "metrics": metrics or {},
            "finished_at": datetime.now(UTC).isoformat(),
        }

        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, ckpt_path)
