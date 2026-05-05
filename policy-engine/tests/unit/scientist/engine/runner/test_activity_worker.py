"""Tests for remote worker context reconstruction."""

from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING

import pytest
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.engine.checkpoint import CASCheckpointHook, resolve_latest_checkpoint
from polisyos.scientist.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.engine.runner import _activity_worker as activity_worker_module
from polisyos.scientist.engine.runner._activity_worker import (
    _build_worker_context,
    _restore_parent_trace_context,
    run_merge_checkpoint_tier_in_worker,
)
from polisyos.scientist.engine.runner.serialization import deserialize_state, serialize_state
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

if TYPE_CHECKING:
    from pathlib import Path


def test_build_worker_context_reconstructs_run_and_registry_bundle() -> None:
    ctx = _build_worker_context(
        {
            "run_id": "worker-run-1",
            "tenant_id": "tenant-1",
            "cell_id": "cell-1",
            "depth": 3,
            "workflow_id": "scientist_default",
            "runner_backend": "ray",
            "trace_id": "0" * 32,
            "span_id": "1" * 16,
            "registry_bundle_ref": {
                "artifact_id": "sha256:" + "c" * 64,
                "kind": "core.registry_bundle",
                "media_type": "application/json",
            },
        }
    )

    assert ctx.depth == 3
    assert ctx.run.run_manifest.run_id == "worker-run-1"
    assert ctx.run.tenant_id == "tenant-1"
    assert ctx.run.cell_id == "cell-1"
    assert str(ctx.run.run_manifest.registry_bundle.artifact_id) == "sha256:" + "c" * 64


def test_build_worker_context_bootstraps_registry_bundle_when_missing() -> None:
    ctx = _build_worker_context({"run_id": "worker-run-2"})

    assert ctx.run.run_manifest.run_id == "worker-run-2"
    assert ctx.run.run_manifest.registry_bundle.kind == "core.registry_bundle"
    assert ctx.metrics is None or len(ctx.metrics.recent_trace_correlations()) == 1


def test_build_worker_context_records_degraded_path_for_invalid_registry_bundle(
    monkeypatch,
) -> None:
    degraded: list[dict[str, object]] = []

    monkeypatch.setattr(
        activity_worker_module,
        "emit_degraded_path",
        lambda **kwargs: degraded.append(kwargs) or {"reason": kwargs["reason"]},
    )

    ctx = _build_worker_context(
        {
            "run_id": "worker-run-invalid-registry",
            "registry_bundle_ref": {"artifact_id": "not-a-valid-artifact-ref"},
        }
    )

    assert ctx.run.run_manifest.run_id == "worker-run-invalid-registry"
    assert ctx.run.run_manifest.registry_bundle.kind == "core.registry_bundle"
    assert any(item["reason"] == "registry_bundle_ref_invalid" for item in degraded)


def test_build_worker_context_reuses_shared_filesystem_store(tmp_path: Path) -> None:
    ctx = _build_worker_context(
        {
            "run_id": "worker-run-3",
            "store_backend": "filesystem",
            "store_root": str(tmp_path),
        }
    )

    assert getattr(ctx.store, "root", None) == tmp_path


def test_build_worker_context_prefers_store_config(tmp_path: Path) -> None:
    ctx = _build_worker_context(
        {
            "run_id": "worker-run-store-config",
            "store_config": ArtifactStoreConfig(
                backend="filesystem",
                root=str(tmp_path),
            ).model_dump(mode="json"),
        }
    )

    assert getattr(ctx.store, "root", None) == tmp_path


def test_restore_parent_trace_context_records_degraded_path_on_runtime_error(
    monkeypatch,
) -> None:
    pytest.importorskip("opentelemetry.context")
    from polisyos.core.observability import propagation

    degraded: list[dict[str, object]] = []

    monkeypatch.setattr(
        activity_worker_module,
        "emit_degraded_path",
        lambda **kwargs: degraded.append(kwargs) or {"reason": kwargs["reason"]},
    )

    def _boom(_carrier: dict[str, str]) -> object:
        raise RuntimeError("broken trace context")

    monkeypatch.setattr(propagation, "extract_headers", _boom)

    token = _restore_parent_trace_context(
        {"traceparent": "00-" + "0" * 32 + "-" + "1" * 16 + "-01"},
        context_meta={"run_id": "worker-trace-restore"},
        operation="restore_trace_context",
    )

    assert token is None
    assert any(item["reason"] == "trace_context_restore_failed" for item in degraded)


def _meta(raw: str, name: str) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse(raw),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name=name,
        description=f"{name} test node",
        tags=["test"],
        capabilities=Capability.SCIENTIST_NODE,
    )


def _artifact_ref(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + hashlib.sha256(name.encode()).hexdigest(),
        kind="test",
        media_type="application/json",
    )


class PolicyOutputNode:
    _spec = NodeSpec(
        metadata=_meta("scientist.node_policy_output@1.0.0", "PolicyOutput"),
        state_reads=[],
        state_writes=["policy_output_bundle_ref"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx, state) -> NodeOutcome:
        return NodeOutcome(status="ok", state=state)


def test_run_merge_checkpoint_tier_in_worker_restores_checkpoint_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / "R_worker_merge",
        checkpoint_policy="strict",
    )
    checkpoint_meta = hook.export_runtime_metadata()
    assert checkpoint_meta is not None

    workflow = WorkflowSpec(
        workflow_id="wf_worker_merge",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias="policy",
                node_id=ComponentId.parse("scientist.node_policy_output@1.0.0"),
            )
        ],
    )
    base_state = ExperimentState(run_id="R_worker_merge")
    result_state = base_state.model_copy(deep=True)
    result_state.policy_output_bundle_ref = _artifact_ref("policy-output")

    def _discover_nodes(registry) -> None:
        registry.register(PolicyOutputNode())

    monkeypatch.setattr(
        "polisyos.scientist.engine.registry.discover_nodes",
        _discover_nodes,
    )

    result = asyncio.run(
        run_merge_checkpoint_tier_in_worker(
            {
                "workflow_spec_json": workflow.model_dump(mode="json"),
                "tier_aliases": ["policy"],
                "result_bytes_by_alias": {"policy": serialize_state(result_state)},
                "base_state_bytes": serialize_state(base_state),
                "context_meta": {
                    "run_id": "R_worker_merge",
                    "workflow_id": workflow.workflow_id,
                    "runner_backend": "temporal",
                    "store_config": {"backend": "filesystem", "root": str(tmp_path)},
                    "store_backend": "filesystem",
                    "store_root": str(tmp_path),
                },
                "workflow_fingerprint": "a" * 64,
                "completed_nodes": [],
                "merge_conflict_policy": "error",
                "checkpoint_hook_meta": checkpoint_meta,
            }
        )
    )

    merged_state = deserialize_state(result["state_bytes"])
    assert merged_state.policy_output_bundle_ref == result_state.policy_output_bundle_ref
    assert result["completed_nodes"] == ["policy"]
    assert result["checkpoint_hook_meta"]["sequence_start"] == 1
    resolved = resolve_latest_checkpoint(store, "R_worker_merge")
    assert resolved is not None
