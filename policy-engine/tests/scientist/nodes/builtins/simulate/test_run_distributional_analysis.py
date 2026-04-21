"""Gap-coverage and D.1 regression tests for RunDistributionalAnalysisNode."""

from __future__ import annotations

from dataclasses import replace

import jax.numpy as jnp
import pytest

from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    MetricsRef,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.executor import put_state_snapshot
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    DistributionalBoundUniformity,
    DistributionalFunctional,
    DistributionalJustification,
    DistributionalProofTarget,
    DistributionalCouplingStatus,
    load_causal_assumption_card,
    load_distributional_bounds_bundle,
    load_distributional_effect_bundle,
    load_distributional_proof_artifact,
    load_distributional_report,
    load_subgroup_distribution_comparison,
)
from polisyos.scientist.nodes.builtins.simulate.run_distributional_analysis import (
    RunDistributionalAnalysisNode,
    _resolve_baseline_snapshot_ref,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_STATE_SNAPSHOT_REF,
)


def _state_with_income(
    incomes: list[float],
    *,
    employer_ids: list[int],
) -> GlobalState:
    state = GlobalState.empty(len(incomes), 3)
    agents = replace(
        state.agents,
        income=jnp.asarray(incomes, dtype=jnp.float32),
        reported_income=jnp.asarray(incomes, dtype=jnp.float32),
        employer_id=jnp.asarray(employer_ids, dtype=jnp.int32),
    )
    market = replace(
        state.market,
        avg_wage=jnp.asarray(float(sum(incomes) / len(incomes)), dtype=jnp.float32),
    )
    return replace(state, agents=agents, market=market)


def _simulation_result_ref(cas_store, *, simulated_ref, artifact_ref_factory):
    sim_result = SimulationResult(
        exec_plan_ref=ExecPlanRef.model_validate(
            artifact_ref_factory(kind="foundry.exec_plan").model_dump()
        ),
        metrics_ref=MetricsRef.model_validate(
            artifact_ref_factory(kind="foundry.metrics").model_dump()
        ),
        state_snapshot_ref=StateSnapshotRef.model_validate(simulated_ref.model_dump()),
        notes=["test"],
    )
    return cas_store.put_json(
        sim_result.model_dump(mode="json"),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )


