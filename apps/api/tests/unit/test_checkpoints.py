from pathlib import Path

from clipforge.jobs.checkpoints import CheckpointManager, compute_hash


def test_compute_hash():
    h1 = compute_hash({"a": 1, "b": 2})
    h2 = compute_hash({"b": 2, "a": 1})
    assert h1 == h2
    assert len(h1) == 64


def test_checkpoint_lifecycle(tmp_path: Path):
    manager = CheckpointManager(job_id="test_job_1", data_dir=tmp_path)
    stage = "fetch_signals"
    input_hash = "abc12345"

    assert not manager.is_stage_completed(stage, input_hash)

    # Output file
    out_rel = "signals/test.npz"
    full_out = manager.job_dir / out_rel
    full_out.parent.mkdir(parents=True, exist_ok=True)
    full_out.write_bytes(b"dummy data")

    manager.save_checkpoint(stage, input_hash, outputs=[out_rel], metrics={"count": 10})

    assert manager.is_stage_completed(stage, input_hash)
    # Different input hash returns False
    assert not manager.is_stage_completed(stage, "different_hash")

    # Missing output file returns False
    full_out.unlink()
    assert not manager.is_stage_completed(stage, input_hash)
