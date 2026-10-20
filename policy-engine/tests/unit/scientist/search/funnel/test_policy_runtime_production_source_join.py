from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
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
    _assess_search_fiscal_measurement,
)
from polisyos.scientist.nodes.builtins.decide import policy_runtime_support
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    ProductionPolicyEvaluationBackend,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _PolicyRuntimeWorkflowEngine,
)
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
