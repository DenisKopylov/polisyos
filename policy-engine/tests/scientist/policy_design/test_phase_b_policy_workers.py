from __future__ import annotations

from decimal import Decimal

from polisyos.scientist.autotune.models import BenchmarkSplitManifest
from polisyos.scientist.doe.designs import ParameterSpec as DOEParameterSpec
from polisyos.scientist.engine.budget import BudgetState
from polisyos.scientist.policy_design.adversary import (
    ScenarioAdversaryConfig,
    ScenarioAdversaryWorker,
    ScenarioAttackSurface,
)
from polisyos.scientist.policy_design.critic import ConstraintCritic, ConstraintCriticInput
from polisyos.scientist.policy_design.output import (
    ChampionPolicyDossier,
    ConstraintSatisfactionEntry,
    ConstraintSatisfactionReport,
    PolicyBrief,
    SubgroupImpactEntry,
    SubgroupImpactReport,
    UncertaintyReport,
)
from polisyos.scientist.policy_design.translator import (
    PolicyTranslatorWorker,
    TranslatorCompliancePass,
    TranslatorInputBundle,
)
from polisyos.scientist.search.objective import CompositeObjective, GDPGrowthObjective
from polisyos.scientist.search.readiness import DecisionReadiness, DecisionReadinessContract

from .test_phase_b_output import _candidate, _evaluation_vector


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
        evidence_depth_required="meta_analytic",
    )


def _translator_bundle() -> TranslatorInputBundle:
    dossier = ChampionPolicyDossier(
        candidate_id="candidate_policy",
        candidate_hash="sha256:" + "a" * 64,
        readiness_level=DecisionReadiness.RECOMMENDATION_READY.value,
        executive_summary="Candidate candidate_policy is assessed at recommendation_ready.",
        objective_summary={"policy_value": 1.2, "employment": 0.4},
        constraint_summary=[
            ConstraintSatisfactionEntry(
                constraint_name="policy_budget_constraint",
                status="near_binding",
                observed_value=0.95,
                threshold=1.0,
            )
        ],
        subgroup_harms=["Low income"],
        surfaced_assumptions=_readiness_contract().assumptions_must_be_surfaced,
        uncertainty_summary={"statistical": 0.2, "structural": 0.3},
        transport_summary={},
        governance_summary={},
        stress_summary={},
    )
    return TranslatorInputBundle(
        dossier=dossier,
        readiness_contract=_readiness_contract(),
        constraint_report=ConstraintSatisfactionReport(
            candidate_id="candidate_policy",
            feasible=True,
            constraints=dossier.constraint_summary,
        ),
        subgroup_report=SubgroupImpactReport(
            candidate_id="candidate_policy",
            harmed_subgroups=[
                SubgroupImpactEntry(
                    subgroup_id="low_income",
                    label="Low income",
                    direction="negative",
                    net_impact=-1.0,
                    vulnerable=True,
                )
            ],
        ),
        uncertainty_report=UncertaintyReport(
            candidate_id="candidate_policy",
            readiness_level=DecisionReadiness.RECOMMENDATION_READY.value,
            uncertainties={"statistical": 0.2, "structural": 0.3},
            binding_types=[],
        ),
        budget_state=BudgetState(),
    )


def test_translator_falls_back_deterministically_without_gateway() -> None:
    bundle = _translator_bundle()
    brief = PolicyTranslatorWorker().translate(bundle)

    assert brief.readiness_level == DecisionReadiness.RECOMMENDATION_READY.value
    assert bundle.readiness_contract.assumptions_must_be_surfaced == brief.surfaced_assumptions
    assert "Low income" in brief.subgroup_harms
    assert "policy_budget_constraint" in brief.hard_constraint_notes


