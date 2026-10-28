from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts import input_ref_from_artifact_ref, load_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    Metrics,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.snapshots import put_state_snapshot
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.evidence.sources import EvidenceSourcesConfig
from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import (
    FunnelExecutedWorkPacket,
    FunnelOutcome,
    FunnelStageResult,
    FunnelTicket,
)
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreStatus,
    SourceMetricObservation,
    _assess_search_fiscal_measurement,
    observe_source_government_balance,
    source_observation_input_refs,
)
from polisyos.scientist.nodes.builtins.decide import (
    policy_runtime_support,
    run_policy_blueprint_runtime,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
    prepare_runtime_session,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationArtifact,
    PolicyRuntimeProvenance,
    ProductionPolicyEvaluationBackend,
    persist_funnel_executed_work_packet,
    persist_policy_evaluation_vector_to_store,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _PolicyRuntimeWorkflowEngine,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_METRICS_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)

_FALLBACK_LIMITATION = "search_objective_fiscal_measurement_unavailable"
_CONFIG = {
    "data_config": {"subsample_fraction": 1.0, "stratified": False},
    "estimation_config": {"estimator": "matching", "n_bootstrap": 500},
    "scenario_config": {"grid": "full"},
    "subgroup_config": {"top_k": 99},
    "model_config": {"scm_complexity": "full"},
}


def _policy_candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="problem_production_source_join",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id="policy_production_source_join"),
            model_spec=ModelSpec(
                model_id="model_production_source_join",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        candidate_id="candidate_production_source_join",
    )


def _candidate_payload(candidate: PolicyCandidateSchema) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "semantic": {
            "interventions": [{"type": "tax_reform", "parameters": {"rate": 0.2}}],
            "objectives": [{"name": "gdp_growth"}],
        },
    }


def _run_production_workflow(
    store: FileSystemCAS,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef,
    simulation_metrics: dict[str, float],
    *,
    signature: str,
    source_measurement: SourceMetricObservation | None = None,
) -> tuple[FunnelOrchestrator, FunnelTicket, FunnelOutcome]:
    context: dict[str, Any] = {
        **deepcopy(_CONFIG),
        "store": store,
        "pinned_input_signature": signature,
        "policy_candidate_schema": candidate,
        "policy_candidate_ref": candidate_ref,
        "simulation_metrics": dict(simulation_metrics),
        "transfer_context": {
            "run_id": "run_production_source_join",
            "task_family": "policy",
            "domain": "fiscal",
            "tenant_hash": "tenant-test",
        },
    }
    if source_measurement is not None:
        context["policy_runtime_source_measurement"] = source_measurement.model_dump(
            mode="json", exclude_none=False
        )
    engine = _PolicyRuntimeWorkflowEngine(
        fidelity="full",
        backend=ProductionPolicyEvaluationBackend(),
    )
    orchestrator = FunnelOrchestrator(
        [Level4FullFidelity(workflow_engine=engine, estimated_cost_usd=0.2)]
    )
    ticket = orchestrator.submit(_candidate_payload(candidate), context)
    outcome = orchestrator.advance(ticket, target_level=4)
    return orchestrator, ticket, outcome


