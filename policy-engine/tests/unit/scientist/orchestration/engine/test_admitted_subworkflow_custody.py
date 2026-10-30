"""Two private children via SubWorkflow, the normal executor and real Core custody.

This bounded test does not appoint the production bootstrap or prove Stage B.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from polisyos.common.async_tools import get_shared_executor
from polisyos.common.borrowed_execution import _BorrowedExecutionGrant
from polisyos.common.job_execution_interrupt import (
    JobExecutionInterrupt,
    JobExecutionInterrupted,
    job_execution_interrupt_scope,
)
from polisyos.core.artifacts.child_release import ChildReleaseUnavailableError
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.child_custody import ChildComputationBinding, ChildComputationCustody
from polisyos.core.run.context import RunContext
from polisyos.fabric.connectors.resilience.circuit_breaker import CircuitBreaker
from polisyos.runtime.http.resilience import BlockingDependencyGuard
from polisyos.scientist.orchestration.engine.child_computation import (
    _ApprovedChildPorts,
    _finite_json,
    _hold_admitted_parent_dispatch,
    _ManagedChildRunner,
    _MemberAtBootstrap,
    _StagedParentRun,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.retry import RetryPolicy
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.sub_workflow import (
    StateMapping,
    SubWorkflowConfig,
    SubWorkflowNode,
)
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactReader
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore


class _Projection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected: tuple[ArtifactRef, ...]


class _Resolver:
    def resolve(
        self, store: ArtifactReader, projection_ref: ArtifactRef
    ) -> tuple[ArtifactRef, ...]:
        manifest = store.get_manifest(projection_ref)
        if manifest.kind == "tests.child.value":
            return ()
        if manifest.kind != "tests.child.projection":
            raise ValueError("unsupported_test_schema")
        payload = _Projection.model_validate_json(store.get_bytes(projection_ref))
        closure: list[ArtifactRef] = []
        for ref in payload.selected:
            store.get_bytes(ref)
            closure.append(ref)
            closure.extend(self.resolve(store, ref))
        return tuple(closure)


_COMPONENT = ComponentId.parse("scientist.node_child_test_producer@1.0.0")
_SPEC = NodeSpec(
    metadata=ComponentMetadata(
        component_id=_COMPONENT,
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name="Child test producer",
        description="Produce a selected reference and private sibling",
        capabilities=Capability.SCIENTIST_NODE,
    ),
    state_reads=["params.candidate"],
    state_writes=["artifacts_index.projection"],
)


class _Producer:
    hidden_refs: list[ArtifactRef] = []
    last_unknown: BaseException | None = None

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if state.params["candidate"] == "force-child-failure":
            raise ValueError("synthetic child failure")
        if state.params["candidate"] == "force-child-unknown":
            from polisyos.core.run.child_custody import ChildGuardedStageWriteUnknown

            _Producer.last_unknown = ChildGuardedStageWriteUnknown(
                release_id="test-release",
                root_run_id="root",
                parent_attempt_id="synthetic",
                parent_basis_json=b"{}",
                job_intent_locator=None,
            )
            raise _Producer.last_unknown
        selected = ctx.store.put_bytes(
            str(state.params["candidate"]).encode(),
            PutOptions(kind="tests.child.value", media_type="application/octet-stream"),
            return_selected_profile=True,
        )
        hidden = ctx.store.put_bytes(
            b"unselected",
            PutOptions(kind="tests.child.value", media_type="application/octet-stream"),
            return_selected_profile=True,
        )
        self.hidden_refs.append(hidden)
        projection = ctx.store.put_json(
            _Projection(selected=(selected,)).model_dump(mode="json"),
            PutOptions(
                kind="tests.child.projection",
                media_type="application/json",
                schema=SchemaInfo(name="tests.ChildProjection", version="1"),
            ),
            return_selected_profile=True,
        )
        state.artifacts_index["projection"] = projection
        return NodeOutcome(status="ok", state=state, artifacts=[projection])


def _parent_inputs(
    store: FileSystemCAS,
    component_id: ComponentId,
    *,
    retry: RetryPolicy | None = None,
    timeout_s: float | None = None,
    state: ExperimentState | None = None,
) -> tuple[ArtifactRef, ArtifactRef, ExperimentState]:
    state = state or ExperimentState(run_id="root")
    workflow = WorkflowSpec(
        workflow_id="actual_parent_test",
        nodes=[
            NodeInvocation(alias="parent", node_id=component_id, retry=retry, timeout_s=timeout_s)
        ],
    )
    workflow_ref = store.put_json(
        workflow.model_dump(),
        PutOptions(
            kind="scientist.workflow_spec",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.WorkflowSpec", version="1.0"
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    state_ref = store.put_json(
        state.model_dump(),
        PutOptions(
            kind="scientist.experiment_state",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.ExperimentState",
                version=state.schema_version,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return workflow_ref, state_ref, state


@pytest.mark.parametrize(
    "probe",
    [
        "normal",
        "revocation_unknown",
        "preserve_unknown",
        "child_cache",
        "producer_stale",
        "producer_expired_during_decision",
        "producer_revoke_first",
        "producer_admit_first",
    ],
)
def test_two_admitted_subworkflows_release_only_selected_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: str
) -> None:
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from tests.unit.runtime.http.test_child_control_authorization import _job

    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    attempt = _job(control, run_id="root", kind="workflow_run")
    guard = BlockingDependencyGuard(
        dependency_name="test-child",
        timeout_seconds=120,
        breaker=CircuitBreaker("test-child"),
        executor=get_shared_executor(),
    )
    try:
        with control.job_execution_fence(job_id="job-a", worker_id="worker-a", attempt=attempt):
            guard.run_with_parent_admission(
                lambda grant: _two_children(tmp_path, monkeypatch, grant, control, probe),
                deadline_monotonic=time.monotonic() + 120,
            )
    finally:
        guard.close()


def _two_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    grant: _BorrowedExecutionGrant,
    control: ControlPlaneStore,
    probe: str,
) -> None:
    from polisyos.core.artifacts.child_release import (
        _JOB_OWNER_BOOTSTRAP_TOKEN,
        _install_child_job_owner,
    )
    from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
        RunHierarchicalPolicySearchNode,
    )
    from polisyos.scientist.orchestration.engine.component_identity import (
        capture_engine_component_identity,
    )

    _Producer.hidden_refs.clear()
    served = FileSystemCAS(tmp_path / "served", ownership_enforced=False)
    registry = build_default_registry_bundle(served, return_selected_profile=True)
    root = RunContext.start(
        served,
        registry.bundle_ref,
        run_id="root",
        run_dir=served.root / "runs" / "root",
        tenant_id="tenant-a",
        cell_id="cell-a",
        control_job_id="job-a",
    )
    workflow = WorkflowSpec(
        workflow_id="admitted_child_test",
        nodes=[NodeInvocation(alias="producer", node_id=_COMPONENT)],
        error_policy="fail_fast",
    )
    config = SubWorkflowConfig(
        workflow=workflow,
        input_mappings=[
            StateMapping(source_path="params.candidate", target_path="params.candidate")
        ],
    )
    template = _finite_json(
        {"sub_workflow": config.model_dump(mode="json"), "projection_key": "projection"}
    )
    attempt_id = str(uuid4())
    parent_node = RunHierarchicalPolicySearchNode()
    parent_id = str(parent_node.spec.metadata.component_id)
    workflow_ref, state_ref, parent_input = _parent_inputs(
        served, parent_node.spec.metadata.component_id
    )
    parent_identity = capture_engine_component_identity(parent_node, parent_id, {})
    assert parent_identity is not None
    basis = root._record_runtime_invocation_started(
        attempt_id=attempt_id,
        attempt_number=1,
        workflow_spec_ref=workflow_ref,
        node_alias="parent",
        component_id=parent_id,
        input_state_ref=state_ref,
        implementation_identity=parent_identity,
    )
    binding = ChildComputationBinding(
        root_run_id="root",
        control_job_id="job-a",
        parent_attempt_id=attempt_id,
        parent_basis_ref=basis,
        tenant_id="tenant-a",
        cell_id="cell-a",
        policy_id="test.appointed",
        policy_version="1",
        template_sha256="sha256:" + hashlib.sha256(template).hexdigest(),
        admission_id="test-admitted",
        child_invocation_id="parent",
        admission_generation=1,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )
    parent_seal = _hold_admitted_parent_dispatch(
        root, binding, parent_node, parent_node, {}, grant, parent_input
    )
    fence = control.child_computation_publication_fence(grant=grant, binding=binding)
    custody = ChildComputationCustody(
        root,
        staging_root=tmp_path / "private",
        closure_resolver=_Resolver(),
        publication_fence=fence,
    )
    _install_child_job_owner(
        custody._ledger.store_identity, control, token=_JOB_OWNER_BOOTSTRAP_TOKEN
    )
    intent = custody.job_session_intent(binding)
    custody.bind_job_intent(intent, fence.begin_session(intent))
    parent_store = custody.parent_store(binding, input_refs=())
    parent_view = _StagedParentRun(root, custody, parent_store)
    parent_view.emit("test.child", "PARENT_STAGED_EVENT")
    assert root.trace_path is not None
    assert "PARENT_STAGED_EVENT" not in root.trace_path.read_text()
    parent_context = ExecutionContext(
        store=served, run=root, logger=logging.getLogger("child-test")
    )
    producer = _Producer()
    if probe in {
        "child_cache",
        "producer_stale",
        "producer_expired_during_decision",
        "producer_revoke_first",
        "producer_admit_first",
    }:
        from polisyos.scientist.orchestration.engine.child_computation import _AdmittedChildDispatch
        from polisyos.scientist.orchestration.engine.component_identity import (
            _capture_configured_component_owner,
        )
        from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
        from polisyos.scientist.orchestration.engine.idempotency import (
            NodeResultCache,
            compute_idempotency_key,
        )
        from polisyos.scientist.orchestration.engine.state_branching import branch_state

        prepared = custody.prepare_scope(
            binding.model_copy(update={"child_invocation_id": "cache-child"}), input_refs=()
        )
        child = fence.admit_prepared_scope(prepared)
        state = ExperimentState(run_id=child.run.run_manifest.run_id, params={"candidate": "fresh"})
        if probe in {"producer_revoke_first", "producer_admit_first"}:

            class EntryProbe:
                entries = 0

                @property
                def spec(self) -> NodeSpec:
                    return _SPEC

                def execute(self, _ctx: ExecutionContext, value: ExperimentState) -> NodeOutcome:
                    self.entries += 1
                    return NodeOutcome(status="ok", state=value)

            node = EntryProbe()
            dispatch = _AdmittedChildDispatch(
                _capture_configured_component_owner(node, {}), {}, grant, fence=fence
            )
            child_ctx = ExecutionContext(
                store=child.store,
                run=child.run,
                depth=1,
                logger=logging.getLogger("child-entry-test"),
            )
            original_decision = fence.admit_producer
            try:
                if probe == "producer_revoke_first":
                    with grant._attempt.transition_lock:
                        grant._attempt.revoked = True
                    with pytest.raises(
                        RuntimeError, match="borrowed_execution_admission_not_current"
                    ):
                        dispatch.execute(child_ctx, state)
                    assert node.entries == 0
                else:

                    def revoke_after_decision() -> None:
                        original_decision()
                        with grant._attempt.transition_lock:
                            grant._attempt.revoked = True

                    with monkeypatch.context() as patch:
                        patch.setattr(fence, "admit_producer", revoke_after_decision)
                        assert dispatch.execute(child_ctx, state).status == "ok"
                    # A completed decision may precede a later signal; it is not quiescence.
                    assert node.entries == 1
            finally:
                with grant._attempt.transition_lock:
                    grant._attempt.revoked = False
            return
        if probe in {"producer_stale", "producer_expired_during_decision"}:
            from polisyos.runtime.http.services.control_plane_store import (
                ControlJobLeaseLostError,
                ControlPlaneStore,
            )

            child_ctx = ExecutionContext(
                store=child.store,
                run=child.run,
                depth=1,
                logger=logging.getLogger("child-stale-test"),
            )
            dispatch = _AdmittedChildDispatch(
                _capture_configured_component_owner(producer, {}), {}, grant, fence=fence
            )
            custody.check_active(child)
            before = len(producer.hidden_refs)
            if probe == "producer_stale":
                fresh_owner = ControlPlaneStore(
                    backend="sqlite", sqlite_path=tmp_path / "control.sqlite3"
                )
                with fresh_owner._job_transaction():
                    fresh_owner._execute(
                        "UPDATE control_jobs SET lease_owner = ? WHERE job_id = ?",
                        ("replacement-worker", "job-a"),
                    )
                with pytest.raises(ControlJobLeaseLostError):
                    dispatch.execute(child_ctx, state)
            else:
                install = fence._install_scope_resource_predicate

                def expire_then_install() -> None:
                    control._execute(
                        "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                        ("2000-01-01T00:00:00+00:00", "job-a"),
                    )
                    install()

                with monkeypatch.context() as patch:
                    patch.setattr(fence, "_install_scope_resource_predicate", expire_then_install)
                    with pytest.raises(
                        ControlJobLeaseLostError, match="child_producer_admission_refused"
                    ):
                        dispatch.execute(child_ctx, state)
            assert len(producer.hidden_refs) == before
            return
        stale_value = child.store.put_bytes(
            b"stale",
            PutOptions(kind="tests.child.value", media_type="application/octet-stream"),
            return_selected_profile=True,
        )
        stale_projection = child.store.put_json(
            _Projection(selected=(stale_value,)).model_dump(mode="json"),
            PutOptions(
                kind="tests.child.projection",
                media_type="application/json",
                schema=SchemaInfo(name="tests.ChildProjection", version="1"),
            ),
            return_selected_profile=True,
        )
        cached_state = branch_state(state, write_paths=("artifacts_index.projection",)).state
        cached_state.artifacts_index["projection"] = stale_projection
        cache_key = compute_idempotency_key(producer.spec, state, {})
        tenant_context = child.run.artifact_tenant_context()
        cache_ref = NodeResultCache(
            child.store, run_id=state.run_id, tenant_context=tenant_context
        ).put(
            cache_key,
            node_id=str(_COMPONENT),
            outcome=NodeOutcome(status="ok", state=cached_state, artifacts=[stale_projection]),
        )
        oracle_cache = NodeResultCache(
            child.store, run_id=state.run_id, tenant_context=tenant_context
        )
        assert oracle_cache.seed_from_entry_refs([cache_ref]) == 1
        cached = oracle_cache.get(cache_key)
        assert cached is not None and cached.state.artifacts_index["projection"] == stale_projection
        registry = NodeRegistry()
        registry.register(
            _AdmittedChildDispatch(
                _capture_configured_component_owner(producer, {}), {}, grant, fence=fence
            )
        )
        child_ctx = ExecutionContext(
            store=child.store, run=child.run, depth=1, logger=logging.getLogger("child-cache-test")
        )
        result = WorkflowExecutor(
            child_ctx,
            registry,
            checkpoint_cache_seed_refs=[cache_ref],
            _admitted_child=True,
        ).execute(workflow, state)
        selected = result.state.artifacts_index["projection"]
        assert selected != stale_projection
        projection = _Projection.model_validate_json(child.store.get_bytes(selected))
        assert child.store.get_bytes(projection.selected[0]) == b"fresh"
        return
    session = _ManagedChildRunner(
        custody=custody,
        parent_seal=parent_seal,
        config=config,
        bootstrap_members={str(_COMPONENT): _MemberAtBootstrap.capture(producer, _Producer)},
        allowed_inputs=(),
        parent_context=parent_context,
        approved_ports=_ApprovedChildPorts(),
        inherited_budgets={},
        monotonic_deadline=grant.deadline_monotonic,
        projection_key="projection",
    )
    with pytest.raises(ValueError, match="child_runtime_control_origin_not_established"):
        session.stage_b_session()
    assert not _Producer.hidden_refs
    with pytest.raises(ValueError, match="child_effect_port_owner_not_established"):
        _ManagedChildRunner(
            custody=custody,
            parent_seal=parent_seal,
            config=config,
            bootstrap_members={str(_COMPONENT): _MemberAtBootstrap.capture(producer, _Producer)},
            allowed_inputs=(),
            parent_context=parent_context,
            approved_ports=_ApprovedChildPorts(foundry=object()),
            inherited_budgets={},
            monotonic_deadline=grant.deadline_monotonic,
            projection_key="projection",
        )
    node = SubWorkflowNode(config, NodeRegistry())
    if probe in {"revocation_unknown", "preserve_unknown"}:
        from polisyos.core.run.child_custody import (
            ChildComputationOutcomeUnknown,
            ChildRevocationUnknown,
        )

        def fail_revoke(*_args: object, **_kwargs: object) -> None:
            raise OSError("revoke-ack-lost")

        with monkeypatch.context() as patch:
            patch.setattr(custody, "revoke", fail_revoke)
            candidate = (
                "force-child-unknown" if probe == "preserve_unknown" else "force-child-failure"
            )
            with pytest.raises(ChildComputationOutcomeUnknown) as observed:
                node.execute_admitted(
                    ExperimentState(run_id="root", params={"candidate": candidate}),
                    session=session,
                )
        if probe == "preserve_unknown":
            assert observed.value is _Producer.last_unknown, repr(observed.value.__cause__)
        else:
            assert isinstance(observed.value, ChildRevocationUnknown)
            assert observed.value.recovery is not None
            assert observed.value.recovery.job_intent_locator is not None
            assert isinstance(observed.value.__cause__, ValueError)
        assert any("OSError" in note for note in observed.value.__notes__)
        return
    invalid = ExperimentState(run_id="root")
    invalid.params["candidate"] = float("nan")
    with pytest.raises(ValueError, match="child_input_nonfinite"):
        node.execute_admitted(invalid, session=session)
    assert not _Producer.hidden_refs
    lost = Event()
    lost.set()
    with (
        job_execution_interrupt_scope(JobExecutionInterrupt("job", "worker", 1, lost)),
        pytest.raises(JobExecutionInterrupted),
    ):
        node.execute_admitted(
            ExperimentState(run_id="root", params={"candidate": "cancelled"}), session=session
        )
    assert not _Producer.hidden_refs
    changed_config = config.model_copy(deep=True)
    changed_config.input_mappings[0].source_path = "params.other"
    changed_node = SubWorkflowNode(changed_config, NodeRegistry())
    with pytest.raises(ValueError, match="child_subworkflow_configuration_changed"):
        changed_node.execute_admitted(
            ExperimentState(run_id="root", params={"other": "changed"}), session=session
        )
    assert not _Producer.hidden_refs
    with monkeypatch.context() as patch:
        patch.setattr(_Producer, "execute", lambda *_args: None)
        with pytest.raises(ValueError, match="child_bootstrap_implementation_changed"):
            node.execute_admitted(
                ExperimentState(run_id="root", params={"candidate": "changed"}), session=session
            )
    assert not _Producer.hidden_refs
    first = node.execute_admitted(
        ExperimentState(run_id="root", params={"candidate": "one"}), session=session
    )
    second = node.execute_admitted(
        ExperimentState(run_id="root", params={"candidate": "two"}), session=session
    )
    assert first.scope_id != second.scope_id
    first_payload = _Projection.model_validate_json(first.store.get_bytes(first.projection_ref))
    second_payload = _Projection.model_validate_json(second.store.get_bytes(second.projection_ref))
    assert first.store.get_bytes(first_payload.selected[0]) == b"one"
    assert second.store.get_bytes(second_payload.selected[0]) == b"two"
    final = parent_store.put_json(
        _Projection(selected=(first.projection_ref, second.projection_ref)).model_dump(mode="json"),
        PutOptions(
            kind="tests.child.projection",
            media_type="application/json",
            schema=SchemaInfo(name="tests.ChildProjection", version="1"),
        ),
        return_selected_profile=True,
    )
    with pytest.raises((FileNotFoundError, ChildReleaseUnavailableError)):
        served.get_bytes(first.projection_ref)
    receipt = custody.release_parent((first, second), final)
    assert receipt.projection_ref == final
    assert "PARENT_STAGED_EVENT" in root.trace_path.read_text()
    assert served.get_bytes(first_payload.selected[0]) == b"one"
    assert served.get_bytes(second_payload.selected[0]) == b"two"
    assert len(_Producer.hidden_refs) == 2
    for hidden in _Producer.hidden_refs:
        with pytest.raises((FileNotFoundError, ChildReleaseUnavailableError)):
            served.get_bytes(hidden)


def test_held_parent_dispatch_reconciles_real_pending_attempt(tmp_path: Path) -> None:
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from tests.unit.runtime.http.test_child_control_authorization import _job

    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    attempt = _job(control, run_id="root", kind="workflow_run")
    guard = BlockingDependencyGuard(
        dependency_name="test-parent",
        timeout_seconds=120,
        breaker=CircuitBreaker("test-parent"),
        executor=get_shared_executor(),
    )
    try:
        with control.job_execution_fence(job_id="job-a", worker_id="worker-a", attempt=attempt):
            guard.run_with_parent_admission(
                lambda grant: _held_parent(tmp_path, grant),
                deadline_monotonic=time.monotonic() + 120,
            )
    finally:
        guard.close()


def test_dynamic_stage_b_candidate_uses_real_guarded_private_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The selected input is copied only into a Core-appointed private child."""
    import polisyos.common.async_tools as async_tools
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.runtime.http.resilience import (
        _bootstrap_guarded_child_control_fence,
        _bootstrap_guarded_child_custody,
        guard_runtime_cas,
        guard_runtime_control_store,
    )
    from polisyos.runtime.http.services.control.child_execution_budget import (
        ChildExecutionBudgetPolicy,
        _require_attempt_budget,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.http.services.control_worker import ControlWorker
    from polisyos.scientist.nodes.builtins.planning.child_stage_b import (
        StageBPrepareNode,
        stage_b_child_template,
    )
    from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
        RunHierarchicalPolicySearchNode,
    )
    from polisyos.scientist.orchestration.engine.child_output_closure import (
        TypedChildOutputClosureResolver,
    )
    from polisyos.scientist.orchestration.engine.component_identity import (
        capture_engine_component_identity,
    )
    from polisyos.scientist.policy_design.schema import (
        PolicyCandidateSchema,
        TargetPopulationSpec,
        load_policy_candidate_schema,
    )
    from tests.unit.runtime.http.test_child_control_authorization import _job

    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    attempt = _job(control, kind="workflow_run")
    job = control.get_job("job-a")
    assert job is not None
    guarded_control = guard_runtime_control_store(control)
    served = FileSystemCAS(tmp_path / "served", ownership_enforced=False)
    guarded_cas = guard_runtime_cas(served)
    shared = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", shared)
    guard = BlockingDependencyGuard(
        dependency_name="stage-b-parent",
        timeout_seconds=90,
        breaker=CircuitBreaker("stage-b-parent"),
        executor=shared,
    )

    def exercise(grant: _BorrowedExecutionGrant) -> None:
        registry = build_default_registry_bundle(guarded_cas, return_selected_profile=True)
        data = guarded_cas.put_json(
            {"population": 1},
            PutOptions(kind="test.data", media_type="application/json"),
            return_selected_profile=True,
        )
        candidate = PolicyCandidateSchema(
            candidate_id="dynamic_candidate",
            trinity_bundle=TrinityBundle(
                problem_frame=ProblemFrame(problem_id="problem_one", domain=ProblemDomain.SOCIAL),
                policy_spec=PolicySpec(policy_id="policy_one", interventions=[]),
                model_spec=ModelSpec(model_id="model_one", data_snapshot_ref=str(data.artifact_id)),
            ),
            target_population=TargetPopulationSpec(population_id="all", description="All"),
        )
        parent_state = ExperimentState(
            run_id="run-a",
            inputs={"data_snapshot_ref": data},
            params={"kept": 1},
        )
        parent_state.params["policy_candidate_schema"] = candidate.model_copy(
            update={"candidate_id": "parent_candidate"}
        )
        root = RunContext.start(
            guarded_cas,
            registry.bundle_ref,
            run_id="run-a",
            run_dir=served.root / "runs" / "run-a",
            tenant_id="tenant-a",
            cell_id="cell-a",
            control_job_id="job-a",
        )
        config, members = stage_b_child_template()
        projection_key = "child_stage_b_projection_ref"
        template = _finite_json(
            {"sub_workflow": config.model_dump(mode="json"), "projection_key": projection_key}
        )
        parent = RunHierarchicalPolicySearchNode()
        parent_id = str(parent.spec.metadata.component_id)
        workflow_ref, state_ref, parent_state = _parent_inputs(
            guarded_cas, parent.spec.metadata.component_id, state=parent_state
        )
        identity = capture_engine_component_identity(parent, parent_id, {})
        assert identity is not None
        attempt_id = str(uuid4())
        basis = root._record_runtime_invocation_started(
            attempt_id=attempt_id,
            attempt_number=1,
            workflow_spec_ref=workflow_ref,
            node_alias="parent",
            component_id=parent_id,
            input_state_ref=state_ref,
            implementation_identity=identity,
        )
        binding = ChildComputationBinding(
            root_run_id="run-a",
            control_job_id="job-a",
            parent_attempt_id=attempt_id,
            parent_basis_ref=basis,
            tenant_id="tenant-a",
            cell_id="cell-a",
            policy_id="fixture-stage-b",
            policy_version="1",
            template_sha256="sha256:" + hashlib.sha256(template).hexdigest(),
            admission_id=attempt_id,
            child_invocation_id="parent",
            admission_generation=attempt,
            deadline=datetime.now(UTC) + timedelta(seconds=60),
        )
        seal = _hold_admitted_parent_dispatch(
            root, binding, parent, parent, {}, grant, parent_state
        )
        fence = _bootstrap_guarded_child_control_fence(root, guarded_control, grant, binding)
        resolver = TypedChildOutputClosureResolver(
            limits=CoreJsonReadLimits(
                max_bytes=4_000_000,
                max_depth=50,
                max_elements=100_000,
                max_manifest_bytes=1_000_000,
            )
        )
        custody, reader = _bootstrap_guarded_child_custody(
            root,
            staging_root=tmp_path / "private",
            closure_resolver=resolver,
            publication_fence=fence,
        )
        try:
            intent = custody.job_session_intent(binding)
            custody.bind_job_intent(intent, fence.begin_session(intent))
            parent_store = custody.parent_store(binding, input_refs=(data,))
            parent_context = ExecutionContext(
                store=parent_store,
                run=_StagedParentRun(root, custody, parent_store),
                logger=logging.getLogger("stage-b-test"),
            )
            observed: list[ArtifactRef] = []
            original_prepare = StageBPrepareNode.execute

            def record_prepared(self, ctx, state):
                outcome = original_prepare(self, ctx, state)
                selected = outcome.state.artifacts_index["child_stage_b_selected_candidate_ref"]
                assert load_policy_candidate_schema(ctx.store, selected) == candidate
                with pytest.raises(FileNotFoundError):
                    served.get_bytes(selected)
                observed.append(selected)
                return outcome

            monkeypatch.setattr(StageBPrepareNode, "execute", record_prepared)

            class LookalikePrepare:
                @property
                def spec(self):
                    return StageBPrepareNode().spec

                def execute(self, ctx, state):
                    pytest.fail("a same-ID sibling reached the child producer")

            def runner_for(selected_members: tuple[object, ...]) -> _ManagedChildRunner:
                return _ManagedChildRunner(
                    custody=custody,
                    parent_seal=seal,
                    config=config,
                    bootstrap_members={
                        str(node.spec.metadata.component_id): _MemberAtBootstrap.capture(
                            node, type(node)
                        )
                        for node in selected_members
                    },
                    allowed_inputs=(data,),
                    parent_context=parent_context,
                    approved_ports=_ApprovedChildPorts(),
                    inherited_budgets={},
                    monotonic_deadline=grant.deadline_monotonic,
                    projection_key=projection_key,
                )

            with pytest.raises(ValueError, match="child_stage_b_member_not_appointed"):
                runner_for((LookalikePrepare(), *members[1:])).stage_b_session()
            session = runner_for(members).stage_b_session()
            assert not hasattr(session, "_grant") and not hasattr(session, "__dict__")
            assert not hasattr(session, "_ManagedStageBSession__runner")
            foreign_errors: list[BaseException] = []

            def use_from_foreign_thread() -> None:
                try:
                    session.evaluate_candidate(candidate.model_dump(mode="json"), parent_state)
                except BaseException as exc:
                    foreign_errors.append(exc)

            foreign = Thread(target=use_from_foreign_thread)
            foreign.start()
            foreign.join(timeout=5)
            assert not foreign.is_alive()
            assert len(foreign_errors) == 1
            assert str(foreign_errors[0]) == "child_read_owner_thread_mismatch"
            changed = parent_state.model_copy(deep=True)
            changed.params["kept"] = 2
            with pytest.raises(ValueError, match="child_parent_input_state_changed"):
                session.evaluate_candidate(candidate.model_dump(mode="json"), changed)
            assert not observed
            before = parent_state.model_dump(mode="json")
            with pytest.raises(ValueError, match="child_workflow_not_successful"):
                session.evaluate_candidate(candidate.model_dump(mode="json"), parent_state)
            assert parent_state.model_dump(mode="json") == before
            assert len(observed) == 1
        finally:
            reader.close()

    def handler(_job_record: object) -> None:
        budget = _require_attempt_budget("job-a", "run-a", attempt)
        completion = guard.create_parent_completion(guarded_control, budget)
        guard.run_with_parent_admission(
            exercise, deadline_monotonic=budget.deadline_monotonic, completion=completion
        )

    worker = ControlWorker(
        store=guarded_control,
        handler=handler,
        worker_id="worker-a",
        child_execution_budget_policy=ChildExecutionBudgetPolicy("stage-b-test", "1", 90),
    )
    try:
        worker._run_with_lease_heartbeat(job)
    finally:
        guard.close()
        guarded_cas.close()
        guarded_control.close()
        shared.shutdown(wait=True)


