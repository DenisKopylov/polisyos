from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceNeed,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceSourceKind,
    EvidenceSourceState,
    EvidenceSourceStatus,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
    TransportStatus,
)
from polisyos.ir.analytics.decision_layer import (
    SocialWeightManifestArtifact,
    build_optimization_ambiguity_certificate,
    persist_optimization_ambiguity_certificate,
    persist_social_weight_manifest,
)
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CohortImpact,
    DimensionBreakdown,
    DistributionalReport,
    ImpactDirection,
    MetricUnit,
    WinnersLosersEntry,
    WinnersLosersTable,
)
from polisyos.ir.analytics.welfare import (
    GEUncertaintyBundle,
    GEUncertaintyRepresentation,
    WelfareBundle,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareStatus,
    persist_ge_uncertainty_bundle,
    persist_welfare_bundle,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
    ConstraintType,
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
)
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.model_layer.model_spec import AssumptionSpec, AssumptionType, ModelSpec
from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.evidence.claims.head_index import build_default_claim_ledger_owner
from polisyos.scientist.methods.search.judge_stack import JudgeVerdict
from polisyos.scientist.methods.search.pareto_registry import (
    ParetoBasisScope,
    ParetoRegistry,
    ParetoRegistryEntry,
    ParetoRegistrySnapshot,
    ParetoView,
    ParetoViewAssessment,
    ParetoViewProjection,
)
from polisyos.scientist.methods.search.readiness import (
    DecisionReadiness,
    DecisionReadinessContract,
    persist_decision_readiness_contract,
)
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)
from polisyos.scientist.policy_design.objectives import (
    ConstraintStatus,
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.output import (
    PolicyArtifactBuilder,
    PolicyArtifactBuildInput,
    PolicyBrief,
    PolicyFrontierReport,
    RejectedAlternativesSummary,
    load_champion_policy_dossier,
    load_policy_artifact_bundle,
    load_policy_brief,
    load_policy_frontier_report,
    load_rejected_alternatives_summary,
    load_replayable_audit_bundle,
    persist_policy_frontier_report,
    persist_rejected_alternatives_summary,
)
from polisyos.scientist.policy_design.phase3 import Phase3CertificateStatus
from polisyos.scientist.policy_design.schema import (
    BudgetAllocationEntry,
    MonitoringSignalSpec,
    ParameterScheduleEntry,
    PolicyCandidateSchema,
    RolloutStep,
    TargetPopulationSpec,
    persist_policy_candidate_schema,
)
from polisyos.scientist.policy_design.translator import TranslatorComplianceResult


def _bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_policy",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="welfare",
                    metric_id="welfare_metric",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
            hard_constraints=[
                ConstraintSpec(
                    constraint_id="budget_cap",
                    constraint_type=ConstraintType.HARD,
                    value=MoneyValue(amount=Decimal("100"), currency="USD"),
                    operator="<=",
                    notes=["budget ceiling"],
                )
            ],
        ),
        policy_spec=PolicySpec(
            policy_id="policy_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="tax_policy",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 2},
                    params={"rate": Decimal("0.1")},
                ),
                InterventionSpec(
                    intervention_id="wage_credit",
                    kind="transfer_policy",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 2},
                    params={"credit": Decimal("10")},
                ),
            ],
            parameters=[
                ParameterSpec(
                    param_id="tax_rate",
                    intervention_id="tax_cut",
                    param_path="rate",
                    default_value=Decimal("0.1"),
                    min_value=Decimal("0.05"),
                    max_value=Decimal("0.2"),
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_policy",
            data_snapshot_ref="sha256:" + "1" * 64,
            assumptions=[
                AssumptionSpec(
                    assumption_id="elasticity",
                    assumption_type=AssumptionType.PARAMETRIC,
                    description="Elasticity remains stable in the policy horizon.",
                )
            ],
        ),
    )