def _put_profiled_balance_source(
    store: FileSystemCAS,
    *,
    value: float = 35.0,
    snapshot_value: float | None = None,
    step: int = 3,
) -> tuple[SimulationResultRef, MetricsRef, StateSnapshotRef]:
    """Persist exact Foundry result, scalar metric, and materialized state refs."""
    metrics = Metrics(values={"government_balance": value})
    metrics_ref_raw = store.put_json(
        metrics,
        PutOptions(
            kind=Metrics.ARTIFACT_KIND,
            media_type=Metrics.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=Metrics.ARTIFACT_SCHEMA_NAME,
                version=Metrics.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    metrics_ref = MetricsRef.model_validate(metrics_ref_raw.model_dump(mode="python"))

    state = replace(
        GlobalState.empty(n_agents=1, n_firms=1),
        step=jnp.asarray(step, dtype=jnp.int32),
        government_balance=jnp.asarray(
            value if snapshot_value is None else snapshot_value,
            dtype=jnp.float32,
        ),
    )
    snapshot_ref_raw = put_state_snapshot(
        store,
        state=state,
        step=step,
        return_selected_profile=True,
    )
    snapshot_ref = StateSnapshotRef.model_validate(snapshot_ref_raw.model_dump(mode="python"))

    simulation = SimulationResult(
        schema_version="1.4",
        exec_plan_ref=ExecPlanRef(artifact_id="sha256:" + "f" * 64),
        metrics_ref=metrics_ref,
        state_snapshot_ref=snapshot_ref,
        execution_source_status="not_recorded",
    )
    simulation_ref_raw = store.put_json(
        simulation,
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=SimulationResult.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                input_ref_from_artifact_ref(metrics_ref, role="metrics"),
                input_ref_from_artifact_ref(snapshot_ref, role="state_snapshot"),
            ],
        ),
        return_selected_profile=True,
    )
    simulation_ref = SimulationResultRef.model_validate(
        simulation_ref_raw.model_dump(mode="python")
    )
    return simulation_ref, metrics_ref, snapshot_ref


