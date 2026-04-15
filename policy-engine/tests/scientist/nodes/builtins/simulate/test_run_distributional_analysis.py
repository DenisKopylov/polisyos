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
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    DistributionalJustification,
    load_distributional_effect_bundle,
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
    assert any("skipped" in event.message.lower() for event in outcome.events)


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
