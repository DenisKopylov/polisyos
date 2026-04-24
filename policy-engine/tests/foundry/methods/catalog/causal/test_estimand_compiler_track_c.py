"""Track C — Compiler: tests for C1-C5 additions to estimand_compiler.py."""

import pytest

from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    EstimandShape,
    EstimationStrategy,
    ExecutorGraph,
    ExecutorNode,
    classify_estimand,
    compile_estimand,
    compile_to_method_dag_nodes,
    recommend_estimator,
)
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ModifiedTreatmentPolicyNode,
    PathSpecificNode,
    ProductNode,
    SideCondition,
    SideConditionKind,
    StochasticInterventionNode,
    StochasticPolicy,
    SumNode,
    make_backdoor_estimand,
    make_frontdoor_estimand,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dml_ast(n_covariates: int = 6) -> EstimandAST:
    """Backdoor AST with enough covariates to trigger DML_COMPATIBLE."""
    adj = tuple(f"Z{i}" for i in range(n_covariates))
    return make_backdoor_estimand(treatment="T", outcome="Y", adjustment_set=adj, dataset_ref="ds1")


def _make_iv_ast_by_marker() -> EstimandAST:
    """AST with identification_method='iv' — simplest IV detection path."""
    base = make_backdoor_estimand(
        treatment="T", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
    )
    return base.model_copy(update={"identification_method": "iv"})


def _make_iv_ast_by_side_condition() -> EstimandAST:
    """AST with EXCLUSION_RESTRICTION side-condition at AST level."""
    sc = SideCondition(kind=SideConditionKind.EXCLUSION_RESTRICTION, variables=("W",))
    base = make_backdoor_estimand(
        treatment="T", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
    )
    return base.model_copy(update={"side_conditions": (sc,)})


def _make_cate_ast_by_marker() -> EstimandAST:
    """AST with identification_method='cate'."""
    base = make_backdoor_estimand(
        treatment="T", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
    )
    return base.model_copy(update={"identification_method": "cate"})


def _make_cate_ast_by_conditioning() -> EstimandAST:
    """AST where outcome conditions on effect modifier V that is NOT marginalized.

    Structure: Σ_Z P(Y | T, Z, V) · P(Z)
    where V is an effect modifier (not summed over), triggering CATE detection.
    """
    # Outcome conditions on T, Z (confounder, summed over), and V (effect modifier, NOT summed)
    outcome_ref = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        conditioning=("T", "Z", "V"),
        dataset_ref="ds1",
    )
    covar_ref = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Z",),
        dataset_ref="ds1",
    )
    product = ProductNode(factors=(outcome_ref, covar_ref))
    # Only Z is summed over — V is NOT in summation_vars → structural CATE signal
    root = SumNode(summation_vars=("Z",), operand=product)
    return EstimandAST(
        query_str="E[Y|do(T), V=v]",
        root=root,
        treatment="T",
        outcome="Y",
        all_variables=("T", "Y", "Z", "V"),
        identification_method="backdoor",
    )


def _make_soft_policy_ast(policy_expr: str = "pi(T|Z)") -> EstimandAST:
    """Simple stochastic-policy AST for compiler routing tests."""
    inner = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        conditioning=("T", "Z"),
        dataset_ref="ds1",
    )
    root = StochasticInterventionNode(
        treatment_var="T",
        policy=StochasticPolicy(
            policy_type="soft",
            conditioning_vars=("Z",),
            policy_expr=policy_expr,
        ),
        inner_do_node=inner,
        integration_var="T",
    )
    return EstimandAST(
        query_str="E_pi[Y]",
        root=root,
        treatment="T",
        outcome="Y",
        all_variables=("T", "Y", "Z"),
        identification_method="sid_soft",
    )


def _make_shift_policy_ast() -> EstimandAST:
    """Simple shift/MTP AST for compiler routing tests."""
    inner = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        conditioning=("T", "Z"),
        dataset_ref="ds1",
    )
    root = ModifiedTreatmentPolicyNode(
        treatment_var="T",
        policy_expr="T+0.25",
        natural_treatment_var="T",
        covariates=("Z",),
        inner_node=inner,
        domain=DistributionDomain.SOURCE,
        dataset_ref="ds1",
    )
    return EstimandAST(
        query_str="E_d[Y|mtp(T)]",
        root=root,
        treatment="T",
        outcome="Y",
        all_variables=("T", "Y", "Z"),
        identification_method="sid_shift",
    )