@pytest.mark.integration
def test_runtime_session_recomputes_indexed_balance_before_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Produce the candidate observation from state refs before selected CAS write."""
    run_id = "run_profiled_source_measurement_session"
    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store)
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle.bundle_ref,
        run_id=run_id,
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.{run_id}"),
    )
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(
        store,
        candidate,
        return_selected_profile=True,
    )
    simulation_ref, metrics_ref, snapshot_ref = _put_profiled_balance_source(store)
    state = ExperimentState(
        run_id=run_id,
        artifacts_index={
            ARTIFACT_SIMULATION_RESULT_REF: simulation_ref,
            ARTIFACT_METRICS_REF: metrics_ref,
            ARTIFACT_STATE_SNAPSHOT_REF: snapshot_ref,
        },
    )
    synthetic_artifact = PolicyRuntimeEvaluationArtifact(
        simulation_metrics={},
        simulation_results={},
        evaluation_vector=PolicyEvaluationVector(candidate_id=candidate.candidate_id),
        fidelity="selection",
        provenance=PolicyRuntimeProvenance(
            backend_kind="synthetic_transport_fixture",
            fidelity_mode="selection",
            promotable_source=False,
        ),
    )
    evaluated_metrics: dict[str, Any] = {}

    def build_evaluation(_candidate: PolicyCandidateSchema, **kwargs: Any) -> Any:
        evaluated_metrics.update(kwargs["simulation_metrics"])
        return synthetic_artifact

    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "ProductionPolicyEvaluationBackend",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "_world_model_record_from_state",
        lambda _state: None,
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "policy_runtime_input_signature",
        lambda **_kwargs: "synthetic-input-signature",
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "build_policy_runtime_evaluation",
        build_evaluation,
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "_resolve_existing_strategic_output",
        lambda _state: SimpleNamespace(
            strategic_scm_ref=None,
            strategic_response_bundle_ref=None,
            strategic_response_summary=None,
        ),
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "_build_runtime_abstraction_metadata",
        lambda _ctx, *, artifacts_index: {},
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "_resolve_benchmark_scope",
        lambda **_kwargs: {
            "artifact_family": "controlled_source_fixture",
            "query_type": "policy_runtime",
            "estimator_name": "matching",
            "readiness_target": "candidate_only",
            "claim_mode": "candidate_only",
        },
    )

    session = prepare_runtime_session(
        ctx,
        state,
        runtime_request=SimpleNamespace(
            candidate=candidate,
            candidate_ref=candidate_ref,
            cross_graph_profile=None,
            evidence_sources=EvidenceSourcesConfig(),
            simulation_metrics={
                "government_balance": 35.0,
                "gov_balance": 35.0,
                "budget_deficit": 0.0,
                "deficit": 0.0,
                "gdp_change": 0.1,
            },
            uncertainty_envelope=None,
            distributional_report=None,
            causal_report=None,
            governance_report=None,
            ambiguity_certificate=None,
            ambiguity_certificate_ref=None,
        ),
        owner=run_policy_blueprint_runtime,
    )

    assert session.selection_evaluation is not None
    assert session.selection_evaluation.status == "not_established"
    assert session.selection_evaluation.notes == ["policy_vector_score_assessment_missing"]
    assert session.selection_evaluation.selection_metrics == {}
    assert session.selection_evaluation.holdout_metrics == {}
    assert session.selection_evaluation.sample_counts == {}
    assert session.selection_evaluation.promotable is False
    assert session.selection_evaluation.metadata["objective_score_status"] == "not_established"
    assert evaluated_metrics == {"gdp_change": 0.1}
    measurement = session.source_measurement
    assert measurement is not None
    assert measurement.source_status == "observed"
    assert measurement.value == 35.0
    assert measurement.unit_id == "usd"
    assert measurement.scope == "global"
    assert measurement.quantity_kind == "stock"
    assert measurement.time_basis == "simulation_step"
    assert measurement.objective_status == "not_established"
    assert measurement.objective_value is None

    selection_ref = session.selection_vector_ref
    assert selection_ref is not None
    assert selection_ref.manifest_profile_sha256 is not None
    selection_payload = load_core_json_artifact(store, selection_ref)
    assert selection_payload["metadata"]["policy_runtime_source_measurement"] == (
        measurement.model_dump(mode="json", exclude_none=False)
    )
    manifest = store.get_manifest(selection_ref)
    expected_inputs = {
        ("candidate", candidate_ref.artifact_id.hex),
        *(
            (role, source_ref.artifact_id.hex)
            for role, source_ref in source_observation_input_refs(measurement)
        ),
    }
    assert {(item.role, item.artifact_id.hex) for item in manifest.inputs} == expected_inputs


def test_source_balance_rejects_sparse_method_input_snapshot_as_simulation_state(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref, metrics_ref, _ = _put_profiled_balance_source(store, value=35.0)
    sparse_snapshot_ref = put_state_snapshot(
        store,
        state={
            "baseline": np.asarray([1.0], dtype=np.float64),
            "scenario": np.asarray([2.0], dtype=np.float64),
        },
        step=3,
        return_selected_profile=True,
    )
    original_simulation = SimulationResult.model_validate(
        load_core_json_artifact(store, simulation_ref)
    )
    simulation = original_simulation.model_copy(update={"state_snapshot_ref": sparse_snapshot_ref})
    simulation_ref_raw = store.put_json(
        simulation,
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=SimulationResult.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                input_ref_from_artifact_ref(metrics_ref, role="metrics"),
                input_ref_from_artifact_ref(sparse_snapshot_ref, role="state_snapshot"),
            ],
        ),
        return_selected_profile=True,
    )
    simulation_ref = SimulationResultRef.model_validate(
        simulation_ref_raw.model_dump(mode="python")
    )

    observed = observe_source_government_balance(
        store,
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
        state_snapshot_ref=sparse_snapshot_ref,
    )

    assert observed.source_status == "invalid"
    assert observed.value is None
    assert observed.limitation == "simulation_state_snapshot_layout_not_global_state"


def test_profiled_balance_observation_rejects_unselected_or_divergent_sources(
    tmp_path: Path,
) -> None:
    """Require selected profiles and a value reproduced from the bound snapshot."""
    store = FileSystemCAS(tmp_path / "cas")
    simulation_ref, metrics_ref, snapshot_ref = _put_profiled_balance_source(
        store,
        value=35.0,
        snapshot_value=34.0,
    )

    divergent = observe_source_government_balance(
        store,
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
        state_snapshot_ref=snapshot_ref,
    )
    assert divergent.source_status == "invalid"
    assert divergent.predicate_status == "not_established"
    assert divergent.value is None
    assert divergent.objective_status == "not_established"
    assert divergent.objective_value is None

    profileless_result_ref = SimulationResultRef(artifact_id=simulation_ref.artifact_id)
    profileless = observe_source_government_balance(
        store,
        simulation_result_ref=profileless_result_ref,
        metrics_ref=metrics_ref,
        state_snapshot_ref=snapshot_ref,
    )
    assert profileless.source_status == "invalid"
    assert profileless.value is None
    assert profileless.objective_value is None


def _assert_fresh_consumer_rejects(
    orchestrator: FunnelOrchestrator,
    ticket: FunnelTicket,
    result: FunnelStageResult,
) -> None:
    orchestrator._admit_executed_work_packet(ticket, result, 4)

    assert result.executed_work_packet_status == "rejected"
    assert result.feedback["policy_runtime_work_packet_status"] == "rejected"
    assert result.feedback["policy_runtime_work_packet_rejection_reason"] == (
        "work_packet_binding_mismatch"
    )


@pytest.mark.integration
def test_profiled_foundry_balance_is_persisted_but_not_ranked_as_budget_deficit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep physical stock evidence content-bound and outside the fiscal objective score."""
    monkeypatch.setattr(
        policy_runtime_support,
        "_production_policy_evaluation_safety_blockers",
        lambda **_: (),
    )

    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(
        store,
        candidate,
        return_selected_profile=True,
    )
    simulation_ref, metrics_ref, snapshot_ref = _put_profiled_balance_source(store)
    measurement = observe_source_government_balance(
        store,
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
        state_snapshot_ref=snapshot_ref,
    )

    assert measurement.source_status == "observed"
    assert measurement.predicate_status == "recomputed"
    assert measurement.metric_id == "government_balance"
    assert measurement.slot_id == "government.balance"
    assert measurement.value == 35.0
    assert measurement.unit_id == "usd"
    assert measurement.scope == "global"
    assert measurement.quantity_kind == "stock"
    assert measurement.simulation_step == 3
    assert measurement.time_basis == "simulation_step"
    assert measurement.objective_status == "not_established"
    assert measurement.objective_value is None
    assert all(
        ref is not None and ref.manifest_profile_sha256 is not None
        for ref in (
            measurement.source_result_ref,
            measurement.source_metrics_ref,
            measurement.source_snapshot_ref,
        )
    )

    orchestrator, ticket, outcome = _run_production_workflow(
        store,
        candidate,
        candidate_ref,
        {
            "government_balance": 35.0,
            "gov_balance": 35.0,
            "budget_deficit": 0.0,
            "deficit": 0.0,
            "gdp_change": 0.1,
        },
        signature="profiled-source-balance-not-a-deficit",
        source_measurement=measurement,
    )

    result = outcome.stage_results[4]
    assert result.executed_work_packet_status == "available"
    packet_ref = result.executed_work_packet_ref
    assert packet_ref is not None
    packet = FunnelExecutedWorkPacket.model_validate(load_core_json_artifact(store, packet_ref))
    source_vector_payload = load_core_json_artifact(store, packet.source_result_ref)
    assert packet.source_result_ref.manifest_profile_sha256 is not None
    assert source_vector_payload["score_assessment"] is not None
    assessment_payload = source_vector_payload["score_assessment"]
    assert {"objective_ref", "rule_spec", "source_sha256", "value"} <= set(assessment_payload)
    assert assessment_payload["source_sha256"] is None
    assert assessment_payload["value"] is None
    source_vector_manifest = store.get_manifest(packet.source_result_ref)
    assert source_vector_manifest.canon is not None
    assert source_vector_manifest.canon.exclude_none is False
    runtime_invocation = source_vector_payload["metadata"]["policy_runtime_invocation"]
    runtime_bootstrap = source_vector_payload["score_source"]["bootstrap"]
    invocation_fields = {
        "evaluation_attempt_id",
        "requested_draw_count",
        "requested_draw_source",
        "effective_estimation_config_sha256",
    }
    assert set(runtime_invocation) == invocation_fields
    assert invocation_fields <= set(runtime_bootstrap)
    assert runtime_invocation == {field: runtime_bootstrap[field] for field in invocation_fields}
    assert runtime_invocation["evaluation_attempt_id"] == packet.evaluation_attempt_id
    assert runtime_invocation["requested_draw_count"] == packet.requested_draw_count
    assert runtime_invocation["requested_draw_source"] == packet.requested_draw_source
    assert runtime_invocation["effective_estimation_config_sha256"] == (
        packet.effective_estimation_config_sha256
    )
    PolicyEvaluationVector.model_validate(source_vector_payload)
    stored_measurement = source_vector_payload["metadata"]["policy_runtime_source_measurement"]
    assert stored_measurement == measurement.model_dump(mode="json", exclude_none=False)
    assert result.simulation_results["budget_deficit_objective_usable"] is False
    assert result.simulation_results["budget_deficit_objective_value"] is None
    assert result.objective_value is None
    assert result.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert result.actual_score is None
    assert _FALLBACK_LIMITATION in result.feedback["objective_limitations"]

    source_vector_manifest = store.get_manifest(packet.source_result_ref)
    expected_source_inputs = {
        ("candidate", candidate_ref.artifact_id.hex),
        *(
            (role, source_ref.artifact_id.hex)
            for role, source_ref in source_observation_input_refs(measurement)
        ),
    }
    assert {
        (item.role, item.artifact_id.hex) for item in source_vector_manifest.inputs
    } == expected_source_inputs
    assert all(item.manifest_profile_sha256 for item in source_vector_manifest.inputs)

    # Keep the selected-profile lineage and every marker, but alter the observation value.
    # The fresh consumer must recompute the exact CAS source body and reject the packet.
    forged_payload = deepcopy(source_vector_payload)
    forged_payload["metadata"]["policy_runtime_source_measurement"]["value"] = 36.0
    forged_vector = PolicyEvaluationVector.model_validate(forged_payload)
    forged_vector_ref = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=candidate_ref,
        evaluation_vector=forged_vector,
    )
    forged_packet = packet.model_copy(update={"source_result_ref": forged_vector_ref})
    forged_packet_ref = persist_funnel_executed_work_packet(store, forged_packet)
    mutated_result = deepcopy(result)
    mutated_result.executed_work_packet_ref = forged_packet_ref
    _assert_fresh_consumer_rejects(orchestrator, ticket, mutated_result)