def _candidate() -> PolicyCandidateSchema:
    bundle = _bundle()
    return PolicyCandidateSchema(
        candidate_id="candidate_policy",
        trinity_bundle=bundle,
        target_population=TargetPopulationSpec(
            population_id="population_policy",
            description="General population",
            geography="national",
        ),
        rollout_plan=[
            RolloutStep(
                step_id="step_tax",
                intervention_id="tax_cut",
                order=0,
                schedule={"start_step": 0, "duration_steps": 2},
            ),
            RolloutStep(
                step_id="step_credit",
                intervention_id="wage_credit",
                order=1,
                schedule={"start_step": 0, "duration_steps": 2},
            ),
        ],
        budget_allocation=[
            BudgetAllocationEntry(
                allocation_id="alloc_policy",
                intervention_id="tax_cut",
                amount=MoneyValue(amount=Decimal("90"), currency="USD"),
            )
        ],
        parameter_schedule=[
            ParameterScheduleEntry(
                entry_id="schedule_tax_rate",
                param_id="tax_rate",
                scheduled_value=Decimal("0.1"),
            )
        ],
        monitoring_plan=[
            MonitoringSignalSpec(
                monitoring_id="monitor_1",
                metric_id="welfare_metric",
                intervention_id="tax_cut",
            )
        ],
        metadata={"policy_family": "core_family", "evidence_depth": "replicated"},
    )


def _distributional_report() -> DistributionalReport:
    return DistributionalReport(
        breakdowns=[
            DimensionBreakdown(
                dimension=CohortDimension.INCOME_QUINTILE,
                dimension_label="Income quintiles",
                primary_metric="income",
                primary_metric_unit=MetricUnit.PERCENT,
                cohorts=[
                    CohortImpact(
                        cohort_id="low_income",
                        cohort_label="Low income",
                        population_share=0.5,
                        metric_deltas={"income": -1.0},
                        impact_direction=ImpactDirection.NEGATIVE,
                        is_vulnerable=True,
                    ),
                    CohortImpact(
                        cohort_id="high_income",
                        cohort_label="High income",
                        population_share=0.5,
                        metric_deltas={"income": 2.0},
                        impact_direction=ImpactDirection.POSITIVE,
                    ),
                ],
                gini_before=0.3,
                gini_after=0.32,
            )
        ],
        winners_losers=WinnersLosersTable(
            winners=[
                WinnersLosersEntry(
                    cohort_id="high_income",
                    cohort_label="High income",
                    dimension=CohortDimension.INCOME_QUINTILE,
                    net_impact=2.0,
                    impact_direction=ImpactDirection.POSITIVE,
                    population_share=0.5,
                    key_metric="income",
                    key_metric_delta=2.0,
                )
            ],
            losers=[
                WinnersLosersEntry(
                    cohort_id="low_income",
                    cohort_label="Low income",
                    dimension=CohortDimension.INCOME_QUINTILE,
                    net_impact=-1.0,
                    impact_direction=ImpactDirection.NEGATIVE,
                    population_share=0.5,
                    key_metric="income",
                    key_metric_delta=-1.0,
                    is_vulnerable=True,
                )
            ],
        ),
        overall_gini_before=0.3,
        overall_gini_after=0.32,
    )


def _cross_graph_profile() -> CrossGraphEvidenceProfile:
    return CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(total_needs=1),
        needs=[
            EvidenceNeedAssessment(
                need=EvidenceNeed(
                    need_id="need_1",
                    need_type=EvidenceNeedType.OBJECTIVE_METRIC,
                    source_path="problem_frame.objectives[0]",
                    metric_id="welfare_metric",
                ),
                legal_status=LegalStatus.ALLOWED,
                observability_status=ObservabilityStatus.DIRECT,
                evidence_status=EvidenceStatus.SUPPORTED,
                transport_status=TransportStatus.PARTIALLY_IDENTIFIED,
                confidence=0.8,
            )
        ],
    )


