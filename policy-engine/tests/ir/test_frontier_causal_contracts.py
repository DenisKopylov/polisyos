from __future__ import annotations

import pytest

import polisyos.ir.analytics as analytics
from polisyos.ir import enumerate_ir_exports, get_ir_type
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_rl import (
    CausalDecisionProcessType,
    CausalRLContract,
    CounterfactualPolicyOptimizationSpec,
)
from polisyos.ir.analytics.invariance import (
    EnvironmentShiftType,
    EnvironmentSpec,
    InvarianceMethod,
    InvarianceResult,
    InvarianceVerdict,
    InvariantMechanismHypothesis,
    MultiEnvironmentCausalContract,
)
from polisyos.ir.analytics.recourse import (
    ContrastiveExplanation,
    CounterfactualExplanation,
    RecourseAction,
    RecourseActionType,
    RecourseFeasibility,
    RecoursePlan,
    RecourseReport,
)
from polisyos.ir.analytics.representation_learning import (
    LatentConfounderContract,
    LatentTrustLevel,
    LatentVariableSpec,
    RepresentationEncoderSpec,
    RepresentationLearningResult,
    RepresentationModelFamily,
)
from polisyos.ir.analytics.temporal_frontier import (
    DynamicProcessFamily,
    EquivalenceClassSummary,
    EquivalenceClassType,
    RegimeSwitchSegment,
    TemporalDiscoveryEdge,
    TemporalDiscoveryFrontierReport,
    TemporalDiscoveryMethod,
)


def test_representation_learning_contracts_round_trip() -> None:
    contract = LatentConfounderContract(
        contract_id="cevae_poverty",
        model_family=RepresentationModelFamily.CEVAE,
        treatment_field="policy.transfer",
        outcome_field="household.income",
        observed_covariates=("baseline_income", "household_size"),
        latent_variables=[
            LatentVariableSpec(
                latent_id="u_resilience",
                dimension=4,
                observed_children=("household.income",),
            )
        ],
        encoder=RepresentationEncoderSpec(
            encoder_id="cevae_encoder_v1",
            input_fields=("baseline_income", "household_size", "policy.transfer"),
            architecture_hint="mlp",
            latent_dimensions={"u_resilience": 4},
        ),
    )
    result = RepresentationLearningResult(
        contract_id="cevae_poverty",
        model_family=RepresentationModelFamily.CEVAE,
        learned_latent_ids=("u_resilience",),
        trust_level=LatentTrustLevel.CONDITIONAL,
        reconstruction_loss=0.21,
        counterfactual_consistency_score=0.83,
    )

    assert LatentConfounderContract.model_validate_json(contract.model_dump_json()) == contract
    assert RepresentationLearningResult.model_validate_json(result.model_dump_json()) == result


def test_invariance_and_temporal_frontier_contracts_validate() -> None:
    contract = MultiEnvironmentCausalContract(
        contract_id="employment_invariance",
        method=InvarianceMethod.ICP,
        target_variable="employment_rate",
        environments=[
            EnvironmentSpec(
                environment_id="city_a",
                shift_type=EnvironmentShiftType.COVARIATE,
                context_features=("labor_market_tightness",),
            ),
            EnvironmentSpec(
                environment_id="city_b",
                shift_type=EnvironmentShiftType.INTERVENTIONAL,
                context_features=("training_subsidy",),
            ),
        ],
    )
    result = InvarianceResult(
        contract_id="employment_invariance",
        method=InvarianceMethod.ICP,
        verdict=InvarianceVerdict.PARTIAL,
        hypotheses=[
            InvariantMechanismHypothesis(
                hypothesis_id="employment_given_training",
                target_variable="employment_rate",
                invariant_parents=("training_subsidy",),
                score=0.74,
            )
        ],
        accepted_hypothesis_ids=("employment_given_training",),
        environment_risks={"city_a": 0.12, "city_b": 0.28},
    )
    report = TemporalDiscoveryFrontierReport(
        method=TemporalDiscoveryMethod.PCMCI_PLUS,
        process_family=DynamicProcessFamily.REGIME_SWITCHING,
        unified_graph=CausalGraphModel(
            graph_type=GraphType.PAG,
            nodes=["X", "Y"],
            edges=[CausalEdge(src="X", dst="Y")],
            discovery_method="pcmci_plus",
        ),
        edges=[
            TemporalDiscoveryEdge(
                src="X",
                dst="Y",
                lag=1,
                confidence=0.91,
                source_method=TemporalDiscoveryMethod.PCMCI_PLUS,
            )
        ],
        regime_segments=[
            RegimeSwitchSegment(regime_id="r1", start_index=0, end_index=24)
        ],
        equivalence_class=EquivalenceClassSummary(
            class_type=EquivalenceClassType.PAG,
            compelled_edges=("X->Y@lag1",),
        ),
    )

    assert contract.method is InvarianceMethod.ICP
    assert result.accepted_hypothesis_ids == ("employment_given_training",)
    assert report.regime_segments[0].regime_id == "r1"


def test_causal_rl_contract_rejects_overlapping_state_and_action_variables() -> None:
    with pytest.raises(ValueError, match="state and action variables must be disjoint"):
        CausalRLContract(
            contract_id="bad_rl",
            process_type=CausalDecisionProcessType.CAUSAL_MDP,
            state_variables=("income", "exposure"),
            action_variables=("exposure",),
            reward_variable="reward",
            optimization=CounterfactualPolicyOptimizationSpec(
                objective="counterfactual_return",
                evaluation_horizon=10,
            ),
        )


def test_recourse_contracts_and_analytics_facade_exports() -> None:
    report = RecourseReport(
        subject_id="hh_1",
        plans=[
            RecoursePlan(
                plan_id="plan_1",
                feasibility=RecourseFeasibility.FEASIBLE,
                actions=[
                    RecourseAction(
                        feature_path="income",
                        action_type=RecourseActionType.INCREASE,
                        to_value=1200,
                        cost=5.0,
                    )
                ],
                total_cost=5.0,
                robustness_score=0.81,
            )
        ],
        counterfactual_explanations=[
            CounterfactualExplanation(
                explanation_id="cf_1",
                factual_outcome="rejected",
                counterfactual_outcome="approved",
                changed_features=("income",),
                supporting_actions=[
                    RecourseAction(
                        feature_path="income",
                        action_type=RecourseActionType.INCREASE,
                        to_value=1200,
                    )
                ],
            )
        ],
        contrastive_explanations=[
            ContrastiveExplanation(
                explanation_id="contrast_1",
                factual_label="rejected",
                foil_label="approved",
                decisive_factors=("income",),
            )
        ],
    )

    assert RecourseReport.model_validate_json(report.model_dump_json()) == report
    assert analytics.LatentConfounderContract is LatentConfounderContract
    assert analytics.RecourseReport is RecourseReport
    analytics_exports = {entry.export_name for entry in enumerate_ir_exports("analytics")}
    assert "TemporalDiscoveryFrontierReport" in analytics_exports

    frontier_type = get_ir_type("LatentConfounderContract")
    assert frontier_type.module == "polisyos.ir.analytics.representation_learning"
    assert frontier_type.docs_link.endswith(
        "#polisyos-ir-analytics-representation-learning-latentconfoundercontract"
    )
