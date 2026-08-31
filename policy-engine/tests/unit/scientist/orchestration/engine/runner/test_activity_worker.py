"""Tests for remote worker context reconstruction."""

from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING

import numpy as np
import pytest

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.methods.causal import PanelObservationalData
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
    RunCausalEvaluationNode,
)
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointScopeMismatchError,
    resolve_latest_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ClaimCapableExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.runner import (
    _activity_worker as activity_worker_module,
)
from polisyos.scientist.orchestration.engine.runner._activity_worker import (
    _build_worker_context,
    _restore_parent_trace_context,
    run_merge_checkpoint_tier_in_worker,
    run_node_in_worker,
)
from polisyos.scientist.orchestration.engine.runner.serialization import (
    deserialize_state,
    serialize_state,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

if TYPE_CHECKING:
    from pathlib import Path


def test_build_worker_context_reconstructs_run_and_registry_bundle() -> None:
    with tenant_scope(None, tenant_id="tenant-1", cell_id="cell-1"):
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
    assert isinstance(ctx, ClaimCapableExecutionContext)
    assert ctx.claim_ledger_owner is not None


def test_build_worker_context_bootstraps_registry_bundle_when_missing() -> None:
    ctx = _build_worker_context({"run_id": "worker-run-2"})

    assert ctx.run.run_manifest.run_id == "worker-run-2"
    assert ctx.run.run_manifest.registry_bundle.kind == "core.registry_bundle"
    assert ctx.metrics is None or len(ctx.metrics.recent_trace_correlations()) == 1
    assert isinstance(ctx, ClaimCapableExecutionContext)
    assert ctx.claim_ledger_owner is not None


def test_non_simulation_worker_without_eval_safety_port_fails_closed(
    monkeypatch,
) -> None:
    """Real worker reconstruction cannot fall back to a local positive verifier."""
    ctx = _build_worker_context({"run_id": "worker-run-eval-safety-omission"})
    data = PanelObservationalData(
        outcome=np.array([[1.0, 2.0], [1.5, 2.5]]),
        treatment=np.array([1, 0]),
        time_treatment=1,
    )
    data_ref = ctx.store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    state = ExperimentState(
        run_id="worker-run-eval-safety-omission",
        observational_data_ref=data_ref,
        causal_method_fqn="causal.inference.synthetic_control@1.0.0",
        params={"random_seed": 42},
    )
    register_calls = 0
    load_calls = 0
    job_calls = 0

    def _register() -> None:
        nonlocal register_calls
        register_calls += 1

    def _load(*args, **kwargs):
        del args, kwargs
        nonlocal load_calls
        load_calls += 1
        return data

    def _run_job(*args, **kwargs):
        del args, kwargs
        nonlocal job_calls
        job_calls += 1
        raise AssertionError("causal job reached")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation."
        "ensure_causal_methods_registered",
        _register,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation._load_observational_data",
        _load,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
        _run_job,
    )

    outcome = RunCausalEvaluationNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.details["blocker_codes"] == [
        "polisyos.eval_safety.execution_context_missing@1.0.0"
    ]
    assert register_calls == 0
    assert load_calls == 0
    assert job_calls == 0


def test_node_worker_rejects_transported_scope_before_context_or_execution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store_build_calls = 0
    node_discovery_calls = 0

    def _protected_store_build(config):
        del config
        nonlocal store_build_calls
        store_build_calls += 1
        raise AssertionError("worker store construction reached")

    def _protected_discovery(registry):
        del registry
        nonlocal node_discovery_calls
        node_discovery_calls += 1
        raise AssertionError("node discovery reached")

    monkeypatch.setattr(
        "polisyos.core.artifacts.backends.config.build_artifact_store",
        _protected_store_build,
    )
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.registry.discover_nodes",
        _protected_discovery,
    )

    state = ExperimentState(run_id="R_worker_node_scope")
    with (
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        pytest.raises(CheckpointScopeMismatchError, match="scope mismatch"),
    ):
        asyncio.run(
            run_node_in_worker(
                {
                    "node_id": "scientist.node_policy_output@1.0.0",
                    "alias": "policy",
                    "params": {},
                    "state_bytes": serialize_state(state),
                    "context_meta": {
                        "run_id": state.run_id,
                        "tenant_id": "tenant-b",
                        "cell_id": "cell-b",
                        "store_config": {
                            "backend": "filesystem",
                            "root": str(tmp_path),
                        },
                    },
                }
            )
        )

    assert store_build_calls == 0
    assert node_discovery_calls == 0


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
    import polisyos.core.observability as observability

    degraded: list[dict[str, object]] = []

    monkeypatch.setattr(
        activity_worker_module,
        "emit_degraded_path",
        lambda **kwargs: degraded.append(kwargs) or {"reason": kwargs["reason"]},
    )

    def _boom(_carrier: dict[str, str]) -> object:
        raise RuntimeError("broken trace context")

    monkeypatch.setattr(observability, "extract_headers", _boom)

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
        "polisyos.scientist.orchestration.engine.registry.discover_nodes",
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


