from __future__ import annotations

from decimal import Decimal

import pytest
from polisyos.foundry.methods.catalog.optimization.protocols import (
    AmbiguityCertificate,
    ConstraintCertificate,
)
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    DiagnosticTest,
    EstimationStatus,
    RefutationResult,
    RefutationTestType,
)
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceNeed,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
    TransportStatus,
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
from polisyos.ir.governance.policy_spec import (
    InterventionSpec,
    ParameterSpec,
    PolicySpec,
)
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
    ConstraintType,
    KPISpec,
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
)
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.model_layer.model_spec import AssumptionSpec, AssumptionType, ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    ProductionPolicyEvaluationBackend,
)
from polisyos.scientist.policy_design.objectives import (
    ConstraintStatus,
    ObjectiveStack,
    PolicyEvaluationBundle,
)
from polisyos.scientist.policy_design.schema import (
    BudgetAllocationEntry,
    MonitoringSignalSpec,
    ParameterScheduleEntry,
    PolicyCandidateSchema,
    RolloutStep,
    TargetPopulationSpec,
)
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)


def _bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_a",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="welfare_objective",
                    metric_id="welfare_metric",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
            kpis=[
                KPISpec(
                    kpi_id="employment_kpi",
                    metric_id="employment_metric",
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
            policy_id="policy_a",
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
                    schedule={"start_step": 0, "duration_steps": 4},
                    params={"rate": Decimal("0.1")},
                )
            ],
            parameters=[
                ParameterSpec(
                    param_id="tax_rate",
                    intervention_id="tax_cut",
                    param_path="rate",
                    default_value=Decimal("0.1"),
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_a",
            data_snapshot_ref="sha256:" + "1" * 64,
            assumptions=[
                AssumptionSpec(
                    assumption_id="elasticity_constant",
                    assumption_type=AssumptionType.PARAMETRIC,
                    description="Elasticity remains stable in the policy horizon.",
                )
            ],
        ),
    )


def _distributional_report(*, gini_delta: float = 0.01) -> DistributionalReport:
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
                        metric_deltas={"income": 2.0},
                        impact_direction=ImpactDirection.POSITIVE,
                        is_vulnerable=True,
                    ),
                    CohortImpact(
                        cohort_id="high_income",
                        cohort_label="High income",
                        population_share=0.5,
                        metric_deltas={"income": 1.0},
                        impact_direction=ImpactDirection.POSITIVE,
                    ),
                ],
                gini_before=0.30,
                gini_after=0.30 + gini_delta,
            )
        ],
        winners_losers=WinnersLosersTable(
            winners=[
                WinnersLosersEntry(
                    cohort_id="low_income",
                    cohort_label="Low income",
                    dimension=CohortDimension.INCOME_QUINTILE,
                    net_impact=2.0,
                    impact_direction=ImpactDirection.POSITIVE,
                    population_share=0.5,
                    is_vulnerable=True,
                    key_metric="income",
                    key_metric_delta=2.0,
                ),
                WinnersLosersEntry(
                    cohort_id="high_income",
                    cohort_label="High income",
                    dimension=CohortDimension.INCOME_QUINTILE,
                    net_impact=1.0,
                    impact_direction=ImpactDirection.POSITIVE,
                    population_share=0.5,
                    key_metric="income",
                    key_metric_delta=1.0,
                ),
            ]
        ),
        overall_gini_before=0.30,
        overall_gini_after=0.30 + gini_delta,
    )


def _causal_effect_report() -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE",
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        inference_method="bootstrap",
        diagnostics=[DiagnosticTest(test_name="bootstrap_stability", passed=True)],
        refutation_results=[
            RefutationResult(
                test_type=test_type,
                original_estimate=1.0,
                refuted_estimate=0.95,
                passed=True,
                effect_ratio=0.95,
            )
            for test_type in (
                RefutationTestType.PLACEBO_TREATMENT,
                RefutationTestType.RANDOM_COMMON_CAUSE,
                RefutationTestType.DATA_SUBSET,
                RefutationTestType.BOOTSTRAP,
            )
        ],
        method_params={"source_type": "external"},
        sample_size=200,
        n_treated=100,
        n_control=100,
        pre_periods=1,
        post_periods=1,
    )


def _cross_graph_profile(
    *, transport_status: TransportStatus = TransportStatus.IDENTIFIED
) -> CrossGraphEvidenceProfile:
    need = EvidenceNeed(
        need_id="need_1",
        need_type=EvidenceNeedType.OBJECTIVE_METRIC,
        source_path="problem_frame.objectives[0]",
        metric_id="welfare_metric",
    )
    return CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(total_needs=1),
        needs=[
            EvidenceNeedAssessment(
                need=need,
                legal_status=LegalStatus.ALLOWED,
                observability_status=ObservabilityStatus.DIRECT,
                evidence_status=EvidenceStatus.SUPPORTED,
                transport_status=transport_status,
                confidence=0.9,
            )
        ],
    )


