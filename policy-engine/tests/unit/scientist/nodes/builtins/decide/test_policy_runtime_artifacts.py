from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import ArtifactIntegrityError, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    RefutationResult,
    RefutationTestType,
)
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CohortImpact,
    DimensionBreakdown,
    DistributionalReport,
    ImpactDirection,
    WinnersLosersEntry,
    WinnersLosersTable,
)
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.doe.stress_report import VulnerabilityType
from polisyos.scientist.methods.search.funnel.types import FunnelExecutedWorkPacket
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    build_vulnerabilities,
    persist_funnel_executed_work_packet,
)


def test_work_packet_cas_round_trip_binds_selected_inputs_and_refuses_tampering(
    cas_store,
) -> None:
    """Persisted work packets retain typed lineage and are read through CAS integrity checks."""
    candidate_ref = cas_store.put_json(
        {"candidate_id": "candidate-artifact-boundary"},
        PutOptions(
            kind="scientist.policy_design.candidate",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyCandidate", version="1.0"),
        ),
        return_selected_profile=True,
    )
    result_ref = cas_store.put_json(
        {"candidate_id": "candidate-artifact-boundary", "feasible": True},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyEvaluationVector", version="1.0"),
        ),
        return_selected_profile=True,
    )
    packet = FunnelExecutedWorkPacket(
        run_id="run-artifact-boundary",
        ticket_id="ticket-artifact-boundary",
        candidate_hash="candidate-content-hash",
        candidate_ref=candidate_ref,
        stage_level=3,
        stage_name="funnel_L3_medium",
        fidelity="medium",
        evaluation_attempt_id="attempt-artifact-boundary",
        observed_at=datetime(2026, 10, 10, tzinfo=UTC),
        backend_kind="production",
        source_result_ref=result_ref,
        requested_draw_count=64,
        requested_draw_source="effective_estimation_config",
        effective_estimation_config_sha256="b" * 64,
        input_signature="caller-input-signature",
    )

    packet_ref = persist_funnel_executed_work_packet(cas_store, packet)
    manifest = cas_store.get_manifest(packet_ref)
    assert packet_ref.manifest_profile_sha256 is not None
    assert packet_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(manifest)
    restored = FunnelExecutedWorkPacket.model_validate(
        from_canonical_bytes(cas_store.get_bytes(packet_ref))
    )

    assert manifest.kind == "scientist.search.funnel_native_work_packet"
    assert manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.search.FunnelExecutedWorkPacket", version="1.1"
    )
    assert manifest.producer is not None
    assert manifest.producer.component == "scientist.policy_runtime_work_packet"
    assert manifest.producer.version == "1.0.0"
    assert manifest.inputs == [
        input_ref_from_artifact_ref(candidate_ref, role="candidate"),
        input_ref_from_artifact_ref(result_ref, role="source_result"),
    ]
    assert restored == packet
    assert restored.candidate_ref.manifest_profile_sha256 == candidate_ref.manifest_profile_sha256
    assert restored.source_result_ref.manifest_profile_sha256 == result_ref.manifest_profile_sha256

    # A generic Core write keeps the historical profileless default selector. The packet
    # owner above explicitly returns the selected view; callers do not infer it from a later read.
    default_ref = cas_store.put_json(
        packet,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    assert default_ref.manifest_profile_sha256 is None
    assert artifact_manifest_profile_sha256(cas_store.get_manifest(default_ref)) is not None

    # The typed IR writer also returns the exact non-default view selector.
    ir_store = ensure_ir_artifact_store(cas_store)
    selected_ref = put_json_artifact(
        ir_store,
        packet,
        kind="scientist.search.funnel_native_work_packet",
        schema_name="tests.SelectedFunnelExecutedWorkPacketView",
        schema_version="1.0",
    )
    assert selected_ref["manifest_profile_sha256"] is not None
    selected_manifest = ir_store.get_manifest(selected_ref)
    assert selected_manifest.artifact_schema == SchemaInfo(
        name="tests.SelectedFunnelExecutedWorkPacketView", version="1.0"
    )
    assert (
        FunnelExecutedWorkPacket.model_validate(get_json_artifact(ir_store, selected_ref)) == packet
    )

    blob_path, _manifest_path = cas_store._paths(packet_ref.artifact_id)
    blob_path.write_bytes(blob_path.read_bytes() + b"tampered")
    with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
        cas_store.get_bytes(packet_ref)
    with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
        get_json_artifact(ir_store, selected_ref)


def test_policy_evaluation_vector_owner_returns_selected_cas_view(cas_store) -> None:
    """The policy-runtime evaluation producer returns the exact selected CAS view."""
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        persist_policy_evaluation_vector_to_store,
    )
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    candidate_ref = cas_store.put_json(
        {"candidate_id": "candidate-selected-evaluation"},
        PutOptions(
            kind="scientist.policy_design.candidate",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyCandidate", version="1.0"),
        ),
        return_selected_profile=True,
    )
    evaluation = PolicyEvaluationVector(
        candidate_id="candidate-selected-evaluation",
        feasible=True,
    )

    evaluation_ref = persist_policy_evaluation_vector_to_store(
        cas_store,
        candidate_ref=candidate_ref,
        evaluation_vector=evaluation,
    )

    manifest = cas_store.get_manifest(evaluation_ref)
    assert evaluation_ref.manifest_profile_sha256 is not None
    assert manifest.kind == "scientist.policy_evaluation_vector"
    assert manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.policy_design.PolicyEvaluationVector",
        version="1.1",
    )
    assert manifest.inputs == [input_ref_from_artifact_ref(candidate_ref, role="candidate")]