def _degraded_cross_graph_profile() -> CrossGraphEvidenceProfile:
    return CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(total_needs=1),
        needs=[
            EvidenceNeedAssessment(
                need=EvidenceNeed(
                    need_id="need_1",
                    need_type=EvidenceNeedType.OBJECTIVE_METRIC,
                    source_path="problem_frame.objectives[0]",
                    metric_id="welfare_metric",
                ),
                legal_status=LegalStatus.ALLOWED,
                observability_status=ObservabilityStatus.UNKNOWN,
                evidence_status=EvidenceStatus.SUPPORTED,
                transport_status=TransportStatus.PARTIALLY_IDENTIFIED,
                confidence=0.8,
            )
        ],
        source_statuses={
            "academic": EvidenceSourceStatus(
                source=EvidenceSourceKind.ACADEMIC,
                configured=False,
                status=EvidenceSourceState.MISSING_CONFIG,
            ),
            "datasets": EvidenceSourceStatus(
                source=EvidenceSourceKind.DATASETS,
                configured=False,
                status=EvidenceSourceState.MISSING_PATH,
            ),
        },
    )


def _evaluation_vector(candidate: PolicyCandidateSchema) -> PolicyEvaluationVector:
    return PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        primary={
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=1.2,
                direction=ObjectiveDirection.MAXIMIZE,
            )
        },
        hard_constraints={
            "policy_budget_constraint": ObjectiveChannelValue(
                name="policy_budget_constraint",
                kind=ObjectiveKind.HARD_CONSTRAINT,
                value=0.95,
                direction=ObjectiveDirection.MINIMIZE,
                threshold=1.0,
                status=ConstraintStatus.NEAR_BINDING,
            )
        },
        secondary={},
        penalties={},
        feasible=True,
        blocking_reasons=[],
        metadata={"policy_family": "core_family", "candidate_hash": candidate.candidate_hash()},
    )


def _readiness_contract() -> DecisionReadinessContract:
    return DecisionReadinessContract(
        readiness_level=DecisionReadiness.RECOMMENDATION_READY,
        required_judges_passed=["structural", "statistical"],
        required_uncertainty_bounds={},
        mandatory_human_gate=True,
        assumptions_must_be_surfaced=[
            "Elasticity remains stable in the policy horizon.",
            "Hard constraint near binding: policy_budget_constraint",
        ],
        expiry_conditions=["freshness_violation"],
        evidence_depth_required="replicated",
    )


def _policy_brief() -> PolicyBrief:
    return PolicyBrief(
        title="Policy brief for candidate_policy",
        executive_summary=(
            "Candidate_policy improves the welfare objective, but low-income households "
            "remain exposed to measurable harm and the budget constraint is near binding."
        ),
        readiness_level=DecisionReadiness.RECOMMENDATION_READY.value,
        surfaced_assumptions=[
            "Elasticity remains stable in the policy horizon.",
            "Hard constraint near binding: policy_budget_constraint",
        ],
        uncertainty_highlights=["statistical: 0.200", "structural: 0.300"],
        subgroup_harms=["Low income"],
        hard_constraint_notes=["policy_budget_constraint"],
    )


def _translator_compliance() -> TranslatorComplianceResult:
    return TranslatorComplianceResult(passed=True, findings=[])


def _phase3_passed(store: FileSystemCAS) -> Phase3CertificateStatus:
    matrix_ref = store.put_json(
        {"matrix": [[1]]},
        PutOptions(kind="ir.welfare_multiplier_matrix", media_type="application/json"),
    )
    social_weight_ref = persist_social_weight_manifest(
        _ensure_ir_artifact_store(store),
        SocialWeightManifestArtifact(
            manifest_ref="swr://phase-b-output/test@1.0.0#weights",
            method_fqn="policy.welfare.state_dependent_inverse_social_weights@1.0.0",
            normalization="mean_one",
            income_grid=(0.0, 1.0),
            weights_on_grid=(1.0, 1.0),
            state_keys=("income",),
        ),
    )
    ge_ref = persist_ge_uncertainty_bundle(
        _ensure_ir_artifact_store(store),
        GEUncertaintyBundle(
            model_class="linearized_ge_io",
            representation=GEUncertaintyRepresentation.MULTIPLIER_INTERVALS,
            multiplier_shape=(1, 1),
            point_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
            lower_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
            upper_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
        ),
    )
    welfare_ref = persist_welfare_bundle(
        _ensure_ir_artifact_store(store),
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            social_weight_ref=social_weight_ref,
            ge_uncertainty_ref=ge_ref,
            point_estimate=1.0,
            credible_interval=(0.9, 1.1),
            robust_interval=(0.8, 1.2),
            interval_semantics=WelfareIntervalSemantics.MIXED_NESTED,
            method_used=WelfareMethod.MIXED_NESTED,
            status=WelfareStatus.OK,
        ),
    )
    ambiguity_ref = persist_optimization_ambiguity_certificate(
        _ensure_ir_artifact_store(store),
        build_optimization_ambiguity_certificate(
            {"mode": "not_applicable"},
            mode="not_applicable",
            source_kind="test",
            overall_status="pass",
        ),
    )
    return Phase3CertificateStatus(
        welfare_bundle_ref=welfare_ref,
        ambiguity_certificate_ref=ambiguity_ref,
        gate_passed=True,
    )