def _make_proximal_mediation_ast() -> EstimandAST:
    """Path-specific AST carrying the Stage 11.3 proximal mediation marker."""
    root = PathSpecificNode(
        treatment="A",
        outcome="Y",
        active_paths=(("A", "M", "Y"),),
        frozen_paths=(("A", "Y"),),
        reference_treatment=0.0,
        active_treatment=1.0,
        dataset_ref="ds1",
    )
    return EstimandAST(
        query_str="E[Y{1, M(0)}]",
        root=root,
        treatment="A",
        outcome="Y",
        all_variables=("A", "M", "Y", "X", "Z", "W"),
        identification_method="proximal_mediation|target=nie|mediator=M",
    )


# ---------------------------------------------------------------------------
# C1: TMLE path
# ---------------------------------------------------------------------------


class TestC1TmleRoute:
    def test_dml_compatible_small_sample_gives_tmle(self):
        ast = _make_dml_ast()
        rec = recommend_estimator(ast, n_obs=300, covariate_dim=6)
        assert rec.strategy is EstimationStrategy.TMLE
        assert rec.shape is EstimandShape.DML_COMPATIBLE
        assert rec.confidence > 0

    def test_dml_compatible_boundary_499_gives_tmle(self):
        ast = _make_dml_ast()
        rec = recommend_estimator(ast, n_obs=499, covariate_dim=6)
        assert rec.strategy is EstimationStrategy.TMLE

    def test_dml_compatible_boundary_500_gives_dml(self):
        ast = _make_dml_ast()
        rec = recommend_estimator(ast, n_obs=500, covariate_dim=6)
        assert rec.strategy is EstimationStrategy.DML

    def test_dml_compatible_large_sample_gives_dml(self):
        ast = _make_dml_ast()
        rec = recommend_estimator(ast, n_obs=1000, covariate_dim=6)
        assert rec.strategy is EstimationStrategy.DML

    def test_dml_compatible_none_obs_gives_dml(self):
        ast = _make_dml_ast()
        rec = recommend_estimator(ast, n_obs=None, covariate_dim=6)
        assert rec.strategy is EstimationStrategy.DML

    def test_tmle_note_mentions_sample_size(self):
        ast = _make_dml_ast()
        rec = recommend_estimator(ast, n_obs=300, covariate_dim=6)
        assert "300" in rec.notes or "500" in rec.notes

    def test_tmle_compile_dag_contains_tmle_node(self):
        ast = _make_dml_ast()
        rec = recommend_estimator(ast, n_obs=300, covariate_dim=6)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c1-1", use_cross_fitting=True)
        fqns = [n.method_fqn for n in eg.nodes]
        assert any("tmle" in fqn for fqn in fqns)

    def test_tmle_compile_dag_contains_cross_fit_with_use_cross_fitting(self):
        ast = _make_dml_ast()
        rec = recommend_estimator(ast, n_obs=300, covariate_dim=6)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c1-2", use_cross_fitting=True)
        fqns = [n.method_fqn for n in eg.nodes]
        assert any("cross_fit" in fqn for fqn in fqns)

    def test_tmle_compile_no_cross_fit_when_disabled(self):
        ast = _make_dml_ast()
        rec = recommend_estimator(ast, n_obs=300, covariate_dim=6)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c1-3", use_cross_fitting=False)
        fqns = [n.method_fqn for n in eg.nodes]
        assert not any("cross_fit" in fqn for fqn in fqns)

    def test_tmle_compile_end_to_end(self):
        ast = _make_dml_ast()
        rec, eg = compile_estimand(ast, run_id="c1-e2e", n_obs=300, covariate_dim=6)
        assert rec.strategy is EstimationStrategy.TMLE
        assert isinstance(eg, ExecutorGraph)
        assert len(eg.nodes) > 0


