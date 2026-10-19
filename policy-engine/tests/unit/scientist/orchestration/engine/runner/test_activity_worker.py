"""Tests for remote worker context reconstruction."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

import duckdb
import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    SchemaInfo,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.skip_blockers import SkippedNodeBlocker
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.run.worker_lifecycle import WorkerLifecycleCapability
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.core.trace.record import TraceRecord
from polisyos.foundry.methods.causal import PanelObservationalData
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import ResolveParametersNode
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
    RunCausalEvaluationNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointScopeMismatchError,
    resolve_latest_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import (
    ClaimCapableExecutionContext,
    ExecutionContext,
)
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.retry import (
    RetryPolicy,
    _AttemptAuthority,
    _build_attempt_context,
    execute_with_retry_sync,
)
from polisyos.scientist.orchestration.engine.runner import (
    _activity_worker as activity_worker_module,
)
from polisyos.scientist.orchestration.engine.runner._activity_worker import (
    _build_timeout_worker_context,
    _build_worker_context,
    _restore_parent_trace_context,
    run_merge_checkpoint_tier_in_worker,
    run_node_in_worker,
)
from polisyos.scientist.orchestration.engine.runner.serialization import (
    DeserializationError,
    deserialize_outcome,
    deserialize_state,
    deserialize_worker_execution_receipt,
    serialize_outcome,
    serialize_state,
    serialize_timeout_context,
    serialize_worker_execution_receipt,
    worker_dispatch_sha256,
)
from polisyos.scientist.orchestration.engine.runner.state_merge import merge_tier_outcomes
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    mutation_journal_for_state,
)
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


def test_build_worker_context_reconstructs_run_and_registry_bundle(tmp_path: Path) -> None:
    store_root = tmp_path / "shared-cas"
    registry_store = FileSystemCAS(
        store_root,
        tenant_id="tenant-1",
        cell_id="cell-1",
    )
    registry_bundle_ref = build_default_registry_bundle(
        registry_store,
        return_selected_profile=True,
    ).bundle_ref
    ctx: ClaimCapableExecutionContext | None = None
    try:
        with tenant_scope(None, tenant_id="tenant-1", cell_id="cell-1"):
            ctx = _build_worker_context(
                {
                    "run_id": "worker-run-1",
                    "tenant_id": "tenant-1",
                    "cell_id": "cell-1",
                    "store_config": {
                        "backend": "filesystem",
                        "root": str(store_root),
                    },
                    "depth": 3,
                    "workflow_id": "scientist_default",
                    "runner_backend": "ray",
                    "trace_id": "0" * 32,
                    "span_id": "1" * 16,
                    "registry_bundle_ref": registry_bundle_ref.model_dump(mode="json"),
                }
            )

        assert ctx is not None
        assert ctx.depth == 3
        assert ctx.run.run_manifest.run_id == "worker-run-1"
        assert ctx.run.tenant_id == "tenant-1"
        assert ctx.run.cell_id == "cell-1"
        assert ctx.run.run_manifest.registry_bundle == registry_bundle_ref
        assert ctx.store.verify(registry_bundle_ref).ok
        assert isinstance(ctx, ClaimCapableExecutionContext)
        assert ctx.claim_ledger_owner is not None
    finally:
        if ctx is not None:
            ctx.run.suspend_for_resume()


def test_build_worker_context_bootstraps_registry_bundle_when_missing() -> None:
    ctx = _build_worker_context({"run_id": "worker-run-2"})

    assert ctx.run.run_manifest.run_id == "worker-run-2"
    assert ctx.run.run_manifest.registry_bundle.kind == "core.registry_bundle"
    assert ctx.metrics is None or len(ctx.metrics.recent_trace_correlations()) == 1
    assert isinstance(ctx, ClaimCapableExecutionContext)
    assert ctx.claim_ledger_owner is not None


def test_timeout_worker_stages_run_events_and_refuses_parent_lifecycle(
    tmp_path: Path,
) -> None:
    tenant_id = "tenant-timeout-stage"
    cell_id = "cell-timeout-stage"
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        store = FileSystemCAS(tmp_path / "timeout-stage-cas", tenant_id=tenant_id, cell_id=cell_id)
        registry_bundle = build_default_registry_bundle(
            store,
            return_selected_profile=True,
        ).bundle_ref
        parent_run = RunContext.start(
            store=store,
            registry_bundle=registry_bundle,
            run_id="R_timeout_stage",
            run_dir=store.root / "runs" / "R_timeout_stage",
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        parent_ctx = ExecutionContext(
            store=store,
            run=parent_run,
            logger=logging.getLogger("test.timeout_worker_staging"),
        )
        attempt_ctx = _build_attempt_context(parent_ctx, _AttemptAuthority())
        with pytest.raises(ValueError, match="timeout_worker_filesystem_cas_required"):
            serialize_timeout_context(
                attempt_ctx,
                expected_run_id=parent_run.run_manifest.run_id,
            )

        class DerivedExecutionContext(ExecutionContext):
            pass

        derived_ctx = DerivedExecutionContext(
            store=store,
            run=parent_run,
            logger=logging.getLogger("test.timeout_worker_derived_context"),
        )
        with pytest.raises(ValueError, match="timeout_worker_unsupported_execution_context"):
            serialize_timeout_context(
                derived_ctx,
                expected_run_id=parent_run.run_manifest.run_id,
            )
        context_meta = serialize_timeout_context(
            parent_ctx, expected_run_id=parent_run.run_manifest.run_id
        )
        worker_ctx = _build_timeout_worker_context(context_meta)
        trace_path = parent_run.trace_path
        assert trace_path is not None
        before = trace_path.read_bytes()

        worker_ctx.run.emit("worker", "candidate_event")
        worker_ctx.run.update_manifest(execution_profile="worker-candidate-profile")

        assert trace_path.read_bytes() == before
        assert [record.event for record in worker_ctx.run.trace.records] == [
            "candidate_event",
            "RUN_CONTEXT_SNAPSHOT",
        ]
        assert worker_ctx.run.run_manifest.execution_profile == "worker-candidate-profile"
        assert parent_run.run_manifest.execution_profile is None
        with pytest.raises(ValueError, match="timeout_worker_run_lifecycle_not_owned"):
            worker_ctx.run.finalize()
        with pytest.raises(ValueError, match="timeout_worker_run_lifecycle_not_owned"):
            worker_ctx.run.suspend_for_resume()
        assert trace_path.read_bytes() == before

        parent_capability = WorkerLifecycleCapability.for_parent(parent_run)
        assert parent_capability.snapshot().run_manifest == parent_run.run_manifest
        with pytest.raises(ValueError, match="worker_lifecycle_core_run_required"):
            WorkerLifecycleCapability.for_parent(worker_ctx.run)
        assert not parent_run._closed and not parent_run._suspended
        assert parent_run._active_lease is not None
        parent_run.suspend_for_resume()


def test_timeout_worker_dispatch_digest_rejects_changed_params_before_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_bytes = serialize_state(ExperimentState(run_id="R_dispatch_binding"))
    payload = {
        "node_id": "scientist.node_resolve_parameters@1.0.0",
        "alias": "resolve",
        "params": {"mode": "original"},
        "state_bytes": state_bytes,
        "trace_carrier": {},
        "timeout_s": None,
        "max_retries": 0,
        "context_meta": {},
        "worker_invocation_id": "a" * 64,
    }
    payload["worker_dispatch_sha256"] = worker_dispatch_sha256(
        node_id=payload["node_id"],
        alias=payload["alias"],
        params=payload["params"],
        state_bytes=state_bytes,
        trace_carrier=payload["trace_carrier"],
        timeout_s=None,
        max_retries=0,
        context_meta=payload["context_meta"],
    )
    payload["params"] = {"mode": "tampered"}
    monkeypatch.setattr(
        activity_worker_module,
        "_build_timeout_worker_context",
        lambda _meta: pytest.fail("dispatch mismatch must fail before context reconstruction"),
    )

    with pytest.raises(ValueError, match="timeout_worker_dispatch_digest_mismatch"):
        asyncio.run(run_node_in_worker(payload, timeout_authority=(True, 1e20)))


def test_worker_execution_receipt_retains_typed_failure_and_rejects_extra_fields() -> None:
    owner_ref = _artifact_ref("worker-owner")
    event = TraceRecord(run_id="R_receipt_error", phase="worker", event="candidate")
    payload = serialize_worker_execution_receipt(
        error_payload={
            "message": "ValueError: candidate failure",
            "category": "fatal",
            "code": "worker.candidate_failure",
        },
        invocation_id="b" * 64,
        dispatch_sha256="c" * 64,
        owner_snapshot_ref=owner_ref,
        records=[event],
    )

    (
        outcome_bytes,
        error_payload,
        invocation_id,
        dispatch_digest,
        decoded_owner_ref,
        records,
    ) = deserialize_worker_execution_receipt(payload)

    assert outcome_bytes is None
    assert error_payload == {
        "message": "ValueError: candidate failure",
        "category": "fatal",
        "code": "worker.candidate_failure",
    }
    assert invocation_id == "b" * 64
    assert dispatch_digest == "c" * 64
    assert decoded_owner_ref == owner_ref
    assert records == [event]

    malformed = json.loads(payload)
    malformed["unadmitted"] = True
    with pytest.raises(DeserializationError, match="Malformed worker execution receipt"):
        deserialize_worker_execution_receipt(json.dumps(malformed).encode("utf-8"))


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


def test_build_worker_context_binds_owner_for_persisted_writes(tmp_path: Path) -> None:
    root = tmp_path / "shared-cas"
    with tenant_scope(None, tenant_id="worker-tenant", cell_id="worker-cell"):
        ctx = _build_worker_context(
            {
                "run_id": "worker-run-owned-store",
                "tenant_id": "worker-tenant",
                "cell_id": "worker-cell",
                "store_config": {"backend": "filesystem", "root": str(root)},
            }
        )
        assert isinstance(ctx.store, FileSystemCAS)
        assert ctx.store._tenant_id == "worker-tenant"
        assert ctx.store._cell_id == "worker-cell"
        assert ctx.store._ownership_enforced is True
        ref = ctx.store.put_json(
            {"candidate": "worker-owned"},
            PutOptions(kind="core.worker_owner_probe", media_type="application/json"),
        )

        parent_reader = FileSystemCAS(root).for_tenant("worker-tenant", "worker-cell")
        assert parent_reader.get_bytes(ref) == ctx.store.get_bytes(ref)


def test_build_worker_context_preserves_unowned_legacy_candidate_store(tmp_path: Path) -> None:
    root = tmp_path / "legacy-cas"
    ctx = _build_worker_context(
        {
            "run_id": "worker-run-unowned-legacy",
            "store_config": {"backend": "filesystem", "root": str(root)},
        }
    )

    assert isinstance(ctx.store, FileSystemCAS)
    assert ctx.store._tenant_id is None
    assert ctx.store._ownership_enforced is False
    ref = ctx.store.put_json(
        {"candidate": "legacy-unowned"},
        PutOptions(kind="core.worker_candidate_probe", media_type="application/json"),
    )
    assert FileSystemCAS(root).get_bytes(ref) == ctx.store.get_bytes(ref)


@pytest.mark.parametrize(
    "store_config",
    [
        None,
        [],
        "malformed-config",
        {"backend": "not-a-backend"},
        {"backend": 17},
        {"unexpected": True},
    ],
    ids=["none", "list", "string", "unknown-backend", "malformed-backend", "extra-field"],
)
@pytest.mark.parametrize(
    "legacy_route",
    [False, True],
    ids=["ephemeral-default", "legacy-root-fallback"],
)
def test_build_worker_context_refuses_malformed_supplied_store_config_before_fallback(
    tmp_path: Path,
    monkeypatch,
    store_config: object,
    legacy_route: bool,
) -> None:
    build_calls: list[bool] = []
    temp_calls: list[bool] = []

    def _unexpected_store_build(config, **kwargs):
        del config, kwargs
        build_calls.append(True)
        raise AssertionError(
            "invalid supplied store config must be rejected before CAS construction"
        )

    def _unexpected_temp_directory(*args, **kwargs):
        del args, kwargs
        temp_calls.append(True)
        raise AssertionError("invalid supplied store config must be rejected before temp creation")

    monkeypatch.setattr(
        "polisyos.core.artifacts.backends.config.build_artifact_store",
        _unexpected_store_build,
    )
    monkeypatch.setattr("tempfile.mkdtemp", _unexpected_temp_directory)
    fallback_root = tmp_path / "legacy-fallback"
    meta: dict[str, object] = {
        "run_id": "worker-run-invalid-supplied-config",
        "store_config": store_config,
    }
    if legacy_route:
        meta.update({"store_backend": "filesystem", "store_root": str(fallback_root)})

    with pytest.raises(CheckpointScopeMismatchError, match="store config invalid"):
        _build_worker_context(meta)

    assert build_calls == []
    assert temp_calls == []
    assert not fallback_root.exists()


def test_build_worker_context_refuses_owner_without_shared_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    build_calls: list[bool] = []

    def _unexpected_store_build(config, **kwargs):
        del config, kwargs
        build_calls.append(True)
        raise AssertionError("explicit owner must not receive an ephemeral CAS")

    monkeypatch.setattr(
        "polisyos.core.artifacts.backends.config.build_artifact_store",
        _unexpected_store_build,
    )
    with tenant_scope(None, tenant_id="worker-tenant", cell_id="worker-cell"):
        with pytest.raises(
            CheckpointScopeMismatchError,
            match="owner scope requires a configured shared store",
        ):
            _build_worker_context(
                {
                    "run_id": "worker-run-owner-without-store",
                    "tenant_id": "worker-tenant",
                    "cell_id": "worker-cell",
                }
            )

    assert build_calls == []
    assert not (tmp_path / "worker-cas").exists()


@pytest.mark.parametrize(
    ("case", "expected_error"),
    [
        ("malformed_run_owner", "tenant scope invalid"),
        ("cell_without_tenant", "cell requires tenant scope"),
        ("mismatched_store_owner", "store owner mismatch"),
        ("mismatched_store_root", "store root metadata mismatch"),
        ("mismatched_store_backend", "store backend metadata mismatch"),
        ("malformed_scoped_store_config", "store config invalid"),
        ("non_mapping_scoped_store_config", "store config invalid"),
        ("unsupported_scoped_backend", "backend cannot enforce tenant ownership"),
    ],
)
def test_build_worker_context_refuses_owner_loss_before_store_creation(
    tmp_path: Path,
    monkeypatch,
    case: str,
    expected_error: str,
) -> None:
    root = tmp_path / "must-not-be-created"
    build_calls: list[bool] = []

    def _unexpected_store_build(config, **kwargs):
        del config, kwargs
        build_calls.append(True)
        raise AssertionError("owner validation must precede CAS construction")

    monkeypatch.setattr(
        "polisyos.core.artifacts.backends.config.build_artifact_store",
        _unexpected_store_build,
    )
    tenant_id: object = "worker-tenant"
    cell_id: str | None = "worker-cell"
    store_config: object = {"backend": "filesystem", "root": str(root)}
    extra: dict[str, object] = {}
    if case == "malformed_run_owner":
        tenant_id = 17
    elif case == "cell_without_tenant":
        tenant_id = None
    elif case == "mismatched_store_owner":
        store_config["tenant_id"] = "other-tenant"
    elif case == "mismatched_store_root":
        extra["store_backend"] = "filesystem"
        extra["store_root"] = str(tmp_path / "other-cas")
    elif case == "mismatched_store_backend":
        extra["store_backend"] = "gcs"
    elif case == "malformed_scoped_store_config":
        assert isinstance(store_config, dict)
        store_config["backend"] = 17
    elif case == "non_mapping_scoped_store_config":
        store_config = "malformed-config"
    elif case == "unsupported_scoped_backend":
        store_config = {"backend": "gcs", "bucket": "unused-test-bucket"}
    else:
        raise AssertionError(f"unknown fixture case: {case}")

    with tenant_scope(None, tenant_id="worker-tenant", cell_id="worker-cell"):
        with pytest.raises(CheckpointScopeMismatchError, match=expected_error):
            _build_worker_context(
                {
                    "run_id": "worker-run-rejected-owner",
                    "tenant_id": tenant_id,
                    "cell_id": cell_id,
                    "store_config": store_config,
                    **extra,
                }
            )

    assert build_calls == []
    assert not root.exists()


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


class JournalReplayWorkerNode:
    _spec = NodeSpec(
        metadata=_meta("scientist.node_journal_replay@1.0.0", "JournalReplay"),
        state_reads=["params"],
        state_writes=["params"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx, state) -> NodeOutcome:
        del ctx
        state.params["y"] = 4
        del state.params["stale"]
        return NodeOutcome(status="ok", state=state)


class SkippedWorkerNode:
    _spec = NodeSpec(
        metadata=_meta("scientist.node_worker_skip@1.0.0", "WorkerSkip"),
        state_reads=[],
        state_writes=["params.worker_status_mutation"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx, state) -> NodeOutcome:
        del ctx
        state = state.model_copy(deep=True)
        state.params["worker_status_mutation"] = "skip"
        return NodeOutcome(
            status="skip",
            state=state,
            artifacts=[_artifact_ref("worker-skip-output")],
            events=[NodeEvent(code="worker.skip", message="worker skipped")],
            skip_blocker=SkippedNodeBlocker(
                node_id=str(self._spec.metadata.component_id),
                alias="skipped",
                node_kind="other_optional_analytic",
                reason="fixture_skip",
                missing_input="fixture input",
                owner="test",
                phase="test",
                downstream_impact="test only",
                allowed_profile="dev",
                closeout_blocking_policy="blocks_serious_closeout",
                scorecard_blocking_policy="blocks_scorecard_pass",
                approval_blocking_policy="blocks_approval_ready",
                public_export_blocking_policy="blocks_public_export",
            ),
        )


class FailedWorkerNode:
    _spec = NodeSpec(
        metadata=_meta("scientist.node_worker_fail@1.0.0", "WorkerFail"),
        state_reads=[],
        state_writes=["params.worker_status_mutation"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx, state) -> NodeOutcome:
        del ctx
        failed_state = state.model_copy(deep=True)
        failed_state.params["worker_status_mutation"] = "fail"
        return NodeOutcome(
            status="fail",
            state=failed_state,
            artifacts=[_artifact_ref("worker-fail-output")],
            events=[NodeEvent(code="worker.fail", message="worker failed")],
            error=NodeError(code="node.worker_failure", message="returned failure"),
        )


def _seed_spawn_timeout_skg(db_path: Path) -> None:
    connection = duckdb.connect(str(db_path))
    try:
        connection.execute("CREATE TABLE ac_skg_versions(version_id INTEGER)")
        connection.execute("INSERT INTO ac_skg_versions VALUES (7)")
        connection.execute(
            """
            CREATE TABLE ac_skg_simulation_parameters (
                numeric_id VARCHAR,
                openalex_id VARCHAR,
                canonical_name VARCHAR,
                estimate_type VARCHAR,
                point_estimate DOUBLE,
                estimate_sign VARCHAR,
                unit VARCHAR,
                evidence_strength VARCHAR,
                confidence_interval_json VARCHAR,
                std_error DOUBLE,
                source_layer VARCHAR,
                uncertainty_source VARCHAR,
                quality_flags_json VARCHAR,
                linked_claim_ids_json VARCHAR,
                linked_edges_json VARCHAR,
                context_json VARCHAR
            )
            """
        )
        connection.execute(
            """
            INSERT INTO ac_skg_simulation_parameters VALUES
                ('p1', 'W1', 'fiscal_multiplier', 'point', 1.4, 'positive',
                 'ratio', 'rct', '[1.1, 1.7]', NULL, 'simulation_ready',
                 'confidence_interval', '[]', '[]', '[]', ?)
            """,
            [
                json.dumps(
                    {
                        "context_id": "us-2025",
                        "countries": ["US"],
                        "publication_year": 2025,
                    }
                )
            ],
        )
    finally:
        connection.close()


def test_canonical_timeout_worker_replays_operations_into_changed_receiver(
    tmp_path: Path,
) -> None:
    """The admitted timed node's typed process result drives the real receiver merge."""
    db_path = tmp_path / "timeout-skg.duckdb"
    _seed_spawn_timeout_skg(db_path)

    tenant_id = "tenant-timeout-wire"
    cell_id = "cell-timeout-wire"
    run_id = "R_worker_canonical_timeout_mutation_journal"
    store = FileSystemCAS(
        tmp_path / "timeout-cas",
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    run: RunContext | None = None
    try:
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            registry_bundle = build_default_registry_bundle(
                store,
                return_selected_profile=True,
            )
            run = RunContext.start(
                store=store,
                registry_bundle=registry_bundle.bundle_ref,
                run_id=run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            graph_ref = persist_causal_graph_model(
                _ensure_ir_artifact_store(store),
                CausalGraphModel(
                    graph_type=GraphType.DAG,
                    nodes=["fiscal_multiplier"],
                    edges=[],
                ),
            )
            context = ExecutionContext(
                store=store,
                run=run,
                logger=logging.getLogger("test.canonical_timeout_mutation_journal"),
            )
            producer_state = ExperimentState(
                run_id=run_id,
                artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
                params={
                    "target_context": {
                        "context_id": "us-2025",
                        "countries": ["US"],
                        "publication_year": 2025,
                    },
                    "required_parameters": ["fiscal_multiplier"],
                    "domain": "fiscal",
                    "skg_db_path": str(db_path),
                    "phase15_runtime_backend": "numpy",
                    "phase15_runtime_draws": 16,
                    "phase15_runtime_seed": 7,
                    "phase15_runtime_backend_used": "producer-before-timeout",
                },
            )
            receiver_state = producer_state.model_copy(deep=True)
            receiver_state.params["phase15_runtime_backend_used"] = "receiver-before-timeout"
            receiver_state.params["receiver_only"] = "changed-after-dispatch"
            node = ResolveParametersNode()

            # This high-level timed call selects Darwin's spawn + typed NodeTask/result
            # channel. Other supported hosts retain their own timed process method.
            outcome = execute_with_retry_sync(
                node,
                context,
                producer_state,
                retry_policy=RetryPolicy(max_retries=0),
                timeout_s=30.0,
                alias="resolve",
                dispatch_params={},
            )
            assert run.trace_path is not None
            durable_trace = [
                json.loads(line)
                for line in run.trace_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert sum(item["event"] == "RUN_STARTED" for item in durable_trace) == 1
            assert sum(item["event"] == "WORKER_INVOCATION_STARTED" for item in durable_trace) == 1
            assert (
                sum(item["event"] == "WORKER_INVOCATION_COMPLETED" for item in durable_trace) == 1
            )
            receipt_ids = {
                item.get("worker_invocation_id")
                for item in durable_trace
                if item.get("worker_invocation_id") is not None
            }
            assert len(receipt_ids) == 1
            assert all(
                item.get("worker_dispatch_sha256") is not None
                for item in durable_trace
                if item.get("worker_invocation_id") in receipt_ids
            )
            assert outcome.status == "ok"
            assert outcome.state.run_id == run_id
            assert (
                outcome.state.params["phase15_runtime_backend_used"]
                != (receiver_state.params["phase15_runtime_backend_used"])
            )
            journal = mutation_journal_for_state(outcome.state)
            assert journal is not None
            assert any(
                mutation.path == "params.phase15_runtime_backend_used"
                and mutation.operation == "set"
                for mutation in journal.operations
            )
            assert {mutation.path for mutation in journal.operations}.issubset(
                set(node.spec.state_writes)
            )

            result_wire = serialize_outcome(outcome)
            merge_args = {
                "requested_aliases": ["resolve"],
                "write_specs": {"resolve": list(node.spec.state_writes)},
            }
            merged = merge_tier_outcomes(
                serialize_state(receiver_state),
                {"resolve": result_wire},
                **merge_args,
            )
            merged_state = deserialize_state(merged.state_bytes)
            assert (
                merged_state.params["phase15_runtime_backend_used"]
                == outcome.state.params["phase15_runtime_backend_used"]
            )
            assert merged_state.params["receiver_only"] == "changed-after-dispatch"
            merged_graph_ref = merged_state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
            expected_graph_ref = ArtifactRef.model_validate(
                {
                    "artifact_id": str(graph_ref.artifact_id),
                    "kind": graph_ref.kind,
                    "media_type": graph_ref.media_type,
                    "manifest_profile_sha256": graph_ref.manifest_profile_sha256,
                }
            )
            assert artifact_ref_identity_key(merged_graph_ref) == artifact_ref_identity_key(
                expected_graph_ref
            )
            assert (
                merged_state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
                == outcome.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
            )

            # Keep both typed envelope markers and the full result snapshot, but remove
            # only the operation body. An empty journal is authoritative at the merge
            # boundary, so this must lose the changed receiver's declared node writes.
            encoded = json.loads(result_wire)
            outer_schema = encoded["wire_schema"]
            operation_envelope = encoded["value"]
            operation_schema = operation_envelope["wire_schema"]
            outcome_snapshot = json.dumps(
                operation_envelope["outcome"], sort_keys=True, separators=(",", ":")
            )
            original_operation_count = len(operation_envelope["state_mutations"])
            assert operation_schema == "polisyos.scientist.node_outcome.mutations.v1"
            assert operation_envelope["state_mutations"]
            operation_envelope["state_mutations"] = []
            assert encoded["wire_schema"] == outer_schema
            assert operation_envelope["wire_schema"] == operation_schema
            assert (
                json.dumps(operation_envelope["outcome"], sort_keys=True, separators=(",", ":"))
                == outcome_snapshot
            )
            stripped_wire = json.dumps(encoded, separators=(",", ":")).encode("utf-8")
            removed = merge_tier_outcomes(
                serialize_state(receiver_state),
                {"resolve": stripped_wire},
                **merge_args,
            )
            removed_state = deserialize_state(removed.state_bytes)
            assert (
                removed_state.params["phase15_runtime_backend_used"]
                == receiver_state.params["phase15_runtime_backend_used"]
            )
            assert (
                removed_state.params["phase15_runtime_backend_used"]
                != merged_state.params["phase15_runtime_backend_used"]
            )
            assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF not in (
                removed_state.artifacts_index
            )
            assert removed_state.params["receiver_only"] == "changed-after-dispatch"

            observation_root = os.environ.get("E02_B_PROPERTY_REMOVAL_OBSERVATION")
            if observation_root:
                observation_dir = Path(observation_root)
                observation_dir.mkdir(parents=True, exist_ok=True)
                observation = {
                    "observation_schema": "e02.prepared_b.removal_observation.v1",
                    "case_id": "worker-operation-replay",
                    "outer_wire_schema": outer_schema,
                    "operation_wire_schema": operation_schema,
                    "operation_count_before_removal": original_operation_count,
                    "operation_count_after_removal": len(operation_envelope["state_mutations"]),
                    "outcome_snapshot_preserved": (
                        json.dumps(
                            operation_envelope["outcome"],
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        == outcome_snapshot
                    ),
                    "receiver_value_before": receiver_state.params["phase15_runtime_backend_used"],
                    "produced_value": outcome.state.params["phase15_runtime_backend_used"],
                    "merged_value": merged_state.params["phase15_runtime_backend_used"],
                    "stripped_value": removed_state.params["phase15_runtime_backend_used"],
                    "receiver_only_after_merge": merged_state.params["receiver_only"],
                    "receiver_only_after_removal": removed_state.params["receiver_only"],
                    "bundle_ref_after_merge": (
                        ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF
                        in merged_state.artifacts_index
                    ),
                    "bundle_ref_after_removal": (
                        ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF
                        in removed_state.artifacts_index
                    ),
                }
                (observation_dir / "worker-operation-replay.json").write_text(
                    json.dumps(observation, sort_keys=True) + "\n", encoding="utf-8"
                )
    finally:
        if run is not None:
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                run.suspend_for_resume()


def test_remote_worker_wire_replays_only_declared_branch_operations(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def _discover_nodes(registry) -> None:
        registry.register(JournalReplayWorkerNode())

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.registry.discover_nodes",
        _discover_nodes,
    )
    producer_state = ExperimentState(
        run_id="R_worker_mutation_journal",
        params={"y": 4, "unrelated": "old", "stale": 1, "removed": "old"},
    )
    current_state = ExperimentState(
        run_id=producer_state.run_id,
        params={"y": 9, "unrelated": "new", "stale": 1, "keep": 2},
    )

    outcome_bytes = asyncio.run(
        run_node_in_worker(
            {
                "node_id": "scientist.node_journal_replay@1.0.0",
                "alias": "mutate",
                "params": {},
                "state_bytes": serialize_state(producer_state),
                # Custom IDs use the generic untimed wire on macOS; the closed spawn
                # timeout contract admits only the canonical builtin node. Linux keeps
                # its established fork-backed timed route.
                "timeout_s": 2.0 if sys.platform == "linux" else None,
                "max_retries": 0,
                "context_meta": {
                    "run_id": producer_state.run_id,
                    "store_config": {"backend": "filesystem", "root": str(tmp_path)},
                },
            }
        )
    )
    outcome = deserialize_outcome(outcome_bytes)
    assert outcome.status == "ok"

    merged = merge_tier_outcomes(
        serialize_state(current_state),
        {"mutate": outcome_bytes},
        requested_aliases=["mutate"],
        write_specs={"mutate": ["params"]},
    )
    params = deserialize_state(merged.state_bytes).params
    assert params == {"y": 4, "unrelated": "new", "keep": 2}
    assert outcome.state.params == {"y": 4, "unrelated": "old", "removed": "old"}

    narrowed = merge_tier_outcomes(
        serialize_state(current_state),
        {"mutate": outcome_bytes},
        requested_aliases=["mutate"],
        write_specs={"mutate": ["params.y"]},
    )
    narrowed_params = deserialize_state(narrowed.state_bytes).params
    assert narrowed_params == {"y": 4, "unrelated": "new", "stale": 1, "keep": 2}


@pytest.mark.parametrize(
    ("node", "node_id", "expected_status"),
    [
        (SkippedWorkerNode, "scientist.node_worker_skip@1.0.0", "skip"),
        (FailedWorkerNode, "scientist.node_worker_fail@1.0.0", "fail"),
    ],
)
def test_node_worker_transport_preserves_native_non_ok_status(
    tmp_path: Path,
    monkeypatch,
    node,
    node_id: str,
    expected_status: str,
) -> None:
    def _discover_nodes(registry) -> None:
        registry.register(node())

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.registry.discover_nodes",
        _discover_nodes,
    )
    state = ExperimentState(run_id="R_worker_native_status")

    result = asyncio.run(
        run_node_in_worker(
            {
                "node_id": node_id,
                "alias": "skipped",
                "params": {},
                "state_bytes": serialize_state(state),
                "context_meta": {
                    "run_id": state.run_id,
                    "store_config": {
                        "backend": "filesystem",
                        "root": str(tmp_path),
                    },
                },
            }
        )
    )

    outcome = deserialize_outcome(result)
    assert outcome.status == expected_status
    assert outcome.state.run_id == state.run_id
    assert outcome.state.params["worker_status_mutation"] == expected_status
    assert len(outcome.artifacts) == 1
    assert outcome.events[0].code == f"worker.{expected_status}"
    if expected_status == "skip":
        assert outcome.skip_blocker is not None
        assert outcome.skip_blocker.reason == "fixture_skip"
    else:
        assert outcome.error is not None
        assert outcome.error.code == "node.worker_failure"


def test_run_merge_checkpoint_tier_in_worker_restores_checkpoint_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    checkpoint_run_dir = tmp_path / "runs" / "R_worker_merge"
    hook = CASCheckpointHook(
        store=store,
        run_dir=checkpoint_run_dir,
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

    def _deny_run_context_start(*args, **kwargs):
        del args, kwargs
        raise AssertionError("checkpoint-only worker must not claim a RunContext lifecycle")

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.registry.discover_nodes",
        _discover_nodes,
    )
    monkeypatch.setattr(RunContext, "start", _deny_run_context_start)

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
    assert not (checkpoint_run_dir / "trace.jsonl").exists()


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


def _worker_unbound_origin_candidate(
    candidate_id: str,
) -> PolicyCandidateSchema:
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle

    bundle = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_worker_unbound_origin",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(policy_id="policy_worker_unbound_origin"),
        model_spec=ModelSpec(
            model_id="model_worker_unbound_origin",
            data_snapshot_ref="sha256:" + "1" * 64,
        ),
    )
    return PolicyCandidateSchema.from_trinity_bundle(bundle, candidate_id=candidate_id)


def test_unbound_worker_retry_consumes_candidate_without_owner_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
        _resolve_candidate,
    )
    from polisyos.scientist.policy_design.phase3 import _load_bound_candidate_source_state

    candidate = _worker_unbound_origin_candidate("candidate_worker_unbound")

    class UnboundCandidateWorkerNode:
        _spec = NodeSpec(
            metadata=_meta("scientist.node_unbound_candidate@1.0.0", "UnboundCandidate"),
            state_reads=["params"],
            state_writes=["params"],
        )

        @property
        def spec(self) -> NodeSpec:
            return self._spec

        def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            basis = _load_bound_candidate_source_state(ctx, state)
            selected, selected_ref = _resolve_candidate(ctx, state)
            assert selected is not None
            assert selected_ref is None
            next_state = state.model_copy(deep=True)
            next_state.params.update(
                {
                    "selected_candidate_id": selected.candidate_id,
                    "owner_basis_present": basis is not None,
                    "owner_attempt_count": len(ctx.run.read_runtime_invocation_attempts()),
                }
            )
            return NodeOutcome(status="ok", state=next_state)

    def _discover_nodes(registry: NodeRegistry, **kwargs: object) -> None:
        del kwargs
        registry.register(UnboundCandidateWorkerNode())

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.registry.discover_nodes",
        _discover_nodes,
    )
    state = ExperimentState(
        run_id="R_worker_unbound_candidate_origin",
        params={"policy_candidate_schema": candidate.model_dump(mode="json")},
    )
    worker_store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(
        worker_store,
        return_selected_profile=True,
    ).bundle_ref
    result = asyncio.run(
        run_node_in_worker(
            {
                "node_id": "scientist.node_unbound_candidate@1.0.0",
                "alias": "candidate",
                "params": {},
                "state_bytes": serialize_state(state),
                "context_meta": {
                    "run_id": state.run_id,
                    "store_config": {"backend": "filesystem", "root": str(tmp_path)},
                    "registry_bundle_ref": registry_bundle.model_dump(mode="json"),
                },
            }
        )
    )
    outcome = deserialize_outcome(result)

    assert outcome.status == "ok"
    assert outcome.state.params["selected_candidate_id"] == "candidate_worker_unbound"
    assert outcome.state.params["owner_basis_present"] is False
    assert outcome.state.params["owner_attempt_count"] == 0
