from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    EquilibriumMultiplicityReport,
    ExecuteRequest,
    FeedbackConfig,
    FeedbackConfigRef,
    FeedbackConvergenceCertificate,
    FeedbackSolveResult,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    ObservedRange,
    ObservedRangeBundle,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry._quickstart import prepare_trivial_feedback_config
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.foundry.welfare.bounds import (
    load_welfare_bound_report,
    persist_observed_range_bundle,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator


def test_execute_supports_feedback_fixed_point_mode(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)
    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_feedback", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_feedback",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_feedback",
            data_snapshot_ref=(
                "sha256:0000000000000000000000000000000000000000000000000000000000000000"
            ),
            registry_bundle_ref=str(bundle.bundle_ref.artifact_id),
        ),
    )
    policy_ref = store.put_json(
        policy,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=policy.schema_version),
        ),
    )
    compile_result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )
    assert compile_result.ok
    assert compile_result.exec_plan_ref is not None

    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    income = base_state.agents.income + 100.0
    base_state = base_state.replace(
        agents=base_state.agents.replace(
            income=income,
            reported_income=income,
        )
    )
    snapshot_ref = put_state_snapshot(store, state=base_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref.artifact_id)
    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    input_bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=bundle.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_snapshot_ref,
        ),
        PutOptions(kind="foundry.input_bindings", media_type="application/json"),
    )
    feedback_config_ref = prepare_trivial_feedback_config(
        store,
        exec_plan_ref=compile_result.exec_plan_ref,
    )
    observed_range_bundle_ref = persist_observed_range_bundle(
        store,
        ObservedRangeBundle(
            ranges={
                "income_tax.eti_effective": ObservedRange(lower=0.1, upper=0.3),
            }
        ),
    )

    exec_result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compile_result.exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=input_bindings_ref.artifact_id),
            registry_bundle_ref=bundle.bundle_ref,
            feedback_config_ref=FeedbackConfigRef(artifact_id=feedback_config_ref.artifact_id),
            observed_range_bundle_ref=observed_range_bundle_ref,
        ),
    )

    assert exec_result.ok is True
    assert exec_result.simulation_result_ref is not None
    assert {artifact.role for artifact in exec_result.derived_refs} >= {
        "feedback_convergence_certificate",
        "feedback_result",
        "feedback_trace",
    }
    welfare_report_refs = [
        artifact.ref
        for artifact in exec_result.derived_refs
        if artifact.role.startswith("welfare_bound_report:")
    ]
    assert len(welfare_report_refs) == 1
    welfare_report = load_welfare_bound_report(store, welfare_report_refs[0])
    assert welfare_report.status == "ok"

    feedback_result_ref = next(
        artifact.ref for artifact in exec_result.derived_refs if artifact.role == "feedback_result"
    )
    feedback_result = FeedbackSolveResult.model_validate(
        from_canonical_bytes(store.get_bytes(feedback_result_ref.artifact_id))
    )

    assert feedback_result.converged is True
    assert feedback_result.status == "converged"
    assert feedback_result.convergence_certificate_ref is not None
    assert feedback_result.final_state.values[0] == 0.5
    assert any(note == "feedback_mode:fixed_point" for note in exec_result.notes)
    certificate = FeedbackConvergenceCertificate.model_validate(
        from_canonical_bytes(
            store.get_bytes(feedback_result.convergence_certificate_ref.artifact_id)
        )
    )
    assert certificate.converged is True
    assert certificate.status == "converged"
    simulation_result = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(exec_result.simulation_result_ref.artifact_id))
    )
    assert simulation_result.welfare_bound_refs is not None
    assert welfare_report.node_id in simulation_result.welfare_bound_refs

    feedback_config = FeedbackConfig.model_validate(
        from_canonical_bytes(store.get_bytes(feedback_config_ref.artifact_id))
    )
    multiplicity_config = feedback_config.model_copy(
        update={
            "solver": feedback_config.solver.model_copy(
                update={
                    "detect_multiplicity": True,
                    "multiplicity_mode": "baseline",
                    "multiplicity_max_attempts": 1,
                    "multiplicity_sobol_draws": 0,
                    "basin_draws": 0,
                }
            )
        }
    )
    multiplicity_config_ref = store.put_json(
        multiplicity_config,
        PutOptions(
            kind="foundry.feedback_config",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FeedbackConfig", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    multiplicity_exec_result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compile_result.exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=input_bindings_ref.artifact_id),
            registry_bundle_ref=bundle.bundle_ref,
            feedback_config_ref=FeedbackConfigRef(artifact_id=multiplicity_config_ref.artifact_id),
        ),
    )

    assert multiplicity_exec_result.ok is True
    assert {artifact.role for artifact in multiplicity_exec_result.derived_refs} >= {
        "equilibrium_multiplicity_report",
        "feedback_result",
    }
    multiplicity_report_ref = next(
        artifact.ref
        for artifact in multiplicity_exec_result.derived_refs
        if artifact.role == "equilibrium_multiplicity_report"
    )
    multiplicity_report = EquilibriumMultiplicityReport.model_validate(
        from_canonical_bytes(store.get_bytes(multiplicity_report_ref.artifact_id))
    )
    assert multiplicity_report.global_diagnostics.num_equilibria >= 1
    multiplicity_feedback_result_ref = next(
        artifact.ref
        for artifact in multiplicity_exec_result.derived_refs
        if artifact.role == "feedback_result"
    )
    multiplicity_feedback_result = FeedbackSolveResult.model_validate(
        from_canonical_bytes(store.get_bytes(multiplicity_feedback_result_ref.artifact_id))
    )
    assert multiplicity_feedback_result.multiplicity_report_ref is not None

    failure_config = feedback_config.model_copy(
        update={
            "solver": feedback_config.solver.model_copy(
                update={
                    "homotopy_grid": [0.0, 1.0],
                    "max_iter": 5,
                    "max_restarts": 1,
                    "stagnation_patience": 2,
                    "budget_diagnostic_id": "government_balance",
                    "budget_tolerance": 0.0,
                    "compute_jacobian_diagnostics": False,
                }
            )
        }
    )
    failure_config_ref = store.put_json(
        failure_config,
        PutOptions(
            kind="foundry.feedback_config",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FeedbackConfig", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    failed_exec_result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compile_result.exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=input_bindings_ref.artifact_id),
            registry_bundle_ref=bundle.bundle_ref,
            feedback_config_ref=FeedbackConfigRef(artifact_id=failure_config_ref.artifact_id),
        ),
    )

    assert failed_exec_result.ok is False
    assert {artifact.role for artifact in failed_exec_result.derived_refs} >= {
        "feedback_convergence_certificate",
        "feedback_result",
        "feedback_trace",
    }
    failed_feedback_result_ref = next(
        artifact.ref
        for artifact in failed_exec_result.derived_refs
        if artifact.role == "feedback_result"
    )
    failed_feedback_result = FeedbackSolveResult.model_validate(
        from_canonical_bytes(store.get_bytes(failed_feedback_result_ref.artifact_id))
    )
    assert failed_feedback_result.converged is False
    assert failed_feedback_result.status in {"stagnated", "restarts_exhausted", "max_iter_exceeded"}
    assert failed_feedback_result.convergence_certificate_ref is not None
    assert failed_feedback_result.failure_reason is not None