# ---------------------------------------------------------------------------
# C2: IV compilation rule
# ---------------------------------------------------------------------------


class TestC2IvRule:
    def test_iv_classification_via_marker(self):
        ast = _make_iv_ast_by_marker()
        assert classify_estimand(ast) is EstimandShape.IV

    def test_iv_classification_via_side_condition(self):
        ast = _make_iv_ast_by_side_condition()
        assert classify_estimand(ast) is EstimandShape.IV

    def test_iv_recommend_low_dim_gives_tsls(self):
        ast = _make_iv_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500, covariate_dim=3)
        assert rec.strategy is EstimationStrategy.IV
        assert "tsls" in rec.primary_method_fqn

    def test_iv_recommend_high_dim_gives_dml_iv(self):
        ast = _make_iv_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500, covariate_dim=10)
        assert rec.strategy is EstimationStrategy.IV
        assert "dml_iv" in rec.primary_method_fqn

    def test_iv_recommend_high_dim_requires_cross_fitting(self):
        ast = _make_iv_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500, covariate_dim=10)
        assert rec.requires_cross_fitting is True

    def test_iv_recommend_low_dim_no_cross_fitting(self):
        ast = _make_iv_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500, covariate_dim=3)
        assert rec.requires_cross_fitting is False

    def test_iv_compile_dag_contains_iv_estimator(self):
        ast = _make_iv_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500, covariate_dim=3)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c2-1")
        fqns = [n.method_fqn for n in eg.nodes]
        assert any("iv" in fqn or "tsls" in fqn for fqn in fqns)

    def test_iv_compile_sensitivity_has_skip_if_failed(self):
        ast = _make_iv_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500, covariate_dim=3)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c2-2")
        sens_nodes = [n for n in eg.nodes if "sensitivity" in n.method_fqn]
        assert len(sens_nodes) > 0
        assert all(len(n.skip_if_failed) > 0 for n in sens_nodes)

    def test_iv_shape_in_recommendation(self):
        ast = _make_iv_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500)
        assert rec.shape is EstimandShape.IV


# ---------------------------------------------------------------------------
# C3: Meta-learner path
# ---------------------------------------------------------------------------


class TestC3MetaLearner:
    def test_cate_classification_via_marker(self):
        ast = _make_cate_ast_by_marker()
        assert classify_estimand(ast) is EstimandShape.CATE_REQUIRED

    def test_cate_classification_via_hte_marker(self):
        base = make_backdoor_estimand(
            treatment="T", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        ast = base.model_copy(update={"identification_method": "hte_estimation"})
        assert classify_estimand(ast) is EstimandShape.CATE_REQUIRED

    def test_cate_classification_via_conditioning(self):
        ast = _make_cate_ast_by_conditioning()
        assert classify_estimand(ast) is EstimandShape.CATE_REQUIRED

    def test_cate_small_sample_t_learner(self):
        ast = _make_cate_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=100)
        assert rec.shape is EstimandShape.CATE_REQUIRED
        assert "t_learner" in rec.primary_method_fqn

    def test_cate_medium_sample_x_learner(self):
        ast = _make_cate_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500)
        assert "x_learner" in rec.primary_method_fqn

    def test_cate_large_sample_dr_learner(self):
        ast = _make_cate_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=2000)
        assert "dr_learner" in rec.primary_method_fqn

    def test_cate_none_obs_dr_learner(self):
        ast = _make_cate_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=None)
        assert "dr_learner" in rec.primary_method_fqn

    def test_cate_boundary_200_x_learner(self):
        ast = _make_cate_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=200)
        assert "x_learner" in rec.primary_method_fqn

    def test_cate_boundary_1000_dr_learner(self):
        ast = _make_cate_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=1000)
        assert "dr_learner" in rec.primary_method_fqn

    def test_cate_compile_contains_meta_learner_node(self):
        ast = _make_cate_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c3-1", use_cross_fitting=True)
        fqns = [n.method_fqn for n in eg.nodes]
        assert any("learner" in fqn for fqn in fqns)

    def test_cate_compile_has_cross_fit(self):
        ast = _make_cate_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c3-2", use_cross_fitting=True)
        fqns = [n.method_fqn for n in eg.nodes]
        assert any("cross_fit" in fqn for fqn in fqns)

    def test_cate_compile_sensitivity_has_skip_if_failed(self):
        ast = _make_cate_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c3-3", use_cross_fitting=False)
        sens_nodes = [n for n in eg.nodes if "sensitivity" in n.method_fqn]
        assert len(sens_nodes) > 0
        assert all(len(n.skip_if_failed) > 0 for n in sens_nodes)

    def test_cate_note_mentions_learner(self):
        ast = _make_cate_ast_by_marker()
        rec = recommend_estimator(ast, n_obs=500)
        assert "learner" in rec.notes.lower() or "CATE" in rec.notes


