"""Real Foundry operations through an actual private child CAS owner."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from polisyos.common.async_tools import get_shared_executor
from polisyos.core.artifacts.child_release import (
    _JOB_OWNER_BOOTSTRAP_TOKEN,
    ChildReleaseUnavailableError,
    _install_child_job_owner,
)
from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
from polisyos.core.artifacts.manifest import ArtifactRef, ArtifactTenantContextInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import CompileRequest, ExecuteRequest
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.child_custody import (
    ChildComputationBinding,
    ChildComputationCustody,
    ChildGuardedStageWriteUnknown,
)
from polisyos.core.run.context import RunContext
from polisyos.core.security import SecuritySettings
from polisyos.fabric.connectors.resilience.circuit_breaker import CircuitBreaker
from polisyos.foundry._internal.quickstart import prepare_trivial_input_bindings
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.canon import CanonViolation
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact
from polisyos.runtime.http.resilience import BlockingDependencyGuard
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.nodes.builtins.planning.child_stage_b import StageBPrepareNode
from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
    RunHierarchicalPolicySearchNode,
)
from polisyos.scientist.orchestration.engine.child_computation import _hold_admitted_parent_dispatch
from polisyos.scientist.orchestration.engine.child_foundry import (
    _CHILD_FOUNDRY_DISPATCH_TOKEN,
    _ScopedChildFoundryPort,
)
from polisyos.scientist.orchestration.engine.component_identity import (
    capture_engine_component_identity,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from tests.unit.runtime.http.test_child_control_authorization import _job
from tests.unit.scientist.orchestration.engine.test_admitted_subworkflow_custody import (
    _SPEC,
    _parent_inputs,
    _Resolver,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("operation", ["compile", "execute"])
def test_same_component_id_cannot_appoint_a_foreign_foundry_producer(
    tmp_path: Path, operation: str
) -> None:
    """A sibling cannot acquire the builtin's Foundry scope by copying its ID."""
    from types import SimpleNamespace

    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.contracts.foundry import ExecPlanRef, FoundryInputBindingsRef
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
    from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode
    from polisyos.scientist.orchestration.engine.child_computation import _AdmittedChildDispatch
    from polisyos.scientist.orchestration.engine.component_identity import (
        _capture_configured_component_owner,
    )
    from tests.unit.scientist.orchestration.engine.test_child_foundry import _Fence, _LocalFoundry

    store = FileSystemCAS(tmp_path / "cas")
    policy = store.put_json(
        {"policy": 1},
        PutOptions(kind="ir.trinity_bundle", media_type="application/json"),
        return_selected_profile=True,
    )
    guard = BlockingDependencyGuard(
        dependency_name="child-foundry-alias-test",
        timeout_seconds=30,
        breaker=CircuitBreaker("child-foundry-alias-test"),
        executor=get_shared_executor(),
    )

    class AliasProducer:
        @property
        def spec(self):
            node = CompileFoundryNode() if operation == "compile" else RunSimulationNode()
            return node.spec

        def execute(self, ctx, state):
            del state
            if operation == "compile":
                return ctx.foundry.compile(
                    ctx.store, CompileRequest(input_kind="trinity", policy_ref=policy)
                )
            return ctx.foundry.execute(
                ctx.store,
                ExecuteRequest(
                    exec_plan_ref=ExecPlanRef(artifact_id=policy.artifact_id),
                    input_bindings_ref=FoundryInputBindingsRef(artifact_id=policy.artifact_id),
                ),
            )

    def exercise(grant):
        port = _ScopedChildFoundryPort(
            delegate=_LocalFoundry(),
            store=store,
            grant=grant,
            fence=_Fence(),
            reconcile_owner=lambda: None,
        )
        node = AliasProducer()
        dispatch = _AdmittedChildDispatch(
            _capture_configured_component_owner(node, {}), {}, grant, fence=_Fence()
        )
        with pytest.raises(ValueError, match="child_foundry_builtin_owner_not_established"):
            dispatch.execute(
                SimpleNamespace(store=store, foundry=port), ExperimentState(run_id="r")
            )

    try:
        guard.run_with_parent_admission(exercise, deadline_monotonic=time.monotonic() + 30)
    finally:
        guard.close()


