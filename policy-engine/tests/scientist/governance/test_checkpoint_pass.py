"""Tests for CheckpointPass."""

from __future__ import annotations

import pytest

from polisyos.scientist.governance.passes.checkpoint_pass import CheckpointPass


class TestCheckpointPass:
    def test_pass_id(self):
        assert CheckpointPass().pass_id == "checkpoint_integrity"

    def test_all_checkpoints_present(self, pass_context_factory):
        ctx = pass_context_factory(state={
            "checkpoints": [
                {"stage": "data_loaded", "timestamp": "2026-01-01T00:00:00Z"},
                {"stage": "estimation_complete", "timestamp": "2026-01-01T01:00:00Z"},
            ],
        })
        issues = CheckpointPass().validate(ctx)
        blocker_or_warning = [i for i in issues if i.code == "CHECKPOINT_MISSING"]
        assert len(blocker_or_warning) == 0

    def test_missing_checkpoints(self, pass_context_factory):
        ctx = pass_context_factory(state={"checkpoints": []})
        issues = CheckpointPass().validate(ctx)
        assert any(i.code == "CHECKPOINT_MISSING" for i in issues)

    def test_no_checkpoints_key(self, pass_context_factory):
        ctx = pass_context_factory(state={})
        issues = CheckpointPass().validate(ctx)
        assert any(i.code == "CHECKPOINT_MISSING" for i in issues)

    def test_unordered_timestamps(self, pass_context_factory):
        ctx = pass_context_factory(state={
            "checkpoints": [
                {"stage": "estimation_complete", "timestamp": "2026-01-02"},
                {"stage": "data_loaded", "timestamp": "2026-01-01"},
            ],
        })
        issues = CheckpointPass().validate(ctx)
        assert any(i.code == "CHECKPOINT_ORDER" for i in issues)