# ---------------------------------------------------------------------------
# C3b: Stochastic / shift policy routing
# ---------------------------------------------------------------------------


class TestC3bPolicyRouting:
    def test_shift_mtp_root_classifies_as_shift_intervention(self):
        ast = _make_shift_policy_ast()
        assert classify_estimand(ast) is EstimandShape.SHIFT_INTERVENTION

    def test_shift_recommendation_uses_registered_continuous_treatment_method(self):
        ast = _make_shift_policy_ast()
        rec = recommend_estimator(ast, n_obs=500)
        assert rec.primary_method_fqn == "causal.continuous_treatment.shift@1.0.0"

    def test_stochastic_recommendation_uses_registered_policy_plugin_method(self):
        ast = _make_soft_policy_ast()
        rec = recommend_estimator(ast, n_obs=500)
        assert rec.primary_method_fqn == "causal.stochastic.policy_plugin@1.0.0"

    def test_shift_compile_preserves_delta_and_adds_policy_overlap_diagnostic(self):
        ast = _make_shift_policy_ast()
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c3b-1")

        shift_node = next(
            n for n in eg.nodes if n.method_fqn == "causal.continuous_treatment.shift"
        )
        assert shift_node.params["delta"] == pytest.approx(0.25)
        assert any(n.method_fqn == "causal.diagnostics.policy_overlap" for n in eg.nodes)

    def test_stochastic_compile_adds_policy_overlap_diagnostic(self):
        ast = _make_soft_policy_ast()
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c3b-2")

        plugin_node = next(n for n in eg.nodes if n.method_fqn == "causal.stochastic.policy_plugin")
        overlap_node = next(
            n for n in eg.nodes if n.method_fqn == "causal.diagnostics.policy_overlap"
        )
        assert overlap_node.depends_on == (plugin_node.node_id,)

    def test_incremental_policy_prefers_binary_policy_tmle_family(self):
        ast = _make_soft_policy_ast(policy_expr="incremental_odds(delta=1.5)")
        rec = recommend_estimator(ast, n_obs=800)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c3b-3")

        assert rec.primary_method_fqn == "causal.stochastic.policy_tmle@1.0.0"
        policy_node = next(n for n in eg.nodes if n.method_fqn == "causal.stochastic.policy_tmle")
        assert policy_node.params["incremental_delta"] == pytest.approx(1.5)
        assert any(n.method_fqn == "causal.diagnostics.policy_overlap" for n in eg.nodes)


# ---------------------------------------------------------------------------
# C3c: Proximal mediation routing
# ---------------------------------------------------------------------------