@pytest.mark.parametrize(
    (
        "hook_tenant_id",
        "runtime_tenant_id",
        "context_tenant_id",
        "malformed_store_config",
    ),
    [
        ("tenant-b", "tenant-b", "tenant-b", False),
        ("tenant-a", 17, "tenant-a", False),
        ("tenant-b", "tenant-b", "tenant-a", True),
    ],
)
def test_worker_rejects_invalid_or_colluding_scope_before_merge(
    tmp_path: Path,
    monkeypatch,
    hook_tenant_id: str,
    runtime_tenant_id: object,
    context_tenant_id: str,
    malformed_store_config: bool,
) -> None:
    store = FileSystemCAS(tmp_path)
    with tenant_scope(None, tenant_id=hook_tenant_id, cell_id="cell-a"):
        hook = CASCheckpointHook(
            store=store,
            run_dir=tmp_path / "runs" / "R_worker_scope",
            checkpoint_policy="strict",
            tenant_id=hook_tenant_id,
            cell_id="cell-a",
        )
    checkpoint_meta = hook.export_runtime_metadata()
    assert checkpoint_meta is not None
    checkpoint_meta["tenant_id"] = runtime_tenant_id
    if malformed_store_config:
        checkpoint_meta["store_config"] = {"backend": 17}

    workflow = WorkflowSpec(
        workflow_id="wf_worker_scope",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias="policy",
                node_id=ComponentId.parse("scientist.node_policy_output@1.0.0"),
            )
        ],
    )
    worker_store_build_calls = 0
    protected_merge_calls = 0

    def _protected_store_build(config):
        del config
        nonlocal worker_store_build_calls
        worker_store_build_calls += 1
        raise AssertionError("worker store construction reached")

    def _protected_merge(**kwargs):
        del kwargs
        nonlocal protected_merge_calls
        protected_merge_calls += 1
        raise AssertionError("protected merge reached")

    monkeypatch.setattr(
        "polisyos.core.artifacts.backends.config.build_artifact_store",
        _protected_store_build,
    )
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.registry.discover_nodes",
        lambda registry: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.runner.distributed_tier.merge_and_checkpoint_tier",
        _protected_merge,
    )

    base_state = ExperimentState(run_id="R_worker_scope")
    with (
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        pytest.raises(CheckpointScopeMismatchError, match="scope mismatch"),
    ):
        asyncio.run(
            run_merge_checkpoint_tier_in_worker(
                {
                    "workflow_spec_json": workflow.model_dump(mode="json"),
                    "tier_aliases": ["policy"],
                    "result_bytes_by_alias": {},
                    "base_state_bytes": serialize_state(base_state),
                    "context_meta": {
                        "run_id": "R_worker_scope",
                        "tenant_id": context_tenant_id,
                        "cell_id": "cell-a",
                        "workflow_id": workflow.workflow_id,
                        "runner_backend": "temporal",
                        "store_config": {
                            "backend": "filesystem",
                            "root": str(tmp_path),
                        },
                    },
                    "workflow_fingerprint": "b" * 64,
                    "completed_nodes": [],
                    "merge_conflict_policy": "error",
                    "checkpoint_hook_meta": checkpoint_meta,
                }
            )
        )

    assert worker_store_build_calls == 0
    assert protected_merge_calls == 0
