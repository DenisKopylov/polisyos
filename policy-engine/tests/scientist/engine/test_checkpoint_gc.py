"""Tests for checkpoint GC, schema validation, lock retry, and CheckpointStore."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from polisyos.scientist.engine.checkpoint import (
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointGCPolicy,
    CheckpointHead,
    CheckpointSchemaError,
    FileSystemCheckpointStore,
    RunLockError,
    _validate_checkpoint_schema,
    acquire_run_lock,
    gc_checkpoints,
    load_checkpoint_head,
    update_checkpoint_head,
)
from polisyos.core.artifacts.manifest import ArtifactRef


def _make_ref(aid: str | None = None) -> ArtifactRef:
    if aid is None:
        aid = "sha256:" + "a" * 64
    return ArtifactRef(artifact_id=aid, kind="scientist.checkpoint", media_type="application/json")


# ── CheckpointGCPolicy ───────────────────────────────────────────────

class TestCheckpointGCPolicy:
    def test_defaults(self) -> None:
        p = CheckpointGCPolicy()
        assert p.max_checkpoints == 10
        assert p.max_age_hours == 72.0

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            CheckpointGCPolicy(unknown=True)  # type: ignore[call-arg]

    def test_bounds(self) -> None:
        with pytest.raises(ValidationError):
            CheckpointGCPolicy(max_checkpoints=0)
        with pytest.raises(ValidationError):
            CheckpointGCPolicy(max_age_hours=0.5)


class TestGCCheckpoints:
    def test_empty_dir_noop(self, tmp_path: Path) -> None:
        policy = CheckpointGCPolicy()
        deleted = gc_checkpoints(tmp_path, policy=policy)
        assert deleted == 0

    def test_with_head_returns_zero(self, tmp_path: Path) -> None:
        # Write a head file
        ref = _make_ref()
        update_checkpoint_head(
            tmp_path, run_id="r1", checkpoint_ref=ref,
            sequence_number=0, node_alias="a",
            writer_pid=os.getpid(), writer_hostname="test",
        )
        policy = CheckpointGCPolicy(max_checkpoints=1)
        deleted = gc_checkpoints(tmp_path, policy=policy, current_head_ref=ref)
        assert deleted == 0


# ── Schema validation ────────────────────────────────────────────────

class TestCheckpointSchemaValidation:
    def test_same_version_passes(self) -> None:
        _validate_checkpoint_schema("1.0", "1.0")

    def test_minor_upgrade_passes(self) -> None:
        _validate_checkpoint_schema("1.0", "1.1")

    def test_minor_newer_warns(self) -> None:
        with patch("polisyos.scientist.engine.checkpoint.logger") as mock_log:
            _validate_checkpoint_schema("1.2", "1.0")
            mock_log.warning.assert_called_once()

    def test_major_mismatch_raises(self) -> None:
        with pytest.raises(CheckpointSchemaError, match="major version mismatch"):
            _validate_checkpoint_schema("2.0", "1.0")

    def test_major_mismatch_reverse(self) -> None:
        with pytest.raises(CheckpointSchemaError, match="major version mismatch"):
            _validate_checkpoint_schema("1.0", "2.0")

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(CheckpointSchemaError, match="Invalid schema version"):
            _validate_checkpoint_schema("abc", "1.0")


# ── Lock retry ────────────────────────────────────────────────────────

class TestLockRetry:
    def test_single_attempt_default(self, tmp_path: Path) -> None:
        handle = acquire_run_lock(tmp_path, run_id="r1", mode="test")
        handle.release()

    def test_retry_succeeds_second_attempt(self, tmp_path: Path) -> None:
        import fcntl
        import threading

        lock_path = tmp_path / "run.lock"
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        def release_soon():
            time.sleep(0.05)
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

        t = threading.Thread(target=release_soon)
        t.start()

        # Use real sleep so the lock has time to be released
        handle = acquire_run_lock(
            tmp_path, run_id="r1", mode="test",
            max_attempts=5, retry_delay_s=0.05,
        )
        handle.release()
        t.join()

    def test_all_attempts_exhausted(self, tmp_path: Path) -> None:
        import fcntl

        lock_path = tmp_path / "run.lock"
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        try:
            with patch("polisyos.scientist.engine.checkpoint.time.sleep"):
                with pytest.raises(RunLockError, match="already active"):
                    acquire_run_lock(
                        tmp_path, run_id="r1", mode="test",
                        max_attempts=2, retry_delay_s=0.01,
                    )
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


# ── FileSystemCheckpointStore ─────────────────────────────────────────

class TestFileSystemCheckpointStore:
    def test_roundtrip(self, tmp_path: Path) -> None:
        store = FileSystemCheckpointStore(tmp_path)
        ref = _make_ref()
        head = CheckpointHead(
            run_id="r1", checkpoint_ref=ref, sequence_number=0,
            node_alias="step_a", writer_pid=os.getpid(),
            writer_hostname="test",
            updated_at="2026-01-01T00:00:00Z",
        )
        store.write_head("r1", head)
        loaded = store.read_head("r1")
        assert loaded is not None
        assert loaded.run_id == "r1"
        assert loaded.sequence_number == 0
        assert loaded.checkpoint_ref.artifact_id == ref.artifact_id

    def test_read_missing_returns_none(self, tmp_path: Path) -> None:
        store = FileSystemCheckpointStore(tmp_path)
        assert store.read_head("nonexistent") is None

    def test_protocol_compliance(self) -> None:
        """FileSystemCheckpointStore satisfies CheckpointStore structurally."""
        store = FileSystemCheckpointStore(Path("."))
        assert hasattr(store, "write_head")
        assert hasattr(store, "read_head")
        assert callable(store.write_head)
        assert callable(store.read_head)