class TestC3cProximalMediationRouting:
    def test_proximal_mediation_marker_classifies_shape(self):
        ast = _make_proximal_mediation_ast()
        assert classify_estimand(ast) is EstimandShape.PROXIMAL_MEDIATION

    def test_proximal_mediation_recommendation_uses_template_method(self):
        ast = _make_proximal_mediation_ast()
        rec = recommend_estimator(ast, n_obs=500)
        assert rec.strategy is EstimationStrategy.PROXIMAL_MEDIATION
        assert rec.primary_method_fqn == "causal.proximal.proximal_mediation@1.0.0"
        assert rec.fallback_method_fqns == ("causal.bounds.bounds_engine@1.0.0",)

    def test_proximal_mediation_compile_emits_template_node(self):
        ast = _make_proximal_mediation_ast()
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c3c-1")

        prox_node = next(
            n for n in eg.nodes if n.method_fqn == "causal.proximal.proximal_mediation"
        )
        assert prox_node.params["theorem_family"] == "proximal_mediation_thm1_dukes_2023"
        assert prox_node.params["oracle_gate"] == "required"
        assert prox_node.params["target_effect"] == "psi"
        assert any("sensitivity" in n.method_fqn for n in eg.nodes)

    def test_proximal_mediation_compile_uses_certificate_roles_when_available(self):
        ast = _make_proximal_mediation_ast()
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(
            ast,
            rec,
            run_id="c3c-2",
            identification_metadata={
                "oracle_assumptions_accepted": True,
                "proximal_mediation_certificate": {
                    "query": {
                        "treatment": "A",
                        "mediator": "M",
                        "outcome": "Y",
                        "target_effect": "nie",
                    },
                    "variable_roles": {
                        "X": ["X"],
                        "Z": ["Z"],
                        "W": ["W"],
                    },
                },
            },
        )

        prox_node = next(
            n for n in eg.nodes if n.method_fqn == "causal.proximal.proximal_mediation"
        )
        assert prox_node.params["oracle_gate"] == "accepted"
        assert prox_node.params["target_effect"] == "nie"
        assert prox_node.params["mediator_name"] == "M"
        assert prox_node.params["treatment_proxy_names"] == ["Z"]


# ---------------------------------------------------------------------------
# C4: Conditional execution (skip_if_failed)
# ---------------------------------------------------------------------------


class TestC4SkipIfFailed:
    def test_executor_node_has_skip_if_failed_field(self):
        ast = make_backdoor_estimand(treatment="T", outcome="Y", adjustment_set=("Z",))
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c4-1", use_cross_fitting=False)
        for node in eg.nodes:
            assert hasattr(node, "skip_if_failed")
            assert isinstance(node.skip_if_failed, tuple)

    def test_sensitivity_node_has_nonempty_skip_if_failed_backdoor(self):
        ast = make_backdoor_estimand(treatment="T", outcome="Y", adjustment_set=("Z",))
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c4-2", use_cross_fitting=False)
        sens_nodes = [n for n in eg.nodes if "sensitivity" in n.method_fqn]
        assert len(sens_nodes) > 0
        assert all(len(n.skip_if_failed) > 0 for n in sens_nodes)

    def test_refute_node_has_nonempty_skip_if_failed_aipw(self):
        ast = make_backdoor_estimand(treatment="T", outcome="Y", adjustment_set=("Z",))
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c4-3", use_cross_fitting=True)
        refute_nodes = [n for n in eg.nodes if "refute" in n.method_fqn or "dowhy" in n.method_fqn]
        assert len(refute_nodes) > 0
        assert all(len(n.skip_if_failed) > 0 for n in refute_nodes)

    def test_skip_if_failed_node_ids_exist_in_graph(self):
        ast = make_backdoor_estimand(treatment="T", outcome="Y", adjustment_set=("Z",))
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c4-4", use_cross_fitting=True)
        all_ids = {n.node_id for n in eg.nodes}
        for node in eg.nodes:
            for sid in node.skip_if_failed:
                assert sid in all_ids, f"skip_if_failed node '{sid}' not found in graph"

    def test_skip_if_failed_serialised_in_dag_dicts(self):
        ast = make_backdoor_estimand(treatment="T", outcome="Y", adjustment_set=("Z",))
        rec = recommend_estimator(ast, n_obs=500)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c4-5", use_cross_fitting=False)
        dicts = eg.to_method_dag_dicts()
        for d in dicts:
            assert "skip_if_failed" in d

    def test_executor_node_default_skip_if_failed_empty(self):
        node = ExecutorNode(
            node_id="test_abc",
            method_fqn="some.method",
            method_version="1.0.0",
            params={},
            depends_on=(),
            reads_slots=(),
            writes_slots=(),
        )
        assert node.skip_if_failed == ()

    def test_dml_refute_skip_if_failed_points_to_estimator(self):
        ast = _make_dml_ast()
        rec = recommend_estimator(ast, n_obs=1000, covariate_dim=6)
        eg = compile_to_method_dag_nodes(ast, rec, run_id="c4-6", use_cross_fitting=False)
        # Find the DML estimator node
        est_node = next(n for n in eg.nodes if "double_ml" in n.method_fqn)
        # Find refute node
        refute_nodes = [n for n in eg.nodes if "dowhy_refute" in n.method_fqn]
        assert len(refute_nodes) > 0
        assert est_node.node_id in refute_nodes[0].skip_if_failed


