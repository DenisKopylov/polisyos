"""Exercise selected multi-coordinate ensembles through Scientist and Foundry."""

from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal
from statistics import mean

import jax
import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import ExecuteRequest, FoundryInputBindings
from polisyos.foundry.compile.randomization import stable_hash
from polisyos.foundry.execute import load_state_snapshot
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.mechanisms.labor import LaborMarketMechanism
from polisyos.ir.analytics.backtest import persist_backtest_report
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.trinity import persist_trinity_bundle_artifact
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.methods.backtesting.native_replay import (
    NativeForecastTrajectory,
    _check_native_plan_request,
    _edge_ref,
    _load_native_plan,
    _require_shared_native_basis,
    load_backtest_report_for_consumption,
    load_native_forecast,
)
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    load_policy_candidate_schema,
    persist_policy_candidate_schema,
)
from tests.unit.scientist.methods.backtesting.test_native_replay import _fixture

_SEEDS = (12, 13, 14)
_FAULT = "lane03_middle_labor_physical_fault"


def _employment_draws(node_id):
    draws = {}
    for seed in _SEEDS:
        key = jax.random.PRNGKey(seed)
        for salt in (stable_hash("stream:default"), stable_hash(f"node:{node_id}")):
            key = jax.random.fold_in(key, salt & 0xFFFFFFFF)
            key = jax.random.fold_in(key, salt >> 32)
        step_key = jax.random.split(key)[1]
        employment_key = jax.random.split(step_key, 3)[0]
        draws[seed] = float(jax.random.uniform(employment_key, shape=(1,))[0])
    return draws


def _labor_fixture(tmp_path):
    # The treasury folds the intervention ID and starts again from the replica
    # seed on each step. Disjoint schedules choose exactly one active node.
    opening_draws = _employment_draws("tax")
    assert len(set(opening_draws.values())) == 3
    opening_seed = min(opening_draws, key=opening_draws.__getitem__)
    opening_sorted = sorted(opening_draws.values())
    opening_threshold = Decimal(str(mean(opening_sorted[:2])))

    for followup_id in ("labor_followup", "labor_review"):
        followup_draws = _employment_draws(followup_id)
        followup_sorted = sorted(followup_draws.values())
        if len(set(followup_sorted)) == 3 and followup_draws[opening_seed] < followup_sorted[2]:
            break
    else:
        pytest.fail("labor fixture requires three distinct employment histories")
    followup_threshold = Decimal(str(mean(followup_sorted[1:])))

    store, plan = _fixture(
        tmp_path,
        count=3,
        horizon=2,
        mechanism="labor_market",
        mechanism_params={"employment_threshold": opening_threshold},
    )
    state = deepcopy(plan.scientist_state)
    assert state is not None
    original = ArtifactRef.model_validate(state["inputs"]["trinity_bundle_ref"])
    candidate_ref = _edge_ref(
        store, original, "policy_candidate", PolicyCandidateSchema.ARTIFACT_KIND
    )
    candidate = load_policy_candidate_schema(store, candidate_ref)
    trinity = candidate.trinity_bundle
    intervention = trinity.policy_spec.interventions[0]
    opening = intervention.model_copy(
        update={"schedule": ScheduleSpec(start_step=0, duration_steps=1)}
    )
    followup = intervention.model_copy(
        update={
            "intervention_id": followup_id,
            "schedule": ScheduleSpec(start_step=1, duration_steps=1),
            "params": {"employment_threshold": followup_threshold},
        }
    )
    policy = trinity.policy_spec.model_copy(update={"interventions": [opening, followup]})
    trinity = trinity.model_copy(update={"policy_spec": policy})
    new_candidate = persist_policy_candidate_schema(
        store,
        candidate.model_copy(update={"trinity_bundle": trinity}),
        inputs=store.get_manifest(candidate_ref).inputs,
        return_selected_profile=True,
    )
    trinity_ref = persist_trinity_bundle_artifact(
        ensure_ir_artifact_store(store),
        trinity,
        inputs=[input_ref_from_artifact_ref(new_candidate, role="policy_candidate")],
    )
    state["inputs"]["trinity_bundle_ref"] = trinity_ref.model_dump(mode="json")
    expected_employment = [
        (seed == opening_seed, followup_draws[seed] < float(followup_threshold)) for seed in _SEEDS
    ]
    assert len(set(expected_employment)) == 3
    return store, plan.model_copy(update={"scientist_state": state}), expected_employment


