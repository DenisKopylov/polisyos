"""Tests for runner serialization round-trips."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.protocol import NodeOutcome
from polisyos.scientist.engine.runner import serialization as serialization_module
from polisyos.scientist.engine.runner.serialization import (
    DeserializationError,
    deserialize_outcome,
    deserialize_state,
    deserialize_state_safe,
    serialize_context_meta,
    serialize_outcome,
    serialize_state,
    serialize_state_safe,
)
from polisyos.scientist.engine.state import ExperimentState

# ---------------------------------------------------------------------------
# State round-trip
# ---------------------------------------------------------------------------


class TestSerializeState:
    def test_round_trip_preserves_run_id(self) -> None:
        state = ExperimentState(run_id="test-run")
        blob = serialize_state(state)
        assert isinstance(blob, bytes)
        restored = deserialize_state(blob)
        assert isinstance(restored, ExperimentState)
        assert restored.run_id == "test-run"

    def test_round_trip_preserves_all_defaults(self) -> None:
        state = ExperimentState(run_id="rt-defaults")
        restored = deserialize_state(serialize_state(state))
        assert restored.schema_version == state.schema_version
        assert restored.inputs == {}
        assert restored.artifacts_index == {}
        assert restored.reports_index == {}
        assert restored.params == {}
        assert restored.budgets == {}
        assert restored.last_checkpoint_ref is None

    def test_round_trip_with_params(self) -> None:
        state = ExperimentState(run_id="rt-params", params={"method": "ols", "n": 1000})
        restored = deserialize_state(serialize_state(state))
        assert restored.params["method"] == "ols"
        assert restored.params["n"] == 1000

    def test_deserialize_state_accepts_list_encoded_wire_payload(self) -> None:
        state = ExperimentState(run_id="rt-wire-list")
        restored = deserialize_state(list(serialize_state(state)))
        assert restored.run_id == "rt-wire-list"


# ---------------------------------------------------------------------------
# Outcome round-trip
# ---------------------------------------------------------------------------


class TestSerializeOutcome:
    def test_round_trip_preserves_status_and_state(self) -> None:
        state = ExperimentState(run_id="outcome-run")
        outcome = NodeOutcome(status="ok", state=state)
        blob = serialize_outcome(outcome)
        assert isinstance(blob, bytes)
        restored = deserialize_outcome(blob)
        assert isinstance(restored, NodeOutcome)
        assert restored.status == "ok"
        assert restored.state.run_id == "outcome-run"

    def test_round_trip_preserves_empty_collections(self) -> None:
        state = ExperimentState(run_id="empty-cols")
        outcome = NodeOutcome(status="ok", state=state)
        restored = deserialize_outcome(serialize_outcome(outcome))
        assert restored.artifacts == []
        assert restored.events == []
        assert restored.error is None

    def test_round_trip_skip_status(self) -> None:
        state = ExperimentState(run_id="skip-run")
        outcome = NodeOutcome(status="skip", state=state)
        restored = deserialize_outcome(serialize_outcome(outcome))
        assert restored.status == "skip"

    def test_deserialize_outcome_accepts_list_encoded_wire_payload(self) -> None:
        outcome = NodeOutcome(status="ok", state=ExperimentState(run_id="out-wire-list"))
        restored = deserialize_outcome(list(serialize_outcome(outcome)))
        assert restored.state.run_id == "out-wire-list"


# ---------------------------------------------------------------------------
# Context meta extraction
# ---------------------------------------------------------------------------


@dataclass
class _FakeRun:
    """Minimal stand-in for RunContext with the attributes serialize_context_meta reads."""

    run_id: str = "ctx-run-123"
    tenant_id: str | None = "t-1"
    cell_id: str | None = "c-1"
    run_manifest: Any = None


@dataclass
class _FakeCtx:
    """Minimal stand-in for ExecutionContext."""

    depth: int = 2
    run: Any = None


class TestSerializeContextMeta:
    def test_extracts_depth(self) -> None:
        ctx = _FakeCtx(depth=3, run=None)
        meta = serialize_context_meta(ctx)
        assert meta["depth"] == 3
        # No run → no run_id key
        assert "run_id" not in meta

    def test_extracts_run_metadata(self) -> None:
        ctx = _FakeCtx(depth=1, run=_FakeRun())
        meta = serialize_context_meta(ctx)
        assert meta["depth"] == 1
        assert meta["run_id"] == "ctx-run-123"
        assert meta["tenant_id"] == "t-1"
        assert meta["cell_id"] == "c-1"

    def test_run_without_tenant_and_cell(self) -> None:
        ctx = _FakeCtx(depth=0, run=_FakeRun(run_id="r-2", tenant_id=None, cell_id=None))
        meta = serialize_context_meta(ctx)
        assert meta["run_id"] == "r-2"
        assert meta["tenant_id"] is None
        assert meta["cell_id"] is None

    def test_extracts_registry_bundle_workflow_and_runner(self) -> None:
        registry_bundle = ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="core.registry_bundle",
            media_type="application/json",
        )
        run = _FakeRun(
            run_manifest=type(
                "Manifest",
                (),
                {
                    "registry_bundle": registry_bundle,
                    "run_id": "ctx-run-123",
                },
            )()
        )
        ctx = _FakeCtx(depth=1, run=run)
        meta = serialize_context_meta(
            ctx,
            workflow_id="scientist_default",
            runner_backend="ray",
        )
        assert meta["workflow_id"] == "scientist_default"
        assert meta["runner_backend"] == "ray"
        assert meta["registry_bundle_ref"]["artifact_id"] == "sha256:" + "a" * 64

    def test_uses_run_manifest_for_real_run_context(self, tmp_path: Path) -> None:
        store = FileSystemCAS(tmp_path)
        registry_bundle = ArtifactRef(
            artifact_id="sha256:" + "b" * 64,
            kind="core.registry_bundle",
            media_type="application/json",
        )
        run = RunContext.start(
            store=store,
            registry_bundle=registry_bundle,
            run_id="real-run",
            tenant_id="tenant-a",
            cell_id="cell-a",
        )
        ctx = _FakeCtx(depth=2, run=run)
        meta = serialize_context_meta(ctx)
        assert meta["run_id"] == "real-run"
        assert meta["tenant_id"] == "tenant-a"
        assert meta["cell_id"] == "cell-a"
        assert meta["registry_bundle_ref"]["artifact_id"] == "sha256:" + "b" * 64

    def test_extracts_trace_ids_when_present(self, monkeypatch) -> None:
        ctx = _FakeCtx(depth=1, run=_FakeRun())
        monkeypatch.setattr(
            "polisyos.scientist.engine.runner.serialization._current_trace_ids",
            lambda: ("0" * 32, "1" * 16),
        )
        meta = serialize_context_meta(ctx)
        assert meta["trace_id"] == "0" * 32
        assert meta["span_id"] == "1" * 16

    def test_current_trace_ids_records_degraded_path_on_runtime_error(self, monkeypatch) -> None:
        pytest.importorskip("opentelemetry.trace")
        import opentelemetry.trace as otel_trace

        degraded: list[dict[str, object]] = []

        monkeypatch.setattr(
            serialization_module,
            "emit_degraded_path",
            lambda **kwargs: degraded.append(kwargs) or {"reason": kwargs["reason"]},
        )

        def _boom() -> object:
            raise RuntimeError("trace backend unavailable")

        monkeypatch.setattr(otel_trace, "get_current_span", _boom)

        trace_id, span_id = serialization_module._current_trace_ids()

        assert trace_id is None
        assert span_id is None
        assert any(item["reason"] == "trace_context_read_failed" for item in degraded)


# ---------------------------------------------------------------------------
# Safe serialization (version 1 — header + integrity hash)
# ---------------------------------------------------------------------------


class TestSafeSerialisation:
    def test_round_trip_safe(self) -> None:
        state = ExperimentState(run_id="safe-run")
        payload, hex_digest = serialize_state_safe(state)
        assert isinstance(payload, bytes)
        assert len(hex_digest) == 64
        restored = deserialize_state_safe(payload)
        assert restored.run_id == "safe-run"

    def test_version_mismatch_raises(self) -> None:
        bad = b"\x99" + b"some json" + b"\x00" * 32
        with pytest.raises(DeserializationError, match="Unsupported serialization version"):
            deserialize_state_safe(bad)

    def test_integrity_failure_raises(self) -> None:
        state = ExperimentState(run_id="tamper")
        payload, _ = serialize_state_safe(state)
        # Flip a byte in the JSON body
        corrupted = payload[:5] + bytes([payload[5] ^ 0xFF]) + payload[6:]
        with pytest.raises(DeserializationError, match="Integrity check failed"):
            deserialize_state_safe(corrupted)

    def test_truncated_payload_raises(self) -> None:
        with pytest.raises(DeserializationError, match="too short"):
            deserialize_state_safe(b"\x01abc")

    def test_deserialize_state_auto_detects_v1(self) -> None:
        """Plain deserialize_state transparently handles version-1 payloads."""
        state = ExperimentState(run_id="auto-v1")
        payload, _ = serialize_state_safe(state)
        restored = deserialize_state(payload)
        assert restored.run_id == "auto-v1"

    def test_deserialize_state_handles_legacy_v0(self) -> None:
        """Plain JSON (version 0) still works with deserialize_state."""
        state = ExperimentState(run_id="legacy-v0")
        raw_json = serialize_state(state)
        restored = deserialize_state(raw_json)
        assert restored.run_id == "legacy-v0"
