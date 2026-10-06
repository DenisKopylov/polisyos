"""Blueprint JSON keeps typed observations without creating provider authority."""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOutcome, FunnelTraceStep
from polisyos.scientist.methods.search.funnel.types import FunnelStageResult
from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _run_and_register_phase_d4_challenge_suites,
    _serialize_funnel_outcome,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


@pytest.mark.parametrize("spend", [None, Decimal("0"), Decimal("0.10000000000000000001")])
def test_declared_resource_observations_survive_blueprint_json_and_fresh_cas_reader(
    tmp_path: Path, spend: Decimal | None
) -> None:
    # This is a DTO projection contract, not an executed provider/billing claim.
    source = "estimated" if spend is None else "provider_reported_only"
    events = () if spend is None else ("actual-event-reference",)
    feedback = {
        "resource_pending_event_id": "pending-reference",
        "resource_response_digest": "response-digest",
        "resource_local_recorded_spend": "0.10000000000000000001",
    }
    stage = FunnelStageResult(
        policy_candidate={"candidate": "typed-fixture"},
        objective_value=0.5,
        is_promising=False,
        stage_name="native-fixture",
        fidelity_level=3,
        compute_actual_usd=0.125,
        compute_cost_source=source,
        provider_spend_usd=spend,
        resource_event_ids=events,
        feedback=feedback,
        terminal_action="reject",
    )
    trace = FunnelTraceStep(
        fidelity_level=3,
        stage_name=stage.stage_name,
        objective_value=stage.objective_value,
        is_promising=False,
        duration_seconds=0.25,
        compute_actual_usd=stage.compute_actual_usd,
        compute_cost_source=source,
        provider_spend_usd=spend,
        resource_event_ids=events,
    )
    outcome = FunnelOutcome(
        ticket_id="typed-ticket",
        candidate_hash="typed-candidate",
        trace=[trace],
        stage_results={3: stage},
        final_result=stage,
        failure_cards=[],
        uncertainty_envelope=UncertaintyEnvelope.unknown(),
        compute_actual_usd=0.125,
        degradation_mode="normal",
        final_action="reject",
        completed=True,
        evaluation_status="partial",
        compute_cost_source=source,
        provider_spend_usd=spend,
        resource_event_ids=events,
    )
    projection = _serialize_funnel_outcome(outcome)
    assert projection["evaluation_status"] == "partial"
    for observed in (projection, projection["trace"][0], projection["stage_results"]["3"]):
        assert observed["compute_actual_usd"] == 0.125
        assert observed["compute_cost_source"] == source
        assert observed["provider_spend_usd"] == (None if spend is None else str(spend))
        assert observed["resource_event_ids"] == list(events)
    assert projection["stage_results"]["3"]["feedback"] == feedback
    state = ExperimentState(run_id="projection", params={"funnel_outcome": projection})
    store = FileSystemCAS(tmp_path / "cas")
    reference = store.put_json(
        state.model_dump(mode="json"),
        PutOptions(kind="scientist.experiment_state", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    restored = ExperimentState.model_validate(
        from_canonical_bytes(FileSystemCAS(tmp_path / "cas").get_bytes(reference.artifact_id))
    )
    assert restored.params["funnel_outcome"] == projection


def test_actual_phase_d4_report_manifest_matches_typed_body_on_fresh_reader(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = store.put_json(
        {"candidate": "declared-strategic-summary"},
        PutOptions(kind="scientist.policy_candidate", media_type="application/json"),
    )
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="phase-d4-schema")
    context = ExecutionContext(store=store, run=run, logger=logging.getLogger("phase-d4-schema"))
    state = ExperimentState(
        run_id="phase-d4-schema",
        params={
            "strategic_response_summary": {
                "fallback_mode": "exact_equilibrium",
                "equilibrium_selection_dependence": "follower_best_response_tie_breaking",
                "closure_summary": {"mode": "exact_equilibrium", "equilibrium_count": 2},
            }
        },
    )
    selection = BenchmarkEvaluation(loop_id="loop", suite_id="selection", candidate_ref=candidate)
    benchmark_refs, stress_refs, warnings = _run_and_register_phase_d4_challenge_suites(
        context,
        state,
        benchmark_registry=BenchmarkRegistry(tmp_path / "benchmarks"),
        candidate_ref=candidate,
        selection_evaluation=selection,
        benchmark_scope={
            "artifact_family": "policy_candidate",
            "claim_mode": "point_identification",
            "query_type": None,
            "estimator_name": None,
            "readiness_target": None,
        },
        artifacts_index={},
    )
    assert benchmark_refs and stress_refs and warnings
    reopened = FileSystemCAS(tmp_path / "cas")
    for reference in stress_refs:
        restored = StressTestReport.model_validate(
            from_canonical_bytes(reopened.get_bytes(reference.artifact_id))
        )
        schema = reopened.get_manifest(reference.artifact_id).artifact_schema
        assert schema is not None
        assert schema.version == restored.schema_version == "1.1"
        assert restored.scenario_evidence is not None
        assert restored.scenario_evidence.assessment_rule == "challenge_case_pass"
