from __future__ import annotations

import pytest

from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    ExecuteRequest,
    FeedbackConfig,
    FeedbackConfigRef,
    FeedbackExecutionContext,
    FeedbackMapEvaluationRecord,
    FeedbackResultRef,
    FeedbackSolverConfig,
    FeedbackSolveResult,
    FeedbackStateSnapshot,
    FeedbackTrace,
    FeedbackTraceRef,
    FeedbackVariableSpec,
    FoundryExecutionInputBasis,
    FoundryExecutionInputBasisRef,
    FoundryInputBindingsRef,
    MethodExecutionBundle,
    MethodExecutionBundleRef,
    MethodExecutionOccurrence,
    MethodMetricBindingSetRef,
    MetricsRef,
    ProgramGraphRef,
    SimulationResult,
    StateDelta,
    StateDeltaRef,
    StateSnapshotRef,
)
from polisyos.foundry.feedback.reconciliation import reconcile_feedback_execution


def _artifact_id(letter: str) -> str:
    return f"sha256:{letter * 64}"


def _profile(letter: str) -> str:
    return f"sha256:{letter * 64}"


def _case(*, candidate: float = 1.9995, mapped: float = 2.0, budget: bool = False):
    basis_ref = FoundryExecutionInputBasisRef(
        artifact_id=_artifact_id("a"), manifest_profile_sha256=_profile("a")
    )
    feedback_result_ref = FeedbackResultRef(
        artifact_id=_artifact_id("b"), manifest_profile_sha256=_profile("b")
    )
    trace_ref = FeedbackTraceRef(
        artifact_id=_artifact_id("c"), manifest_profile_sha256=_profile("c")
    )
    config_ref = FeedbackConfigRef(
        artifact_id=_artifact_id("d"), manifest_profile_sha256=_profile("d")
    )
    final_state_ref = StateSnapshotRef(
        artifact_id=_artifact_id("e"), manifest_profile_sha256=_profile("e")
    )
    override_ref = None
    bundle_ref = MethodExecutionBundleRef(
        artifact_id=_artifact_id("f"), manifest_profile_sha256=_profile("f")
    )
    plan_ref = ExecPlanRef(artifact_id=_artifact_id("1"), manifest_profile_sha256=_profile("1"))
    graph_ref = ProgramGraphRef(
        artifact_id=_artifact_id("2"), manifest_profile_sha256=_profile("2")
    )
    context = FeedbackExecutionContext(
        final_injected_state_snapshot_ref=final_state_ref,
        feedback_result_ref=feedback_result_ref,
        feedback_trace_ref=trace_ref,
        final_map_evaluation_id="feedback-map-evaluation.000002",
        final_graph_invocation_id="graph-final",
        final_method_execution_bundle_ref=bundle_ref,
        execution_link_status="captured",
    )
    request = ExecuteRequest(
        exec_plan_ref=plan_ref,
        input_bindings_ref=FoundryInputBindingsRef(
            artifact_id=_artifact_id("3"), manifest_profile_sha256=_profile("3")
        ),
        feedback_config_ref=config_ref,
    )
    basis = FoundryExecutionInputBasis.model_construct(
        schema_version="1.3",
        execution_mode="feedback",
        request=request,
        exec_plan_ref=plan_ref,
        program_graph_ref=graph_ref,
        feedback_execution_context=context,
    )
    simulation = SimulationResult(
        schema_version="1.5",
        exec_plan_ref=plan_ref,
        metrics_ref=MetricsRef(
            artifact_id=_artifact_id("4"), manifest_profile_sha256=_profile("4")
        ),
        execution_input_basis_ref=basis_ref,
        execution_source_status="feedback_basis",
        feedback_result_ref=feedback_result_ref,
    )
    solver = FeedbackSolverConfig(
        atol=0.001,
        rtol=0.0,
        xtol=0.001,
        **(
            {"budget_diagnostic_id": "total", "budget_tolerance": 1.0}
            if budget
            else {}
        ),
    )
    config = FeedbackConfig(
        variables=[
            FeedbackVariableSpec(
                variable_id="balance",
                source_kind="state_path",
                source_ref="government.balance",
                target_kind="state_path",
                target_ref="government.balance",
                scale=1.0,
                weight=1.0,
            )
        ],
        solver=solver,
    )
    initial_state = FeedbackStateSnapshot(
        variable_ids=["balance"],
        values=[0.0],
        scales=[1.0],
        lower_bounds=[None],
        upper_bounds=[None],
        weights=[1.0],
    )
    final_state = FeedbackStateSnapshot(
        variable_ids=["balance"],
        values=[mapped],
        scales=[1.0],
        lower_bounds=[None],
        upper_bounds=[None],
        weights=[1.0],
    )
    record = FeedbackMapEvaluationRecord(
        evaluation_id="feedback-map-evaluation.000002",
        phase="final_materialization",
        candidate_values=(candidate,),
        mapped_values=(mapped,),
        graph_invocation_id="graph-final",
        execution_link_status="captured",
    )
    trace = FeedbackTrace(
        schema_version="1.1",
        map_evaluations=(record,),
        evaluation_scope="complete",
    )
    feedback_result = FeedbackSolveResult(
        converged=True,
        initial_state=initial_state,
        final_state=final_state,
        trace_ref=trace_ref,
        final_parameter_override_bundle_ref=override_ref,
    )
    bundle = MethodExecutionBundle(
        schema_version="1.1",
        program_graph_ref=graph_ref,
        exec_plan_ref=plan_ref,
        method_metric_binding_set_ref=MethodMetricBindingSetRef(
            artifact_id=_artifact_id("5"), manifest_profile_sha256=_profile("5")
        ),
        occurrences=[
            MethodExecutionOccurrence(
                occurrence_id="graph-final:0:system.node",
                invocation_id="graph-final",
                plan_index=0,
                node_id="system.node",
                node_kind="mechanism",
                status="succeeded",
            )
        ],
    )
    delta = StateDelta(base_ref=final_state_ref)
    delta_ref = StateDeltaRef(
        artifact_id=_artifact_id("6"), manifest_profile_sha256=_profile("6")
    )
    return {
        "simulation_result": simulation,
        "execution_input_basis": basis,
        "execution_input_basis_ref": basis_ref,
        "feedback_config": config,
        "feedback_config_ref": config_ref,
        "feedback_result": feedback_result,
        "feedback_result_ref": feedback_result_ref,
        "feedback_trace": trace,
        "feedback_trace_ref": trace_ref,
        "state_delta": delta,
        "state_delta_ref": delta_ref,
        "method_execution_bundle": bundle,
        "method_execution_bundle_ref": bundle_ref,
    }


