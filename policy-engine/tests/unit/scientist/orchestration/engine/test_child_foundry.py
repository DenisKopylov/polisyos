"""Foundry operations must remain bound to the admitted producer and store."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import pytest

from polisyos.common.async_tools import get_shared_executor
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    CompileRequest,
    CompileResult,
    ExecPlanRef,
    ExecuteRequest,
    ExecuteResult,
    FoundryInputBindingsRef,
)
from polisyos.fabric.connectors.resilience.circuit_breaker import CircuitBreaker
from polisyos.runtime.http.resilience import BlockingDependencyGuard
from polisyos.scientist.orchestration.engine.child_foundry import (
    _CHILD_FOUNDRY_DISPATCH_TOKEN,
    _ScopedChildFoundryPort,
)

if TYPE_CHECKING:
    from pathlib import Path


class _LocalFoundry:
    """A finite local delegate whose real CAS write exposes admitted dispatch."""

    def compile(self, store, request):
        assert request.return_selected_profile is True
        ref = store.put_json(
            {"operation": "compile", "policy": str(request.policy_ref.artifact_id)},
            PutOptions(kind="test.child_compile_report", media_type="application/json"),
            return_selected_profile=True,
        )
        return CompileResult(ok=True, compile_report_ref=ref)

    def execute(self, store, request):
        del store
        assert request.return_selected_profile is True
        return ExecuteResult(ok=True)


class _Fence:
    def admit_producer(self):
        return None


def test_only_the_admitted_foundry_operation_can_reach_its_bound_store(tmp_path: Path) -> None:
    """Removing operation or store checks lets a sibling producer write an artifact."""
    store = FileSystemCAS(tmp_path / "selected")
    other = FileSystemCAS(tmp_path / "other")
    policy = store.put_json(
        {"policy": 1},
        PutOptions(kind="ir.trinity_bundle", media_type="application/json"),
        return_selected_profile=True,
    )
    compile_request = CompileRequest(policy_ref=policy, input_kind="trinity")
    execute_request = ExecuteRequest(
        exec_plan_ref=ExecPlanRef(artifact_id=policy.artifact_id),
        input_bindings_ref=FoundryInputBindingsRef(artifact_id=policy.artifact_id),
    )
    guard = BlockingDependencyGuard(
        dependency_name="child-foundry-test",
        timeout_seconds=30,
        breaker=CircuitBreaker("child-foundry-test"),
        executor=get_shared_executor(),
    )

    def exercise(grant):
        delegate = _LocalFoundry()
        port = _ScopedChildFoundryPort(
            delegate=delegate,
            store=store,
            grant=grant,
            fence=_Fence(),
            reconcile_owner=lambda: None,
        )
        with pytest.raises(ValueError, match="child_foundry_operation_not_admitted"):
            port.compile(store, compile_request)
        with port._producer_scope(
            "scientist.node_compile_foundry@1.0.0", _token=_CHILD_FOUNDRY_DISPATCH_TOKEN
        ):
            report = port.compile(store, compile_request)
            assert json.loads(store.get_bytes(report.compile_report_ref))["operation"] == "compile"
            with pytest.raises(ValueError, match="child_foundry_operation_not_admitted"):
                port.execute(store, execute_request)
            with pytest.raises(ValueError, match="child_foundry_store_not_admitted"):
                port.compile(other, compile_request)
        with port._producer_scope(
            "scientist.node_run_simulation@1.0.1", _token=_CHILD_FOUNDRY_DISPATCH_TOKEN
        ):
            assert port.execute(store, execute_request).ok
        assert execute_request.return_selected_profile is False
        with pytest.raises(ValueError, match="child_foundry_operation_not_admitted"):
            port.compile(store, compile_request)

    try:
        guard.run_with_parent_admission(exercise, deadline_monotonic=time.monotonic() + 30)
    finally:
        guard.close()


def test_scoped_port_runs_the_actual_local_foundry_compile_and_simulation(tmp_path: Path) -> None:
    """The admitted operations reach the real Foundry producer and its CAS outputs."""
    from decimal import Decimal

    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef, input_ref_from_artifact_ref
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.security import SecuritySettings
    from polisyos.foundry._internal.quickstart import prepare_trivial_input_bindings
    from polisyos.foundry.data_plane.bindings import load_input_bindings
    from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import SelectorOperator
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
    from polisyos.scientist.nodes.builtins.planning.stage_b_projection import (
        persist_stage_b_candidate,
    )
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    backing_store = FileSystemCAS(tmp_path / "cas")

    class SelectedWriteView:
        """Mirror the private store's selected-occurrence write contract."""

        def __getattr__(self, name):
            return getattr(backing_store, name)

        def put_json(self, obj, opts, canon_spec=None, *, return_selected_profile=False):
            return backing_store.put_json(obj, opts, canon_spec, return_selected_profile=True)

        def put_bytes(self, data, opts, *, return_selected_profile=False):
            return backing_store.put_bytes(data, opts, return_selected_profile=True)

    store = SelectedWriteView()
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    input_ref = prepare_trivial_input_bindings(
        store, registry.bundle_ref, n_agents=2, n_firms=1, step=0
    )
    data_ref = load_input_bindings(store, input_ref).data_snapshot_ref
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_1", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_1",
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
            model_id="model_1",
            data_snapshot_ref=str(data_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    candidate = PolicyCandidateSchema.from_trinity_bundle(bundle, candidate_id="candidate_one")
    candidate_ref = persist_stage_b_candidate(
        store,
        candidate,
        {"data_snapshot_ref": data_ref, "registry_bundle_ref": registry.bundle_ref},
    )
    policy_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store),
            bundle,
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")],
        ).model_dump(mode="json")
    )
    guard = BlockingDependencyGuard(
        dependency_name="child-real-foundry-test",
        timeout_seconds=90,
        breaker=CircuitBreaker("child-real-foundry-test"),
        executor=get_shared_executor(),
    )

    def exercise(grant):
        port = _ScopedChildFoundryPort(
            delegate=DefaultFoundryPort(settings=SecuritySettings()),
            store=store,
            grant=grant,
            fence=_Fence(),
            reconcile_owner=lambda: None,
        )
        with port._producer_scope(
            "scientist.node_compile_foundry@1.0.0", _token=_CHILD_FOUNDRY_DISPATCH_TOKEN
        ):
            compiled = port.compile(
                store,
                CompileRequest(
                    input_kind="trinity",
                    policy_ref=policy_ref,
                    registry_bundle_ref=registry.bundle_ref,
                    return_selected_profile=True,
                ),
            )
        assert compiled.ok and compiled.exec_plan_ref is not None
        assert compiled.exec_plan_ref.manifest_profile_sha256 is not None
        request = ExecuteRequest(
            exec_plan_ref=compiled.exec_plan_ref,
            input_bindings_ref=input_ref,
            registry_bundle_ref=registry.bundle_ref,
        )
        with port._producer_scope(
            "scientist.node_run_simulation@1.0.1", _token=_CHILD_FOUNDRY_DISPATCH_TOKEN
        ):
            result = port.execute(store, request)
        assert result.ok and result.simulation_result_ref is not None
        assert result.simulation_result_ref.manifest_profile_sha256 is not None
        assert store.get_bytes(result.simulation_result_ref)

    try:
        guard.run_with_parent_admission(exercise, deadline_monotonic=time.monotonic() + 90)
    finally:
        guard.close()