def _held_parent(tmp_path: Path, grant: _BorrowedExecutionGrant) -> None:
    from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
        RunHierarchicalPolicySearchNode,
    )
    from polisyos.scientist.orchestration.engine.child_computation import (
        _hold_admitted_parent_dispatch,
    )
    from polisyos.scientist.orchestration.engine.component_identity import (
        capture_engine_component_identity,
    )

    store = FileSystemCAS(tmp_path / "served", ownership_enforced=False)
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    root = RunContext.start(
        store,
        registry.bundle_ref,
        run_id="root",
        tenant_id="tenant-a",
        cell_id="cell-a",
        control_job_id="job-a",
    )
    parent = RunHierarchicalPolicySearchNode()
    component_id = str(parent.spec.metadata.component_id)
    identity = capture_engine_component_identity(parent, component_id, {})
    assert identity is not None
    selected_data = store.put_bytes(
        b"same-data",
        PutOptions(
            kind="tests.data",
            media_type="application/octet-stream",
            schema=SchemaInfo(name="tests.Data", version="1"),
        ),
        return_selected_profile=True,
    )
    other_profile = store.put_bytes(
        b"same-data",
        PutOptions(
            kind="tests.data",
            media_type="application/octet-stream",
            schema=SchemaInfo(name="tests.Data", version="2"),
        ),
        return_selected_profile=True,
    )
    parent_source = ExperimentState(
        run_id="root",
        inputs={
            "data_snapshot_ref": selected_data,
            "registry_bundle_ref": registry.bundle_ref,
        },
    )
    workflow_ref, state_ref, parent_input = _parent_inputs(
        store, parent.spec.metadata.component_id, state=parent_source
    )
    attempt_id = str(uuid4())
    basis = root._record_runtime_invocation_started(
        attempt_id=attempt_id,
        attempt_number=1,
        workflow_spec_ref=workflow_ref,
        node_alias="parent",
        component_id=component_id,
        input_state_ref=state_ref,
        implementation_identity=identity,
    )
    binding = ChildComputationBinding(
        root_run_id="root",
        control_job_id="job-a",
        parent_attempt_id=attempt_id,
        parent_basis_ref=basis,
        tenant_id="tenant-a",
        cell_id="cell-a",
        policy_id="test.appointed",
        policy_version="1",
        template_sha256="sha256:" + "1" * 64,
        admission_id="test-admitted",
        child_invocation_id="parent",
        admission_generation=1,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )
    held = _hold_admitted_parent_dispatch(root, binding, parent, parent, {}, grant, parent_input)
    jobless = binding.model_copy(update={"control_job_id": None})
    with pytest.raises(ValueError, match="child_parent_job_scope_not_established"):
        _hold_admitted_parent_dispatch(root, jobless, parent, parent, {}, grant, parent_input)
    assert held.dispatch.implementation_identity() == identity
    assert selected_data.artifact_id == other_profile.artifact_id
    assert selected_data.manifest_profile_sha256 != other_profile.manifest_profile_sha256
    assert held.selections.selected_source_ref("model_primary_data_snapshot") == selected_data
    assert held.selections.selected_source_ref("model_primary_data_snapshot") != other_profile
    assert held.selections.selected_source_ref("model_primary_registry") == registry.bundle_ref
    with pytest.raises(ValueError, match="child_source_role_not_established"):
        held.selections.selected_source_ref("model_primary_calibration")
    changed_state = parent_input.model_copy(deep=True)
    changed_state.params["candidate"] = "not-the-attempt-input"
    with pytest.raises(ValueError, match="child_parent_input_state_changed"):
        _hold_admitted_parent_dispatch(root, binding, parent, parent, {}, grant, changed_state)
    with pytest.raises(ValueError, match="child_parent_selected_registration_changed"):
        _hold_admitted_parent_dispatch(
            root, binding, RunHierarchicalPolicySearchNode(), parent, {}, grant, parent_input
        )
    with pytest.raises(ValueError, match="child_parent_implementation_not_established"):
        _hold_admitted_parent_dispatch(root, binding, parent, object(), {}, grant, parent_input)
    for configured_retry, configured_timeout in ((RetryPolicy(max_retries=1), None), (None, 1.0)):
        other_workflow, other_state_ref, other_input = _parent_inputs(
            store,
            parent.spec.metadata.component_id,
            retry=configured_retry,
            timeout_s=configured_timeout,
        )
        other_id = str(uuid4())
        other_basis = root._record_runtime_invocation_started(
            attempt_id=other_id,
            attempt_number=1,
            workflow_spec_ref=other_workflow,
            node_alias="parent",
            component_id=component_id,
            input_state_ref=other_state_ref,
            implementation_identity=identity,
        )
        other_binding = binding.model_copy(
            update={"parent_attempt_id": other_id, "parent_basis_ref": other_basis}
        )
        with pytest.raises(ValueError, match="child_parent_retry_or_timeout_route_unsupported"):
            _hold_admitted_parent_dispatch(
                root, other_binding, parent, parent, {}, grant, other_input
            )
        root._record_runtime_invocation_completed(
            attempt_id=other_id,
            attempt_number=1,
            basis_ref=other_basis,
            status="unknown",
            outcome_state_ref=None,
            output_refs=[],
        )
    root._record_runtime_invocation_completed(
        attempt_id=attempt_id,
        attempt_number=1,
        basis_ref=basis,
        status="ok",
        outcome_state_ref=state_ref,
        output_refs=[],
    )
    with pytest.raises(ValueError, match="child_parent_attempt_not_current"):
        _hold_admitted_parent_dispatch(root, binding, parent, parent, {}, grant, parent_input)
