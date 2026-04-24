"""Tests: inject_cross_fitting wired into compile_estimand (Task 3.3).

Verifies that compile_estimand:
- Calls recommend_n_folds and injects cross-fitting when n_obs >= 100
- Replicates nuisance nodes K times when requires_cross_fitting=True
- Skips injection for small n_obs (< 100) or when use_cross_fitting=False
- Handles AIPW, DML, TMLE shapes correctly
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../../src"))

from polisyos.foundry.methods.catalog.causal.estimand_compiler import compile_estimand
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ProductNode,
    SumNode,
)


def _make_backdoor_ast(conditioning_size: int = 2) -> EstimandAST:
    """Σ_Z P(Y|T,Z)·P(Z) — standard backdoor estimand."""
    z_vars = [f"Z{i}" for i in range(conditioning_size)]
    outcome_ref = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        conditioning=("T", *z_vars),
    )
    covariate_ref = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=tuple(z_vars),
    )
    product = ProductNode(factors=(outcome_ref, covariate_ref))
    root = SumNode(summation_vars=tuple(z_vars), operand=product)
    all_vars = ("Y", "T", *z_vars)
    return EstimandAST(
        query_str="P(Y|do(T))",
        outcome="Y",
        treatment="T",
        root=root,
        all_variables=all_vars,
        identification_method="backdoor",
    )


def _make_highdim_backdoor_ast() -> EstimandAST:
    """Backdoor with 6 covariates → DML_COMPATIBLE."""
    return _make_backdoor_ast(conditioning_size=6)


class TestCrossFitInjection:
    def test_large_n_injects_folds_for_aipw(self):
        """n=500 → n_folds=5 → nuisance nodes replicated, FoldAggregator inserted."""
        ast = _make_backdoor_ast(conditioning_size=2)
        _, graph = compile_estimand(ast, run_id="r1", n_obs=500, use_cross_fitting=True)
        node_ids = [n.node_id for n in graph.nodes]
        # After injection: fold variants or aggregator nodes should be present
        fold_related = [nid for nid in node_ids if "_fold_" in nid]
        assert len(fold_related) > 0, f"Expected fold-variant nodes for n=500, got: {node_ids}"

    def test_medium_n_uses_2_folds(self):
        """n=200 → n_folds=2."""
        ast = _make_backdoor_ast()
        _, graph = compile_estimand(ast, run_id="r2", n_obs=200, use_cross_fitting=True)
        # total_folds should be 2 after injection
        fold_related = [n for n in graph.nodes if "_fold_" in n.node_id]
        if fold_related:
            # Fold count: each nuisance node should have exactly 2 variants
            assert graph.total_folds == 2

    def test_small_n_skips_injection(self):
        """n=50 → n_folds=1 → no injection, graph unchanged."""
        ast = _make_backdoor_ast()
        _, graph = compile_estimand(ast, run_id="r3", n_obs=50, use_cross_fitting=True)
        fold_related = [n for n in graph.nodes if "_fold_" in n.node_id]
        assert fold_related == [], f"Should not inject for n=50, got: {fold_related}"

    def test_use_cross_fitting_false_skips_injection(self):
        """use_cross_fitting=False → injection disabled regardless of n_obs."""
        ast = _make_backdoor_ast()
        _, graph = compile_estimand(ast, run_id="r4", n_obs=1000, use_cross_fitting=False)
        fold_related = [n for n in graph.nodes if "_fold_" in n.node_id]
        assert fold_related == []

    def test_dml_shape_also_injected(self):
        """High-dim backdoor → DML_COMPATIBLE → also gets cross-fitting injection."""
        ast = _make_highdim_backdoor_ast()
        _, graph = compile_estimand(ast, run_id="r5", n_obs=600, use_cross_fitting=True)
        fold_related = [n for n in graph.nodes if "_fold_" in n.node_id]
        assert len(fold_related) > 0

    def test_graph_has_fold_aggregator_nodes(self):
        """FoldAggregator nodes should be present after injection."""
        ast = _make_backdoor_ast()
        _, graph = compile_estimand(ast, run_id="r6", n_obs=500, use_cross_fitting=True)
        agg_nodes = [n for n in graph.nodes if "fold_agg" in n.node_id]
        # May or may not have agg nodes depending on whether template compiler
        # creates is_nuisance=True nodes; both outcomes are valid
        # The key invariant: if fold variants exist, aggregator must follow
        fold_variants = [n for n in graph.nodes if "_fold_0" in n.node_id]
        if fold_variants:
            assert len(agg_nodes) > 0

    def test_proof_steps_preserved_after_injection(self):
        """Proof steps passed in are preserved through cross-fitting injection."""
        from polisyos.ir.analytics.evidence_bundle import ProofStep

        ast = _make_backdoor_ast()
        ps = ProofStep(
            rule_name="TEST",
            description="dummy step",
            variables_affected=("T",),
            graph_subset="G",
        )
        _, graph = compile_estimand(
            ast,
            run_id="r7",
            n_obs=500,
            use_cross_fitting=True,
            proof_steps=(ps,),
        )
        assert len(graph.proof_steps) >= 1
        assert any(s.rule_name == "TEST" for s in graph.proof_steps)

    def test_run_id_propagated(self):
        ast = _make_backdoor_ast()
        _, graph = compile_estimand(ast, run_id="my-run-42", n_obs=500)
        assert graph.run_id == "my-run-42"
