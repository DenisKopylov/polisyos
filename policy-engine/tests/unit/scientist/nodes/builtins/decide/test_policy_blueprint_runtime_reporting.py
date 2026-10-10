from __future__ import annotations

import logging
from pathlib import Path

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.search.funnel.orchestrator import (
    FunnelOutcome,
    FunnelTraceStep,
)
from polisyos.scientist.methods.search.funnel.types import FunnelStageResult
from polisyos.scientist.methods.search.promotion_evidence import (
    PromotionEvidenceBundle,
    persist_promotion_evidence_bundle,
)
from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope
from polisyos.scientist.nodes.builtins.decide import run_policy_blueprint_runtime as runtime
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
    _RuntimeSession,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_reporting import (
    _serialize_funnel_outcome,
    finalize_runtime_session,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    persist_policy_evaluation_vector_to_store,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


def _candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="problem_reporting_projection",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id="policy_reporting_projection"),
            model_spec=ModelSpec(
                model_id="model_reporting_projection",
                data_snapshot_ref="sha256:" + "4" * 64,
            ),
        ),
        candidate_id="candidate_reporting_projection",
    )


def _context(tmp_path: Path, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path / run_id)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    return ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.{run_id}"),
    )


def _outcome(*, objective_value: float, feedback: dict[str, object]) -> FunnelOutcome:
    result = FunnelStageResult(
        policy_candidate={"candidate_id": "candidate_reporting_projection"},
        objective_value=objective_value,
        is_promising=objective_value >= 0.0,
        stage_name="funnel_L4_full",
        simulation_results={"gdp_change": 0.25},
        feedback=feedback,
        fidelity_level=4,
        compute_cost_usd=0.2,
        compute_cost_origin="estimated",
    )
    step = FunnelTraceStep(
        fidelity_level=4,
        stage_name="funnel_L4_full",
        objective_value=objective_value,
        is_promising=result.is_promising,
        duration_seconds=0.25,
        compute_cost_usd=0.2,
        compute_cost_origin="estimated",
    )
    return FunnelOutcome(
        ticket_id="ticket_reporting_projection",
        candidate_hash="candidate-hash-reporting-projection",
        trace=[step],
        stage_results={4: result},
        final_result=result,
        failure_cards=[],
        uncertainty_envelope=UncertaintyEnvelope.unknown(source="reporting fixture"),
        compute_cost_usd=0.2,
        compute_cost_origin="estimated",
        degradation_mode="normal",
        final_action="advance",
        completed=True,
    )


def test_reporting_finite_projection_roundtrips_nested_evidence_without_loss() -> None:
    outcome = _outcome(
        objective_value=0.375,
        feedback={
            "runtime_marker": "l4-evaluation-preserved",
            "diagnostics": [{"metric": "gdp_change", "value": 0.25}],
        },
    )

    projection = _serialize_funnel_outcome(outcome)
    encoded = to_canonical_bytes(
        projection,
        CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
    )
    restored = from_canonical_bytes(encoded)

    assert restored["stage_results"]["4"]["objective_value"] == 0.375
    assert restored["stage_results"]["4"]["feedback"] == {
        "runtime_marker": "l4-evaluation-preserved",
        "diagnostics": [{"metric": "gdp_change", "value": 0.25}],
    }
    assert restored["trace"][0]["duration_seconds"] == 0.25
    assert restored["stage_results"]["4"]["compute_cost_origin"] == "estimated"
    assert restored["uncertainty_current"] is None
    assert restored["final_action"] == "advance"


def test_reporting_refusal_keeps_prior_state_and_real_cas_evidence_refs(tmp_path: Path) -> None:
    ctx = _context(tmp_path, "run_reporting_refusal")
    candidate = _candidate()
    candidate_ref = persist_policy_candidate_schema(ctx.store, candidate)
    vector = PolicyEvaluationVector(candidate_id=candidate.candidate_id, feasible=True)
    vector_ref = persist_policy_evaluation_vector_to_store(
        ctx.store,
        candidate_ref=candidate_ref,
        evaluation_vector=vector,
    )
    selection = BenchmarkEvaluation(
        loop_id="loop_reporting_refusal",
        suite_id="native_selection",
        candidate_ref=candidate_ref,
        runtime_split_type=BenchmarkSplit.SELECTION,
        selection_metrics={"policy_value": 0.2},
    )
    selection_ref = persist_benchmark_evaluation(ctx.store, selection)
    evidence_bundle = PromotionEvidenceBundle(
        run_id="run_reporting_refusal",
        produced_by_run_id="run_reporting_refusal",
        candidate_ref=candidate_ref,
        selection_evaluation_ref=selection_ref,
    )
    evidence_ref = persist_promotion_evidence_bundle(ctx.store, evidence_bundle)
    state = ExperimentState(
        run_id="run_reporting_refusal",
        params={"prior_state_marker": {"kept": True}},
        artifacts_index={"candidate_ref": candidate_ref},
    )
    session = _RuntimeSession(
        ctx=ctx,
        state=state,
        owner=runtime,
        candidate=candidate,
        candidate_ref=candidate_ref,
        uncertainty_envelope=UncertaintyEnvelope.unknown(source="reporting fixture"),
        governance_report=None,
        causal_report=None,
        distributional_report=None,
        cross_graph_profile=None,
        evidence_sources=None,
        runtime_source_statuses={},
        simulation_metrics={},
        ambiguity_certificate=None,
        ambiguity_certificate_ref=None,
        runtime_backend=object(),
        input_signature="input-signature-reporting-refusal",
        selection_vector=vector,
        selection_vector_ref=vector_ref,
        selection_ref=selection_ref,
        evidence_bundle=evidence_bundle,
        evidence_ref=evidence_ref,
        outcome=_outcome(
            objective_value=float("inf"),
            feedback={"stage_marker": "ranking-sentinel-retained-in-memory"},
        ),
    )
    artifacts_before = _artifact_id_snapshot(ctx.store)

    result = finalize_runtime_session(session)

    assert result.status == "fail"
    assert result.error is not None
    assert result.error.code == "node.invalid_state"
    assert result.error.details["failure_basis"] == (
        "canonical_json_rejected_non_finite_funnel_leaf"
    )
    assert any(
        item["kind"] == "positive_infinity"
        and item["location"] == "$.stage_results['4'].objective_value"
        for item in result.error.details["non_finite_values"]
    )
    assert result.state is state
    assert result.state.params == {"prior_state_marker": {"kept": True}}
    assert "funnel_outcome" not in result.state.params
    assert "_funnel_outcome" not in result.state.params
    artifact_ids = {
        str(ref.artifact_id) for ref in result.artifacts if isinstance(ref, ArtifactRef)
    }
    assert artifact_ids >= {
        str(candidate_ref.artifact_id),
        str(vector_ref.artifact_id),
        str(selection_ref.artifact_id),
        str(evidence_ref.artifact_id),
    }
    assert _artifact_id_snapshot(ctx.store) == artifacts_before


def _artifact_id_snapshot(store: FileSystemCAS) -> tuple[str, ...]:
    return tuple(sorted(str(artifact_id) for artifact_id in store.iter_artifact_ids()))