def test_skip_when_no_simulation_result_ref(execution_context, minimal_state):
    """No simulation_result_ref in artifacts_index -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = RunDistributionalAnalysisNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("No simulation_result_ref" in e.message for e in outcome.events)


def test_skip_when_simulation_result_invalid(
    execution_context, minimal_state, artifact_ref_factory
):
    """simulation_result_ref artifact is not a valid SimulationResult -> skip."""
    ref = artifact_ref_factory(
        kind="foundry.simulation_result",
        data={"not": "valid"},
    )
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = ref

    outcome = RunDistributionalAnalysisNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("Unable to load SimulationResult" in e.message for e in outcome.events)


def test_skip_when_no_state_snapshot_ref(
    execution_context, minimal_state, cas_store
):
    """SimulationResult has no state_snapshot_ref -> skip."""
    sim_result_payload = {
        "exec_plan_ref": {
            "artifact_id": "sha256:" + "1" * 64,
            "kind": "foundry.exec_plan",
            "media_type": "application/json",
        },
        "metrics_ref": {
            "artifact_id": "sha256:" + "2" * 64,
            "kind": "foundry.metrics",
            "media_type": "application/json",
        },
        "state_snapshot_ref": None,
        "notes": [],
    }
    ref = cas_store.put_json(
        sim_result_payload,
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = ref

    outcome = RunDistributionalAnalysisNode().execute(execution_context, state)
    assert outcome.status == "skip"


def test_happy_path_writes_report_and_effect_bundle(
    execution_context,
    minimal_state,
    cas_store,
    artifact_ref_factory,
):
    baseline = _state_with_income(
        [10, 12, 15, 18, 20, 22, 24, 26, 28, 30, 35, 40, 45, 50, 55, 60, 65, 72, 80, 90],
        employer_ids=[0] * 10 + [1] * 10,
    )
    simulated = _state_with_income(
        [12, 14, 18, 20, 23, 25, 27, 30, 32, 34, 40, 46, 52, 58, 64, 70, 77, 84, 92, 101],
        employer_ids=[0] * 10 + [1] * 10,
    )
    baseline_ref = put_state_snapshot(cas_store, state=baseline)
    simulated_ref = put_state_snapshot(cas_store, state=simulated)
    sim_result_ref = _simulation_result_ref(
        cas_store,
        simulated_ref=simulated_ref,
        artifact_ref_factory=artifact_ref_factory,
    )

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_STATE_SNAPSHOT_REF] = baseline_ref
    state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = sim_result_ref

    outcome = RunDistributionalAnalysisNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert ARTIFACT_DISTRIBUTIONAL_REPORT_REF in outcome.state.artifacts_index
    assert ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF in outcome.state.artifacts_index
    report = load_distributional_report(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_REPORT_REF],
    )
    bundle = load_distributional_effect_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF],
    )

    assert bundle.justification is DistributionalJustification.SCENARIO
    assert bundle.readiness_cap == "simulation_ready"
    assert len(bundle.subgroup_distribution_refs) == 7
    assert report.metadata["geography_breakdown_status"] == "included"
    assert report.metadata["geography_group_ids"] == ["region_0", "region_1"]
    assert report.get_breakdown(CohortDimension.GEOGRAPHY) is not None
    assert report.winners_losers.total_winners_share >= 0.0


def test_geography_subgroups_require_aligned_employer_ids(
    execution_context,
    minimal_state,
    cas_store,
    artifact_ref_factory,
):
    incomes_before = list(range(10, 30))
    incomes_after = list(range(12, 32))
    baseline = _state_with_income(incomes_before, employer_ids=[0] * 10 + [1] * 10)
    simulated = _state_with_income(incomes_after, employer_ids=[0] * 8 + [1] * 12)
    baseline_ref = put_state_snapshot(cas_store, state=baseline)
    simulated_ref = put_state_snapshot(cas_store, state=simulated)
    sim_result_ref = _simulation_result_ref(
        cas_store,
        simulated_ref=simulated_ref,
        artifact_ref_factory=artifact_ref_factory,
    )

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_STATE_SNAPSHOT_REF] = baseline_ref
    state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = sim_result_ref

    outcome = RunDistributionalAnalysisNode().execute(execution_context, state)

    assert outcome.status == "ok"
    bundle = load_distributional_effect_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF],
    )
    report = load_distributional_report(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_REPORT_REF],
    )
    subgroup_items = [
        load_subgroup_distribution_comparison(cas_store, ref)
        for ref in bundle.subgroup_distribution_refs
    ]
    assert all(item.subgroup_dimension is CohortDimension.INCOME_QUINTILE for item in subgroup_items)
    assert report.get_breakdown(CohortDimension.GEOGRAPHY) is None
    assert report.metadata["geography_breakdown_status"] == "skipped"
    assert any(
        "employer_id not aligned" in reason
        for reason in report.metadata["geography_breakdown_skipped_reasons"]
    )
    assert any("employer_id not aligned" in event.message for event in outcome.events)


def test_undersized_geography_groups_emit_warning_without_failing(
    execution_context,
    minimal_state,
    cas_store,
    artifact_ref_factory,
):
    incomes_before = list(range(10, 30))
    incomes_after = list(range(11, 31))
    baseline = _state_with_income(incomes_before, employer_ids=[0] * 11 + [1] * 9)
    simulated = _state_with_income(incomes_after, employer_ids=[0] * 11 + [1] * 9)
    baseline_ref = put_state_snapshot(cas_store, state=baseline)
    simulated_ref = put_state_snapshot(cas_store, state=simulated)
    sim_result_ref = _simulation_result_ref(
        cas_store,
        simulated_ref=simulated_ref,
        artifact_ref_factory=artifact_ref_factory,
    )

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_STATE_SNAPSHOT_REF] = baseline_ref
    state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = sim_result_ref

    outcome = RunDistributionalAnalysisNode().execute(execution_context, state)

    assert outcome.status == "ok"
    bundle = load_distributional_effect_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF],
    )
    report = load_distributional_report(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_REPORT_REF],
    )
    assert len(bundle.subgroup_distribution_refs) == 5
    assert report.get_breakdown(CohortDimension.GEOGRAPHY) is None
    assert report.metadata["geography_breakdown_status"] == "skipped"
    assert any(
        "fewer than two sufficiently sized aligned regions" in reason
        for reason in report.metadata["geography_breakdown_skipped_reasons"]
    )


def test_uses_proof_kernel_for_distribution_law_when_graph_and_treatment_available(
    execution_context,
    minimal_state,
    cas_store,
    artifact_ref_factory,
):
    baseline = _state_with_income(
        [10, 12, 15, 18, 20, 22, 24, 26, 28, 30, 35, 40, 45, 50, 55, 60, 65, 72, 80, 90],
        employer_ids=[0] * 10 + [1] * 10,
    )
    simulated = _state_with_income(
        [11, 13, 17, 20, 23, 25, 28, 31, 33, 36, 42, 48, 54, 60, 66, 72, 79, 86, 94, 103],
        employer_ids=[0] * 10 + [1] * 10,
    )
    baseline_ref = put_state_snapshot(cas_store, state=baseline)
    simulated_ref = put_state_snapshot(cas_store, state=simulated)
    sim_result_ref = _simulation_result_ref(
        cas_store,
        simulated_ref=simulated_ref,
        artifact_ref_factory=artifact_ref_factory,
    )
    graph_ref = persist_causal_graph_model(
        cas_store,
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["policy_shock", "income"],
            edges=[
                CausalEdge(
                    src="policy_shock",
                    dst="income",
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                )
            ],
        ),
    )

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_STATE_SNAPSHOT_REF] = baseline_ref
    state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = sim_result_ref
    state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = graph_ref
    state.params["distributional_treatment_variable"] = "policy_shock"

    outcome = RunDistributionalAnalysisNode().execute(execution_context, state)

    assert outcome.status == "ok"
    bundle = load_distributional_effect_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF],
    )

    assert bundle.justification is DistributionalJustification.SCENARIO
    assert bundle.distributional_query_kind == "interventional_law"
    assert bundle.marginal_justification is DistributionalJustification.IDENTIFIED
    assert bundle.marginal_law_justification is DistributionalJustification.IDENTIFIED
    assert bundle.coupling_justification is DistributionalJustification.SCENARIO
    assert "distributional_estimand_not_proof_kernel_identified" not in bundle.causal_assumptions
    assert bundle.metadata["marginal_law_justification"] == DistributionalJustification.IDENTIFIED.value
    assert bundle.metadata["distributional_query_kind"] == "interventional_law"
    assert bundle.metadata["coupling_justification"] == DistributionalJustification.SCENARIO.value
    assert bundle.metadata["proof_kernel"]["status"] == "identified"
    assert bundle.metadata["proof_kernel"]["query_kind"] == "distribution_law"
    assert bundle.metadata["proof_kernel"]["distributional_query_kind"] == "interventional_law"
    assert bundle.marginal_law_proof_ref == bundle.distributional_proof_ref
    assert bundle.distributional_proof_ref is not None
    assert bundle.coupling_proof_ref is not None
    assert bundle.causal_assumption_refs

    marginal_proof = load_distributional_proof_artifact(
        cas_store,
        bundle.distributional_proof_ref,
    )
    coupling_proof = load_distributional_proof_artifact(
        cas_store,
        bundle.coupling_proof_ref,
    )
    assumption_cards = [
        load_causal_assumption_card(cas_store, ref)
        for ref in bundle.causal_assumption_refs
    ]

    assert marginal_proof.target is DistributionalProofTarget.CDF
    assert coupling_proof.target is DistributionalProofTarget.COUPLING
    assert coupling_proof.coupling_status is DistributionalCouplingStatus.SCENARIO_ONLY
    assert any(card.scope == "coupling" for card in assumption_cards)
    assert any(card.scope == "estimation" for card in assumption_cards)
    assert bundle.distributional_bounds_refs == []


def test_lee_distributional_bounds_are_wired_into_production_bundle(
    execution_context,
    minimal_state,
    cas_store,
    artifact_ref_factory,
):
    baseline = _state_with_income(
        list(range(10, 30)),
        employer_ids=[0] * 10 + [1] * 10,
    )
    simulated = _state_with_income(
        list(range(12, 32)),
        employer_ids=[0] * 10 + [1] * 10,
    )
    baseline_ref = put_state_snapshot(cas_store, state=baseline)
    simulated_ref = put_state_snapshot(cas_store, state=simulated)
    sim_result_ref = _simulation_result_ref(
        cas_store,
        simulated_ref=simulated_ref,
        artifact_ref_factory=artifact_ref_factory,
    )

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_STATE_SNAPSHOT_REF] = baseline_ref
    state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = sim_result_ref
    state.params["distributional_bounds"] = {
        "enabled": True,
        "requests": [
            {
                "theorem_family": "lee_trimming_distributional",
                "assumptions": ["monotone_selection_S1_ge_S0"],
                "outcome": [10, 11, 12, 13, 14, 15, 16, 17],
                "treatment": [0, 0, 0, 0, 1, 1, 1, 1],
                "selected": [1, 1, 0, 0, 1, 1, 1, 0],
                "tail_thresholds": [14.0],
                "quantiles": [0.5],
            }
        ],
    }

    outcome = RunDistributionalAnalysisNode().execute(execution_context, state)

    assert outcome.status == "ok"
    bundle = load_distributional_effect_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF],
    )
    assert bundle.marginal_law_justification is DistributionalJustification.BOUNDED
    assert bundle.coupling_justification is DistributionalJustification.SCENARIO
    assert bundle.justification is DistributionalJustification.SCENARIO
    assert bundle.distributional_bounds_refs
    assert bundle.distributional_proof_ref is not None
    assert bundle.metadata["bounded_functionals"] == [
        DistributionalFunctional.TAIL_DELTA.value,
        DistributionalFunctional.QUANTILE_SHIFT.value,
    ]
    assert bundle.metadata["bounds_theorem_families"] == ["lee_trimming_distributional"]

    proof = load_distributional_proof_artifact(cas_store, bundle.distributional_proof_ref)
    assert proof.target is DistributionalProofTarget.CDF
    assert proof.bounded_curve_ref is not None
    assert proof.bounded_curve_ref.artifact_id == bundle.distributional_bounds_refs[0].artifact_id
    assert proof.bound_uniformity is DistributionalBoundUniformity.POINTWISE_ONLY


def test_makarov_distributional_bounds_require_licensed_marginals_and_warn_pointwise(
    execution_context,
    minimal_state,
    cas_store,
    artifact_ref_factory,
):
    baseline = _state_with_income(
        list(range(10, 30)),
        employer_ids=[0] * 10 + [1] * 10,
    )
    simulated = _state_with_income(
        list(range(11, 31)),
        employer_ids=[0] * 10 + [1] * 10,
    )
    baseline_ref = put_state_snapshot(cas_store, state=baseline)
    simulated_ref = put_state_snapshot(cas_store, state=simulated)
    sim_result_ref = _simulation_result_ref(
        cas_store,
        simulated_ref=simulated_ref,
        artifact_ref_factory=artifact_ref_factory,
    )

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_STATE_SNAPSHOT_REF] = baseline_ref
    state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = sim_result_ref
    state.params["distributional_bounds"] = {
        "enabled": True,
        "requests": [
            {
                "theorem_family": "makarov_pointwise",
                "marginal_law_status": "identified",
                "treated_outcome": [12, 14, 15, 18, 20, 22],
                "control_outcome": [10, 11, 13, 14, 16, 17],
                "harm_thresholds": [0.0, 1.0],
                "quantiles": [0.25, 0.5],
            }
        ],
    }

    outcome = RunDistributionalAnalysisNode().execute(execution_context, state)

    assert outcome.status == "ok"
    bundle = load_distributional_effect_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF],
    )
    assert bundle.marginal_law_justification is DistributionalJustification.BOUNDED
    assert bundle.coupling_justification is DistributionalJustification.SCENARIO
    assert bundle.distributional_bounds_refs
    assert bundle.distributional_proof_ref is not None
    assert bundle.metadata["bound_uniformity"] == DistributionalBoundUniformity.POINTWISE_ONLY.value
    assert bundle.metadata["distributional_bounds"]["pointwise_warning"] is True

    bounds = [
        load_distributional_bounds_bundle(cas_store, ref)
        for ref in bundle.distributional_bounds_refs
    ]
    assert {item.functional for item in bounds} == {
        DistributionalFunctional.ITE_TAIL_RISK,
        DistributionalFunctional.QUANTILE,
    }
    proof = load_distributional_proof_artifact(cas_store, bundle.distributional_proof_ref)
    assert proof.target is DistributionalProofTarget.MARGINAL_PAIR
    assert proof.bound_uniformity is DistributionalBoundUniformity.POINTWISE_ONLY


def test_resolve_baseline_snapshot_ref_assertion_is_not_swallowed(
    execution_context,
    minimal_state,
    artifact_ref_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_STATE_SNAPSHOT_REF] = artifact_ref_factory(kind="foundry.state_snapshot")

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("state snapshot invariant")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_distributional_analysis.StateSnapshotRef.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="state snapshot invariant"):
        _resolve_baseline_snapshot_ref(execution_context, state)
