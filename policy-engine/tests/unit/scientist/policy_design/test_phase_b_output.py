from __future__ import annotations

from decimal import Decimal

import pytest
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
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
from polisyos.ir.model_spec import AssumptionSpec, AssumptionType, ModelSpec
from polisyos.ir.refs import ArtifactRefModel
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import OptimizationDirection, SelectorOperator
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
    load_champion_policy_dossier,
    load_policy_artifact_bundle,
    load_policy_brief,
    load_replayable_audit_bundle,
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
from polisyos.scientist.search.judge_stack import JudgeVerdict
from polisyos.scientist.search.pareto_registry import ParetoRegistryEntry, ParetoRegistrySnapshot
from polisyos.scientist.search.readiness import (
    DecisionReadiness,
    DecisionReadinessContract,
    persist_decision_readiness_contract,
)
from polisyos.scientist.search.uncertainty import (
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)


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
        store,
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
        store,
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
        store,
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
        store,
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
    )

    bundle = load_policy_artifact_bundle(store, bundle_ref)
    dossier = load_champion_policy_dossier(store, bundle.champion_policy_dossier_ref)

    caveats = dossier.transport_summary["caveats"]
    assert any("academic (missing_config)" in item for item in caveats)
    assert any("datasets (missing_path)" in item for item in caveats)