def test_runtime_vulnerabilities_reuse_typed_constraint_distributional_and_refutation_contracts() -> (
    None
):
    """The runtime projection preserves the existing vulnerability taxonomy and gates."""
    from polisyos.scientist.policy_design.objectives import (
        ConstraintStatus,
        ObjectiveChannelValue,
        ObjectiveDirection,
        ObjectiveKind,
        PolicyEvaluationVector,
    )

    evaluation = PolicyEvaluationVector(
        hard_constraints={
            "spending_cap": ObjectiveChannelValue(
                name="spending_cap",
                kind=ObjectiveKind.HARD_CONSTRAINT,
                value=10.0,
                direction=ObjectiveDirection.MINIMIZE,
                status=ConstraintStatus.NEAR_BINDING,
            )
        }
    )
    distributional = DistributionalReport(
        breakdowns=[
            DimensionBreakdown(
                dimension=CohortDimension.INCOME_QUINTILE,
                dimension_label="Income quintile",
                cohorts=[
                    CohortImpact(
                        cohort_id="q1",
                        cohort_label="Lowest quintile",
                        population_share=0.5,
                        metric_deltas={"income": -3.0},
                    ),
                    CohortImpact(
                        cohort_id="q5",
                        cohort_label="Highest quintile",
                        population_share=0.5,
                        metric_deltas={"income": 1.0},
                    ),
                ],
                primary_metric="income",
            )
        ],
        winners_losers=WinnersLosersTable(
            losers=[
                WinnersLosersEntry(
                    cohort_id="q1",
                    cohort_label="Lowest quintile",
                    dimension=CohortDimension.INCOME_QUINTILE,
                    net_impact=-3.0,
                    impact_direction=ImpactDirection.NEGATIVE,
                    population_share=0.5,
                    is_vulnerable=True,
                    key_metric="income",
                    key_metric_delta=-3.0,
                )
            ]
        ),
    )
    causal_report = CausalEffectReport(
        method=CausalMethod.DOUBLE_ML,
        estimand="average treatment effect",
        point_estimate=1.0,
        confidence_interval=(0.2, 1.8),
        inference_method="fixture",
        sample_size=20,
        n_treated=10,
        n_control=10,
        pre_periods=1,
        post_periods=1,
        refutation_results=[
            RefutationResult(
                test_type=RefutationTestType.PLACEBO_TREATMENT,
                original_estimate=1.0,
                refuted_estimate=0.1,
                p_value=0.01,
                passed=False,
                effect_ratio=0.1,
            )
        ],
    )
    governance_report = GovernanceReport(
        verdict="reject",
        issues=[{"code": "policy_blocked"}],
    )

    vulnerabilities = build_vulnerabilities(
        evaluation=evaluation,
        distributional=distributional,
        causal_report=causal_report,
        governance_report=governance_report,
    )

    by_id = {item.vulnerability_id: item for item in vulnerabilities}
    assert set(by_id) == {
        "constraint_spending_cap",
        "distributional_q1",
        "refutation_0",
        "governance_reject",
    }
    assert (
        by_id["constraint_spending_cap"].vulnerability_type
        is VulnerabilityType.CONSTRAINT_VIOLATION
    )
    assert by_id["constraint_spending_cap"].severity == "high"
    assert by_id["distributional_q1"].vulnerability_type is VulnerabilityType.DISTRIBUTIONAL
    assert by_id["distributional_q1"].affected_kpis == ["income"]
    assert by_id["refutation_0"].vulnerability_type is VulnerabilityType.EXTREME_SENSITIVITY
    assert by_id["refutation_0"].objective_value == 0.1
    assert by_id["governance_reject"].vulnerability_type is VulnerabilityType.CONSTRAINT_VIOLATION

    approved_with_issues = build_vulnerabilities(
        evaluation=None,
        distributional=None,
        causal_report=None,
        governance_report=GovernanceReport(
            verdict="approve",
            issues=[{"code": "warning_only"}],
        ),
    )
    assert approved_with_issues == []