def test_canonical_held_compiler_reaches_its_scoped_foundry_port(tmp_path: Path) -> None:
    """The genuine held builtin can still use the selected store through its port."""
    from types import SimpleNamespace

    from polisyos.core.artifacts.store import PutOptions
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
    from polisyos.scientist.orchestration.engine.child_computation import _AdmittedChildDispatch
    from polisyos.scientist.orchestration.engine.component_identity import (
        _capture_configured_component_owner,
    )
    from tests.unit.scientist.orchestration.engine.test_child_foundry import _Fence, _LocalFoundry

    store = FileSystemCAS(tmp_path / "cas")
    policy = store.put_json(
        {"policy": 1},
        PutOptions(kind="ir.trinity_bundle", media_type="application/json"),
        return_selected_profile=True,
    )
    guard = BlockingDependencyGuard(
        dependency_name="child-foundry-builtin-test",
        timeout_seconds=30,
        breaker=CircuitBreaker("child-foundry-builtin-test"),
        executor=get_shared_executor(),
    )

    def exercise(grant):
        port = _ScopedChildFoundryPort(
            delegate=_LocalFoundry(),
            store=store,
            grant=grant,
            fence=_Fence(),
            reconcile_owner=lambda: None,
        )
        node = CompileFoundryNode()
        dispatch = _AdmittedChildDispatch(
            _capture_configured_component_owner(node, {}), {}, grant, fence=_Fence()
        )
        outcome = dispatch.execute(
            SimpleNamespace(store=store, foundry=port),
            ExperimentState(run_id="r", inputs={"trinity_bundle_ref": policy}),
        )
        assert outcome.status == "ok"
        assert store.get_bytes(outcome.artifacts[0])

    try:
        guard.run_with_parent_admission(exercise, deadline_monotonic=time.monotonic() + 30)
    finally:
        guard.close()


def test_held_compiler_refuses_an_unappointed_foundry_port_before_work(tmp_path: Path) -> None:
    """A raw Foundry port cannot escape the child's operation-scoped boundary."""
    from contextlib import contextmanager
    from types import SimpleNamespace

    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.contracts.foundry import CompileResult
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
    from polisyos.scientist.orchestration.engine.child_computation import _AdmittedChildDispatch
    from polisyos.scientist.orchestration.engine.component_identity import (
        _capture_configured_component_owner,
    )
    from tests.unit.scientist.orchestration.engine.test_child_foundry import _Fence

    store = FileSystemCAS(tmp_path / "cas")
    policy = store.put_json(
        {"policy": 1},
        PutOptions(kind="ir.trinity_bundle", media_type="application/json"),
        return_selected_profile=True,
    )
    calls: list[str] = []

    class RawFoundry:
        @contextmanager
        def _producer_scope(self, *_args, **_kwargs):
            yield

        def compile(self, destination, request):
            del request
            calls.append("compile")
            ref = destination.put_json(
                {"report": "unscoped"},
                PutOptions(kind="test.child_compile_report", media_type="application/json"),
                return_selected_profile=True,
            )
            return CompileResult(ok=True, compile_report_ref=ref)

    guard = BlockingDependencyGuard(
        dependency_name="child-foundry-unappointed-test",
        timeout_seconds=30,
        breaker=CircuitBreaker("child-foundry-unappointed-test"),
        executor=get_shared_executor(),
    )

    def exercise(grant):
        node = CompileFoundryNode()
        dispatch = _AdmittedChildDispatch(
            _capture_configured_component_owner(node, {}), {}, grant, fence=_Fence()
        )
        with pytest.raises(ValueError, match="child_foundry_port_not_appointed"):
            dispatch.execute(
                SimpleNamespace(store=store, foundry=RawFoundry()),
                ExperimentState(run_id="r", inputs={"trinity_bundle_ref": policy}),
            )
        assert not calls

    try:
        guard.run_with_parent_admission(exercise, deadline_monotonic=time.monotonic() + 30)
    finally:
        guard.close()


