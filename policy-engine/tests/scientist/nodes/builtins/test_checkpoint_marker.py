"""Tests for checkpoint markers."""

from __future__ import annotations

from polisyos.scientist.nodes.builtins.checkpoint_marker import (
    CHECKPOINT_CODE,
    emit_checkpoint,
)


class TestEmitCheckpoint:
    def test_basic_emission(self):
        event = emit_checkpoint("node_1", 0.5, "halfway")
        assert event.code == CHECKPOINT_CODE
        assert event.attrs["node_id"] == "node_1"
        assert event.attrs["progress"] == 50
        assert event.attrs["label"] == "halfway"

    def test_progress_clamping(self):
        event = emit_checkpoint("n", 1.5)
        assert event.attrs["progress"] == 100

        event = emit_checkpoint("n", -0.1)
        assert event.attrs["progress"] == 0

    def test_engine_intercept_code(self):
        event = emit_checkpoint("n", 0.75, "phase_3")
        assert event.code == "node.checkpoint"
        assert "75%" in event.message