def test_reconciliation_recomputes_nonexact_final_fixed_point_and_joins_actual_graph() -> None:
    evidence = _case(candidate=1.9995, mapped=2.0)

    result = reconcile_feedback_execution(**evidence)

    assert result.source_binding_status == "recomputed"
    assert result.final_materialization_status == "recomputed"
    assert result.graph_invocation_status == "recomputed"
    assert result.final_delta_base_status == "recomputed"
    assert result.fixed_point_tolerance_status == "recomputed"
    assert result.fixed_point_tolerance_satisfied is True
    assert result.solver_convergence_claim_matches is True


def test_reconciliation_reports_nonconverged_final_map_and_unestablished_graph_link() -> None:
    evidence = _case(candidate=1.0, mapped=2.0)
    result = reconcile_feedback_execution(**evidence)
    assert result.fixed_point_tolerance_status == "recomputed"
    assert result.fixed_point_tolerance_satisfied is False
    assert result.solver_convergence_claim_matches is False

    basis = evidence["execution_input_basis"]
    context = FeedbackExecutionContext.model_copy(
        basis.feedback_execution_context,
        update={
            "final_graph_invocation_id": None,
            "final_method_execution_bundle_ref": None,
            "execution_link_status": "not_established",
        },
    )
    unlinked_basis = FoundryExecutionInputBasis.model_copy(
        basis,
        update={"feedback_execution_context": context},
    )
    record = FeedbackMapEvaluationRecord.model_copy(
        evidence["feedback_trace"].map_evaluations[0],
        update={"graph_invocation_id": None, "execution_link_status": "not_established"},
    )
    unlinked_trace = FeedbackTrace.model_copy(
        evidence["feedback_trace"], update={"map_evaluations": (record,)}
    )
    unlinked = reconcile_feedback_execution(
        **{
            **evidence,
            "execution_input_basis": unlinked_basis,
            "feedback_trace": unlinked_trace,
            "method_execution_bundle": None,
            "method_execution_bundle_ref": None,
        }
    )
    assert unlinked.graph_invocation_status == "not_established"
    assert unlinked.fixed_point_tolerance_status == "recomputed"


def test_reconciliation_rejects_changed_final_evaluation_or_graph_identity() -> None:
    evidence = _case()
    wrong_id = FeedbackExecutionContext.model_copy(
        evidence["execution_input_basis"].feedback_execution_context,
        update={"final_map_evaluation_id": "feedback-map-evaluation.removed"},
    )
    wrong_basis = FoundryExecutionInputBasis.model_copy(
        evidence["execution_input_basis"], update={"feedback_execution_context": wrong_id}
    )
    with pytest.raises(ValueError, match="feedback_execution_final_evaluation_identity_mismatch"):
        reconcile_feedback_execution(**{**evidence, "execution_input_basis": wrong_basis})

    wrong_record = FeedbackMapEvaluationRecord.model_copy(
        evidence["feedback_trace"].map_evaluations[0],
        update={"graph_invocation_id": "other-graph"},
    )
    wrong_trace = FeedbackTrace.model_copy(
        evidence["feedback_trace"], update={"map_evaluations": (wrong_record,)}
    )
    with pytest.raises(ValueError, match="feedback_execution_final_graph_invocation_mismatch"):
        reconcile_feedback_execution(**{**evidence, "feedback_trace": wrong_trace})


def test_reconciliation_uses_injected_state_as_delta_base_and_preserves_budget_unknown() -> None:
    evidence = _case(budget=True)
    wrong_delta = StateDelta(base_ref=StateSnapshotRef(
        artifact_id=_artifact_id("7"), manifest_profile_sha256=_profile("7")
    ))
    with pytest.raises(ValueError, match="feedback_execution_final_delta_base_mismatch"):
        reconcile_feedback_execution(**{**evidence, "state_delta": wrong_delta})

    result = reconcile_feedback_execution(**evidence)
    assert result.final_delta_base_status == "recomputed"
    assert result.fixed_point_tolerance_status == "not_established"
    assert result.fixed_point_tolerance_satisfied is None
    assert result.limitations == ("final_budget_gap_not_recorded",)
