"""Default Scientist/Foundry replay controls with a known fiscal transition."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pytest

from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.registry import build_default_registry_bundle
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle, persist_trinity_bundle_artifact
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    TargetPopulationSpec,
    persist_policy_candidate_schema,
)


def _favorable_leaderboard_inputs():
    from polisyos.ir.analytics.interference import (
        ExposureMappingType,
        InterferenceCertificate,
        InterferenceEffectDecomposition,
        InterferenceMethod,
        NetworkInterferenceReport,
    )
    from polisyos.ir.observation.contract_compilers import SpecificationCurveInput
    from polisyos.scientist.governance.calibration import (
        CalibrationAdversarialResult,
        CalibrationGovernanceReport,
    )
    from polisyos.scientist.governance.stress_scenarios import StressScenarioResult
    from polisyos.scientist.methods.discovery.utility_judge import (
        DownstreamUtilityReport,
        HypothesisUtilityScore,
    )

    return dict(
        candidate_ref=None,
        governance_report=CalibrationGovernanceReport(
            verdict="approve",
            adversarial_results=[
                CalibrationAdversarialResult(
                    alias="strategic_gaming_adversarial",
                    suite_id="strategic_gaming_v1",
                    required=True,
                    status="passed",
                )
            ],
        ),
        calibration_fit_score=0.9,
        stress_scenarios=StressScenarioResult(report_id="stress", robustness_score=0.9),
        specification_curve_input=SpecificationCurveInput(
            specification_ids=["s1", "s2"], estimates=[0.4, 0.35], standard_errors=[0.1, 0.1]
        ),
        downstream_utility_report=DownstreamUtilityReport(
            scores=[
                HypothesisUtilityScore(
                    hypothesis_id="h1",
                    identification_status="identified",
                    identifiability_score=1.0,
                    stability_score=0.8,
                    transportability_score=0.9,
                    composite_score=0.9,
                    rank=1,
                )
            ],
            recommended_shortlist=["h1"],
        ),
        network_interference_report=NetworkInterferenceReport(
            method=InterferenceMethod.PARTIAL_IPW,
            status="success",
            effects=InterferenceEffectDecomposition(
                direct_effect=0.2, spillover_effect=0.05, total_effect=0.25, n_units=10, n_treated=4
            ),
            exposure_mapping=ExposureMappingType.FRACTIONAL,
            n_units=10,
            n_treated=4,
        ),
        interference_certificate=InterferenceCertificate(
            supported_query_family="spillover", fallback_mode="pairwise", reduction_error_bound=0.05
        ),
        strategic_summary={"fallback_mode": "exact_equilibrium"},
    )


def _fixture(tmp_path, *, count=3, horizon=2, mechanism="income_tax", mechanism_params=None):
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    history = {
        "income": [1.0, 2.0, *[900.0 + i for i in range(horizon)]],
        "time_index": [f"t{i}" for i in range(2 + horizon)],
        "row_ids": [f"r{i}" for i in range(2 + horizon)],
    }
    data = store.put_json(
        history,
        PutOptions(kind="test.historical_rows", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    snapshot = store.put_json(
        DataSnapshot(data_ref=data),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[input_ref_from_artifact_ref(data, role="data_ref")],
        ),
        return_selected_profile=True,
    )
    model = ModelSpec(
        model_id="fiscal_model",
        data_snapshot_ref=str(snapshot.artifact_id),
        registry_bundle_ref=str(registry.bundle_ref.artifact_id),
    )
    policy = PolicySpec(
        policy_id="tax_policy",
        interventions=[
            InterventionSpec(
                intervention_id="tax",
                kind=mechanism,
                target={
                    "kind": "predicate",
                    "field": "id",
                    "operator": SelectorOperator.EQUALS,
                    "value": 0,
                },
                schedule={"start_step": 0, "duration_steps": 2},
                params=mechanism_params
                if mechanism_params is not None
                else {"rate": Decimal("0.25")},
            )
        ],
    )
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="predictive_fixture", domain=ProblemDomain.FISCAL),
        policy_spec=policy,
        model_spec=model,
    )
    candidate_ref = persist_policy_candidate_schema(
        store,
        PolicyCandidateSchema(
            candidate_id="fiscal_candidate",
            trinity_bundle=trinity,
            target_population=TargetPopulationSpec(population_id="test", description="Fixture"),
        ),
        inputs=[
            input_ref_from_artifact_ref(snapshot, role="world_model_data_snapshot"),
            input_ref_from_artifact_ref(registry.bundle_ref, role="world_model_registry"),
        ],
        return_selected_profile=True,
    )
    trinity_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store),
            trinity,
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")],
        ).model_dump(mode="json")
    )
    state = {
        "run_id": "native-fiscal",
        "inputs": {
            "trinity_bundle_ref": trinity_ref.model_dump(mode="json"),
            "registry_bundle_ref": registry.bundle_ref.model_dump(mode="json"),
            "data_snapshot_ref": snapshot.model_dump(mode="json"),
        },
        "params": {
            "workflow_id": "scientist_default",
            "foundry_input_binding_rules": [
                {
                    "binding_id": "income",
                    "source_path": "income.1",
                    "target_slot_id": "agents.income",
                },
                {
                    "binding_id": "reported_income",
                    "source_path": "income.1",
                    "target_slot_id": "agents.reported_income",
                },
            ],
            "backtest_native_forecast": {
                "purpose": "predictive_simulation",
                "origin": "t2",
                "time_index": [f"t{i}" for i in range(2, 2 + horizon)],
                "history_columns": ["income"],
                "targets": [
                    {
                        "metric": "income",
                        "slot_id": "agents.income",
                        "unit_id": "usd",
                        "reduction": "mean",
                    }
                ],
            },
        },
    }
    plan = HistoricalValidationPlan(
        plan_id="native",
        historical_data_ref=str(data.artifact_id),
        intervention_date="t2",
        intervention_step=2,
        ground_truth_outcomes={"income": [900.0 + i for i in range(horizon)]},
        prediction_source=PredictionSource.SCIENTIST,
        scientist_state=state,
        n_simulation_runs=count,
        random_seed=12,
    )
    return store, plan


def test_native_forecast_survives_persisted_report_readback(tmp_path, monkeypatch):
    """A real model trajectory must reach the fresh report's comparisons."""
    import logging

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.run.context import RunContext
    from polisyos.core.run.manifest import RunManifest
    from polisyos.core.trace.sink import JsonlTraceSink
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
    from polisyos.scientist.governance.report_currentness import resolve_current_governance_report
    from polisyos.scientist.methods.backtesting.native_replay import (
        execute_native_forecast,
        load_native_backtest_report,
        load_native_forecast,
    )
    from polisyos.scientist.nodes.builtins.state_keys import REPORT_GOVERNANCE_REPORT_REF
    from polisyos.scientist.orchestration.engine.context import (
        ExecutionContext,
        _EngineInvocationBinding,
        _load_engine_owned_invocation_input_state,
    )
    from polisyos.scientist.orchestration.engine.executor import WorkflowReport
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store, plan = _fixture(tmp_path, count=1)
    calls = []
    execute = DefaultFoundryPort.execute

    def observe(port, actual_store, request):
        calls.append(request)
        return execute(port, actual_store, request)

    monkeypatch.setattr(DefaultFoundryPort, "execute", observe)
    _, report_ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    fresh_store = FileSystemCAS(store.root)
    fresh = load_native_backtest_report(
        fresh_store, ArtifactRef.model_validate(report_ref.model_dump(mode="json"))
    )
    scenario = fresh.scenarios[0]
    workflow_status = scenario.metadata["native_workflow_status"]
    cohort_ref = ArtifactRef.model_validate(scenario.metadata["replica_cohort_ref"])
    cohort = load_core_json_artifact(fresh_store, cohort_ref)
    assert workflow_status == "ok"
    assert fresh.prediction_mode_effective == "scientist"
    assert (cohort["completed_count"], cohort["failed_count"]) == (1, 0)

    # Overall workflow success also permits skips. Read the selected node record
    # and its owner-bound input, then verify the packet's governance at that input.
    replica = cohort["replicas"][0]
    workflow_ref = ArtifactRef.model_validate(replica["workflow_report_ref"])
    workflow = WorkflowReport.model_validate(load_core_json_artifact(fresh_store, workflow_ref))
    packet_record = next(node for node in workflow.nodes if node.alias == "build_decision_packet")
    assert packet_record.status == "ok"
    packet_refs = [
        ref for ref in packet_record.artifacts if ref.kind == "scientist.decision_packet"
    ]
    assert len(packet_refs) == 1
    packet_ref = packet_refs[0]
    run_ref = ArtifactRef.model_validate(replica["run_manifest_ref"])
    run = RunManifest.model_validate(load_core_json_artifact(fresh_store, run_ref))
    finalization_ref = next(
        ref for ref in run.outputs if ref.kind == "scientist.workflow_state_finalization"
    )
    finalization = load_core_json_artifact(fresh_store, finalization_ref)
    final_state = ExperimentState.model_validate(
        load_core_json_artifact(
            fresh_store, ArtifactRef.model_validate(finalization["final_state_ref"])
        )
    )
    assert final_state.artifacts_index["decision_packet_ref"] == packet_ref
    trace_path = fresh_store.root / "runs" / run.run_id / "trace.jsonl"
    run_context = RunContext(
        store=fresh_store,
        trace=JsonlTraceSink(trace_path),
        run_manifest=run,
        _trace_path=trace_path,
    )
    packet_attempt = next(
        attempt
        for attempt in run_context.read_runtime_invocation_attempts()
        if attempt.basis.node_alias == "build_decision_packet"
    )
    packet_ctx = ExecutionContext(
        store=fresh_store,
        run=run_context,
        logger=logging.getLogger(__name__),
        _engine_invocation=_EngineInvocationBinding(
            run_id=run.run_id,
            attempt_id=packet_attempt.basis.attempt_id,
            basis_ref=packet_attempt.basis_ref,
            require_successful_completion=True,
        ),
    )
    packet_input = _load_engine_owned_invocation_input_state(packet_ctx, final_state)
    assert packet_input is not None
    governance_ref = packet_input.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    governance = resolve_current_governance_report(packet_ctx, packet_input, governance_ref)
    assert governance.is_current
    assert governance.report is not None
    assert governance.report.invocation_binding is not None
    assert governance.report.invocation_binding.node_alias == "refresh_governance"
    packet = load_core_json_artifact(fresh_store, packet_ref)
    assert packet["governance"]["currentness"] == "current"
    assert packet["governance"]["verdict"] == governance.report.verdict

    assert [row.y_pred for row in fresh.scenarios[0].outcome_comparisons] == pytest.approx(
        [1.5, 1.0]
    )
    assert [row.y_true for row in fresh.scenarios[0].outcome_comparisons] == [900.0, 901.0]
    assert not fresh.trust_eligible
    assert fresh.trust_score is None
    from polisyos.calibration.forecast_bridge import _load_verified_report
    from polisyos.ir.analytics.backtest import (
        NativeBacktestVerificationRequiredError,
        load_backtest_report,
    )
    from polisyos.scientist.nodes.builtins.decide.decision_packet.outcome_sections import (
        _build_backtest_section,
    )
    from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_BACKTEST_REPORT_REF

    report_core_ref = ArtifactRef.model_validate(report_ref.model_dump(mode="json"))
    with pytest.raises(NativeBacktestVerificationRequiredError):
        load_backtest_report(ensure_ir_artifact_store(fresh_store), report_ref)
    with pytest.raises(NativeBacktestVerificationRequiredError):
        _load_verified_report(fresh_store, report_ref)
    packet_context = SimpleNamespace(store=fresh_store)
    packet_section = _build_backtest_section(
        packet_context, {ARTIFACT_BACKTEST_REPORT_REF: report_core_ref}
    )
    assert packet_section is not None
    assert packet_section["backtest_report_status"] == "available"
    assert packet_section["overall_rmse"] == fresh.overall_rmse
    assert not packet_section["trust_eligible"]
    forecast_ref = ArtifactRef.model_validate(scenario.metadata["native_forecast_ref"])
    request_ref = ArtifactRef.model_validate(scenario.metadata["native_request_ref"])
    forecast, request = load_native_forecast(fresh_store, forecast_ref, request_ref)
    assert forecast.values == {"income": [1.5, 1.0]}
    assert request.profile.purpose == "predictive_simulation"
    assert request.randomness_scope == "same_seed_submitted_each_step"
    assert scenario.metadata["native_randomness_scope"] == request.randomness_scope
    assert scenario.metadata["native_limitations"] == request.limitations
    assert set(request.limitations) == {
        "native_external_source_provenance_not_established",
        "native_model_provenance_not_established",
        "native_producer_authenticity_not_established",
        "native_temporal_mapping_not_established",
        "native_observation_independence_not_established",
        "native_stochastic_continuity_not_established",
        "native_empirical_calibration_not_established",
        "native_causal_validity_not_established",
    }
    assert request.profile.time_index == ["t2", "t3"]
    snapshot = DataSnapshot.model_validate(
        load_core_json_artifact(fresh_store, request.data_snapshot_ref)
    )
    rows = load_core_json_artifact(fresh_store, snapshot.data_ref)
    assert rows == {"income": [1.0, 2.0], "row_ids": ["r0", "r1"], "time_index": ["t0", "t1"]}
    assert len(calls) == 2
    assert scenario.metadata["native_foundry_step_count"] == len(calls)
    assert all(call.exec_config.seed == 12 and call.return_selected_profile for call in calls)
    assert [call.input_bindings_ref for call in calls] == forecast.execution_bindings_refs
    assert (
        input_ref_from_artifact_ref(forecast_ref, role="native_forecast:native")
        in fresh_store.get_manifest(
            ArtifactRef.model_validate(report_ref.model_dump(mode="json"))
        ).inputs
    )

    # Preserve the authentic source edges while changing only the claimed values.
    forged = forecast.model_copy(update={"values": {"income": [2.0, 2.0]}})
    manifest = fresh_store.get_manifest(forecast_ref)
    forged_ref = fresh_store.put_json(
        forged,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="values differ from recomputed state observations"):
        load_native_forecast(FileSystemCAS(store.root), forged_ref, request_ref)

    # Preserve the real final delta and base while substituting a different
    # post-state, simulation and trajectory with correct selected edges.
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts import FoundryInputBindings, SimulationResult, SimulationResultRef
    from polisyos.foundry.execute import load_state_snapshot, put_state_snapshot

    final_sim_ref = forecast.simulation_refs[-1]
    simulation = validate_core_model_json_artifact(SimulationResult, fresh_store, final_sim_ref)
    sim_manifest = fresh_store.get_manifest(final_sim_ref)
    delta_edge = next(edge for edge in sim_manifest.inputs if edge.role == "state_delta")
    delta_ref = ArtifactRef(
        artifact_id=delta_edge.artifact_id,
        kind="foundry.state_delta",
        media_type="application/json",
        manifest_profile_sha256=delta_edge.manifest_profile_sha256,
    )
    binding = validate_core_model_json_artifact(
        FoundryInputBindings, fresh_store, forecast.execution_bindings_refs[-1]
    )
    actual_state = load_state_snapshot(fresh_store, snapshot_ref=forecast.state_snapshot_refs[-1])
    changed_agents = replace(
        actual_state.agents, income=np.asarray(actual_state.agents.income) + 100.0
    )
    fake_state = replace(actual_state, agents=changed_agents)
    fake_state_ref = put_state_snapshot(
        fresh_store,
        state=fake_state,
        step=int(np.asarray(fake_state.step)),
        inputs=[
            input_ref_from_artifact_ref(delta_ref, role="state_delta"),
            input_ref_from_artifact_ref(binding.bound_state_snapshot_ref, role="base_state"),
        ],
        return_selected_profile=True,
    )
    fake_simulation = simulation.model_copy(update={"state_snapshot_ref": fake_state_ref})
    fake_sim_ref = fresh_store.put_json(
        fake_simulation.to_artifact_payload(),
        PutOptions(
            kind=sim_manifest.kind,
            media_type=sim_manifest.media_type,
            schema=sim_manifest.artifact_schema,
            inputs=[
                input_ref_from_artifact_ref(fake_state_ref, role="state_snapshot")
                if edge.role == "state_snapshot"
                else edge
                for edge in sim_manifest.inputs
            ],
        ),
        return_selected_profile=True,
    )
    fake_trajectory = forecast.model_copy(
        update={
            "simulation_refs": [
                *forecast.simulation_refs[:-1],
                SimulationResultRef.model_validate(fake_sim_ref.model_dump(mode="json")),
            ],
            "state_snapshot_refs": [*forecast.state_snapshot_refs[:-1], fake_state_ref],
            "values": {"income": [*forecast.values["income"][:-1], 101.0]},
        }
    )
    fake_trajectory_ref = fresh_store.put_json(
        fake_trajectory,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=[
                input_ref_from_artifact_ref(fake_sim_ref, role="simulation.1")
                if edge.role == "simulation.1"
                else input_ref_from_artifact_ref(fake_state_ref, role="state.1")
                if edge.role == "state.1"
                else edge
                for edge in manifest.inputs
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="output state differs from applied state delta"):
        load_native_forecast(FileSystemCAS(store.root), fake_trajectory_ref, request_ref)

    # A real, selected extra execution input is outside this request's
    # admitted source scope, even when the feedback config itself is valid.
    from polisyos.core.contracts import FeedbackConfig, FeedbackConfigRef

    feedback_ref = fresh_store.put_json(
        FeedbackConfig(mode="off"),
        PutOptions(
            kind=FeedbackConfig.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=FeedbackConfig.ARTIFACT_SCHEMA_NAME, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    attempts = []
    context = SimpleNamespace(
        store=fresh_store,
        run=SimpleNamespace(run_manifest=SimpleNamespace(run_id=request.run_id)),
        foundry=SimpleNamespace(execute=lambda *args: attempts.append(args)),
    )
    with pytest.raises(ValueError, match="execution contains unscoped inputs"):
        execute_native_forecast(
            context,
            calls[0].model_copy(
                update={
                    "feedback_config_ref": FeedbackConfigRef.model_validate(
                        feedback_ref.model_dump(mode="json")
                    )
                }
            ),
            request_ref,
        )
    assert not attempts

    # A forged initial state or clock with valid selected lineage is refused
    # before the real Foundry port can receive a request.
    original_binding_ref = forecast.execution_bindings_refs[0]
    original_binding = validate_core_model_json_artifact(
        FoundryInputBindings, fresh_store, original_binding_ref
    )
    initial_state = load_state_snapshot(
        fresh_store, snapshot_ref=original_binding.bound_state_snapshot_ref
    )
    binding_manifest = fresh_store.get_manifest(original_binding_ref)
    for mutation in ("value", "clock"):
        if mutation == "value":
            altered = replace(
                initial_state,
                agents=replace(
                    initial_state.agents,
                    income=np.asarray(initial_state.agents.income) + 100.0,
                ),
            )
        else:
            altered = replace(
                initial_state,
                step=np.asarray(
                    int(np.asarray(initial_state.step)) + 1,
                    dtype=np.asarray(initial_state.step).dtype,
                ),
            )
        altered_ref = put_state_snapshot(
            fresh_store,
            state=altered,
            step=int(np.asarray(altered.step)),
            inputs=[
                input_ref_from_artifact_ref(
                    request.data_snapshot_ref, role="input.data_snapshot_ref"
                ),
                input_ref_from_artifact_ref(request.registry_ref, role="input.registry_bundle_ref"),
            ],
            return_selected_profile=True,
        )
        altered_binding = original_binding.model_copy(
            update={"bound_state_snapshot_ref": altered_ref}
        )
        altered_binding_ref = fresh_store.put_json(
            altered_binding,
            PutOptions(
                kind=binding_manifest.kind,
                media_type=binding_manifest.media_type,
                schema=binding_manifest.artifact_schema,
                inputs=[
                    input_ref_from_artifact_ref(
                        altered_ref, role="artifact.bound_state_snapshot_ref"
                    )
                    if edge.role == "artifact.bound_state_snapshot_ref"
                    else edge
                    for edge in binding_manifest.inputs
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        actual_execution = calls[0].model_copy(update={"input_bindings_ref": altered_binding_ref})
        attempts = []
        context = SimpleNamespace(
            store=FileSystemCAS(store.root),
            run=SimpleNamespace(run_manifest=SimpleNamespace(run_id=request.run_id)),
            foundry=SimpleNamespace(execute=lambda *args, attempts=attempts: attempts.append(args)),
        )
        with pytest.raises(ValueError, match="initial materialization differs from source"):
            execute_native_forecast(context, actual_execution, request_ref)
        assert not attempts

    # Rebuild a coherent selected candidate and derived Trinity with a different
    # policy, while retaining the actually executed simulation and its basis.
    from polisyos.ir.trinity import load_trinity_bundle_artifact

    original_trinity = load_trinity_bundle_artifact(
        ensure_ir_artifact_store(fresh_store), request.original_trinity_ref
    )
    changed_policy = original_trinity.policy_spec.model_dump(mode="json")
    changed_policy["interventions"][0]["params"]["rate"] = "0.5"
    other_trinity = original_trinity.model_copy(
        update={"policy_spec": PolicySpec.model_validate(changed_policy)}
    )
    candidate = validate_core_model_json_artifact(
        PolicyCandidateSchema, fresh_store, request.candidate_ref
    )
    other_candidate_ref = persist_policy_candidate_schema(
        fresh_store,
        candidate.model_copy(update={"trinity_bundle": other_trinity}),
        inputs=fresh_store.get_manifest(request.candidate_ref).inputs,
        return_selected_profile=True,
    )
    other_original_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(fresh_store),
            other_trinity,
            inputs=[input_ref_from_artifact_ref(other_candidate_ref, role="policy_candidate")],
        ).model_dump(mode="json")
    )
    other_model = other_trinity.model_spec.model_copy(
        update={"data_snapshot_ref": str(request.data_snapshot_ref.artifact_id)}
    )
    other_derived_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(fresh_store),
            other_trinity.model_copy(update={"model_spec": other_model}),
            inputs=[
                input_ref_from_artifact_ref(other_original_ref, role="original_trinity"),
                input_ref_from_artifact_ref(request.data_snapshot_ref, role="masked_snapshot"),
                input_ref_from_artifact_ref(other_candidate_ref, role="policy_candidate"),
            ],
        ).model_dump(mode="json")
    )
    other_request = request.model_copy(
        update={
            "original_trinity_ref": other_original_ref,
            "candidate_ref": other_candidate_ref,
            "trinity_ref": other_derived_ref,
        }
    )
    request_manifest = fresh_store.get_manifest(request_ref)
    replacement_refs = {
        "original_trinity": other_original_ref,
        "candidate": other_candidate_ref,
        "derived_trinity": other_derived_ref,
    }
    other_request_ref = fresh_store.put_json(
        other_request,
        PutOptions(
            kind=request_manifest.kind,
            media_type=request_manifest.media_type,
            schema=request_manifest.artifact_schema,
            inputs=[
                input_ref_from_artifact_ref(replacement_refs[edge.role], role=edge.role)
                if edge.role in replacement_refs
                else edge
                for edge in request_manifest.inputs
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    other_forecast = forecast.model_copy(update={"request_ref": other_request_ref})
    other_forecast_ref = fresh_store.put_json(
        other_forecast,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=[
                input_ref_from_artifact_ref(other_request_ref, role="request")
                if edge.role == "request"
                else edge
                for edge in manifest.inputs
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="execution basis differs from declared trajectory"):
        load_native_forecast(FileSystemCAS(store.root), other_forecast_ref, other_request_ref)

    # Missing version, randomness scope, or limitations cannot become defaults.
    for field in ("schema_version", "randomness_scope", "limitations", "one_limitation"):
        incomplete = request.model_dump(mode="json")
        if field == "one_limitation":
            incomplete["limitations"].pop()
            expected_error = "complete declared limitations"
        else:
            incomplete.pop(field)
            expected_error = field
        incomplete_ref = fresh_store.put_json(
            incomplete,
            PutOptions(
                kind=request_manifest.kind,
                media_type=request_manifest.media_type,
                schema=request_manifest.artifact_schema,
                inputs=request_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        incomplete_forecast = forecast.model_copy(update={"request_ref": incomplete_ref})
        incomplete_forecast_ref = fresh_store.put_json(
            incomplete_forecast,
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                inputs=[
                    input_ref_from_artifact_ref(incomplete_ref, role="request")
                    if edge.role == "request"
                    else edge
                    for edge in manifest.inputs
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match=expected_error):
            load_native_forecast(FileSystemCAS(store.root), incomplete_forecast_ref, incomplete_ref)

    # The report's native values must agree with the linked genuine trajectory.
    from polisyos.ir.analytics.backtest import persist_backtest_report

    # Preserve the residual and absolute truth while changing both values. The
    # aggregate statistics remain valid, so the IR owner still admits the bytes.
    first = scenario.outcome_comparisons[0]
    shifted_truth = -first.y_true
    shifted_prediction = shifted_truth + (first.y_pred - first.y_true)
    changed_row = first.model_copy(update={"y_pred": shifted_prediction, "y_true": shifted_truth})
    changed_scenario = scenario.model_copy(
        update={"outcome_comparisons": [changed_row, *scenario.outcome_comparisons[1:]]}
    )
    changed_report = fresh.model_copy(update={"scenarios": [changed_scenario]})
    forged_report_ref = persist_backtest_report(
        ensure_ir_artifact_store(fresh_store),
        changed_report,
        inputs=fresh_store.get_manifest(report_core_ref).inputs,
    )
    with pytest.raises(ValueError, match="predictions differ from verified trajectory"):
        load_native_backtest_report(
            FileSystemCAS(store.root),
            ArtifactRef.model_validate(forged_report_ref.model_dump(mode="json")),
        )
    bad_packet_section = _build_backtest_section(
        packet_context,
        {
            ARTIFACT_BACKTEST_REPORT_REF: ArtifactRef.model_validate(
                forged_report_ref.model_dump(mode="json")
            )
        },
    )
    assert bad_packet_section is not None
    assert bad_packet_section["backtest_report_status"] == "unavailable"
    assert not bad_packet_section["trust_eligible"]
    assert "overall_rmse" not in bad_packet_section

    # Legacy IR accepts a report with diagnostics omitted as limited. Native
    # consumers must not expose its now-unreconciled aggregate projections.
    from polisyos.ir.analytics.backtest import BacktestReport

    legacy_payload = fresh.model_dump(mode="json")
    legacy_payload.pop("metric_diagnostics")
    legacy_payload["overall_rmse"] = 0.0
    legacy_payload["overall_coverage_probability"] = 1.0
    unbound_report = BacktestReport.model_validate(legacy_payload)
    unbound_ref = persist_backtest_report(
        ensure_ir_artifact_store(fresh_store),
        unbound_report,
        inputs=fresh_store.get_manifest(report_core_ref).inputs,
    )
    unbound_core_ref = ArtifactRef.model_validate(unbound_ref.model_dump(mode="json"))
    with pytest.raises(ValueError, match="requires source-bound metric diagnostics"):
        load_native_backtest_report(fresh_store, unbound_core_ref)
    unbound_section = _build_backtest_section(
        packet_context, {ARTIFACT_BACKTEST_REPORT_REF: unbound_core_ref}
    )
    assert unbound_section is not None
    assert unbound_section["backtest_report_status"] == "unavailable"
    assert "overall_rmse" not in unbound_section

    for field, value, reason in (
        ("overall_macro_rmse", 0.0, "macro RMSE differs from source outcomes"),
        ("overall_r_squared", 0.5, "does not establish R-squared"),
    ):
        changed = fresh.model_copy(update={field: value})
        changed_ref = persist_backtest_report(
            ensure_ir_artifact_store(fresh_store),
            changed,
            inputs=fresh_store.get_manifest(report_core_ref).inputs,
        )
        with pytest.raises(ValueError, match=reason):
            load_native_backtest_report(
                fresh_store, ArtifactRef.model_validate(changed_ref.model_dump(mode="json"))
            )

    changed_metadata = dict(scenario.metadata)
    changed_metadata["native_workflow_status"] = "fail" if workflow_status == "ok" else "ok"
    status_scenario = scenario.model_copy(update={"metadata": changed_metadata})
    status_report = fresh.model_copy(update={"scenarios": [status_scenario]})
    status_ref = persist_backtest_report(
        ensure_ir_artifact_store(fresh_store),
        status_report,
        inputs=fresh_store.get_manifest(report_core_ref).inputs,
    )
    with pytest.raises(ValueError, match="workflow status or forecast evidence mismatch"):
        load_native_backtest_report(
            FileSystemCAS(store.root),
            ArtifactRef.model_validate(status_ref.model_dump(mode="json")),
        )

    other_mode = "scientist_candidate" if workflow_status == "ok" else "scientist"
    mode_report = fresh.model_copy(update={"prediction_mode_effective": other_mode})
    mode_ref = persist_backtest_report(
        ensure_ir_artifact_store(fresh_store),
        mode_report,
        inputs=fresh_store.get_manifest(report_core_ref).inputs,
    )
    with pytest.raises(ValueError, match="prediction mode differs from its scenarios"):
        load_native_backtest_report(
            FileSystemCAS(store.root), ArtifactRef.model_validate(mode_ref.model_dump(mode="json"))
        )

    # A port that changes the second submitted request must not produce a
    # trajectory, even when its individual execution basis is admissible.
    from polisyos.foundry.execute import admit_execution_source

    altered_results = []

    def change_second_execution(actual_store, actual_request):
        if altered_results:
            altered_config = actual_request.exec_config.model_copy(update={"mode": "perf"})
            actual_request = actual_request.model_copy(update={"exec_config": altered_config})
        result = execute(DefaultFoundryPort(), actual_store, actual_request)
        altered_results.append(result)
        return result

    context = SimpleNamespace(
        store=fresh_store,
        run=SimpleNamespace(run_manifest=SimpleNamespace(run_id=request.run_id)),
        foundry=SimpleNamespace(execute=change_second_execution),
    )
    with pytest.raises(ValueError, match="execution differs from submitted request"):
        execute_native_forecast(context, calls[0], request_ref)
    assert len(altered_results) == 2
    altered_basis = admit_execution_source(fresh_store, altered_results[1].simulation_result_ref)
    assert altered_basis.basis is not None and altered_basis.basis.effective_mode == "perf"

    # Remove an actual selected state blob after the unchanged fresh read passed.
    from polisyos.core.contracts import StateSnapshot

    state = validate_core_model_json_artifact(
        StateSnapshot, fresh_store, forecast.state_snapshot_refs[0]
    )
    blob_path, _ = fresh_store._paths(state.state_ref.artifact_id)
    blob_path.unlink()
    with pytest.raises((FileNotFoundError, ValueError)):
        load_native_forecast(FileSystemCAS(store.root), forecast_ref, request_ref)


def test_native_report_reaches_persisted_reissued_decision_packet(tmp_path):
    """A later Engine packet consumes the real selected report and refuses a forgery."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.run.manifest import RunManifest
    from polisyos.ir.analytics.backtest import persist_backtest_report
    from polisyos.scientist.methods.backtesting.native_replay import load_native_backtest_report
    from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
    from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode
    from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_BACKTEST_REPORT_REF
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor, WorkflowReport
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.workflows.builder import build_execution_context
    from polisyos.scientist.orchestration.workflows.default import default_workflow_spec

    store, plan = _fixture(tmp_path, count=1)
    _, report_ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    reader = FileSystemCAS(store.root)
    report_ref = ArtifactRef.model_validate(report_ref.model_dump(mode="json"))
    report = load_native_backtest_report(reader, report_ref)

    # Keep the report's source edges and residual statistics valid while making
    # one comparison disagree with its selected native trajectory.
    scenario = report.scenarios[0]
    assert report.prediction_mode_effective == "scientist"
    assert scenario.metadata["native_workflow_status"] == "ok"
    assert [row.y_pred for row in scenario.outcome_comparisons] == pytest.approx([1.5, 1.0])
    first = scenario.outcome_comparisons[0]
    shifted_truth = -first.y_true
    shifted_prediction = shifted_truth + (first.y_pred - first.y_true)
    shifted = first.model_copy(update={"y_pred": shifted_prediction, "y_true": shifted_truth})
    forged_scenario = scenario.model_copy(
        update={"outcome_comparisons": [shifted, *scenario.outcome_comparisons[1:]]}
    )
    forged_report = report.model_copy(update={"scenarios": [forged_scenario]})
    forged_ref = ArtifactRef.model_validate(
        persist_backtest_report(
            ensure_ir_artifact_store(reader),
            forged_report,
            inputs=reader.get_manifest(report_ref).inputs,
        ).model_dump(mode="json")
    )
    with pytest.raises(ValueError, match="predictions differ from verified trajectory"):
        load_native_backtest_report(reader, forged_ref)

    # Reissue through the actual default workflow's governance/evaluation/packet
    # invocations, after the producer has returned the selected report. Only
    # unrelated earlier nodes are excluded from this bounded later execution.
    default = default_workflow_spec()
    invocations = {node.alias: node for node in default.nodes}
    workflow = default.model_copy(
        update={
            "nodes": [
                invocations["run_governance"].model_copy(update={"depends_on": []}),
                invocations["run_evaluator"],
                invocations["refresh_governance"],
                invocations["build_decision_packet"].model_copy(
                    update={"depends_on": ["refresh_governance"]}
                ),
            ],
            "required_binds": ["run_id"],
        }
    )
    registry_ref = ArtifactRef.model_validate(plan.scientist_state["inputs"]["registry_bundle_ref"])

    def issue_packet(selected_report_ref, run_id):
        context = build_execution_context(reader, registry_ref, run_id=run_id)
        registry = NodeRegistry()
        for node in (RunGovernanceNode(), RunEvaluatorNode(), BuildDecisionPacketNode()):
            registry.register(node)
        initial = ExperimentState(
            run_id=run_id,
            inputs={"registry_bundle_ref": registry_ref},
            artifacts_index={ARTIFACT_BACKTEST_REPORT_REF: selected_report_ref},
            params={"random_seed": 12},
        )
        result = WorkflowExecutor(context, registry).execute(workflow, initial)
        assert result.run_ref is not None
        fresh_store = FileSystemCAS(store.root)
        run = RunManifest.model_validate(load_core_json_artifact(fresh_store, result.run_ref))
        finalization_ref = next(
            ref for ref in run.outputs if ref.kind == "scientist.workflow_state_finalization"
        )
        finalization = load_core_json_artifact(fresh_store, finalization_ref)
        final_state = ExperimentState.model_validate(
            load_core_json_artifact(
                fresh_store, ArtifactRef.model_validate(finalization["final_state_ref"])
            )
        )
        workflow_ref = final_state.reports_index["workflow_report"]
        persisted_workflow = WorkflowReport.model_validate(
            load_core_json_artifact(fresh_store, workflow_ref)
        )
        records = {node.alias: node for node in persisted_workflow.nodes}
        assert {alias: node.status for alias, node in records.items()} == {
            "run_governance": "ok",
            "run_evaluator": "ok",
            "refresh_governance": "ok",
            "build_decision_packet": "ok",
        }
        packet_ref = final_state.artifacts_index["decision_packet_ref"]
        assert packet_ref in records["build_decision_packet"].artifacts
        assert packet_ref in run.outputs
        assert input_ref_from_artifact_ref(selected_report_ref, role="backtest.report_ref") in (
            fresh_store.get_manifest(packet_ref).inputs
        )
        packet = load_core_json_artifact(fresh_store, packet_ref)
        assert packet["governance"]["currentness"] == "current"
        assert packet["backtest"]["report_ref"] == str(selected_report_ref.artifact_id)
        return packet["backtest"]

    good = issue_packet(report_ref, "native-packet-positive")
    assert good["backtest_report_status"] == "available"
    assert good["overall_rmse"] == report.overall_rmse
    assert good["degraded"] and not good["trust_eligible"]
    assert good["trust_score"] is None

    bad = issue_packet(forged_ref, "native-packet-forged")
    assert bad["backtest_report_status"] == "unavailable"
    assert not bad["trust_eligible"]
    assert bad["trust_score"] is None
    assert "overall_rmse" not in bad


def test_native_mixed_with_legacy_cohort_reopens_selected_report(tmp_path, monkeypatch):
    """A native batch can census a real legacy cohort without changing legacy-only writes."""
    import logging

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.run.context import RunContext
    from polisyos.ir.analytics.backtest import load_backtest_report, persist_backtest_report
    from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
    from polisyos.ir.trinity import load_trinity_bundle_artifact
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
    from polisyos.scientist.governance.backtest_matrix import (
        BacktestKind,
        BacktestMatrixRunner,
        _admit_matrix_for_leaderboard,
        verify_backtest_diagnostic_projection,
    )
    from polisyos.scientist.governance.calibration_leaderboard import CalibrationLeaderboard
    from polisyos.scientist.governance.calibration_validation import (
        CalibrationValidationBundle,
        load_calibration_validation_bundle,
        persist_calibration_validation_bundle,
    )
    from polisyos.scientist.methods.backtesting.native_replay import load_native_backtest_report
    from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.nodes.builtins.state_keys import (
        ARTIFACT_BACKTEST_REPORT_REF,
        ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store, plan = _fixture(tmp_path, count=1, horizon=1)
    legacy = plan.model_copy(deep=True, update={"plan_id": "legacy"})
    legacy.scientist_state["params"].pop("backtest_native_forecast")
    orchestrator = BacktestOrchestrator(cas=store)
    masked = orchestrator._masker.mask(orchestrator._load_historical_data(legacy), legacy)
    legacy_snapshot = ArtifactRef.model_validate(orchestrator._persist_masked_view(legacy, masked))
    original_ref = ArtifactRef.model_validate(plan.scientist_state["inputs"]["trinity_bundle_ref"])
    original = load_trinity_bundle_artifact(ensure_ir_artifact_store(store), original_ref)
    legacy_model = original.model_spec.model_copy(
        update={"data_snapshot_ref": str(legacy_snapshot.artifact_id)}
    )
    legacy_trinity = original.model_copy(update={"model_spec": legacy_model})
    registry_ref = ArtifactRef.model_validate(plan.scientist_state["inputs"]["registry_bundle_ref"])
    legacy_candidate = persist_policy_candidate_schema(
        store,
        PolicyCandidateSchema(
            candidate_id="legacy_fiscal_candidate",
            trinity_bundle=legacy_trinity,
            target_population=TargetPopulationSpec(population_id="test", description="Fixture"),
        ),
        inputs=[
            input_ref_from_artifact_ref(legacy_snapshot, role="world_model_data_snapshot"),
            input_ref_from_artifact_ref(registry_ref, role="world_model_registry"),
        ],
        return_selected_profile=True,
    )
    legacy_trinity_ref = persist_trinity_bundle_artifact(
        ensure_ir_artifact_store(store),
        legacy_trinity,
        inputs=[input_ref_from_artifact_ref(legacy_candidate, role="policy_candidate")],
    )
    legacy.scientist_state["inputs"]["trinity_bundle_ref"] = legacy_trinity_ref.model_dump(
        mode="json"
    )
    calls = []
    execute = DefaultFoundryPort.execute

    def observe(port, actual_store, execution):
        result = execute(port, actual_store, execution)
        calls.append(result)
        return result

    monkeypatch.setattr(DefaultFoundryPort, "execute", observe)
    _, report_ref = orchestrator.run_with_ref([plan, legacy])
    reader = FileSystemCAS(store.root)
    report_core_ref = ArtifactRef.model_validate(report_ref.model_dump(mode="json"))
    report = load_native_backtest_report(reader, report_core_ref)
    assert len(calls) == 2 and all(result.ok for result in calls)
    assert [scenario.scenario_id for scenario in report.scenarios] == ["native", "legacy"]
    assert report.scenarios[0].metadata["native_forecast_ref"]
    legacy_cohort = ArtifactRef.model_validate(report.scenarios[1].metadata["replica_cohort_ref"])
    assert legacy_cohort.manifest_profile_sha256 is not None
    assert report.prediction_mode_effective == "mixed"
    assert report.degraded and not report.trust_eligible
    legacy_only = orchestrator.run([legacy])
    legacy_only_ref = ArtifactRef.model_validate(
        legacy_only.scenarios[0].metadata["replica_cohort_ref"]
    )
    assert legacy_only_ref.manifest_profile_sha256 is None
    assert len(calls) == 3 and calls[-1].ok

    # Removing the selected cohort view makes the census unable to distinguish
    # a legacy scenario from a stripped native trajectory.
    inputs = [
        edge.model_copy(update={"manifest_profile_sha256": None})
        if edge.role == "replica_cohort:legacy"
        else edge
        for edge in reader.get_manifest(report_core_ref).inputs
    ]
    incomplete = persist_backtest_report(ensure_ir_artifact_store(reader), report, inputs=inputs)
    with pytest.raises(ValueError, match="selected"):
        load_native_backtest_report(reader, ArtifactRef.model_validate(incomplete.model_dump()))

    # Retain the genuine legacy cohort while replacing both report rows with an
    # exact-zero claim. The current legacy owner has no source reconciliation.
    actual_legacy = report.scenarios[1]
    assert actual_legacy.outcome_comparisons
    assert actual_legacy.outcome_comparisons[0].y_true != 123456.0

    def forge_rows(decorated_plan, **_kwargs):
        scenario = orchestrator._evaluator.evaluate(
            scenario_id=decorated_plan.plan_id,
            scenario_label=decorated_plan.plan_label,
            y_pred={"income": [123456.0]},
            y_true={"income": [123456.0]},
            metadata=dict(actual_legacy.metadata),
        )
        return scenario, [], "scientist", "scientist", []

    monkeypatch.setattr(orchestrator, "_run_single_scenario", forge_rows)
    bundle = BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id="legacy_cohort_forgery", contract_fqn="polisyos.tests.BacktestPlanBundle"
        ),
        required_fields=["income"],
        plans=[legacy.model_dump(mode="json")],
    )
    forged_matrix = BacktestMatrixRunner(store, orchestrator=orchestrator).run(
        dict.fromkeys(BacktestKind, bundle)
    )
    forged_report = load_backtest_report(
        ensure_ir_artifact_store(reader), forged_matrix.backtest_report_ref
    )
    assert all(
        row.y_true == row.y_pred == 123456.0
        for item in forged_report.scenarios
        for row in item.outcome_comparisons
    )
    assert not forged_report.trust_eligible
    assert verify_backtest_diagnostic_projection(forged_report).recomputed
    assert forged_matrix.metadata["report_trust_eligible"] is False
    assert all(
        item.metadata["replica_cohort_ref"] == legacy_cohort.model_dump(mode="json")
        for item in forged_report.scenarios
    )
    admitted, reasons = _admit_matrix_for_leaderboard(reader, forged_matrix)
    assert admitted and reasons == [
        "backtest_matrix_source_not_established",
        "backtest_matrix_report_not_trust_eligible",
    ]
    entry = CalibrationLeaderboard(store=reader).build_entry(
        run_id="forged_legacy_rows",
        backtest_matrix=forged_matrix,
        **_favorable_leaderboard_inputs(),
    )
    assert entry.metrics.composite_score is not None
    assert entry.metrics.gap_flags == [
        "backtest_matrix_source_not_established",
        "backtest_matrix_report_not_trust_eligible",
    ]
    assert not entry.metrics.eligible_for_promotion
    assert entry.metadata["composite_score_purpose"] == "candidate_diagnostic"

    # Reopen that forged report through the real persisted C5b and packet
    # consumers; neither may turn its exact-zero rows into trust authority.
    validation = CalibrationValidationBundle(
        run_id="legacy_cohort_forgery",
        candidate_ref=legacy_candidate,
        governance_verdict="approve",
        status="completed",
        backtest_matrix=forged_matrix,
        leaderboard_entry=entry,
    )
    forged_matrix_ref = ArtifactRef.model_validate(forged_matrix.backtest_report_ref.model_dump())
    validation_ref = persist_calibration_validation_bundle(
        reader,
        validation,
        inputs=list(reader.get_manifest(forged_matrix_ref).inputs),
        return_selected_profile=True,
    )
    validation_read = load_calibration_validation_bundle(reader, validation_ref)
    summary = validation_read.readout_summary()
    assert summary["backtest_report_status"] == "available"
    assert summary["backtest_trust_status"] == "not_established"
    assert summary["backtest_trust_score"] is None
    assert not summary["eligible_for_promotion"]

    packet_run = RunContext.start(
        store=reader, registry_bundle=registry_ref, run_id="R_legacy_forgery"
    )
    packet_ctx = ExecutionContext(store=reader, run=packet_run, logger=logging.getLogger(__name__))
    packet_state = ExperimentState(
        run_id="R_legacy_forgery",
        inputs={
            "trinity_bundle_ref": ArtifactRef.model_validate(legacy_trinity_ref.model_dump()),
            "registry_bundle_ref": registry_ref,
            "data_snapshot_ref": legacy_snapshot,
        },
        artifacts_index={
            ARTIFACT_BACKTEST_REPORT_REF: forged_matrix_ref,
            ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: ArtifactRef.model_validate(
                validation_ref.model_dump()
            ),
        },
    )
    packet_outcome = BuildDecisionPacketNode().execute(packet_ctx, packet_state)
    assert packet_outcome.status == "ok"
    packet = load_core_json_artifact(reader, packet_outcome.artifacts[0])
    assert packet["backtest"]["trust_score_status"] == "not_established"
    assert not packet["backtest"]["trust_eligible"]
    assert packet["backtest"]["trust_score"] is None
    assert packet["trust_profile"]["backtest_trust_score"] is None
    assert packet["calibration_validation"]["summary"]["backtest_trust_status"] == "not_established"
    assert not packet["calibration_validation"]["summary"]["eligible_for_promotion"]


def test_native_seed_preserves_compiled_audit_posture_and_step_limit(tmp_path, monkeypatch):
    """Real Foundry inherits a compiled limit instead of receiving explicit defaults."""
    from polisyos.foundry.execute import admit_execution_source
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort

    store, plan = _fixture(tmp_path, count=1)
    compile_real = DefaultFoundryPort.compile
    execute_real = DefaultFoundryPort.execute
    calls = []

    def limited_compile(port, actual_store, request):
        config = request.compile_config.model_copy(update={"mode": "audit", "max_steps": 1})
        return compile_real(
            port, actual_store, request.model_copy(update={"compile_config": config})
        )

    def observe(port, actual_store, request):
        result = execute_real(port, actual_store, request)
        calls.append((request, result))
        return result

    monkeypatch.setattr(DefaultFoundryPort, "compile", limited_compile)
    monkeypatch.setattr(DefaultFoundryPort, "execute", observe)
    report = BacktestOrchestrator(cas=store).run([plan])
    assert len(calls) == 2
    assert calls[0][1].ok and not calls[1][1].ok
    assert any("max_steps_reached:1>=1" in note for note in calls[1][1].notes)
    assert all(
        "mode" not in request.exec_config.model_fields_set
        and "max_steps" not in request.exec_config.model_fields_set
        and request.exec_config.seed == 12
        for request, _ in calls
    )
    admission = admit_execution_source(store, calls[0][1].simulation_result_ref)
    assert admission.basis is not None
    assert admission.basis.effective_mode == "audit"
    assert admission.basis.effective_max_steps == 1
    assert report.prediction_mode_effective == "scientist_unavailable"
    assert not report.scenarios[0].outcome_comparisons
    assert not report.trust_eligible


def test_native_registry_profiles_bind_real_compile_and_runtime_basis(tmp_path, monkeypatch):
    """Same-content selected profiles cannot be substituted at execution."""
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts import FoundryInputBindings
    from polisyos.foundry.execute import admit_execution_source
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
    from polisyos.scientist.methods.backtesting import native_replay

    store, plan = _fixture(tmp_path, count=1, horizon=1)
    compiled = []
    executed = []
    actual_compile = DefaultFoundryPort.compile
    actual_execute = DefaultFoundryPort.execute

    def observe_compile(port, actual_store, request):
        compiled.append(request)
        return actual_compile(port, actual_store, request)

    def observe_execute(port, actual_store, request):
        executed.append(request)
        return actual_execute(port, actual_store, request)

    monkeypatch.setattr(DefaultFoundryPort, "compile", observe_compile)
    monkeypatch.setattr(DefaultFoundryPort, "execute", observe_execute)
    _, report_ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    reader = FileSystemCAS(store.root)
    report = native_replay.load_native_backtest_report(
        reader, ArtifactRef.model_validate(report_ref.model_dump(mode="json"))
    )
    scenario = report.scenarios[0]
    forecast_ref = ArtifactRef.model_validate(scenario.metadata["native_forecast_ref"])
    request_ref = ArtifactRef.model_validate(scenario.metadata["native_request_ref"])
    forecast, request = native_replay.load_native_forecast(reader, forecast_ref, request_ref)
    assert len(compiled) == len(executed) == 1
    original_execution = executed[0]
    original = request.registry_ref
    manifest = reader.get_manifest(original)
    sibling = reader.put_bytes(
        reader.get_bytes(original),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=manifest.inputs,
            producer=ProducerInfo(component="test.execution-registry-sibling", version="1.0"),
        ),
        return_selected_profile=True,
    )
    assert sibling.artifact_id == original.artifact_id
    assert sibling.manifest_profile_sha256 != original.manifest_profile_sha256

    # Foundry's compiler really selects the sibling, keeping the candidate,
    # input binding, and runtime registry selections fixed.
    compiled_sibling = actual_compile(
        DefaultFoundryPort(),
        reader,
        compiled[0].model_copy(update={"registry_bundle_ref": sibling}),
    )
    assert compiled_sibling.ok and compiled_sibling.exec_plan_ref is not None
    variations = {
        "compile_registry_ref": original_execution.model_copy(
            update={"exec_plan_ref": compiled_sibling.exec_plan_ref}
        ),
        "runtime_registry_ref": original_execution.model_copy(
            update={"registry_bundle_ref": sibling}
        ),
    }
    registry_roles = (
        "binding_registry_ref",
        "compile_registry_ref",
        "runtime_registry_ref",
        "candidate_registry_bundle_ref",
    )

    class RegistryIdentityControl:
        def __init__(self, base):
            self.base = base

        def __getattr__(self, name):
            return getattr(self.base, name)

        def artifact_ref_identity_key(self, ref):
            return self.base.artifact_ref_identity_key(original if ref == sibling else ref)

    actual_put = native_replay._put
    for changed_role, changed_execution in variations.items():
        simulations = []
        trajectories = []

        def execute_real(actual_store, execution, simulations=simulations):
            result = actual_execute(DefaultFoundryPort(), actual_store, execution)
            simulations.append(result.simulation_result_ref)
            return result

        def capture_trajectory(*args, trajectories=trajectories, **kwargs):
            ref = actual_put(*args, **kwargs)
            if kwargs.get("kind") == native_replay.NativeForecastTrajectory.ARTIFACT_KIND:
                trajectories.append(ref)
            return ref

        context = SimpleNamespace(
            store=reader,
            run=SimpleNamespace(run_manifest=SimpleNamespace(run_id=request.run_id)),
            foundry=SimpleNamespace(execute=execute_real),
        )
        with monkeypatch.context() as capture:
            capture.setattr(native_replay, "_put", capture_trajectory)
            with pytest.raises(
                ValueError, match="execution basis differs from declared trajectory"
            ):
                native_replay.execute_native_forecast(context, changed_execution, request_ref)
        assert len(simulations) == len(trajectories) == 1
        admission = admit_execution_source(reader, simulations[0])
        assert admission.basis is not None
        for role in registry_roles:
            assert getattr(admission.basis, role) == (sibling if role == changed_role else original)

        # This selectively removes the profile distinction at the native
        # reader's comparison; all actual Foundry source admission remains in
        # force. Acceptance proves this particular equality decides the case.
        with monkeypatch.context() as removed:
            removed.setattr(native_replay, "cas", RegistryIdentityControl(native_replay.cas))
            loaded, _ = native_replay.load_native_forecast(reader, trajectories[0], request_ref)
        assert len(loaded.simulation_refs) == 1

    # A selected sibling on the binding itself is refused before a Foundry
    # call, independently of the execution-basis registry comparison.
    binding_ref = forecast.execution_bindings_refs[0]
    binding = validate_core_model_json_artifact(FoundryInputBindings, reader, binding_ref)
    binding_manifest = reader.get_manifest(binding_ref)
    changed_binding = binding.model_copy(update={"registry_bundle_ref": sibling})
    changed_binding_ref = reader.put_json(
        changed_binding,
        PutOptions(
            kind=binding_manifest.kind,
            media_type=binding_manifest.media_type,
            schema=binding_manifest.artifact_schema,
            inputs=[
                input_ref_from_artifact_ref(sibling, role=edge.role)
                if edge.role == "input.registry_bundle_ref"
                else edge
                for edge in binding_manifest.inputs
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    attempts = []
    context = SimpleNamespace(
        store=reader,
        run=SimpleNamespace(run_manifest=SimpleNamespace(run_id=request.run_id)),
        foundry=SimpleNamespace(execute=lambda *args: attempts.append(args)),
    )
    with pytest.raises(ValueError, match="initial input bindings differ from request"):
        native_replay.execute_native_forecast(
            context,
            original_execution.model_copy(update={"input_bindings_ref": changed_binding_ref}),
            request_ref,
        )
    assert not attempts


@pytest.mark.parametrize(
    "escape",
    [
        "future_binding",
        "wrong_unit",
        "wrong_time",
        "hidden_param",
        "prebound",
        "profileless",
        "profile_sibling",
        "different_holdout",
    ],
)
def test_native_admission_refuses_unscoped_inputs_before_workflow(tmp_path, monkeypatch, escape):
    import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module

    store, plan = _fixture(tmp_path, count=1)
    state = plan.scientist_state
    profile = state["params"]["backtest_native_forecast"]
    if escape == "future_binding":
        state["params"]["foundry_input_binding_rules"][0]["source_path"] = "income.2"
    elif escape == "wrong_unit":
        profile["targets"][0]["unit_id"] = "count"
    elif escape == "wrong_time":
        profile["time_index"][1] = "t99"
    elif escape == "hidden_param":
        state["params"]["future_income"] = [900, 901]
    elif escape == "prebound":
        state["inputs"]["input_bindings_ref"] = state["inputs"]["data_snapshot_ref"]
    elif escape == "profileless":
        state["inputs"]["registry_bundle_ref"].pop("manifest_profile_sha256")
    elif escape == "different_holdout":
        plan.ground_truth_outcomes["income"][0] = 42.0
    else:
        original = ArtifactRef.model_validate(state["inputs"]["registry_bundle_ref"])
        manifest = store.get_manifest(original)
        sibling = store.put_bytes(
            store.get_bytes(original),
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                canon=manifest.canon,
                inputs=manifest.inputs,
                producer=ProducerInfo(component="test.sibling", version="1.0"),
            ),
            return_selected_profile=True,
        )
        assert sibling.artifact_id == original.artifact_id
        assert sibling.manifest_profile_sha256 != original.manifest_profile_sha256
        state["inputs"]["registry_bundle_ref"] = sibling.model_dump(mode="json")

    def forbidden(*args, **kwargs):
        pytest.fail("unadmitted native source reached the workflow")

    monkeypatch.setattr(orchestrator_module, "run_experiment", forbidden)
    report = BacktestOrchestrator(cas=store).run([plan])
    assert report.prediction_mode_effective == "scientist_unavailable"
    assert report.degraded
    assert not report.trust_eligible
    assert not report.scenarios[0].outcome_comparisons
    expected_reason = {
        "future_binding": "binding is outside the admitted historical prefix",
        "wrong_unit": "target/slot/unit mismatch",
        "wrong_time": "source row/time axis or cutoff mismatch",
        "hidden_param": "unscoped Scientist parameters",
        "prebound": "requires exactly source, Trinity and registry inputs",
        "profileless": "requires selected artifact profiles",
        "profile_sibling": "exact lineage mismatch: world_model_registry",
        "different_holdout": "supplied outcomes differ from selected source holdout",
    }[escape]
    assert any(expected_reason in reason for reason in report.degraded_reasons)


def test_native_replica_mean_requires_complete_aligned_finite_axes():
    from polisyos.scientist.methods.backtesting.native_replay import _mean_native_values

    assert _mean_native_values([{"income": [0.0, 4.0]}, {"income": [2.0, 8.0]}]) == {
        "income": [1.0, 6.0]
    }
    assert _mean_native_values([{"income": [1e308]}, {"income": [1e308]}]) == {"income": [1e308]}
    with pytest.raises(ValueError, match="metric axes differ"):
        _mean_native_values([{"income": [1.0]}, {"other": [1.0]}])
    with pytest.raises(ValueError, match="time axes differ"):
        _mean_native_values([{"income": [1.0]}, {"income": [1.0, 2.0]}])
    with pytest.raises(ValueError, match="nonfinite"):
        _mean_native_values([{"income": [float("nan")]}, {"income": [2.0]}])


def test_native_replica_plan_reopens_selected_input_and_refuses_missing_edge(tmp_path):
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.scientist.methods.backtesting.native_replay import (
        _load_native_plan,
        _persist_native_plan,
    )

    store, plan = _fixture(tmp_path, count=2, horizon=1)
    ref = _persist_native_plan(store, plan)
    reader = FileSystemCAS(store.root)
    assert _load_native_plan(reader, ref) == plan
    manifest = reader.get_manifest(ref)
    stripped = reader.put_json(
        load_core_json_artifact(reader, ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=[edge for edge in manifest.inputs if edge.role != "registry"],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="exact lineage mismatch: registry"):
        _load_native_plan(reader, stripped)


def test_native_multi_replica_report_reopens_and_reconciles_complete_cohort(tmp_path):
    from copy import deepcopy

    import jax

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.foundry.compile.randomization import stable_hash
    from polisyos.ir.analytics.backtest import persist_backtest_report
    from polisyos.scientist.methods.backtesting.native_replay import (
        NativeForecastTrajectory,
        _load_native_plan,
        _require_shared_native_basis,
        _require_shared_native_execution,
        load_native_backtest_report,
        load_native_forecast,
    )

    def labor_draw(seed):
        key = jax.random.PRNGKey(seed)
        for salt in (stable_hash("stream:default"), stable_hash("node:tax")):
            key = jax.random.fold_in(key, salt & 0xFFFFFFFF)
            key = jax.random.fold_in(key, salt >> 32)
        step_key = jax.random.split(key)[1]
        employment_key = jax.random.split(step_key, 3)[0]
        return float(jax.random.uniform(employment_key, shape=(1,))[0])

    draws = [labor_draw(seed) for seed in (12, 13)]
    assert abs(draws[0] - draws[1]) > 1e-5
    threshold = Decimal(str((draws[0] + draws[1]) / 2.0))
    store, plan = _fixture(
        tmp_path,
        count=2,
        horizon=1,
        mechanism="labor_market",
        mechanism_params={"employment_threshold": threshold},
    )
    _, ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    reader = FileSystemCAS(store.root)
    report_ref = ArtifactRef.model_validate(ref.model_dump(mode="json"))
    report = load_native_backtest_report(reader, report_ref)
    scenario = report.scenarios[0]
    projection = scenario.metadata["native_replica_projection"]
    assert projection["method"] == "arithmetic_mean_complete_cohort_v1"
    forecast_refs = [ArtifactRef.model_validate(item) for item in projection["forecast_refs"]]
    plan_ref = ArtifactRef.model_validate(projection["plan_ref"])
    assert _load_native_plan(reader, plan_ref).n_simulation_runs == 2
    cohort_ref = ArtifactRef.model_validate(scenario.metadata["replica_cohort_ref"])
    cohort = load_core_json_artifact(reader, cohort_ref)
    assert (cohort["requested_count"], cohort["started_count"]) == (2, 2)
    assert (cohort["completed_count"], cohort["failed_count"]) == (2, 0)
    assert [item["seed"] for item in cohort["replicas"]] == [12, 13]
    assert len({item["run_id"] for item in cohort["replicas"]}) == 2
    forecasts = []
    requests = []
    for forecast_ref in forecast_refs:
        stored = NativeForecastTrajectory.model_validate(
            load_core_json_artifact(reader, forecast_ref)
        )
        forecast, request = load_native_forecast(reader, forecast_ref, stored.request_ref)
        forecasts.append(forecast)
        requests.append(request)
    assert len(forecasts) == 2
    _require_shared_native_basis(requests)
    _require_shared_native_execution(forecasts)
    altered_execution = forecasts[1].submitted_execution.model_copy(
        update={
            "exec_config": forecasts[1].submitted_execution.exec_config.model_copy(
                update={"mode": "audit"}
            )
        }
    )
    with pytest.raises(ValueError, match="submitted execution differs across cohort"):
        _require_shared_native_execution(
            [
                forecasts[0],
                forecasts[1].model_copy(update={"submitted_execution": altered_execution}),
            ]
        )
    trinity_ref = requests[1].trinity_ref
    trinity_manifest = reader.get_manifest(trinity_ref)
    sibling = reader.put_bytes(
        reader.get_bytes(trinity_ref),
        PutOptions(
            kind=trinity_manifest.kind,
            media_type=trinity_manifest.media_type,
            schema=trinity_manifest.artifact_schema,
            canon=trinity_manifest.canon,
            inputs=trinity_manifest.inputs,
            producer=ProducerInfo(component="test.replica-sibling", version="1.0"),
        ),
        return_selected_profile=True,
    )
    assert sibling.artifact_id == trinity_ref.artifact_id
    assert sibling.manifest_profile_sha256 != trinity_ref.manifest_profile_sha256
    with pytest.raises(ValueError, match="shared execution basis differs"):
        _require_shared_native_basis(
            [requests[0], requests[1].model_copy(update={"trinity_ref": sibling})]
        )
    individual = [forecast.values["income"][0] for forecast in forecasts]
    assert individual[0] != individual[1]
    observed_mean = scenario.outcome_comparisons[0].y_pred
    assert observed_mean == pytest.approx((individual[0] + individual[1]) / 2.0)
    assert observed_mean not in individual
    assert scenario.metadata["native_foundry_step_count"] == 2
    assert report.degraded and not report.trust_eligible
    assert all(
        row.ci_lower is None and row.ci_upper is None for row in scenario.outcome_comparisons
    )

    report_inputs = reader.get_manifest(report_ref).inputs
    missing_edge = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        report,
        inputs=[edge for edge in report_inputs if edge.role != "native_forecast:native:2"],
    )
    with pytest.raises(ValueError, match="exact lineage mismatch: native_forecast:native:2"):
        load_native_backtest_report(reader, ArtifactRef.model_validate(missing_edge.model_dump()))

    def republish(ref, payload, inputs):
        manifest = reader.get_manifest(ref)
        return reader.put_json(
            payload,
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                inputs=inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
            return_selected_profile=True,
        )

    def rebind_report(new_cohort, *, new_projection=None):
        metadata = dict(scenario.metadata)
        metadata["replica_cohort_ref"] = new_cohort.model_dump(mode="json")
        if new_projection is not None:
            metadata["native_replica_projection"] = new_projection
        altered = report.model_copy(
            update={"scenarios": [scenario.model_copy(update={"metadata": metadata})]}
        )
        ref = persist_backtest_report(
            ensure_ir_artifact_store(reader),
            altered,
            inputs=[
                input_ref_from_artifact_ref(new_cohort, role=edge.role)
                if edge.role == "replica_cohort:native"
                else edge
                for edge in report_inputs
            ],
        )
        return ArtifactRef.model_validate(ref.model_dump(mode="json"))

    cohort_inputs = reader.get_manifest(cohort_ref).inputs
    without_mask = republish(
        cohort_ref, cohort, [edge for edge in cohort_inputs if edge.role != "masked_data"]
    )
    with pytest.raises(ValueError, match="exact lineage mismatch: masked_data"):
        load_native_backtest_report(reader, rebind_report(without_mask))
    without_second = republish(
        cohort_ref,
        cohort,
        [edge for edge in cohort_inputs if edge.role != "native_forecast:2"],
    )
    with pytest.raises(ValueError, match="trajectory census mismatch"):
        load_native_backtest_report(reader, rebind_report(without_second))

    changed_plan = load_core_json_artifact(reader, plan_ref)
    changed_plan["n_simulation_runs"] = 3
    changed_plan_ref = republish(plan_ref, changed_plan, reader.get_manifest(plan_ref).inputs)
    changed_cohort = republish(
        cohort_ref,
        cohort,
        [
            input_ref_from_artifact_ref(changed_plan_ref, role=edge.role)
            if edge.role == "native_plan"
            else edge
            for edge in cohort_inputs
        ],
    )
    changed_projection = deepcopy(projection)
    changed_projection["plan_ref"] = changed_plan_ref.model_dump(mode="json")
    with pytest.raises(ValueError, match="cohort census mismatch"):
        load_native_backtest_report(
            reader, rebind_report(changed_cohort, new_projection=changed_projection)
        )

    changed_cohort_payload = deepcopy(cohort)
    changed_cohort_payload["replicas"][1]["seed"] = 12
    changed_cohort = republish(cohort_ref, changed_cohort_payload, cohort_inputs)
    with pytest.raises(ValueError, match="workflow status or forecast evidence mismatch"):
        load_native_backtest_report(reader, rebind_report(changed_cohort))

    first = scenario.outcome_comparisons[0]
    shifted_truth = -first.y_true
    shifted = first.model_copy(
        update={
            "y_true": shifted_truth,
            "y_pred": shifted_truth + (first.y_pred - first.y_true),
        }
    )
    forged = report.model_copy(
        update={"scenarios": [scenario.model_copy(update={"outcome_comparisons": [shifted]})]}
    )
    forged_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader), forged, inputs=report_inputs
    )
    with pytest.raises(ValueError, match="predictions differ from verified replica projection"):
        load_native_backtest_report(reader, ArtifactRef.model_validate(forged_ref.model_dump()))


def test_native_multi_replica_refuses_different_real_execution_postures(tmp_path, monkeypatch):
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
    from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode

    store, plan = _fixture(tmp_path, count=2, horizon=1)
    original_node = RunSimulationNode.execute
    original_foundry = DefaultFoundryPort.execute
    calls = []

    def vary_posture(node, ctx, state):
        if state.params.get("random_seed") == 13:
            node = replace(node, exec_config=node.exec_config.model_copy(update={"mode": "audit"}))
        return original_node(node, ctx, state)

    def observe(port, actual_store, request):
        result = original_foundry(port, actual_store, request)
        calls.append((request.exec_config.seed, request.exec_config.mode, result.ok))
        return result

    monkeypatch.setattr(RunSimulationNode, "execute", vary_posture)
    monkeypatch.setattr(DefaultFoundryPort, "execute", observe)
    with pytest.raises(ValueError, match="submitted execution differs across cohort"):
        BacktestOrchestrator(cas=store).run_with_ref([plan])
    assert calls == [(12, "dev", True), (13, "audit", True)]


def test_native_multi_replica_failure_preserves_full_cohort_without_survivor_mean(
    tmp_path, monkeypatch
):
    from copy import deepcopy

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.ir.analytics.backtest import persist_backtest_report
    from polisyos.scientist.methods.backtesting.native_replay import load_native_backtest_report
    from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome

    store, plan = _fixture(tmp_path, count=2, horizon=1)
    original = BuildDecisionPacketNode.execute

    def fail_second(node, ctx, state):
        if state.params.get("random_seed") == 13:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="native_second_failure", message="controlled later failure"),
            )
        return original(node, ctx, state)

    monkeypatch.setattr(BuildDecisionPacketNode, "execute", fail_second)
    _, ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    reader = FileSystemCAS(store.root)
    report_ref = ArtifactRef.model_validate(ref.model_dump(mode="json"))
    report = load_native_backtest_report(reader, report_ref)
    scenario = report.scenarios[0]
    assert report.prediction_mode_effective == "scientist_unavailable"
    assert not report.trust_eligible and not scenario.outcome_comparisons
    assert scenario.metadata["native_requested_count_status"] == "not_established"
    assert scenario.metadata["native_started_count_status"] == "not_established"
    cohort_ref = ArtifactRef.model_validate(scenario.metadata["replica_cohort_ref"])
    cohort = load_core_json_artifact(reader, cohort_ref)
    assert (cohort["requested_count"], cohort["started_count"]) == (2, 2)
    assert (cohort["completed_count"], cohort["failed_count"]) == (1, 1)
    assert cohort["replicas"][1]["failure"] == "native_second_failure: controlled later failure"

    manifest = reader.get_manifest(cohort_ref)
    for removed_role, reason in (
        ("native_forecast:1", "completed replica trajectory is missing"),
        ("native_forecast:2", "succeeded simulation trajectory is missing"),
        ("masked_data", "exact lineage mismatch: masked_data"),
        ("replica_2_exec_plan", "exact lineage mismatch: replica_2_exec_plan"),
        ("replica_2_input_bindings", "exact lineage mismatch: replica_2_input_bindings"),
        ("replica_2_simulation_result", "exact lineage mismatch: replica_2_simulation_result"),
        ("replica_2_metrics", "exact lineage mismatch: replica_2_metrics"),
        ("replica_2_workflow_report", "exact lineage mismatch: replica_2_workflow_report"),
        ("replica_2_run_manifest", "exact lineage mismatch: replica_2_run_manifest"),
    ):
        stripped = reader.put_json(
            cohort,
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                inputs=[edge for edge in manifest.inputs if edge.role != removed_role],
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
            return_selected_profile=True,
        )
        metadata = {**scenario.metadata, "replica_cohort_ref": stripped.model_dump(mode="json")}
        altered = report.model_copy(
            update={"scenarios": [scenario.model_copy(update={"metadata": metadata})]}
        )
        altered_ref = persist_backtest_report(
            ensure_ir_artifact_store(reader),
            altered,
            inputs=[
                input_ref_from_artifact_ref(stripped, role=edge.role)
                if edge.role == "replica_cohort:native"
                else edge
                for edge in reader.get_manifest(report_ref).inputs
            ],
        )
        with pytest.raises(ValueError, match=reason):
            load_native_backtest_report(
                reader, ArtifactRef.model_validate(altered_ref.model_dump())
            )

    # A retained failed workflow must agree with its cohort record even when
    # its selected trajectory edge was removed.
    forged_cohort = deepcopy(cohort)
    forged_cohort["replicas"][1]["workflow_status"] = "ok"
    forged_cohort["replicas"][1]["workflow_failures"] = []
    forged_ref = reader.put_json(
        forged_cohort,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=[edge for edge in manifest.inputs if edge.role != "native_forecast:2"],
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
        return_selected_profile=True,
    )
    forged_metadata = {
        **scenario.metadata,
        "replica_cohort_ref": forged_ref.model_dump(mode="json"),
    }
    forged_report = report.model_copy(
        update={"scenarios": [scenario.model_copy(update={"metadata": forged_metadata})]}
    )
    forged_report_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        forged_report,
        inputs=[
            input_ref_from_artifact_ref(forged_ref, role=edge.role)
            if edge.role == "replica_cohort:native"
            else edge
            for edge in reader.get_manifest(report_ref).inputs
        ],
    )
    with pytest.raises(ValueError, match="workflow status or forecast evidence mismatch"):
        load_native_backtest_report(
            reader, ArtifactRef.model_validate(forged_report_ref.model_dump())
        )

    # Removing payload pointers does not hide the still-selected workflow edges.
    hidden_workflow = deepcopy(cohort)
    hidden_workflow["replicas"][1]["workflow_report_ref"] = None
    hidden_workflow["replicas"][1].pop("run_manifest_ref")
    hidden_ref = reader.put_json(
        hidden_workflow,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=[edge for edge in manifest.inputs if edge.role != "native_forecast:2"],
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
        return_selected_profile=True,
    )
    hidden_metadata = {
        **scenario.metadata,
        "replica_cohort_ref": hidden_ref.model_dump(mode="json"),
    }
    hidden_report = report.model_copy(
        update={"scenarios": [scenario.model_copy(update={"metadata": hidden_metadata})]}
    )
    hidden_report_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        hidden_report,
        inputs=[
            input_ref_from_artifact_ref(hidden_ref, role=edge.role)
            if edge.role == "replica_cohort:native"
            else edge
            for edge in reader.get_manifest(report_ref).inputs
        ],
    )
    with pytest.raises(ValueError, match="retained evidence census mismatch"):
        load_native_backtest_report(
            reader, ArtifactRef.model_validate(hidden_report_ref.model_dump())
        )


def test_native_multi_replica_matrix_reopens_but_cannot_score_promotion(tmp_path, monkeypatch):
    import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module
    from polisyos.calibration.forecast_bridge import _load_verified_report
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.ir.analytics.backtest import (
        NativeBacktestVerificationRequiredError,
        load_backtest_report,
        persist_backtest_report,
    )
    from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
    from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixRunner
    from polisyos.scientist.governance.calibration_leaderboard import CalibrationLeaderboard
    from polisyos.scientist.methods.backtesting.native_replay import (
        load_backtest_report_for_consumption,
    )

    store, plan = _fixture(tmp_path, count=2, horizon=1)
    supplied = plan.model_copy(
        deep=True,
        update={
            "plan_id": "supplied",
            "prediction_source": PredictionSource.PROVIDED,
            "predicted_outcomes": {"income": [1.5]},
            "scientist_state": None,
            "n_simulation_runs": 1,
        },
    )

    def bundle(selected_plan):
        return BacktestPlanBundle(
            contract_target=ContractCompatibilityTarget(
                contract_id="test_native_matrix", contract_fqn="polisyos.tests.BacktestPlanBundle"
            ),
            required_fields=["income"],
            plans=[selected_plan.model_dump(mode="json")],
        )

    result = BacktestMatrixRunner(store).run(
        {BacktestKind.MACRO: bundle(plan), BacktestKind.CELL: bundle(supplied)}
    )
    assert result.backtest_report_ref is not None
    reader = FileSystemCAS(store.root)
    report = load_backtest_report_for_consumption(reader, result.backtest_report_ref)
    assert report.prediction_mode_effective == "mixed"
    assert not report.trust_eligible and report.degraded
    native = next(item for item in report.scenarios if item.scenario_id == "macro:native")
    assert len(native.metadata["native_replica_projection"]["forecast_refs"]) == 2
    assert [row.y_pred for row in native.outcome_comparisons] == pytest.approx([1.5])
    assert result.composite_score is None and result.worst_kind is None
    assert "native_predictive_simulation_only:macro" in result.gap_flags
    macro = next(item for item in result.kind_results if item.kind is BacktestKind.MACRO)
    assert macro.status == "gap" and macro.score is None
    assert report.metadata["backtest_kinds"]["macro"]["status"] == "gap"
    assert report.metadata["backtest_kinds"]["macro"]["score"] is None
    favorable_inputs = _favorable_leaderboard_inputs()
    leaderboard = CalibrationLeaderboard(store=reader)
    entry = leaderboard.build_entry(
        run_id="native_matrix_consumer", backtest_matrix=result, **favorable_inputs
    )
    assert entry.metrics.backtest_matrix_score is None
    assert entry.metrics.composite_score is None
    assert not entry.metrics.eligible_for_promotion
    assert "native_predictive_simulation_not_calibration" in entry.metrics.gap_flags

    # Keep the genuine selected native report while forging every public gap/score.
    forged = result.model_copy(deep=True)
    forged.gap_flags = []
    forged.composite_score = 1.0
    for item in forged.kind_results:
        item.status, item.gap_flag, item.score = "ok", None, 1.0
    forged_entry = leaderboard.build_entry(
        run_id="native_matrix_forgery", backtest_matrix=forged, **favorable_inputs
    )
    assert forged_entry.metrics.backtest_matrix_score is None
    assert forged_entry.metrics.composite_score is None
    assert not forged_entry.metrics.eligible_for_promotion
    assert forged_entry.metrics.gap_flags == [
        "missing_metric:backtest_matrix_score",
        "native_predictive_simulation_not_calibration",
    ]

    # The compatibility reader can read an ambiguous legacy-shaped report, but
    # its unresolved cohort edge cannot establish a leaderboard source.
    stripped_native = native.model_copy(
        update={
            "metadata": {
                key: value
                for key, value in native.metadata.items()
                if not key.startswith("native_")
            }
        }
    )
    stripped_report = report.model_copy(
        update={
            "scenarios": [
                stripped_native if item.scenario_id == native.scenario_id else item
                for item in report.scenarios
            ],
            "degraded_reasons": [
                reason
                for reason in report.degraded_reasons
                if not reason.startswith("native_") and ": native_" not in reason
            ],
        }
    )
    original_core_ref = ArtifactRef.model_validate(
        result.backtest_report_ref.model_dump(mode="json")
    )
    original_cohort_ref = ArtifactRef.model_validate(native.metadata["replica_cohort_ref"])
    cohort_manifest = reader.get_manifest(original_cohort_ref)
    assert any(edge.role == "native_plan" for edge in cohort_manifest.inputs)
    stripped_cohort_ref = reader.put_json(
        load_core_json_artifact(reader, original_cohort_ref),
        PutOptions(
            kind=cohort_manifest.kind,
            media_type=cohort_manifest.media_type,
            schema=cohort_manifest.artifact_schema,
            inputs=[
                edge
                for edge in cohort_manifest.inputs
                if not edge.role.startswith("native_forecast:")
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
        return_selected_profile=True,
    )
    selected_plan_scenario = stripped_native.model_copy(
        update={
            "metadata": {
                **stripped_native.metadata,
                "replica_cohort_ref": stripped_cohort_ref.model_dump(mode="json"),
            }
        }
    )
    selected_plan_report = stripped_report.model_copy(
        update={
            "scenarios": [
                selected_plan_scenario if item.scenario_id == native.scenario_id else item
                for item in stripped_report.scenarios
            ]
        }
    )
    selected_plan_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        selected_plan_report,
        inputs=[
            input_ref_from_artifact_ref(stripped_cohort_ref, role=edge.role)
            if edge.role == "replica_cohort:macro:native"
            else edge
            for edge in reader.get_manifest(original_core_ref).inputs
            if not edge.role.startswith("native_forecast:")
        ],
    )
    with pytest.raises(NativeBacktestVerificationRequiredError):
        load_backtest_report(ensure_ir_artifact_store(reader), selected_plan_ref)
    with pytest.raises(ValueError, match="native scenario trajectory metadata is missing"):
        load_backtest_report_for_consumption(reader, selected_plan_ref)
    retained_plan_matrix = forged.model_copy(update={"backtest_report_ref": selected_plan_ref})
    retained_plan_entry = leaderboard.build_entry(
        run_id="retained_native_plan", backtest_matrix=retained_plan_matrix, **favorable_inputs
    )
    assert retained_plan_entry.metrics.composite_score is None
    assert not retained_plan_entry.metrics.eligible_for_promotion
    assert "native_predictive_simulation_not_calibration" in retained_plan_entry.metrics.gap_flags

    ambiguous_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        stripped_report,
        inputs=[
            edge.model_copy(update={"manifest_profile_sha256": None})
            if edge.role == "replica_cohort:macro:native"
            else edge
            for edge in reader.get_manifest(original_core_ref).inputs
            if not edge.role.startswith("native_forecast:")
        ],
    )
    load_backtest_report(ensure_ir_artifact_store(reader), ambiguous_ref)
    ambiguous = forged.model_copy(update={"backtest_report_ref": ambiguous_ref})
    ambiguous_entry = leaderboard.build_entry(
        run_id="ambiguous_cohort_forgery", backtest_matrix=ambiguous, **favorable_inputs
    )
    assert ambiguous_entry.metrics.composite_score is None
    assert not ambiguous_entry.metrics.eligible_for_promotion
    assert "backtest_matrix_report_not_established" in ambiguous_entry.metrics.gap_flags
    with pytest.raises(NativeBacktestVerificationRequiredError):
        _load_verified_report(reader, result.backtest_report_ref)

    report_ref = ArtifactRef.model_validate(result.backtest_report_ref.model_dump(mode="json"))
    stripped = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        report,
        inputs=[
            edge
            for edge in reader.get_manifest(report_ref).inputs
            if edge.role != "native_forecast:macro:native:2"
        ],
    )
    with pytest.raises(ValueError, match="native_forecast:macro:native:2"):
        load_backtest_report_for_consumption(reader, stripped)

    def forbidden(*args, **kwargs):
        pytest.fail("conflicting matrix metadata reached the native producer")

    monkeypatch.setattr(orchestrator_module, "run_experiment", forbidden)
    for metadata in (
        {"backtest_kinds": {"macro": {"status": "ok", "score": 1}}},
        {"source_reconciliation_status": "recomputed"},
    ):
        with pytest.raises(ValueError, match="computed backtest matrix metadata is reserved"):
            BacktestMatrixRunner(store).run({BacktestKind.MACRO: bundle(plan)}, metadata=metadata)


def test_native_without_cutoff_is_unavailable_without_dispatch_or_predictions(
    tmp_path, monkeypatch
):
    import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module
    from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
    from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixRunner
    from polisyos.scientist.methods.backtesting.native_replay import (
        load_backtest_report_for_consumption,
    )

    store, plan = _fixture(tmp_path, count=2, horizon=1)
    plan = plan.model_copy(
        update={
            "intervention_date": "",
            "intervention_step": None,
            "pre_intervention_periods": None,
        }
    )

    def forbidden(*args, **kwargs):
        pytest.fail("a native plan without a cutoff reached the workflow")

    monkeypatch.setattr(orchestrator_module, "run_experiment", forbidden)
    _, ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    reader = FileSystemCAS(store.root)
    report = load_backtest_report_for_consumption(reader, ref)
    assert report.prediction_mode_effective == "scientist_unavailable"
    assert not report.scenarios[0].outcome_comparisons
    assert not report.trust_eligible
    assert any(
        "native_forecast_unavailable:historical_cutoff_missing" in r
        for r in report.degraded_reasons
    )

    bundle = BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id="native_no_cutoff", contract_fqn="polisyos.tests.BacktestPlanBundle"
        ),
        required_fields=["income"],
        plans=[plan.model_dump(mode="json")],
    )
    matrix = BacktestMatrixRunner(store).run({BacktestKind.MACRO: bundle})
    assert matrix.composite_score is None
    assert "native_predictive_simulation_only:macro" in matrix.gap_flags
    matrix_report = load_backtest_report_for_consumption(reader, matrix.backtest_report_ref)
    assert not matrix_report.scenarios[0].outcome_comparisons
    assert not matrix_report.trust_eligible


def test_native_multi_replica_admission_failure_is_unavailable_before_work(tmp_path, monkeypatch):
    import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module
    from polisyos.ir.analytics.backtest import persist_backtest_report
    from polisyos.scientist.methods.backtesting.native_replay import (
        load_backtest_report_for_consumption,
    )
    from polisyos.scientist.nodes.builtins.decide.decision_packet.outcome_sections import (
        _build_backtest_section,
    )
    from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_BACKTEST_REPORT_REF

    store, plan = _fixture(tmp_path, count=7)
    plan.scientist_state["params"]["foundry_input_binding_rules"][0]["source_path"] = "income.2"

    def forbidden(*args, **kwargs):
        pytest.fail("unadmitted native replica request reached the workflow")

    monkeypatch.setattr(orchestrator_module, "run_experiment", forbidden)
    _, report_ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    reader = FileSystemCAS(store.root)
    report = load_backtest_report_for_consumption(reader, report_ref)
    scenario = report.scenarios[0]
    assert report.prediction_mode_effective == "scientist_unavailable"
    assert scenario.metadata["native_requested_replicas"] == 7
    assert scenario.metadata["native_started_replicas"] == 0
    assert scenario.metadata["native_requested_count_status"] == "not_established"
    assert scenario.metadata["native_started_count_status"] == "not_established"
    assert not scenario.outcome_comparisons
    assert not report.trust_eligible
    section = _build_backtest_section(
        SimpleNamespace(store=reader),
        {ARTIFACT_BACKTEST_REPORT_REF: ArtifactRef.model_validate(report_ref.model_dump())},
    )
    assert section is not None and section["backtest_report_status"] == "available"
    assert section["prediction_mode_effective"] == "scientist_unavailable"
    assert not section["trust_eligible"]

    # A persisted pre-extension refusal remains readable as limited historical
    # data; its requested count was never independently established.
    historical = report.model_copy(
        update={
            "degraded_reasons": [
                reason
                for reason in report.degraded_reasons
                if ": native_forecast_unavailable:" not in reason
            ]
            + ["native: native_replica_projection_unsupported"]
        }
    )
    historical_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        historical,
        inputs=reader.get_manifest(ArtifactRef.model_validate(report_ref.model_dump())).inputs,
    )
    historical_read = load_backtest_report_for_consumption(reader, historical_ref)
    assert (
        historical_read.scenarios[0].metadata["native_requested_count_status"] == "not_established"
    )
    assert not historical_read.trust_eligible

    # There is no persisted input plan for the pre-dispatch refusal. A changed
    # count is therefore explicitly unestablished, never trusted as a fact.
    unbound_metadata = dict(scenario.metadata)
    unbound_metadata["native_requested_replicas"] = 8
    unbound_report = report.model_copy(
        update={"scenarios": [scenario.model_copy(update={"metadata": unbound_metadata})]}
    )
    unbound_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        unbound_report,
        inputs=reader.get_manifest(ArtifactRef.model_validate(report_ref.model_dump())).inputs,
    )
    unbound = load_backtest_report_for_consumption(reader, unbound_ref)
    assert unbound.scenarios[0].metadata["native_requested_replicas"] == 8
    assert unbound.scenarios[0].metadata["native_requested_count_status"] == "not_established"
    assert unbound.scenarios[0].metadata["native_started_count_status"] == "not_established"
    assert not unbound.trust_eligible

    empty_metrics = report.model_copy(update={"overall_rmse": 0.0, "overall_mae": 0.0})
    empty_metrics_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        empty_metrics,
        inputs=reader.get_manifest(ArtifactRef.model_validate(report_ref.model_dump())).inputs,
    )
    with pytest.raises(ValueError, match="empty outcomes cannot claim error metrics"):
        load_backtest_report_for_consumption(reader, empty_metrics_ref)
    empty_section = _build_backtest_section(
        SimpleNamespace(store=reader),
        {ARTIFACT_BACKTEST_REPORT_REF: ArtifactRef.model_validate(empty_metrics_ref.model_dump())},
    )
    assert empty_section is not None
    assert empty_section["backtest_report_status"] == "unavailable"
    assert "overall_rmse" not in empty_section

    empty_statistics = report.model_copy(
        update={
            "scenarios": [
                scenario.model_copy(update={"squared_error_sum": 1.0, "absolute_error_sum": 1.0})
            ]
        }
    )
    empty_statistics_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        empty_statistics,
        inputs=reader.get_manifest(ArtifactRef.model_validate(report_ref.model_dump())).inputs,
    )
    with pytest.raises(ValueError, match="empty scenario cannot claim error metrics"):
        load_backtest_report_for_consumption(reader, empty_statistics_ref)

    metadata = dict(scenario.metadata)
    metadata["native_started_replicas"] = 1
    changed = report.model_copy(
        update={"scenarios": [scenario.model_copy(update={"metadata": metadata})]}
    )
    forged_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        changed,
        inputs=reader.get_manifest(ArtifactRef.model_validate(report_ref.model_dump())).inputs,
    )
    with pytest.raises(ValueError, match="native unavailable scenario reason mismatch"):
        load_backtest_report_for_consumption(reader, forged_ref)


def test_native_admission_failure_survives_guarded_report_readback(tmp_path, monkeypatch):
    import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module
    from polisyos.ir.analytics.backtest import persist_backtest_report
    from polisyos.scientist.methods.backtesting.native_replay import (
        load_backtest_report_for_consumption,
    )

    store, plan = _fixture(tmp_path, count=1)
    plan.scientist_state["params"]["foundry_input_binding_rules"][0]["source_path"] = "income.2"

    def forbidden(*args, **kwargs):
        pytest.fail("unadmitted input reached the workflow")

    monkeypatch.setattr(orchestrator_module, "run_experiment", forbidden)
    _, report_ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    reader = FileSystemCAS(store.root)
    report = load_backtest_report_for_consumption(reader, report_ref)
    scenario = report.scenarios[0]
    assert scenario.metadata["native_requested_replicas"] == 1
    assert scenario.metadata["native_started_replicas"] == 0
    assert not scenario.outcome_comparisons
    assert report.prediction_mode_effective == "scientist_unavailable"
    assert report.degraded and not report.trust_eligible
    assert any(
        "binding is outside the admitted historical prefix" in reason
        for reason in report.degraded_reasons
    )

    metadata = dict(scenario.metadata)
    metadata.pop("native_started_replicas")
    changed = report.model_copy(
        update={"scenarios": [scenario.model_copy(update={"metadata": metadata})]}
    )
    forged_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        changed,
        inputs=reader.get_manifest(ArtifactRef.model_validate(report_ref.model_dump())).inputs,
    )
    with pytest.raises(
        ValueError, match="native unavailable scenario denominator or status mismatch"
    ):
        load_backtest_report_for_consumption(reader, forged_ref)


def test_native_horizon_reaches_phase4_gate_before_foundry_execution(tmp_path, monkeypatch):
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
    from polisyos.scientist.methods.backtesting.native_replay import (
        load_backtest_report_for_consumption,
    )

    store, plan = _fixture(tmp_path, count=1, horizon=13)

    def forbidden(*args, **kwargs):
        pytest.fail("long native horizon passed Phase4 without regime evidence")

    monkeypatch.setattr(DefaultFoundryPort, "execute", forbidden)
    _, report_ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    report = load_backtest_report_for_consumption(FileSystemCAS(store.root), report_ref)
    assert report.prediction_mode_effective == "scientist_unavailable"
    assert not report.trust_eligible
    assert not report.scenarios[0].outcome_comparisons
    assert report.scenarios[0].metadata["native_requested_replicas"] == 1
    assert report.scenarios[0].metadata["native_started_replicas"] == 1
    cohort_ref = ArtifactRef.model_validate(report.scenarios[0].metadata["replica_cohort_ref"])
    cohort = load_core_json_artifact(FileSystemCAS(store.root), cohort_ref)
    assert (cohort["started_count"], cohort["completed_count"], cohort["failed_count"]) == (1, 0, 1)
    assert cohort["foundry_execute_count"] == 0
    assert "phase4_regime_gate_failed" in cohort["replicas"][0]["failure"]


def test_native_post_simulation_failure_and_joint_status_forgery(tmp_path, monkeypatch):
    from copy import deepcopy

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.ir.analytics.backtest import persist_backtest_report
    from polisyos.scientist.methods.backtesting.native_replay import load_native_backtest_report
    from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome

    store, plan = _fixture(tmp_path, count=1)

    def fail_after_simulation(_self, _ctx, state):
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(code="native_test_post_failure", message="controlled later failure"),
        )

    monkeypatch.setattr(BuildDecisionPacketNode, "execute", fail_after_simulation)
    _, report_ref = BacktestOrchestrator(cas=store).run_with_ref([plan])
    report_core_ref = ArtifactRef.model_validate(report_ref.model_dump(mode="json"))
    reader = FileSystemCAS(store.root)
    report = load_native_backtest_report(reader, report_core_ref)
    scenario = report.scenarios[0]
    assert report.prediction_mode_effective == "scientist_candidate"
    assert not report.trust_eligible
    assert scenario.metadata["native_workflow_status"] == "fail"
    assert scenario.metadata["native_workflow_failures"] == [
        {
            "alias": "build_decision_packet",
            "status": "fail",
            "error": {
                "code": "native_test_post_failure",
                "message": "controlled later failure",
                "details": {},
            },
        }
    ]
    cohort_ref = ArtifactRef.model_validate(scenario.metadata["replica_cohort_ref"])
    cohort = load_core_json_artifact(reader, cohort_ref)
    assert (cohort["completed_count"], cohort["failed_count"]) == (0, 1)
    assert cohort["replicas"][0]["failure"] == "native_test_post_failure: controlled later failure"

    # Forge the workflow status, cohort status/counts and report mode together,
    # but retain the original failed node in the selected workflow record.
    workflow_ref = ArtifactRef.model_validate(cohort["replicas"][0]["workflow_report_ref"])
    workflow = load_core_json_artifact(reader, workflow_ref)
    workflow["status"] = "ok"
    workflow_manifest = reader.get_manifest(workflow_ref)
    forged_workflow = reader.put_json(
        workflow,
        PutOptions(
            kind=workflow_manifest.kind,
            media_type=workflow_manifest.media_type,
            schema=workflow_manifest.artifact_schema,
            inputs=workflow_manifest.inputs,
        ),
        return_selected_profile=True,
    )
    cohort_manifest = reader.get_manifest(cohort_ref)

    # Rebind the selected run, finalization and final state as well; the
    # original selected workflow specification remains the census anchor.
    run_ref = ArtifactRef.model_validate(cohort["replicas"][0]["run_manifest_ref"])
    run = load_core_json_artifact(reader, run_ref)
    finalization_ref = ArtifactRef.model_validate(
        next(
            item
            for item in run["outputs"]
            if item["kind"] == "scientist.workflow_state_finalization"
        )
    )
    finalization = load_core_json_artifact(reader, finalization_ref)
    final_state_ref = ArtifactRef.model_validate(finalization["final_state_ref"])
    final_state = load_core_json_artifact(reader, final_state_ref)

    def rewrite_payload(ref, payload):
        source_manifest = reader.get_manifest(ref)
        return reader.put_json(
            payload,
            PutOptions(
                kind=source_manifest.kind,
                media_type=source_manifest.media_type,
                schema=source_manifest.artifact_schema,
                inputs=source_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
            return_selected_profile=True,
        )

    def forge_run(replacement_workflow):
        altered_state = deepcopy(final_state)
        altered_state["reports_index"]["workflow_report"] = replacement_workflow.model_dump(
            mode="json"
        )
        altered_state_ref = rewrite_payload(final_state_ref, altered_state)
        altered_finalization = deepcopy(finalization)
        altered_finalization["final_state_ref"] = altered_state_ref.model_dump(mode="json")
        for binding in altered_finalization["output_bindings"]:
            if binding["state_path"] == "reports_index.workflow_report":
                binding["artifact_ref"] = replacement_workflow.model_dump(mode="json")
        altered_finalization_ref = rewrite_payload(finalization_ref, altered_finalization)
        replacements = {
            str(workflow_ref.artifact_id): replacement_workflow,
            str(final_state_ref.artifact_id): altered_state_ref,
            str(finalization_ref.artifact_id): altered_finalization_ref,
        }
        altered_run = deepcopy(run)
        altered_run["status"] = "ok"
        altered_run["errors"] = []
        altered_run["outputs"] = [
            replacements[item["artifact_id"]].model_dump(mode="json")
            if item["artifact_id"] in replacements
            else item
            for item in altered_run["outputs"]
        ]
        return rewrite_payload(run_ref, altered_run)

    def write_cohort(payload, inputs):
        return reader.put_json(
            payload,
            PutOptions(
                kind=cohort_manifest.kind,
                media_type=cohort_manifest.media_type,
                schema=cohort_manifest.artifact_schema,
                inputs=inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
            return_selected_profile=True,
        )

    def forge_cohort(replacement_workflow):
        altered_run_ref = forge_run(replacement_workflow)
        forged_cohort = deepcopy(cohort)
        forged_cohort["completed_count"] = 1
        forged_cohort["failed_count"] = 0
        forged_cohort["replicas"][0].update(
            status="completed",
            workflow_status="ok",
            workflow_failures=[],
            failure=None,
            workflow_report_ref=replacement_workflow.model_dump(mode="json"),
            run_manifest_ref=altered_run_ref.model_dump(mode="json"),
        )
        return write_cohort(
            forged_cohort,
            [
                input_ref_from_artifact_ref(replacement_workflow, role=edge.role)
                if edge.role == "replica_1_workflow_report"
                else input_ref_from_artifact_ref(altered_run_ref, role=edge.role)
                if edge.role == "replica_1_run_manifest"
                else edge
                for edge in cohort_manifest.inputs
            ],
        )

    def write_report(new_cohort_ref, *, claim_ok):
        metadata = dict(scenario.metadata)
        metadata["replica_cohort_ref"] = new_cohort_ref.model_dump(mode="json")
        if claim_ok:
            metadata["native_workflow_status"] = "ok"
            metadata["native_workflow_failures"] = []
            metadata["prediction_source_effective"] = "scientist"
        changed_scenario = scenario.model_copy(update={"metadata": metadata})
        report_changes = {"scenarios": [changed_scenario]}
        if claim_ok:
            report_changes.update(
                prediction_mode_effective="scientist",
                degraded_reasons=[
                    reason
                    for reason in report.degraded_reasons
                    if not reason.endswith("scientist_replica_cohort_incomplete")
                ],
            )
        changed_report = report.model_copy(update=report_changes)
        inputs = [
            input_ref_from_artifact_ref(new_cohort_ref, role="replica_cohort:native")
            if edge.role == "replica_cohort:native"
            else edge
            for edge in reader.get_manifest(report_core_ref).inputs
        ]
        ref = persist_backtest_report(
            ensure_ir_artifact_store(reader), changed_report, inputs=inputs
        )
        return ArtifactRef.model_validate(ref.model_dump(mode="json"))

    with pytest.raises(ValueError, match="workflow status differs from its node failures"):
        load_native_backtest_report(
            reader, write_report(forge_cohort(forged_workflow), claim_ok=True)
        )

    # A jointly reselected run cannot hide the failed node by deleting it;
    # the selected workflow spec still requires that alias and node identity.
    stripped_workflow = deepcopy(workflow)
    stripped_workflow["status"] = "ok"
    stripped_workflow["nodes"] = [
        node for node in stripped_workflow["nodes"] if node["alias"] != "build_decision_packet"
    ]
    stripped_ref = rewrite_payload(workflow_ref, stripped_workflow)
    with pytest.raises(ValueError, match="workflow node census differs from selected workflow"):
        load_native_backtest_report(reader, write_report(forge_cohort(stripped_ref), claim_ok=True))

    # A self-consistent count with a record saying it never started is also invalid.
    not_started = deepcopy(cohort)
    not_started["replicas"][0]["workflow_started"] = False
    not_started_ref = write_cohort(not_started, cohort_manifest.inputs)
    with pytest.raises(ValueError, match="workflow status or forecast evidence mismatch"):
        load_native_backtest_report(reader, write_report(not_started_ref, claim_ok=False))


def test_fresh_report_rejects_one_native_trajectory_removed_from_two_scenarios(
    tmp_path, monkeypatch
):
    from polisyos.ir.analytics.backtest import persist_backtest_report
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
    from polisyos.scientist.methods.backtesting.native_replay import (
        load_backtest_report_for_consumption,
        load_native_backtest_report,
    )

    store, plan = _fixture(tmp_path, count=1)
    second = plan.model_copy(deep=True, update={"plan_id": "native_second"})
    calls = []
    execute = DefaultFoundryPort.execute

    def observe(port, actual_store, request):
        calls.append(request)
        return execute(port, actual_store, request)

    monkeypatch.setattr(DefaultFoundryPort, "execute", observe)
    _, report_ref = BacktestOrchestrator(cas=store).run_with_ref([plan, second])
    report_core_ref = ArtifactRef.model_validate(report_ref.model_dump(mode="json"))
    reader = FileSystemCAS(store.root)
    report = load_native_backtest_report(reader, report_core_ref)
    assert len(calls) == 4
    assert [s.scenario_id for s in report.scenarios] == ["native", "native_second"]
    assert all(s.metadata.get("native_forecast_ref") for s in report.scenarios)
    inputs = reader.get_manifest(report_core_ref).inputs

    def persist_with_metadata(metadata, report_inputs):
        changed = report.scenarios[1].model_copy(update={"metadata": metadata})
        mutated = report.model_copy(update={"scenarios": [report.scenarios[0], changed]})
        ref = persist_backtest_report(
            ensure_ir_artifact_store(reader), mutated, inputs=report_inputs
        )
        return ArtifactRef.model_validate(ref.model_dump(mode="json"))

    missing_ref = dict(report.scenarios[1].metadata)
    missing_ref.pop("native_forecast_ref")
    with pytest.raises(ValueError, match="native scenario trajectory metadata is missing"):
        load_native_backtest_report(reader, persist_with_metadata(missing_ref, inputs))

    # Even removing every native metadata key and the direct forecast edge
    # cannot hide the selected native edge retained by this scenario's cohort.
    stripped = {
        key: value
        for key, value in report.scenarios[1].metadata.items()
        if not key.startswith("native_")
    }
    stripped_inputs = [edge for edge in inputs if edge.role != "native_forecast:native_second"]
    with pytest.raises(ValueError, match="native scenario trajectory metadata is missing"):
        load_native_backtest_report(reader, persist_with_metadata(stripped, stripped_inputs))

    for missing_reason in (
        "native_predictive_simulation_only",
        "native_temporal_mapping_not_established",
    ):
        changed_report = report.model_copy(
            update={
                "degraded_reasons": [
                    reason
                    for reason in report.degraded_reasons
                    if reason != f"native_second: {missing_reason}"
                ]
            }
        )
        assert f"native: {missing_reason}" in changed_report.degraded_reasons
        changed_ref = persist_backtest_report(
            ensure_ir_artifact_store(reader), changed_report, inputs=inputs
        )
        with pytest.raises(ValueError, match="declared limitations are incomplete"):
            load_native_backtest_report(
                reader, ArtifactRef.model_validate(changed_ref.model_dump())
            )

    # Keep the first selected trajectory intact while removing the second
    # trajectory and cohort. Its own mode or native reason must still prevent
    # the intact scenario from masking the lost evidence.
    for marker in ("candidate", "unavailable", "reason"):
        second_metadata = dict(stripped)
        second_metadata.pop("replica_cohort_ref", None)
        if marker == "candidate":
            second_metadata["prediction_source_effective"] = "scientist_candidate"
        elif marker == "unavailable":
            second_metadata["prediction_source_effective"] = "scientist_unavailable"
        second = report.scenarios[1].model_copy(update={"metadata": second_metadata})
        first_mode = report.scenarios[0].metadata["prediction_source_effective"]
        second_mode = second_metadata["prediction_source_effective"]
        report_mode = first_mode if first_mode == second_mode else "mixed"
        reasons = [
            reason
            for reason in report.degraded_reasons
            if marker == "reason" or not reason.startswith("native_second: native_")
        ]
        altered_report = report.model_copy(
            update={
                "scenarios": [report.scenarios[0], second],
                "prediction_mode_effective": report_mode,
                "degraded_reasons": reasons,
            }
        )
        altered_ref = persist_backtest_report(
            ensure_ir_artifact_store(reader),
            altered_report,
            inputs=[
                edge
                for edge in inputs
                if edge.role
                not in {
                    "native_forecast:native_second",
                    "replica_cohort:native_second",
                }
            ],
        )
        expected = (
            "native unavailable scenario denominator or status mismatch"
            if marker == "unavailable"
            else "native scenario trajectory metadata is missing"
        )
        with pytest.raises(ValueError, match=expected):
            load_native_backtest_report(
                reader, ArtifactRef.model_validate(altered_ref.model_dump())
            )

    # The canonical lower-layer reader must also recognize the selected
    # cohort evidence when all direct native markers have been stripped.
    from polisyos.ir.analytics.backtest import (
        NativeBacktestVerificationRequiredError,
        load_backtest_report,
    )

    stripped_scenarios = [
        scenario.model_copy(
            update={
                "metadata": {
                    key: value
                    for key, value in scenario.metadata.items()
                    if not key.startswith("native_")
                }
            }
        )
        for scenario in report.scenarios
    ]
    stripped_report = report.model_copy(update={"scenarios": stripped_scenarios})
    stripped_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader),
        stripped_report,
        inputs=[edge for edge in inputs if not edge.role.startswith("native_forecast:")],
    )
    with pytest.raises(NativeBacktestVerificationRequiredError):
        load_backtest_report(ensure_ir_artifact_store(reader), stripped_ref)

    profileless_inputs = [
        edge.model_copy(update={"manifest_profile_sha256": None})
        if edge.role.startswith("replica_cohort:")
        else edge
        for edge in inputs
        if not edge.role.startswith("native_forecast:")
    ]
    profileless_report_ref = persist_backtest_report(
        ensure_ir_artifact_store(reader), stripped_report, inputs=profileless_inputs
    )
    with pytest.raises(NativeBacktestVerificationRequiredError):
        load_backtest_report(ensure_ir_artifact_store(reader), profileless_report_ref)
    with pytest.raises(ValueError, match="selected lineage missing"):
        load_backtest_report_for_consumption(reader, profileless_report_ref)

    # A mixed report may retain only one scenario's candidate-mode marker.
    # Its report-wide mode cannot be used as a substitute for that census.
    for retained_mode in ("scientist_candidate", "scientist_unavailable"):
        candidate_metadata = dict(stripped_scenarios[0].metadata)
        candidate_metadata["prediction_source_effective"] = retained_mode
        mixed_scenarios = [
            stripped_scenarios[0].model_copy(update={"metadata": candidate_metadata}),
            stripped_scenarios[1],
        ]
        mixed = stripped_report.model_copy(
            update={
                "scenarios": mixed_scenarios,
                "prediction_mode_effective": "mixed",
                "degraded_reasons": [
                    reason
                    for reason in stripped_report.degraded_reasons
                    if not reason.startswith("native_") and ": native_" not in reason
                ],
            }
        )
        mixed_ref = persist_backtest_report(
            ensure_ir_artifact_store(reader), mixed, inputs=profileless_inputs
        )
        with pytest.raises(NativeBacktestVerificationRequiredError):
            load_backtest_report(ensure_ir_artifact_store(reader), mixed_ref)
        with pytest.raises(ValueError, match="selected lineage missing"):
            load_backtest_report_for_consumption(reader, mixed_ref)


@pytest.mark.parametrize(
    "statuses", [("completed",), ("completed", "completed"), ("completed", "failed")]
)
def test_native_cohort_writer_supplies_typed_selected_ref_to_every_projection_branch(
    tmp_path, statuses
):
    """The real IR mapping writer bridges to a fresh native cohort reader."""
    from polisyos.scientist.methods.backtesting.native_replay import _load_selected_native_cohort
    from polisyos.scientist.methods.backtesting.orchestrator import (
        _BacktestReplicaCohort,
        _BacktestReplicaRecord,
    )

    store = FileSystemCAS(tmp_path / "cohort-writer-cas")
    masked = store.put_json(
        {"masked": True},
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
        return_selected_profile=True,
    )
    cohort = _BacktestReplicaCohort(
        plan_id="cohort-return-shape",
        masked_data_snapshot_ref=masked.model_dump(mode="json"),
        requested_count=len(statuses),
        started_count=len(statuses),
        foundry_execute_count=0,
        completed_count=statuses.count("completed"),
        failed_count=statuses.count("failed"),
        replicas=[
            _BacktestReplicaRecord(
                index=index,
                run_id=f"cohort-{index}",
                seed=index,
                workflow_started=True,
                status=status,
            )
            for index, status in enumerate(statuses, start=1)
        ],
    )
    ref = BacktestOrchestrator(cas=store)._persist_replica_cohort(
        cohort,
        inputs=[input_ref_from_artifact_ref(masked, role="masked_data")],
        select_profile=True,
    )
    assert isinstance(ref, ArtifactRef)
    assert ref.manifest_profile_sha256 is not None
    assert store.verify(ref).ok
    fresh = FileSystemCAS(store.root)
    assert _load_selected_native_cohort(fresh, ref) == cohort
    assert fresh.get_manifest(ref).inputs[0].artifact_id == masked.artifact_id