# ---------------------------------------------------------------------------
# C5: Frontdoor nuisance schedule
# ---------------------------------------------------------------------------


class TestC5FrontdoorNuisanceSchedule:
    def test_frontdoor_compile_has_two_nuisance_nodes(self):
        ast = make_frontdoor_estimand(treatment="T", outcome="Y", mediator="M", dataset_ref="ds1")
        rec, eg = compile_estimand(ast, run_id="c5-1", n_obs=500)
        nuisance_nodes = [n for n in eg.nodes if n.is_nuisance]
        assert len(nuisance_nodes) == 2

    def test_frontdoor_nuisance_schedule_has_two_entries(self):
        ast = make_frontdoor_estimand(treatment="T", outcome="Y", mediator="M", dataset_ref="ds1")
        rec, eg = compile_estimand(ast, run_id="c5-2", n_obs=500)
        assert len(eg.nuisance_schedule) == 2

    def test_frontdoor_nuisance_schedule_ids_are_valid(self):
        ast = make_frontdoor_estimand(treatment="T", outcome="Y", mediator="M", dataset_ref="ds1")
        rec, eg = compile_estimand(ast, run_id="c5-3", n_obs=500)
        all_ids = {n.node_id for n in eg.nodes}
        for nid in eg.nuisance_schedule:
            assert nid in all_ids

    def test_frontdoor_mediator_nuisance_node_present(self):
        ast = make_frontdoor_estimand(treatment="T", outcome="Y", mediator="M", dataset_ref="ds1")
        rec, eg = compile_estimand(ast, run_id="c5-4", n_obs=500)
        fqns = [n.method_fqn for n in eg.nodes]
        assert any("mediator_density" in fqn for fqn in fqns)

    def test_frontdoor_outcome_nuisance_node_present(self):
        ast = make_frontdoor_estimand(treatment="T", outcome="Y", mediator="M", dataset_ref="ds1")
        rec, eg = compile_estimand(ast, run_id="c5-5", n_obs=500)
        fqns = [n.method_fqn for n in eg.nodes]
        assert any("outcome_given_mediator" in fqn for fqn in fqns)

    def test_frontdoor_mediation_estimator_depends_on_nuisance_nodes(self):
        ast = make_frontdoor_estimand(treatment="T", outcome="Y", mediator="M", dataset_ref="ds1")
        rec, eg = compile_estimand(ast, run_id="c5-6", n_obs=500)
        nuisance_ids = {n.node_id for n in eg.nodes if n.is_nuisance}
        med_node = next(n for n in eg.nodes if "causal_mediation" in n.method_fqn)
        # The mediation estimator must depend on both nuisance nodes
        assert nuisance_ids.issubset(set(med_node.depends_on))

    def test_frontdoor_mediation_estimator_skip_if_failed_nuisance(self):
        ast = make_frontdoor_estimand(treatment="T", outcome="Y", mediator="M", dataset_ref="ds1")
        rec, eg = compile_estimand(ast, run_id="c5-7", n_obs=500)
        nuisance_ids = {n.node_id for n in eg.nodes if n.is_nuisance}
        med_node = next(n for n in eg.nodes if "causal_mediation" in n.method_fqn)
        assert nuisance_ids.issubset(set(med_node.skip_if_failed))

    def test_frontdoor_nuisance_schedule_subset_of_all_node_ids(self):
        ast = make_frontdoor_estimand(treatment="T", outcome="Y", mediator="M", dataset_ref="ds1")
        rec, eg = compile_estimand(ast, run_id="c5-8", n_obs=500)
        all_ids = {n.node_id for n in eg.nodes}
        assert set(eg.nuisance_schedule).issubset(all_ids)
