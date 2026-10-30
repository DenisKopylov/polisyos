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


def _fixture(tmp_path, *, count=3, horizon=2):
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
                kind="income_tax",
                target={
                    "kind": "predicate",
                    "field": "id",
                    "operator": SelectorOperator.EQUALS,
                    "value": 0,
                },
                schedule={"start_step": 0, "duration_steps": 2},
                params={"rate": Decimal("0.25")},
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


def test_native_mixed_with_legacy_cohort_reopens_selected_report(tmp_path, monkeypatch):
    """A native batch can census a real legacy cohort without changing legacy-only writes."""
    from polisyos.ir.analytics.backtest import persist_backtest_report
    from polisyos.ir.trinity import load_trinity_bundle_artifact
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
    from polisyos.scientist.methods.backtesting.native_replay import load_native_backtest_report

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


def test_native_multiple_replicas_are_explicitly_unsupported_before_work(tmp_path, monkeypatch):
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

    def forbidden(*args, **kwargs):
        pytest.fail("unsupported native replica projection reached the workflow")

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
    with pytest.raises(ValueError, match="replica status or candidate limitation mismatch"):
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