def test_real_foundry_uses_private_selected_store_and_does_not_publish(tmp_path: Path) -> None:
    """Compile and simulate on real Core custody; a fresh served reader stays denied."""
    import logging

    served = FileSystemCAS(tmp_path / "served", ownership_enforced=False)
    registry = build_default_registry_bundle(served, return_selected_profile=True)
    input_ref = prepare_trivial_input_bindings(served, registry.bundle_ref)
    data_ref = load_input_bindings(served, input_ref).data_snapshot_ref
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_one", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_one",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id", operator=SelectorOperator.EQUALS, value="all"
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_one",
            data_snapshot_ref=str(data_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    candidate = PolicyCandidateSchema.from_trinity_bundle(bundle, candidate_id="candidate_one")
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    attempt = _job(control, run_id="root", kind="workflow_run")
    root = RunContext.start(
        served,
        registry.bundle_ref,
        run_id="root",
        run_dir=served.root / "runs" / "root",
        tenant_id="tenant-a",
        cell_id="cell-a",
        control_job_id="job-a",
    )
    parent = RunHierarchicalPolicySearchNode()
    workflow_ref, state_ref, parent_state = _parent_inputs(
        served, parent.spec.metadata.component_id
    )
    identity = capture_engine_component_identity(parent, str(parent.spec.metadata.component_id), {})
    assert identity is not None
    attempt_id = str(uuid4())
    basis = root._record_runtime_invocation_started(
        attempt_id=attempt_id,
        attempt_number=1,
        workflow_spec_ref=workflow_ref,
        node_alias="parent",
        component_id=str(parent.spec.metadata.component_id),
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
        template_sha256="sha256:" + "0" * 64,
        admission_id="test-admitted",
        child_invocation_id="child-one",
        admission_generation=1,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )
    inventory = served.inventory_snapshot()
    assert inventory.verdict == "pass"
    allowed = tuple(
        entry.artifact_ref
        for entry in inventory.entries
        if isinstance(entry.artifact_ref, ArtifactRef)
    )
    guard = BlockingDependencyGuard(
        dependency_name="managed-foundry-test",
        timeout_seconds=90,
        breaker=CircuitBreaker("managed-foundry-test"),
        executor=get_shared_executor(),
    )

    def exercise(grant):
        _hold_admitted_parent_dispatch(root, binding, parent, parent, {}, grant, parent_state)
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
        scope = fence.admit_prepared_scope(custody.prepare_scope(binding, input_refs=allowed))
        port = _ScopedChildFoundryPort(
            delegate=DefaultFoundryPort(settings=SecuritySettings()),
            store=scope.store,
            grant=grant,
            fence=fence,
            reconcile_owner=lambda: None,
        )
        context = ExecutionContext(
            store=scope.store,
            run=scope.run,
            depth=1,
            logger=logging.getLogger("test.managed-foundry"),
            foundry=port,
        )
        child_state = ExperimentState(
            run_id=scope.run.run_manifest.run_id,
            params={"child_stage_b_candidate": candidate.model_dump(mode="json")},
            inputs={
                "data_snapshot_ref": data_ref,
                "registry_bundle_ref": registry.bundle_ref,
                "input_bindings_ref": input_ref,
            },
        )
        prepared = StageBPrepareNode().execute(context, child_state)
        selected_trinity = prepared.state.inputs["trinity_bundle_ref"]
        # State branching wraps refs in journaled subclasses. The owner must
        # still reconcile all four selected fields against its own scope.
        assert scope.store.get_bytes(selected_trinity)

        from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
        from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode
        from polisyos.scientist.orchestration.engine.child_computation import _AdmittedChildDispatch
        from polisyos.scientist.orchestration.engine.component_identity import (
            _capture_configured_component_owner,
        )

        compiler = CompileFoundryNode()
        dispatch = _AdmittedChildDispatch(
            _capture_configured_component_owner(compiler, {}), {}, grant, fence=fence
        )
        compiled_node = dispatch.execute(context, prepared.state)
        assert compiled_node.status == "ok", compiled_node.error
        assert compiled_node.state.artifacts_index["exec_plan_ref"].manifest_profile_sha256
        simulator = RunSimulationNode()
        simulation_dispatch = _AdmittedChildDispatch(
            _capture_configured_component_owner(simulator, {}), {}, grant, fence=fence
        )
        simulated_node = simulation_dispatch.execute(context, compiled_node.state)
        assert simulated_node.status == "ok", simulated_node.error
        assert simulated_node.state.artifacts_index["simulation_result_ref"].manifest_profile_sha256

        class SiblingProducer:
            @property
            def spec(self):
                return _SPEC

            def execute(self, ctx, _state):
                return ctx.foundry.compile(
                    ctx.store,
                    CompileRequest(
                        input_kind="trinity",
                        policy_ref=selected_trinity,
                        registry_bundle_ref=registry.bundle_ref,
                    ),
                )

        sibling = SiblingProducer()
        sibling_dispatch = _AdmittedChildDispatch(
            _capture_configured_component_owner(sibling, {}), {}, grant, fence=fence
        )
        with pytest.raises(ValueError, match="child_foundry_operation_not_admitted"):
            sibling_dispatch.execute(context, prepared.state)

        class ForgedRef(ArtifactRef):
            def model_dump(self, **_kwargs: object):
                return selected_trinity.model_dump()

        forged = ForgedRef(
            artifact_id=selected_trinity.artifact_id,
            kind="ir.foreign",
            media_type=selected_trinity.media_type,
            manifest_profile_sha256=selected_trinity.manifest_profile_sha256,
        )
        with pytest.raises(ChildReleaseUnavailableError, match="private_exact_read_basis_denied"):
            scope.store.get_bytes(forged)
        with pytest.raises(ChildReleaseUnavailableError, match="exact_selected_reference_required"):
            scope.store.get_bytes(
                selected_trinity.model_copy(update={"manifest_profile_sha256": None})
            )

        class ForgedManagedStore:
            """A wrapper exposes owner-looking methods but cannot appoint itself."""

            def __getattr__(self, name: str):
                return getattr(scope.store, name)

        with pytest.raises(CanonViolation, match="ir_owned_artifact_write_refused") as refused:
            persist_trinity_bundle_artifact(
                CoreToIRArtifactStoreAdapter(ForgedManagedStore()),
                bundle,
                tenant_context=ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a"),
            )
        assert str(refused.value.__cause__) == "artifact_write_selected_manifest_options_mismatch"

        with port._producer_scope(
            "scientist.node_compile_foundry@1.0.0", _token=_CHILD_FOUNDRY_DISPATCH_TOKEN
        ):
            compiled = port.compile(
                scope.store,
                CompileRequest(
                    input_kind="trinity",
                    policy_ref=prepared.state.inputs["trinity_bundle_ref"],
                    registry_bundle_ref=registry.bundle_ref,
                ),
            )
        assert compiled.ok and compiled.exec_plan_ref is not None
        unknown = ChildGuardedStageWriteUnknown(
            release_id="release-one",
            root_run_id="root",
            parent_attempt_id=attempt_id,
            parent_basis_json=b"{}",
            job_intent_locator=None,
        )

        def fail_with_unknown(*_args, **_kwargs):
            raise unknown

        # Foundry normally converts ordinary errors to result envelopes. A
        # child owner cannot treat an unresolved entered effect as a failure.
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(type(scope.store), "get_raw_manifest_bytes", fail_with_unknown)
            with port._producer_scope(
                "scientist.node_compile_foundry@1.0.0", _token=_CHILD_FOUNDRY_DISPATCH_TOKEN
            ):
                with pytest.raises(ChildGuardedStageWriteUnknown) as caught:
                    port.compile(
                        scope.store,
                        CompileRequest(
                            input_kind="trinity",
                            policy_ref=selected_trinity,
                            registry_bundle_ref=registry.bundle_ref,
                        ),
                    )
            assert caught.value is unknown
        with port._producer_scope(
            "scientist.node_run_simulation@1.0.1", _token=_CHILD_FOUNDRY_DISPATCH_TOKEN
        ):
            result = port.execute(
                scope.store,
                ExecuteRequest(
                    exec_plan_ref=compiled.exec_plan_ref,
                    input_bindings_ref=input_ref,
                    registry_bundle_ref=registry.bundle_ref,
                ),
            )
        assert result.ok and result.simulation_result_ref is not None
        assert result.simulation_result_ref.manifest_profile_sha256 is not None
        assert scope.store.get_bytes(result.simulation_result_ref)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(type(scope.store), "get_raw_manifest_bytes", fail_with_unknown)
            with port._producer_scope(
                "scientist.node_run_simulation@1.0.1", _token=_CHILD_FOUNDRY_DISPATCH_TOKEN
            ):
                with pytest.raises(ChildGuardedStageWriteUnknown) as caught:
                    port.execute(
                        scope.store,
                        ExecuteRequest(
                            exec_plan_ref=compiled.exec_plan_ref,
                            input_bindings_ref=input_ref,
                            registry_bundle_ref=registry.bundle_ref,
                        ),
                    )
            assert caught.value is unknown
        with pytest.raises((ChildReleaseUnavailableError, FileNotFoundError)):
            FileSystemCAS(served.root, ownership_enforced=False).get_bytes(
                result.simulation_result_ref
            )
        scope.run.finalize(status="ok")
        custody.revoke(scope, reason="test-complete")

    try:
        with control.job_execution_fence(job_id="job-a", worker_id="worker-a", attempt=attempt):
            guard.run_with_parent_admission(exercise, deadline_monotonic=time.monotonic() + 90)
    finally:
        guard.close()
