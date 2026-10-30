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
    _parent_inputs,
    _Resolver,
)

if TYPE_CHECKING:
    from pathlib import Path


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