def test_policy_evaluation_vector_serialization_keeps_required_nullable_score_fields(
    cas_store,
) -> None:
    """Persist required nullable score-basis keys and refuse missing historical keys."""
    from pydantic import ValidationError

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.scientist.methods.search.objective import (
        ObjectiveScoreAssessment,
        ObjectiveScoreStatus,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        persist_policy_evaluation_vector_to_store,
    )
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    candidate_ref = cas_store.put_json(
        {"candidate_id": "candidate-nullable-score-basis"},
        PutOptions(
            kind="scientist.policy_design.candidate",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyCandidate", version="1.0"),
        ),
        return_selected_profile=True,
    )
    vector = PolicyEvaluationVector(
        candidate_id="candidate-nullable-score-basis",
        score_assessment=ObjectiveScoreAssessment(
            objective_ref=None,
            rule_spec=None,
            required_input_groups=(),
            source_field_names=(),
            source_values=(),
            source_sha256=None,
            value=None,
            status=ObjectiveScoreStatus.NOT_ESTABLISHED,
            limitation="objective_source_not_established",
        ),
    )

    vector_ref = persist_policy_evaluation_vector_to_store(
        cas_store,
        candidate_ref=candidate_ref,
        evaluation_vector=vector,
    )

    manifest = cas_store.get_manifest(vector_ref)
    payload = load_core_json_artifact(cas_store, vector_ref)
    assert vector_ref.manifest_profile_sha256 is not None
    assert manifest.kind == "scientist.policy_evaluation_vector"
    assert manifest.media_type == "application/json"
    assert manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.policy_design.PolicyEvaluationVector",
        version="1.1",
    )
    assert manifest.canon is not None
    assert manifest.canon.forbid_floats is False
    assert manifest.canon.exclude_none is False
    for required_nullable in ("objective_ref", "rule_spec", "source_sha256", "value"):
        assert required_nullable in payload["score_assessment"]
        assert payload["score_assessment"][required_nullable] is None
    assert PolicyEvaluationVector.model_validate(payload) == vector

    malformed = dict(payload)
    assessment_payload = dict(payload["score_assessment"])
    for required_nullable in ("objective_ref", "rule_spec", "source_sha256", "value"):
        assessment_payload.pop(required_nullable)
    malformed["score_assessment"] = assessment_payload
    with pytest.raises(ValidationError):
        PolicyEvaluationVector.model_validate(malformed)


def test_unestablished_selection_score_stays_limited_after_metadata_extension(
    cas_store,
) -> None:
    """Candidate metadata cannot turn an unscored selection into promotion evidence."""
    from polisyos.scientist.methods.search.objective import (
        ObjectiveScoreAssessment,
        ObjectiveScoreStatus,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        build_selection_benchmark_evaluation,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

    candidate_ref = cas_store.put_json(
        {"candidate_id": "candidate-unscored-selection"},
        PutOptions(
            kind="scientist.policy_design.candidate",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyCandidate", version="1.0"),
        ),
        return_selected_profile=True,
    )
    vector = PolicyEvaluationVector(
        candidate_id="candidate-unscored-selection",
        score_assessment=ObjectiveScoreAssessment(
            objective_ref=None,
            rule_spec=None,
            required_input_groups=(),
            source_field_names=(),
            source_values=(),
            source_sha256=None,
            value=None,
            status=ObjectiveScoreStatus.NOT_ESTABLISHED,
            limitation="objective_source_not_established",
        ),
    )

    evaluation = build_selection_benchmark_evaluation(
        state=ExperimentState(run_id="run-unscored-selection"),
        candidate_ref=candidate_ref,
        evaluation_vector=vector,
        metadata_extension={
            "objective_score_status": "available",
            "objective_score_limitation": None,
        },
    )

    assert evaluation.selection_metrics == {}
    assert evaluation.holdout_metrics == {}
    assert evaluation.sample_counts == {}
    assert evaluation.status == "not_established"
    assert evaluation.notes == ["objective_source_not_established"]
    assert evaluation.promotable is False
    assert evaluation.metadata["objective_score_status"] == "not_established"
    assert evaluation.metadata["objective_score_limitation"] == "objective_source_not_established"
