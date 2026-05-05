"""Tests for CheckpointPass."""

from __future__ import annotations

from polisyos.scientist.governance.passes.checkpoint_pass import CheckpointPass


class TestCheckpointPass:
    def test_pass_id(self):
        assert CheckpointPass().pass_id == "checkpoint"

    def test_accepts_last_checkpoint_ref(self, pass_context_factory):
        ctx = pass_context_factory(state={"last_checkpoint_ref": "sha256:" + "a" * 64})
        issues = CheckpointPass().validate(ctx)
        blocker_or_warning = [i for i in issues if i.code == "CHECKPOINT_MISSING"]
        assert len(blocker_or_warning) == 0

    def test_missing_checkpoint_is_warning_when_not_required(self, pass_context_factory):
        ctx = pass_context_factory(state={"checkpoints": []})
        issues = CheckpointPass().validate(ctx)
        missing = next(i for i in issues if i.code == "CHECKPOINT_MISSING")
        assert missing.severity == "warning"

    def test_missing_checkpoint_is_blocker_when_required(self, pass_context_factory):
        ctx = pass_context_factory(state={"checkpoint_policy": "strict"})
        issues = CheckpointPass().validate(ctx)
        missing = next(i for i in issues if i.code == "CHECKPOINT_MISSING")
        assert missing.severity == "blocker"

    def test_accepts_explicit_calibration_checkpoint_payload(self, pass_context_factory):
        ctx = pass_context_factory(state={"calibration_checkpoint_payload": {"step": "holdout"}})
        issues = CheckpointPass().validate(ctx)
        assert not any(i.code == "CHECKPOINT_MISSING" for i in issues)

    def test_unordered_timestamps(self, pass_context_factory):
        ctx = pass_context_factory(
            state={
                "checkpoints": [
                    {"stage": "estimation_complete", "timestamp": "2026-01-02"},
                    {"stage": "data_loaded", "timestamp": "2026-01-01"},
                ],
            }
        )
        issues = CheckpointPass().validate(ctx)
        assert any(i.code == "CHECKPOINT_ORDER" for i in issues)