@pytest.mark.integration
def test_production_backend_fiscal_source_survives_cas_packet_and_fresh_consumer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Carry a unitless production-backend observation through CAS as unavailable.

    Numeric aliases carry no independently selected fiscal unit in this fixture.
    Their observation is persisted as candidate evidence, while an
    available fiscal score is refused. This test isolates
    the source-to-packet join by accepting the separate EvalSafety admission hook;
    it does not claim that EvalSafety was exercised here. Production backend
    evaluation, ObjectiveStack projection, CAS persistence, packet construction,
    and the orchestrator's fresh consumer all run. No draw loop is invoked.
    """
    # EvalSafety admission is separately covered by its owner tests. This test
    # keeps that gate isolated while exercising the actual production backend.
    monkeypatch.setattr(
        policy_runtime_support,
        "_production_policy_evaluation_safety_blockers",
        lambda **_: (),
    )

    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(
        store,
        candidate,
        return_selected_profile=True,
    )
    orchestrator, ticket, outcome = _run_production_workflow(
        store,
        candidate,
        candidate_ref,
        {"policy_value": 0.2, "gdp_change": 0.1, "budget_deficit": 0.02},
        signature="production-source-join-unitless-fiscal-input",
    )

    result = outcome.stage_results[4]
    assert result.executed_work_packet_status == "available"
    assert result.feedback["policy_runtime_work_packet_status"] == "available"
    packet_ref = result.executed_work_packet_ref
    assert packet_ref is not None
    packet = FunnelExecutedWorkPacket.model_validate(load_core_json_artifact(store, packet_ref))
    source_result = load_core_json_artifact(store, packet.source_result_ref)
    source_metadata = source_result["metadata"]
    expected_fiscal = {
        "usable": False,
        "normalized_value": None,
        "source_values": {"budget_deficit": 0.02},
    }
    assert source_metadata["policy_runtime_fiscal_measurement"] == expected_fiscal
    assert result.simulation_results["budget_deficit"] == 0.02
    assert result.simulation_results["budget_deficit_objective_usable"] is False
    assert result.simulation_results["budget_deficit_objective_value"] is None
    assert result.objective_value is None
    assert result.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert result.actual_score is None
    assert _FALLBACK_LIMITATION in result.feedback["objective_limitations"]

    bootstrap = result.simulation_results["bootstrap"]
    invocation = source_metadata["policy_runtime_invocation"]
    assert packet.schema_version == "1.1"
    assert packet.backend_kind == "production"
    assert packet.evaluation_attempt_id == invocation["evaluation_attempt_id"]
    assert packet.evaluation_attempt_id == bootstrap["evaluation_attempt_id"]
    assert packet.requested_draw_count == 500
    assert packet.requested_draw_source == "effective_estimation_config"
    assert (
        packet.effective_estimation_config_sha256 == bootstrap["effective_estimation_config_sha256"]
    )
    assert bootstrap["requested_draw_source"] == "effective_estimation_config"
    assert bootstrap["draw_execution_status"] == "not_instrumented"
    assert all(
        bootstrap[key] is None
        for key in (
            "attempted_draw_count",
            "successful_draw_count",
            "failed_draw_count",
            "unattempted_draw_count",
        )
    )
    assert packet.attempted_draw_count is None
    assert packet.successful_draw_count is None
    assert packet.failed_draw_count is None
    assert packet.unattempted_draw_count is None

    # A second actual production invocation has no fiscal alias. Its zero fallback
    # remains explicitly limited and its persisted source record says unavailable.
    fallback_orchestrator, fallback_ticket, fallback_outcome = _run_production_workflow(
        store,
        candidate,
        candidate_ref,
        {"policy_value": 0.2, "gdp_change": 0.1},
        signature="production-source-join-missing-fiscal-input",
    )
    fallback = fallback_outcome.stage_results[4]
    fallback_packet_ref = fallback.executed_work_packet_ref
    assert fallback_packet_ref is not None
    fallback_packet = FunnelExecutedWorkPacket.model_validate(
        load_core_json_artifact(store, fallback_packet_ref)
    )
    fallback_source = load_core_json_artifact(store, fallback_packet.source_result_ref)
    assert fallback_source["metadata"]["policy_runtime_fiscal_measurement"] == {
        "usable": False,
        "normalized_value": None,
        "source_values": {},
    }
    assert fallback.simulation_results["budget_deficit_objective_usable"] is False
    assert fallback.simulation_results["budget_deficit_objective_value"] is None
    assert fallback.objective_value is None
    assert fallback.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert fallback.actual_score is None
    assert _FALLBACK_LIMITATION in fallback.feedback["objective_limitations"]
    assert fallback.executed_work_packet_status == "available"

    # Changing a measured alias without changing its persisted producer record is
    # rejected by the actual fresh consumer.
    changed_alias = deepcopy(result)
    changed_alias.simulation_results["budget_deficit"] = 0.03
    _assert_fresh_consumer_rejects(orchestrator, ticket, changed_alias)

    # A different, valid packet from the second invocation cannot be rebound to
    # the first ticket even when both packets use the same typed candidate.
    rebound = deepcopy(result)
    rebound.executed_work_packet_ref = fallback_packet_ref
    _assert_fresh_consumer_rejects(orchestrator, ticket, rebound)

    # Neither a unitless numeric alias nor absent fiscal data can be relabeled as
    # a measured zero. Keep both markers but falsify availability; the stored
    # source/vector and fresh consumer must still reject the authority claim.
    for consumer, selected_ticket, unavailable_result in (
        (orchestrator, ticket, result),
        (fallback_orchestrator, fallback_ticket, fallback),
    ):
        false_availability = deepcopy(unavailable_result)
        false_availability.simulation_results["budget_deficit_objective_usable"] = True
        false_availability.simulation_results["budget_deficit_objective_value"] = 0.0
        fiscal_value, fiscal_status = _assess_search_fiscal_measurement(
            false_availability.simulation_results
        )
        assert fiscal_value is None
        assert fiscal_status is ObjectiveScoreStatus.INVALID
        _assert_fresh_consumer_rejects(consumer, selected_ticket, false_availability)


def test_c48_public_vector_writer_does_not_establish_candidate_producer(
    tmp_path: Path,
) -> None:
    """A public vector writer cannot prove which candidate produced its values."""
    from polisyos.scientist.methods.search.contracts import (
        CandidateProposal,
        CandidateStrategyContext,
        ParetoBasisScope,
    )
    from polisyos.scientist.methods.search.frontier import strategy_candidate_payload
    from polisyos.scientist.methods.search.pareto_registry import (
        ParetoRegistry,
        ParetoView,
        verify_policy_evaluation_source,
    )
    from polisyos.scientist.methods.search.transfer_context import TransferContext

    # isort: split
    from unit.scientist.search.test_pareto_transfer import _evaluation_vector

    store = FileSystemCAS(tmp_path / "cas")
    candidate = _policy_candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    other = candidate.model_copy(update={"candidate_id": "other-candidate"})
    other_vector = _evaluation_vector(other, employment=0.8)
    vector = other_vector.model_copy(
        update={
            "candidate_id": candidate.candidate_id,
            "metadata": {**other_vector.metadata, "candidate_hash": candidate.candidate_hash()},
        }
    )
    vector_ref = policy_runtime_support.persist_policy_evaluation_vector_to_store(
        store, candidate_ref=candidate_ref, evaluation_vector=vector
    )
    subject = CandidateStrategyContext(
        producer="policy_design",
        subject=candidate.model_dump(mode="json", exclude_none=True),
        policy_schema=True,
        policy_transport=True,
    )
    proposal = CandidateProposal(
        candidate_id=candidate.candidate_id,
        payload=strategy_candidate_payload(subject),
        strategy_context=subject,
    )
    assert not verify_policy_evaluation_source(store, proposal, vector, candidate_ref, vector_ref)
    altered = vector.model_copy(update={"candidate_id": "other-candidate"})
    assert not verify_policy_evaluation_source(store, proposal, altered, candidate_ref, vector_ref)
    scope = TransferContext(
        task_family="policy", domain="fiscal", run_id="c48-source", tenant_hash="tenant-test"
    )
    registry = ParetoRegistry(tmp_path / "registry", source_store=store)
    axes = sorted(vector.frontier_objectives("global_feasible"))
    basis = ParetoBasisScope(scope="declared" if axes else "not_established", coordinate_ids=axes)
    registry.update(
        "c48-source",
        candidate_hash=candidate.candidate_hash(),
        evaluation=vector,
        candidate_proposal=proposal,
        seed_payload=proposal.payload,
        candidate_ref=candidate_ref,
        evaluation_ref=vector_ref,
        transfer_context=scope,
        seed_only=True,
        objective_basis_by_view={"global_feasible": basis},
    )
    fresh_store = FileSystemCAS(tmp_path / "cas")
    fresh = ParetoRegistry(tmp_path / "registry", source_store=fresh_store).get_snapshot(
        "c48-source", transfer_context=scope
    )
    assert fresh.entries[candidate.candidate_hash()].evaluation_ref == vector_ref
    assert not verify_policy_evaluation_source(
        fresh_store, proposal, vector, candidate_ref, vector_ref
    )
    assert not fresh.project_view(ParetoView.GLOBAL_FEASIBLE).ranked_frontier_hashes