def _uncertainty(*, statistical: float, transport: float = 0.2) -> UncertaintyEnvelope:
    return UncertaintyEnvelope.from_partial(
        {
            UncertaintyType.STATISTICAL: UncertaintyEstimate(
                level=statistical,
                source="test",
                quantification_method="manual",
                is_reducible=True,
            ),
            UncertaintyType.TRANSPORT: UncertaintyEstimate(
                level=transport,
                source="test",
                quantification_method="manual",
                is_reducible=True,
            ),
        }
    )


def test_policy_candidate_schema_roundtrip_and_hash() -> None:
    candidate = PolicyCandidateSchema.from_trinity_bundle(_bundle(), candidate_id="candidate_a")

    assert candidate.to_trinity_bundle().policy_spec.policy_id == "policy_a"
    assert candidate.candidate_hash().startswith("sha256:")
    assert candidate.as_search_payload()["candidate_hash"] == candidate.candidate_hash()


def test_policy_candidate_schema_rejects_budget_overflow() -> None:
    bundle = _bundle()

    with pytest.raises(ValueError, match="budget allocation exceeds ProblemFrame budget envelope"):
        PolicyCandidateSchema(
            candidate_id="candidate_a",
            trinity_bundle=bundle,
            target_population=TargetPopulationSpec(
                population_id="population_a",
                description="Default target population",
            ),
            budget_allocation=[
                BudgetAllocationEntry(
                    allocation_id="alloc_1",
                    intervention_id="tax_cut",
                    amount=MoneyValue(amount=Decimal("101"), currency="USD"),
                )
            ],
        )


def test_policy_candidate_schema_rejects_rollout_order_schedule_conflict() -> None:
    bundle = _bundle()

    with pytest.raises(ValueError, match="rollout order contradicts schedule ordering"):
        PolicyCandidateSchema(
            candidate_id="candidate_a",
            trinity_bundle=bundle,
            target_population=TargetPopulationSpec(
                population_id="population_a",
                description="Default target population",
            ),
            rollout_plan=[
                RolloutStep(
                    step_id="step_1",
                    intervention_id="tax_cut",
                    order=0,
                    schedule={"start_step": 2, "duration_steps": 1},
                ),
                RolloutStep(
                    step_id="step_2",
                    intervention_id="tax_cut",
                    order=1,
                    schedule={"start_step": 1, "duration_steps": 1},
                ),
            ],
        )


def test_objective_stack_marks_exact_thresholds_as_feasible_near_binding() -> None:
    candidate = PolicyCandidateSchema(
        candidate_id="candidate_a",
        trinity_bundle=_bundle(),
        target_population=TargetPopulationSpec(
            population_id="population_a",
            description="Default target population",
        ),
        rollout_plan=[
            RolloutStep(
                step_id="step_1",
                intervention_id="tax_cut",
                order=0,
            )
        ],
        parameter_schedule=[
            ParameterScheduleEntry(
                entry_id="param_1",
                param_id="tax_rate",
                scheduled_value=Decimal("0.1"),
            )
        ],
        budget_allocation=[
            BudgetAllocationEntry(
                allocation_id="alloc_1",
                intervention_id="tax_cut",
                amount=MoneyValue(amount=Decimal("90"), currency="USD"),
            )
        ],
        monitoring_plan=[
            MonitoringSignalSpec(
                monitoring_id="monitor_1",
                metric_id="welfare_metric",
            )
        ],
        metadata={"interpretability_score": 0.75},
    )
    stack = ObjectiveStack(max_statistical_uncertainty=0.5)
    vector = stack.evaluate(
        PolicyEvaluationBundle(
            candidate=candidate,
            simulation_metrics={
                "policy_value": 10.0,
                "employment_rate": 0.93,
                "welfare": 12.0,
            },
            distributional_report=_distributional_report(gini_delta=0.01),
            causal_effect_report=_causal_effect_report(),
            cross_graph_profile=_cross_graph_profile(),
            uncertainty_envelope=_uncertainty(statistical=0.5, transport=0.2),
        )
    )

    assert vector.feasible is True
    assert (
        vector.hard_constraints["policy_budget_constraint"].status == ConstraintStatus.NEAR_BINDING
    )
    assert vector.hard_constraints["statistical_constraint"].status == ConstraintStatus.NEAR_BINDING
    assert vector.secondary["transportability"].value == pytest.approx(1.0)