def _observe_foundry(monkeypatch, *, fail_middle=False):
    execute = DefaultFoundryPort.execute
    emit_patches = LaborMarketMechanism.emit_patches
    attempts = []
    results = []
    faults = []
    active = None

    def observe(port, store, request, **kwargs):
        nonlocal active
        attempts.append(request)
        active = request
        try:
            result = execute(port, store, request, **kwargs)
        finally:
            active = None
        results.append(result)
        return result

    def fail_in_physical_step(mechanism, state, key, **kwargs):
        if active is not None and active.exec_config.seed == 13 and int(state.step) == 1:
            faults.append(active)
            raise RuntimeError(_FAULT)
        return emit_patches(mechanism, state, key, **kwargs)

    monkeypatch.setattr(DefaultFoundryPort, "execute", observe)
    if fail_middle:
        monkeypatch.setattr(LaborMarketMechanism, "emit_patches", fail_in_physical_step)
    return attempts, results, faults


def _republish(store, ref, payload, **replacement_refs):
    manifest = store.get_manifest(ref)
    return store.put_json(
        payload,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=[
                input_ref_from_artifact_ref(replacement_refs[edge.role], role=edge.role)
                if edge.role in replacement_refs
                else edge
                for edge in manifest.inputs
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def test_native_three_by_two_projects_selected_coordinates_and_refuses_foreign_estimand(
    tmp_path, monkeypatch, record_property
):
    store, plan, expected_employment = _labor_fixture(tmp_path)
    attempts, results, faults = _observe_foundry(monkeypatch)
    _, raw_report_ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    report_ref = ArtifactRef.model_validate(raw_report_ref.model_dump(mode="json"))
    record_property("selected_report_ref", report_ref.model_dump_json())
    assert [call.exec_config.seed for call in attempts] == [12, 12, 13, 13, 14, 14]
    assert not faults
    assert all(result.ok and result.simulation_result_ref is not None for result in results)
    successes = [result.simulation_result_ref for result in results]
    assert len({artifact_ref_identity_key(ref) for ref in successes}) == 6

    reader = FileSystemCAS(store.root)
    report = load_backtest_report_for_consumption(reader, report_ref)
    scenario = report.scenarios[0]
    cohort_ref = ArtifactRef.model_validate(scenario.metadata["replica_cohort_ref"])
    cohort = load_core_json_artifact(reader, cohort_ref)
    projection = scenario.metadata["native_replica_projection"]
    plan_ref = ArtifactRef.model_validate(projection["plan_ref"])
    selected_plan = _load_native_plan(reader, plan_ref)
    forecast_refs = [ArtifactRef.model_validate(ref) for ref in projection["forecast_refs"]]

    assert projection["method"] == "arithmetic_mean_complete_cohort_v1"
    assert selected_plan.n_simulation_runs == len(forecast_refs) == 3
    assert (
        cohort["requested_count"],
        cohort["started_count"],
        cohort["foundry_execute_count"],
    ) == (
        3,
        3,
        3,
    )
    assert (cohort["completed_count"], cohort["failed_count"]) == (3, 0)
    assert len({record["run_id"] for record in cohort["replicas"]}) == 3
    assert scenario.metadata["native_foundry_step_count"] == 6
    assert scenario.metadata["native_randomness_scope"] == "same_seed_submitted_each_step"
    assert report.prediction_mode_effective == "scientist"
    assert report.degraded and not report.trust_eligible
    assert all(
        row.ci_lower is None and row.ci_upper is None for row in scenario.outcome_comparisons
    )

    forecasts, requests, individual = [], [], []
    for index, (ref, record, employment) in enumerate(
        zip(forecast_refs, cohort["replicas"], expected_employment, strict=True)
    ):
        stored = validate_core_model_json_artifact(NativeForecastTrajectory, reader, ref)
        forecast, request = load_native_forecast(reader, ref, stored.request_ref)
        assert request.seed == record["seed"] == _SEEDS[index]
        assert request.run_id == record["run_id"]
        assert request.profile.purpose == "predictive_simulation"
        assert request.profile.origin == "t2"
        assert request.profile.time_index == ["t2", "t3"]
        assert request.profile.targets[0].model_dump() == {
            "metric": "income",
            "slot_id": "agents.income",
            "unit_id": "usd",
            "reduction": "mean",
        }
        assert request.cutoff == 2 and request.row_ids == ["r0", "r1"]
        assert ref == _edge_ref(
            reader, cohort_ref, f"native_forecast:{index + 1}", stored.ARTIFACT_KIND
        )
        assert forecast.simulation_refs == successes[2 * index : 2 * index + 2]
        assert forecast.execution_bindings_refs == [
            call.input_bindings_ref for call in attempts[2 * index : 2 * index + 2]
        ]
        binding = validate_core_model_json_artifact(
            FoundryInputBindings, reader, forecast.execution_bindings_refs[0]
        )
        baseline = load_state_snapshot(reader, snapshot_ref=binding.bound_state_snapshot_ref)
        assert baseline.agents.income.tolist() == [2.0]
        wage = float(baseline.firms.wage_offer[0] * baseline.agents.skill_level[0])
        assert wage == 10.0
        values = [
            float(load_state_snapshot(reader, snapshot_ref=state_ref).agents.income[0])
            for state_ref in forecast.state_snapshot_refs
        ]
        assert values == [wage if employed else 0.0 for employed in employment]
        assert forecast.values == {"income": values}
        forecasts.append(forecast)
        requests.append(request)
        individual.append(values)
    assert len({tuple(values) for values in individual}) == 3
    expected = [mean(values) for values in zip(*individual, strict=True)]
    assert expected == pytest.approx([10.0 / 3.0, 20.0 / 3.0])
    assert [row.y_pred for row in scenario.outcome_comparisons] == pytest.approx(expected)
    assert [row.y_true for row in scenario.outcome_comparisons] == [900.0, 901.0]
    record_property(
        "ensemble",
        json.dumps(
            {
                "cohort": cohort_ref.model_dump(mode="json"),
                "forecast_refs": projection["forecast_refs"],
                "trajectories": individual,
                "mean": expected,
            }
        ),
    )

    # For this one-agent world, sum and mean have identical values but different
    # meanings. Reopen the genuine selected states under the alternate request.
    middle = requests[1]
    foreign_target = middle.profile.targets[0].model_copy(update={"reduction": "sum"})
    foreign_profile = middle.profile.model_copy(update={"targets": [foreign_target]})
    foreign_request_ref = _republish(
        store, forecasts[1].request_ref, middle.model_copy(update={"profile": foreign_profile})
    )
    foreign_forecast_ref = _republish(
        store,
        forecast_refs[1],
        forecasts[1].model_copy(update={"request_ref": foreign_request_ref}),
        request=foreign_request_ref,
    )
    alternate, foreign_request = load_native_forecast(
        reader, foreign_forecast_ref, foreign_request_ref
    )
    assert alternate.values == forecasts[1].values
    assert alternate.state_snapshot_refs == forecasts[1].state_snapshot_refs
    assert foreign_request.profile.targets[0].reduction == "sum"
    _require_shared_native_basis(requests)
    with pytest.raises(ValueError, match="shared execution basis differs"):
        _require_shared_native_basis([requests[0], foreign_request, requests[2]])
    with pytest.raises(ValueError, match="request differs from selected plan"):
        _check_native_plan_request(reader, selected_plan, foreign_request, index=2)

    foreign_cohort = _republish(
        store, cohort_ref, cohort, **{"native_forecast:2": foreign_forecast_ref}
    )
    assert foreign_cohort.artifact_id == cohort_ref.artifact_id
    assert foreign_cohort.manifest_profile_sha256 != cohort_ref.manifest_profile_sha256
    altered_refs = [forecast_refs[0], foreign_forecast_ref, forecast_refs[2]]
    altered_scenario = scenario.model_copy(
        update={
            "metadata": {
                **scenario.metadata,
                "replica_cohort_ref": foreign_cohort.model_dump(mode="json"),
                "native_replica_projection": {
                    **projection,
                    "forecast_refs": [item.model_dump(mode="json") for item in altered_refs],
                },
            }
        }
    )
    replacements = {
        "native_forecast:native:2": foreign_forecast_ref,
        "replica_cohort:native": foreign_cohort,
    }
    altered_report_ref = persist_backtest_report(
        ensure_ir_artifact_store(store),
        report.model_copy(update={"scenarios": [altered_scenario]}),
        inputs=[
            input_ref_from_artifact_ref(replacements[edge.role], role=edge.role)
            if edge.role in replacements
            else edge
            for edge in reader.get_manifest(report_ref).inputs
        ],
    )
    with pytest.raises(ValueError, match="workflow status or forecast evidence mismatch"):
        load_backtest_report_for_consumption(reader, altered_report_ref)
    assert load_backtest_report_for_consumption(reader, report_ref) == report
    assert len(attempts) == 6


def test_native_middle_physical_failure_preserves_requested_three_without_survivor_mean(
    tmp_path, monkeypatch, record_property
):
    store, plan, _ = _labor_fixture(tmp_path)
    attempts, results, faults = _observe_foundry(monkeypatch, fail_middle=True)
    _, raw_report_ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    report_ref = ArtifactRef.model_validate(raw_report_ref.model_dump(mode="json"))
    record_property("selected_report_ref", report_ref.model_dump_json())
    assert [call.exec_config.seed for call in attempts] == [12, 12, 13, 13, 14, 14]
    assert faults == [attempts[3]]
    assert [result.ok for result in results] == [True, True, True, False, True, True]
    assert "method_execution_aborted" in results[3].notes
    assert results[3].simulation_result_ref is None

    reader = FileSystemCAS(store.root)
    report = load_backtest_report_for_consumption(reader, report_ref)
    scenario = report.scenarios[0]
    cohort_ref = ArtifactRef.model_validate(scenario.metadata["replica_cohort_ref"])
    cohort = load_core_json_artifact(reader, cohort_ref)
    assert (
        cohort["requested_count"],
        cohort["started_count"],
        cohort["foundry_execute_count"],
    ) == (
        3,
        3,
        3,
    )
    assert (cohort["completed_count"], cohort["failed_count"]) == (2, 1)
    assert [replica["seed"] for replica in cohort["replicas"]] == list(_SEEDS)
    assert [replica["status"] for replica in cohort["replicas"]] == [
        "completed",
        "failed",
        "completed",
    ]
    middle = cohort["replicas"][1]
    assert middle["failure"] == "; ".join(results[3].notes)
    assert ExecuteRequest.model_validate(middle["physical_request"]) == faults[0]
    opening_ref = results[2].simulation_result_ref
    assert opening_ref is not None
    opening = admit_execution_source(reader, opening_ref)
    assert opening.basis is not None
    assert (opening.basis.effective_seed, opening.basis.effective_step) == (13, 0)
    assert {
        edge.role
        for edge in reader.get_manifest(cohort_ref).inputs
        if edge.role.startswith("native_forecast:")
    } == {"native_forecast:1", "native_forecast:3"}
    assert report.prediction_mode_effective == "scientist_unavailable"
    assert report.degraded and not report.trust_eligible
    assert not scenario.outcome_comparisons
    assert "native_replica_projection" not in scenario.metadata
    assert len(attempts) == 6
    record_property(
        "partial_ensemble",
        json.dumps(
            {
                "cohort": cohort_ref.model_dump(mode="json"),
                "requested": cohort["requested_count"],
                "started": cohort["started_count"],
                "statuses": [replica["status"] for replica in cohort["replicas"]],
                "failure": middle["failure"],
                "middle_opening_simulation": opening_ref.model_dump(mode="json"),
                "completed_physical_calls": sum(result.ok for result in results),
            }
        ),
    )