def _uncertainty() -> UncertaintyEnvelope:
    return UncertaintyEnvelope.from_partial(
        {
            UncertaintyType.STATISTICAL: UncertaintyEstimate(
                level=0.2,
                source="test",
                quantification_method="bootstrap",
                is_reducible=True,
            ),
            UncertaintyType.STRUCTURAL: UncertaintyEstimate(
                level=0.3,
                source="test",
                quantification_method="expert_bound",
                is_reducible=False,
            ),
        }
    )


def test_policy_artifact_builder_round_trip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    candidate = _candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    evaluation = _evaluation_vector(candidate)
    readiness = _readiness_contract()
    readiness_ref = persist_decision_readiness_contract(store, readiness)

    snapshot = ParetoRegistrySnapshot(
        loop_id="loop_policy",
        entries={
            candidate.candidate_hash(): ParetoRegistryEntry(
                candidate_hash=candidate.candidate_hash(),
                candidate_id=candidate.candidate_id,
                evaluation=evaluation,
                policy_family="core_family",
            )
        },
        frontiers={"global_feasible": [candidate.candidate_hash()]},
    )

    bundle_ref = PolicyArtifactBuilder().build(
        store,
        PolicyArtifactBuildInput(
            loop_id="loop_policy",
            run_id="run_policy",
            candidate=candidate,
            candidate_hash=candidate.candidate_hash(),
            candidate_ref=candidate_ref,
            evaluation_vector=evaluation,
            pareto_snapshot=snapshot,
            judge_verdict=JudgeVerdict(per_judge={}, composite_decision="promote"),
            readiness_contract=readiness,
            readiness_ref=readiness_ref,
            phase3_gate=_phase3_passed(store),
            policy_brief=_policy_brief(),
            translator_compliance=_translator_compliance(),
            distributional_report=_distributional_report(),
            cross_graph_profile=_cross_graph_profile(),
            uncertainty_envelope=_uncertainty(),
            constraint_findings=["budget_driver"],
            mutation_hints=["Reduce allocation size or add cheaper fallback variant."],
        ),
        claim_owner=build_default_claim_ledger_owner(store=store),
    )

    bundle = load_policy_artifact_bundle(store, bundle_ref)
    dossier = load_champion_policy_dossier(store, bundle.champion_policy_dossier_ref)
    brief = load_policy_brief(store, bundle.policy_brief_ref)
    audit = load_replayable_audit_bundle(store, bundle.replayable_audit_bundle_ref)

    assert bundle.policy_brief_ref is not None
    assert bundle.welfare_bundle_ref == bundle.phase3_gate.welfare_bundle_ref
    assert bundle.ambiguity_certificate_ref == bundle.phase3_gate.ambiguity_certificate_ref
    assert dossier.readiness_level == DecisionReadiness.RECOMMENDATION_READY.value
    assert "Low income" in brief.subgroup_harms
    assert audit.readiness_ref is not None
    assert "policy_brief_ref" in audit.artifact_refs