def test_objective_stack_extracts_blockers_from_uncertainty_and_equity() -> None:
    candidate = PolicyCandidateSchema.from_trinity_bundle(_bundle(), candidate_id="candidate_a")
    stack = ObjectiveStack(max_statistical_uncertainty=0.5)
    vector = stack.evaluate(
        PolicyEvaluationBundle(
            candidate=candidate,
            simulation_metrics={"policy_value": 8.0, "employment_rate": 0.8},
            distributional_report=_distributional_report(gini_delta=0.05),
            causal_effect_report=_causal_effect_report(),
            cross_graph_profile=_cross_graph_profile(transport_status=TransportStatus.UNSUPPORTED),
            uncertainty_envelope=_uncertainty(statistical=0.51, transport=0.6),
        )
    )

    assert vector.feasible is False
    assert "statistical_constraint" in vector.blocking_reasons
    assert "equity_constraint" in vector.blocking_reasons
    assert "transport_constraint" in vector.blocking_reasons
    assert vector.secondary["evidence_depth"].value >= 0.0


def test_objective_stack_uses_ambiguity_certificate_for_budget_equity_and_robustness() -> None:
    candidate = PolicyCandidateSchema.from_trinity_bundle(_bundle(), candidate_id="candidate_a")
    certificate = AmbiguityCertificate(
        ambiguity_set_type="moment_mean_cov_support",
        confidence_level=0.95,
        overall_status="warn",
        per_constraint=(
            ConstraintCertificate(
                name="budget",
                constraint_class="budget",
                formulation="dr_chance_scalar_moment",
                exactness="conservative_exact_for_scalarized_moments",
                worst_case_bound=97.0,
                threshold=100.0,
                slack=3.0,
                solver_family="SOCP",
                epsilon=0.05,
                violation_probability_bound=0.031,
            ),
            ConstraintCertificate(
                name="equity_low_vs_high",
                constraint_class="equity",
                formulation="dr_chance_scalar_moment",
                exactness="conservative_exact_for_scalarized_moments",
                worst_case_bound=-0.01,
                threshold=0.0,
                slack=0.01,
                solver_family="SOCP",
                epsilon=0.05,
                violation_probability_bound=0.046,
            ),
        ),
        price_of_ambiguity=4.2,
    )

    stack = ObjectiveStack(max_statistical_uncertainty=0.5)
    vector = stack.evaluate(
        PolicyEvaluationBundle(
            candidate=candidate,
            simulation_metrics={"policy_value": 11.0, "employment_rate": 0.91},
            distributional_report=_distributional_report(gini_delta=0.01),
            causal_effect_report=_causal_effect_report(),
            cross_graph_profile=_cross_graph_profile(),
            uncertainty_envelope=_uncertainty(statistical=0.2, transport=0.2),
            ambiguity_certificate=certificate,
        )
    )

    assert vector.hard_constraints["policy_budget_constraint"].source == "ambiguity_certificate"
    assert (
        vector.hard_constraints["policy_budget_constraint"].status == ConstraintStatus.NEAR_BINDING
    )
    assert vector.hard_constraints["equity_constraint"].source == "ambiguity_certificate"
    assert vector.hard_constraints["equity_constraint"].status == ConstraintStatus.NEAR_BINDING
    assert (
        vector.hard_constraints["statistical_constraint"].source
        == "uncertainty_envelope+ambiguity_certificate"
    )
    assert vector.secondary["robustness"].source == "causal_effect_report+ambiguity_certificate"
    assert vector.metadata["ambiguity_certificate_status"] == "warn"


def test_policy_runtime_propagates_ambiguity_certificate_into_outputs() -> None:
    candidate = PolicyCandidateSchema.from_trinity_bundle(_bundle(), candidate_id="candidate_a")
    certificate = AmbiguityCertificate(
        ambiguity_set_type="moment_mean_cov_support",
        confidence_level=0.95,
        overall_status="pass",
        per_constraint=(
            ConstraintCertificate(
                name="budget",
                constraint_class="budget",
                formulation="dr_chance_scalar_moment",
                exactness="conservative_exact_for_scalarized_moments",
                worst_case_bound=92.0,
                threshold=100.0,
                slack=8.0,
                solver_family="SOCP",
                epsilon=0.05,
                violation_probability_bound=0.02,
            ),
        ),
    )

    artifact = ProductionPolicyEvaluationBackend().evaluate(
        candidate,
        fidelity="selection",
        simulation_metrics={"policy_value": 9.0, "employment_rate": 0.84},
        uncertainty=_uncertainty(statistical=0.2, transport=0.2),
        distributional_report=None,
        causal_effect_report=None,
        cross_graph_profile=None,
        governance_report=None,
        ambiguity_certificate=certificate,
    )

    assert "ambiguity_certificate" in artifact.provenance.source_components
    assert artifact.simulation_results["ambiguity_certificate"]["overall_status"] == "pass"
    assert artifact.evaluation_vector.metadata["ambiguity_certificate_status"] == "pass"
    assert (
        artifact.evaluation_vector.hard_constraints["policy_budget_constraint"].source
        == "ambiguity_certificate"
    )
