"""Tests for compile-time recovery strategy selection (Stage 12.3)."""

from polisyos.foundry.methods.catalog.causal.ast_lowerer import recursive_compile
from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    EstimandShape,
    EstimationStrategy,
    classify_estimand,
    compile_estimand,
    recommend_estimator,
)
from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
    _recoverability_certificate_from_result,
    ordered_recovery,
    test_recoverability as run_recoverability_check,
)
from polisyos.foundry.methods.catalog.causal.recovery_strategy_selector import (
    RecoveryEstimatorFamily,
    build_compile_time_recovery_summary,
    select_recovery_strategy,
)
from polisyos.ir.analytics.recoverability import (
    RecoverabilityEstimatorFamily,
    RecoverabilityNuisanceKind,
    RecoverabilityProofForm,
    RecoveryScope,
)
from polisyos.ir.analytics.mgraph import MissingnessKind, build_mgraph, extract_mgraph_metadata


def _make_mcar_recovery_ast():
    graph = build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        missingness_map={"X": MissingnessKind.MCAR},
    )
    meta = extract_mgraph_metadata(graph)
    return ordered_recovery(graph=graph, mgraph_meta=meta)


def _make_mcar_recovery_graph():
    graph = build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        missingness_map={"X": MissingnessKind.MCAR},
    )
    meta = extract_mgraph_metadata(graph)
    return graph, meta


def test_classify_ordered_recovery_as_missing_data_recovery():
    ast = _make_mcar_recovery_ast()

    assert classify_estimand(ast) is EstimandShape.MISSING_DATA_RECOVERY


def test_recovery_selector_prefers_doubly_robust_for_mcar_ordered_recovery():
    ast = _make_mcar_recovery_ast()

    plan = select_recovery_strategy(ast, n_obs=1000, covariate_dim=4)

    assert plan.family is RecoveryEstimatorFamily.DOUBLY_ROBUST
    assert plan.preferred_strategy == "aipw"
    assert plan.required_nuisance == ("propensity", "outcome_regression")


def test_recommend_estimator_routes_mcar_recovery_into_aipw_family():
    ast = _make_mcar_recovery_ast()

    recommendation = recommend_estimator(ast, n_obs=1000, covariate_dim=4)

    assert recommendation.shape is EstimandShape.MISSING_DATA_RECOVERY
    assert recommendation.strategy is EstimationStrategy.AIPW
    assert recommendation.primary_method_fqn == "causal.missing_data.aipw@1.0.0"


def test_recovery_selector_refuses_when_readiness_blocks_positivity():
    ast = _make_mcar_recovery_ast()

    plan = select_recovery_strategy(
        ast,
        n_obs=1000,
        covariate_dim=4,
        data_readiness={
            "decision": "block",
            "can_compile_estimation": False,
            "can_run_estimation": False,
            "blocking_reasons": ["positivity_failed"],
            "positivity": {"passes_positivity": False},
        },
    )

    assert plan.family is RecoveryEstimatorFamily.REFUSE
    assert "positivity_failed" in plan.reason
    assert "data_readiness_gate" in plan.safety_guards


def test_recovery_selector_prefers_tmle_when_readiness_warns_about_weights():
    ast = _make_mcar_recovery_ast()

    plan = select_recovery_strategy(
        ast,
        n_obs=1000,
        covariate_dim=4,
        data_readiness={
            "decision": "warn",
            "can_compile_estimation": True,
            "can_run_estimation": True,
            "positivity": {
                "passes_positivity": True,
                "ess_fraction": 0.40,
                "overlap_score": 0.65,
            },
        },
    )

    assert plan.family is RecoveryEstimatorFamily.DOUBLY_ROBUST
    assert plan.preferred_strategy == "tmle"
    assert "weight_stability_diagnostics" in plan.safety_guards
    assert "missing_data.tmle" in plan.compiler_lowering_hooks


def test_assumption_sensitive_recovery_refuses_without_human_acceptance():
    ast = _make_mcar_recovery_ast()
    certificate_summary = {
        "status": "recoverable_under_assumptions",
        "blocking_r_nodes": ["R_X"],
        "compile_time_recovery": build_compile_time_recovery_summary(ast),
    }

    recommendation = recommend_estimator(
        ast,
        n_obs=1000,
        covariate_dim=4,
        recoverability_certificate=certificate_summary,
    )

    assert recommendation.shape is EstimandShape.MISSING_DATA_RECOVERY
    assert recommendation.strategy is EstimationStrategy.REFUSE
    assert "automatic compilation refuses" in recommendation.notes.lower()


def test_compile_estimand_missing_data_recovery_builds_missing_data_aipw_graph():
    ast = _make_mcar_recovery_ast()

    recommendation, graph = compile_estimand(ast, run_id="recovery-aipw", n_obs=1000)
    method_fqns = [node.method_fqn for node in graph.nodes]

    assert recommendation.strategy is EstimationStrategy.AIPW
    assert "causal.nuisance.propensity_model" in method_fqns
    assert "causal.nuisance.outcome_model" in method_fqns
    assert "causal.missing_data.aipw" in method_fqns


def test_compile_estimand_recovery_refusal_builds_refusal_node():
    ast = _make_mcar_recovery_ast()
    certificate_summary = {
        "status": "recoverable_under_assumptions",
        "blocking_r_nodes": ["R_X"],
        "compile_time_recovery": build_compile_time_recovery_summary(ast),
    }

    recommendation, graph = compile_estimand(
        ast,
        run_id="recovery-refuse",
        n_obs=1000,
        recoverability_certificate=certificate_summary,
    )
    method_fqns = [node.method_fqn for node in graph.nodes]

    assert recommendation.strategy is EstimationStrategy.REFUSE
    assert "causal.missing_data.refusal" in method_fqns
    assert graph.warnings


def test_recoverability_certificate_publishes_typed_compile_time_fields():
    graph, meta = _make_mcar_recovery_graph()
    result = run_recoverability_check(
        query_vars=frozenset({"X", "Y"}),
        graph=graph,
        mgraph_meta=meta,
    )

    certificate = _recoverability_certificate_from_result(
        result=result,
        graph=graph,
        target_query="P(Y|do(X))",
        scope=RecoveryScope.CAUSAL_QUERY,
    )

    assert certificate.recovery_form is RecoverabilityProofForm.CONDITIONING
    assert certificate.identified_nuisance == (
        RecoverabilityNuisanceKind.OUTCOME_REGRESSION,
        RecoverabilityNuisanceKind.PROPENSITY,
    )
    assert certificate.recommended_estimator_family is RecoverabilityEstimatorFamily.DOUBLY_ROBUST
    assert certificate.compile_time_strategy == "aipw"
    assert "missing_data.aipw" in certificate.compile_time_lowering_hooks


def test_recursive_lowering_supports_recovered_distribution_nodes():
    ast = _make_mcar_recovery_ast()

    graph = recursive_compile(ast, run_id="recovery-recursive")
    method_fqns = [node.method_fqn for node in graph.nodes]

    assert "causal.missing_data.recovered_dist_dr" in method_fqns