def test_translator_surfaces_degraded_evidence_channels() -> None:
    bundle = _translator_bundle()
    bundle = bundle.model_copy(
        update={
            "readiness_contract": bundle.readiness_contract.model_copy(
                update={
                    "metadata": {
                        "cross_graph_source_statuses": {
                            "academic": "missing_config",
                            "datasets": "missing_path",
                        },
                        "prior_knowledge_status": "degraded",
                    }
                }
            )
        }
    )

    brief = PolicyTranslatorWorker().translate(bundle)
    descriptions = [risk.description for risk in brief.risks]

    assert any("academic" in description and "missing_config" in description for description in descriptions)
    assert any("datasets" in description and "missing_path" in description for description in descriptions)
    assert any("Academic prior support is unavailable or degraded" in description for description in descriptions)


def test_translator_compliance_flags_all_anti_spin_invariants() -> None:
    bundle = _translator_bundle()
    brief = PolicyBrief(
        title="Spinny brief",
        executive_summary="Everything is deployment ready and safe.",
        readiness_level=DecisionReadiness.DEPLOYMENT_READY.value,
        surfaced_assumptions=[],
        uncertainty_highlights=[],
        subgroup_harms=[],
        hard_constraint_notes=[],
    )

    result = TranslatorCompliancePass().evaluate(
        brief,
        dossier=bundle.dossier,
        readiness_contract=bundle.readiness_contract,
        constraint_report=bundle.constraint_report,
        subgroup_report=bundle.subgroup_report,
        uncertainty_report=bundle.uncertainty_report,
    )

    codes = {finding.code for finding in result.findings}
    assert result.passed is False
    assert "readiness_overstated" in codes
    assert "assumptions_omitted" in codes
    assert "uncertainty_collapsed" in codes
    assert "negative_harm_omitted" in codes
    assert "binding_constraints_omitted" in codes


def test_constraint_critic_surfaces_budget_and_not_assessed_findings() -> None:
    candidate = _candidate()
    candidate = candidate.model_copy(
        update={
            "budget_allocation": [
                item.model_copy(update={"amount": item.amount.model_copy(update={"amount": Decimal("95")})})
                for item in candidate.budget_allocation
            ]
        }
    )
    critique = ConstraintCritic().evaluate(
        ConstraintCriticInput(
            candidate=candidate,
            evaluation_vector=_evaluation_vector(candidate),
        )
    )

    failure_types = {finding.failure_type for finding in critique.findings}
    assert critique.passed is True
    assert "budget_driver" in failure_types
    assert "overlap_not_assessed" in failure_types
    assert "binding_hard_constraint" in failure_types


def test_scenario_adversary_fallback_and_execution(tmp_path) -> None:
    worker = ScenarioAdversaryWorker(
        ScenarioAdversaryConfig(max_scenarios=3, collect_top_k=2)
    )
    surface = ScenarioAttackSurface(
        candidate_id="candidate_policy",
        parameter_specs=[
            DOEParameterSpec(name="shock", lower_bound=0.0, upper_bound=1.0),
            DOEParameterSpec(name="noise", lower_bound=0.0, upper_bound=1.0),
        ],
        base_metrics={"gdp_change": [0.1, 0.2, 0.3]},
        benchmark_split_manifest=BenchmarkSplitManifest(
            suite_id="suite",
            selection_ids=["a"],
            holdout_ids=["b"],
        ),
        vulnerability_threshold=0.5,
    )
    bundle = worker.propose(surface, run_id="adv_test", budget_state=BudgetState())

    assert bundle.fallback_used is True
    assert bundle.scenarios
    assert any(item.target_split == "hidden_holdout_only" for item in bundle.scenarios)

    result = worker.execute(
        surface=surface,
        base_objective=CompositeObjective([GDPGrowthObjective()]),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {
                "gdp_change": float(candidate.get("shock", 0.0)) + float(candidate.get("noise", 0.0))
            }
        },
        cas=None,
        run_id="adv_test",
    )

    assert result.compiled_plan.parameter_specs
    assert result.stress_test_report.total_scenarios_evaluated >= 1
    assert result.stress_test_report.vulnerabilities
