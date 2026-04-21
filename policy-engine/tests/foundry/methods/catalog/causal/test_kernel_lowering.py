from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    EstimationStrategy,
    compile_estimand,
    recommend_estimator,
)
from polisyos.foundry.methods.catalog.causal.kernel_lowering import (
    build_kernel_estimator_spec,
)
from polisyos.ir.analytics.estimand import (
    DistributionLawQuery,
    make_backdoor_estimand,
    make_distribution_law_estimand,
    make_frontdoor_estimand,
)
from polisyos.ir.analytics.kernel_causal import (
    KernelEstimatorTemplate,
    KernelLoweringDisposition,
)


def _distributional_backdoor_ast():
    query = DistributionLawQuery(
        outcome_variables=("Y",),
        intervention_set=("T",),
        conditioning=("Z",),
        support_space="real",
        representation="cdf",
    )
    return make_distribution_law_estimand(query=query, identification_method="dist_id_v1")


def test_build_kernel_estimator_spec_respects_explicit_template_for_distribution_law() -> None:
    ast = _distributional_backdoor_ast()
    spec = build_kernel_estimator_spec(
        ast,
        shape="unknown",
        identification_metadata={
            "kernel_template": "backdoor_cme",
            "query_kind": "distribution_law",
            "distributional_query_kind": "interventional_law",
        },
    )

    assert spec.template is KernelEstimatorTemplate.BACKDOOR_CME
    assert spec.lowering_disposition is KernelLoweringDisposition.READY
    assert spec.output_kernel.characteristic is True
    assert spec.variable_roles["treatment"] == ("T",)
    assert spec.variable_roles["outcome"] == ("Y",)


def test_build_kernel_estimator_spec_downgrades_non_characteristic_distributional_kernel() -> None:
    ast = _distributional_backdoor_ast()
    spec = build_kernel_estimator_spec(
        ast,
        shape="unknown",
        identification_metadata={
            "kernel_template": "backdoor_cme",
            "query_kind": "distribution_law",
            "distributional_query_kind": "interventional_law",
            "output_kernel": {
                "name": "linear",
                "params": {},
                "characteristic": False,
                "weak_metrizing": False,
            },
        },
    )

    assert spec.lowering_disposition is KernelLoweringDisposition.REPRESENTATION_ONLY
    assert "output_kernel_not_characteristic" in spec.blocking_reasons


def test_build_kernel_estimator_spec_blocks_inverse_mode_without_operator_certificate() -> None:
    ast = make_backdoor_estimand(
        treatment="T",
        outcome="Y",
        adjustment_set=("Z",),
        dataset_ref="ds1",
    ).model_copy(update={"identification_method": "iv"})
    spec = build_kernel_estimator_spec(
        ast,
        shape="iv",
        identification_metadata={
            "kernel_lowering_requested": True,
        },
    )

    assert spec.template is KernelEstimatorTemplate.KIV
    assert spec.lowering_disposition is KernelLoweringDisposition.PROOF_ONLY
    assert "operator_certificate_missing" in spec.blocking_reasons


def test_recommend_estimator_routes_kernel_requested_backdoor_into_cme_plugin() -> None:
    ast = make_backdoor_estimand(
        treatment="T",
        outcome="Y",
        adjustment_set=("Z",),
        dataset_ref="ds1",
    )
    recommendation = recommend_estimator(
        ast,
        n_obs=500,
        identification_metadata={
            "kernel_lowering_requested": True,
            "kernel_template": "backdoor_cme",
            "distributional_query_kind": "interventional_law",
        },
    )

    assert recommendation.strategy is EstimationStrategy.CME_PLUGIN
    assert recommendation.primary_method_fqn == "causal.kernel.cme_plugin@1.0.0"


def test_recommend_estimator_routes_kernel_requested_frontdoor_into_kernel_frontdoor() -> None:
    ast = make_frontdoor_estimand(
        treatment="T",
        outcome="Y",
        mediator="M",
        dataset_ref="ds1",
    )
    recommendation = recommend_estimator(
        ast,
        n_obs=500,
        identification_metadata={"kernel_lowering_requested": True},
    )

    assert recommendation.strategy is EstimationStrategy.KERNEL_FRONTDOOR
    assert recommendation.primary_method_fqn == "causal.kernel.frontdoor_cme@1.0.0"


def test_recommend_estimator_refuses_kernel_inverse_mode_without_certificate() -> None:
    ast = make_backdoor_estimand(
        treatment="T",
        outcome="Y",
        adjustment_set=("Z",),
        dataset_ref="ds1",
    ).model_copy(update={"identification_method": "iv"})
    recommendation = recommend_estimator(
        ast,
        n_obs=500,
        identification_metadata={"kernel_lowering_requested": True},
    )

    assert recommendation.strategy is EstimationStrategy.REFUSE
    assert recommendation.primary_method_fqn == "causal.kernel.refusal@1.0.0"
    assert "operator_certificate_missing" in recommendation.notes


def test_compile_estimand_kernel_backdoor_adds_kernel_nodes() -> None:
    ast = make_backdoor_estimand(
        treatment="T",
        outcome="Y",
        adjustment_set=("Z",),
        dataset_ref="ds1",
    )
    recommendation, graph = compile_estimand(
        ast,
        run_id="kernel-backdoor",
        n_obs=500,
        identification_metadata={
            "kernel_lowering_requested": True,
            "kernel_template": "dr_cme",
            "distributional_query_kind": "interventional_law",
            "binary_treatment": True,
        },
    )

    fqns = [node.method_fqn for node in graph.nodes]
    assert recommendation.strategy is EstimationStrategy.DR_CME
    assert "causal.kernel.kernel_semantics_diagnostics" in fqns
    assert "causal.kernel.nuisance.fit_cme_y_given_xz" in fqns
    assert "causal.kernel.nuisance.fit_propensity" in fqns
    assert "causal.kernel.dr_cme" in fqns
    assert "causal.kernel.effect_test" in fqns


def test_compile_estimand_distribution_law_kernel_template_is_supported_via_metadata() -> None:
    ast = _distributional_backdoor_ast()
    recommendation, graph = compile_estimand(
        ast,
        run_id="kernel-law",
        identification_metadata={
            "kernel_lowering_requested": True,
            "kernel_template": "backdoor_cme",
            "query_kind": "distribution_law",
            "distributional_query_kind": "interventional_law",
        },
    )

    fqns = [node.method_fqn for node in graph.nodes]
    assert recommendation.strategy is EstimationStrategy.CME_PLUGIN
    assert "causal.kernel.cme_plugin" in fqns
    assert "causal.kernel.kernel_semantics_diagnostics" in fqns