def test_policy_artifact_builder_refuses_forged_phase3_gate(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    candidate = _candidate()

    with pytest.raises(ValueError, match="Phase 3 certificate"):
        PolicyArtifactBuilder().build(
            store,
            PolicyArtifactBuildInput(
                loop_id="loop_policy",
                run_id="run_policy",
                candidate=candidate,
                candidate_hash=candidate.candidate_hash(),
                phase3_gate=Phase3CertificateStatus(gate_passed=True),
            ),
            claim_owner=build_default_claim_ledger_owner(store=store),
        )


def test_policy_artifact_builder_surfaces_degraded_evidence_channels(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    candidate = _candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    evaluation = _evaluation_vector(candidate)
    readiness = _readiness_contract()
    readiness_ref = persist_decision_readiness_contract(store, readiness)

    snapshot = ParetoRegistrySnapshot(
        loop_id="loop_policy",
        entries={
            candidate.candidate_hash(): ParetoRegistryEntry(
                candidate_hash=candidate.candidate_hash(),
                candidate_id=candidate.candidate_id,
                evaluation=evaluation,
                policy_family="core_family",
            )
        },
        frontiers={"global_feasible": [candidate.candidate_hash()]},
    )

    bundle_ref = PolicyArtifactBuilder().build(
        store,
        PolicyArtifactBuildInput(
            loop_id="loop_policy",
            run_id="run_policy",
            candidate=candidate,
            candidate_hash=candidate.candidate_hash(),
            candidate_ref=candidate_ref,
            evaluation_vector=evaluation,
            pareto_snapshot=snapshot,
            judge_verdict=JudgeVerdict(per_judge={}, composite_decision="promote"),
            readiness_contract=readiness,
            readiness_ref=readiness_ref,
            phase3_gate=_phase3_passed(store),
            policy_brief=_policy_brief(),
            translator_compliance=_translator_compliance(),
            distributional_report=_distributional_report(),
            cross_graph_profile=_degraded_cross_graph_profile(),
            uncertainty_envelope=_uncertainty(),
            constraint_findings=["budget_driver"],
            mutation_hints=["Reduce allocation size or add cheaper fallback variant."],
        ),
        claim_owner=build_default_claim_ledger_owner(store=store),
    )

    bundle = load_policy_artifact_bundle(store, bundle_ref)
    dossier = load_champion_policy_dossier(store, bundle.champion_policy_dossier_ref)

    caveats = dossier.transport_summary["caveats"]
    assert any("academic (missing_config)" in item for item in caveats)
    assert any("datasets (missing_path)" in item for item in caveats)


def test_partial_pareto_view_is_not_promoted_to_global_frontier(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    candidate = _candidate()
    template = _evaluation_vector(candidate)
    selected_hash = candidate.candidate_hash()
    complete_hash = "sha256:" + "a" * 64
    omitted_hash = "sha256:" + "b" * 64
    nonfinite_hash = "sha256:" + "c" * 64
    declared_basis = ParetoBasisScope(
        scope="declared",
        coordinate_ids=["policy_value", "employment"],
        basis_ref="test:b111.objective-basis.v1",
    )
    employment = ObjectiveChannelValue(
        name="employment",
        kind=ObjectiveKind.PRIMARY,
        value=0.9,
        direction=ObjectiveDirection.MAXIMIZE,
    )
    complete_evaluation = template.model_copy(
        update={
            "candidate_id": "complete",
            "primary": {**template.primary, "employment": employment},
        }
    )
    omitted_evaluation = template.model_copy(
        update={
            "candidate_id": "omitted",
            "primary": {"policy_value": template.primary["policy_value"]},
        }
    )
    nonfinite_evaluation = template.model_copy(
        update={
            "candidate_id": "nonfinite",
            "primary": {
                **template.primary,
                "employment": employment.model_copy(update={"value": math.inf}),
            },
        }
    )
    registry = ParetoRegistry(root=tmp_path / "registry")
    snapshot = registry._recompute(
        ParetoRegistrySnapshot(
            loop_id="b111-partial",
            entries={
                candidate_hash: ParetoRegistryEntry(
                    candidate_hash=candidate_hash,
                    candidate_id=evaluation.candidate_id,
                    evaluation=evaluation,
                )
                for candidate_hash, evaluation in (
                    (complete_hash, complete_evaluation),
                    (omitted_hash, omitted_evaluation),
                    (nonfinite_hash, nonfinite_evaluation),
                )
            },
            objective_basis_by_view={"global_feasible": declared_basis},
        )
    )
    registry_assessment = snapshot.view_assessments["global_feasible"]
    assert registry_assessment.status == "partial"
    assert set(registry_assessment.missing_coordinate_ids_by_candidate_hash) == {omitted_hash}
    missing_coordinate_ids = registry_assessment.missing_coordinate_ids_by_candidate_hash[
        omitted_hash
    ]
    assert len(missing_coordinate_ids) == 1
    assert registry_assessment.non_finite_coordinate_ids_by_candidate_hash == {
        nonfinite_hash: missing_coordinate_ids
    }
    source = PolicyArtifactBuildInput(
        loop_id="b111-partial",
        run_id="b111-partial",
        candidate=candidate,
        candidate_hash=selected_hash,
        evaluation_vector=template,
        pareto_snapshot=snapshot,
    )
    builder = PolicyArtifactBuilder()

    report = builder._build_frontier_report(source)
    summary = builder._build_rejected_alternatives(source)

    assert report.global_frontier == []
    projection = report.view_projections["global_feasible"]
    assert projection.assessment.status == "partial"
    assert projection.candidate_frontier_hashes == (complete_hash,)
    assert projection.eligible_candidate_hashes == (
        complete_hash,
        omitted_hash,
        nonfinite_hash,
    )
    assert {item.candidate_hash: item.disposition for item in summary.alternatives} == {
        complete_hash: "candidate_only",
        omitted_hash: "unassessed",
        nonfinite_hash: "unassessed",
    }
    assert summary.view_projection.assessment == projection.assessment

    report_ref = persist_policy_frontier_report(store, report)
    summary_ref = persist_rejected_alternatives_summary(store, summary)
    replayed_report = load_policy_frontier_report(store, report_ref)
    replayed_summary = load_rejected_alternatives_summary(store, summary_ref)
    assert replayed_report.global_frontier == []
    assert [item.candidate_hash for item in replayed_report.candidate_frontier] == [complete_hash]
    assert replayed_report.view_projections["global_feasible"].assessment.status == "partial"
    assert {item.candidate_hash: item.disposition for item in replayed_summary.alternatives} == {
        complete_hash: "candidate_only",
        omitted_hash: "unassessed",
        nonfinite_hash: "unassessed",
    }
    assert (
        replayed_summary.view_projection.assessment.non_finite_coordinate_ids_by_candidate_hash
        == registry_assessment.non_finite_coordinate_ids_by_candidate_hash
    )
    assert store.get_manifest(report_ref.artifact_id).artifact_schema.version == "3.0"
    assert store.get_manifest(summary_ref.artifact_id).artifact_schema.version == "3.0"

    finite_low = template.model_copy(
        update={
            "candidate_id": "finite_low",
            "primary": {
                "policy_value": template.primary["policy_value"].model_copy(update={"value": 0.5}),
                "employment": employment.model_copy(update={"value": 0.5}),
            },
        }
    )
    finite_snapshot = registry._recompute(
        ParetoRegistrySnapshot(
            loop_id="b111-finite-control",
            entries={
                complete_hash: ParetoRegistryEntry(
                    candidate_hash=complete_hash,
                    candidate_id="complete",
                    evaluation=complete_evaluation,
                ),
                "sha256:" + "d" * 64: ParetoRegistryEntry(
                    candidate_hash="sha256:" + "d" * 64,
                    candidate_id="finite_low",
                    evaluation=finite_low,
                ),
            },
            objective_basis_by_view={"global_feasible": declared_basis},
        )
    )
    finite_projection = finite_snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
    finite_report = builder._build_frontier_report(
        source.model_copy(
            update={
                "loop_id": "b111-finite-control",
                "pareto_snapshot": finite_snapshot,
            }
        )
    )
    assert finite_projection.assessment.status == "complete"
    assert finite_projection.ranked_frontier_hashes == (complete_hash,)
    assert finite_snapshot.hypervolume_by_view["global_feasible"] == pytest.approx(0.28)
    assert [item.candidate_hash for item in finite_report.global_frontier] == [complete_hash]


def test_rejected_summary_rejects_partial_projection_that_drops_assessment_identity() -> None:
    finite_hash = "sha256:" + "a" * 64
    omitted_hash = "sha256:" + "b" * 64
    assessment = ParetoViewAssessment(
        status="partial",
        coverage_status="partial",
        basis_scope=ParetoBasisScope(
            scope="declared",
            coordinate_ids=["policy_value", "employment"],
            basis_ref="test:b111.objective-basis.v1",
        ),
        input_count=2,
        assessed_count=1,
        unassessed_candidate_hashes=[omitted_hash],
        missing_coordinate_ids_by_candidate_hash={omitted_hash: ["employment"]},
    )
    summary_payload = {
        "loop_id": "contradictory-partial-projection",
        "alternatives": [
            {
                "candidate_hash": omitted_hash,
                "candidate_id": "omitted",
                "reason": "candidate_only",
                "disposition": "candidate_only",
            }
        ],
        "view_projection": {
            "view": "global_feasible",
            "assessment": assessment.model_dump(mode="json"),
            "eligible_candidate_hashes": [finite_hash, omitted_hash],
            "candidate_frontier_hashes": [finite_hash],
            "ranked_frontier_hashes": [],
            "unassessed_candidate_hashes": [],
        },
    }

    with pytest.raises(ValidationError, match="unassessed candidate identities"):
        RejectedAlternativesSummary.model_validate(summary_payload)


def test_v3_frontier_requires_global_projection_and_source_denominator() -> None:
    """A v3 report cannot skip reconciliation while retaining the schema marker."""
    limited_projection = ParetoViewProjection(
        view="global_feasible",
        assessment=ParetoViewAssessment(
            status="basis_limited",
            coverage_status="no_usable_inputs",
            basis_scope=ParetoBasisScope(scope="not_established"),
            input_count=0,
            assessed_count=0,
        ),
        eligible_candidate_hashes=(),
    )

    with pytest.raises(ValidationError, match="global_feasible"):
        PolicyFrontierReport(loop_id="unbound-v3")
    with pytest.raises(ValidationError, match="source feasible denominator"):
        PolicyFrontierReport(
            loop_id="missing-source-denominator",
            view_projections={"global_feasible": limited_projection},
        )
    with pytest.raises(ValidationError, match="view projection"):
        RejectedAlternativesSummary(loop_id="unbound-summary-v3")
    with pytest.raises(ValidationError, match="view membership"):
        PolicyFrontierReport(
            loop_id="stale-membership-v3",
            source_feasible_candidate_hashes=(),
            view_membership={"global_feasible": ["stale-rank"]},
            view_projections={"global_feasible": limited_projection},
        )

    foreign_projection = ParetoViewProjection(
        view="low_risk",
        assessment=ParetoViewAssessment(
            status="basis_limited",
            coverage_status="no_usable_inputs",
            basis_scope=ParetoBasisScope(scope="not_established"),
            input_count=1,
            assessed_count=0,
            unassessed_candidate_hashes=["foreign-candidate"],
        ),
        eligible_candidate_hashes=("foreign-candidate",),
        unassessed_candidate_hashes=("foreign-candidate",),
    )
    with pytest.raises(ValidationError, match="source feasible denominator"):
        PolicyFrontierReport(
            loop_id="foreign-view-v3",
            source_feasible_candidate_hashes=(),
            view_membership={"global_feasible": [], "low_risk": []},
            view_projections={
                "global_feasible": limited_projection,
                "low_risk": foreign_projection,
            },
        )

    complete = PolicyFrontierReport(
        loop_id="bounded-v3",
        source_feasible_candidate_hashes=(),
        view_membership={"global_feasible": []},
        view_projections={"global_feasible": limited_projection},
    )
    assert complete.view_projections["global_feasible"].eligible_candidate_hashes == ()
    assert (
        RejectedAlternativesSummary(
            loop_id="bounded-summary-v3", view_projection=limited_projection
        ).view_projection
        == limited_projection
    )
    assert PolicyFrontierReport(schema_version="1.0", loop_id="historical-v1")
    assert RejectedAlternativesSummary(schema_version="1.0", loop_id="historical-v1")


def test_unissued_v2_frontier_and_summary_are_rejected() -> None:
    # The integrated producer advances directly from the standing v1 format to
    # v3. A draft v2 projection lacked the eligible-identity denominator.
    for model_cls in (PolicyFrontierReport, RejectedAlternativesSummary):
        with pytest.raises(ValidationError):
            model_cls.model_validate({"schema_version": "2.0", "loop_id": "unissued-v2"})


def test_v3_rejected_summary_cannot_call_unassessed_candidate_dominated() -> None:
    projection = ParetoViewProjection(
        view="global_feasible",
        assessment=ParetoViewAssessment(
            status="basis_limited",
            coverage_status="no_usable_inputs",
            basis_scope=ParetoBasisScope(scope="not_established"),
            input_count=1,
            assessed_count=0,
            unassessed_candidate_hashes=["candidate-1"],
        ),
        eligible_candidate_hashes=("candidate-1",),
        unassessed_candidate_hashes=("candidate-1",),
    )
    payload = {
        "loop_id": "limited-summary",
        "view_projection": projection.model_dump(mode="python"),
        "alternatives": [
            {"candidate_hash": "candidate-1", "reason": "dominated", "disposition": "dominated"}
        ],
    }

    with pytest.raises(ValidationError, match="dominated.*complete"):
        RejectedAlternativesSummary.model_validate(payload)

    payload["alternatives"][0].update(reason="unassessed", disposition="unassessed")
    result = RejectedAlternativesSummary.model_validate(payload)
    assert result.alternatives[0].disposition == "unassessed"


def test_policy_frontier_report_v1_serialization_is_byte_exact(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    report = PolicyFrontierReport(
        schema_version="1.0",
        loop_id="legacy-v1",
        generated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    expected = (
        b'{"artifact_functions":["cross_run_learning","routing"],'
        b'"generated_at":{"_type":"datetime","iso_utc":"2026-01-02T03:04:05Z"},'
        b'"global_frontier":[],"loop_id":"legacy-v1","metadata":{},'
        b'"schema_version":"1.0","view_membership":{}}'
    )

    historical_payload = report.historical_v1_payload()
    ref = persist_policy_frontier_report(store, report)

    assert to_canonical_bytes(historical_payload, CanonSpec(forbid_floats=False)) == expected
    assert store.get_bytes(ref.artifact_id) == expected
    replayed = load_policy_frontier_report(store, ref)
    assert replayed.schema_version == "1.0"
    assert (
        to_canonical_bytes(replayed.historical_v1_payload(), CanonSpec(forbid_floats=False))
        == expected
    )
    manifest = store.get_manifest(ref.artifact_id)
    assert manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.policy_design.PolicyFrontierReport",
        version="1.0",
    )


def test_rejected_alternatives_v1_serialization_is_byte_exact(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    summary = RejectedAlternativesSummary(schema_version="1.0", loop_id="legacy-v1")
    expected = (
        b'{"alternatives":[],"artifact_functions":["cross_run_learning"],'
        b'"dominant_rejection_reasons":[],"loop_id":"legacy-v1","schema_version":"1.0"}'
    )

    historical_payload = summary.historical_v1_payload()
    ref = persist_rejected_alternatives_summary(store, summary)

    assert to_canonical_bytes(historical_payload, CanonSpec(forbid_floats=False)) == expected
    assert store.get_bytes(ref.artifact_id) == expected
    replayed = load_rejected_alternatives_summary(store, ref)
    assert replayed.schema_version == "1.0"
    assert (
        to_canonical_bytes(replayed.historical_v1_payload(), CanonSpec(forbid_floats=False))
        == expected
    )
    manifest = store.get_manifest(ref.artifact_id)
    assert manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.policy_design.RejectedAlternativesSummary",
        version="1.0",
    )
