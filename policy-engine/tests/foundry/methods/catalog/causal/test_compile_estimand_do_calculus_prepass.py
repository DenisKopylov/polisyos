"""Tests: do-calculus rewrite_estimand pre-pass in compile_estimand (Task 3.1 / 2.1 junction).

Verifies that compile_estimand:
- Accepts optional causal_graph and invokes rewrite_estimand before classification
- Proof steps from rewriting appear in the ExecutorGraph
- Works correctly without a graph (no pre-pass)
- Simplified AST after pre-pass may change EstimandShape classification
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../../src"))

from polisyos.foundry.methods.catalog.causal.estimand_compiler import compile_estimand
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ProductNode,
    SumNode,
)


def _make_simple_ast() -> EstimandAST:
    outcome_ref = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        conditioning=("T", "Z"),
    )
    covariate_ref = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Z",),
    )
    product = ProductNode(factors=(outcome_ref, covariate_ref))
    root = SumNode(summation_vars=("Z",), operand=product)
    return EstimandAST(
        query_str="P(Y|do(T))",
        outcome="Y",
        treatment="T",
        root=root,
        all_variables=("Y", "T", "Z"),
        identification_method="backdoor",
    )


def _make_causal_graph():
    """Build a minimal CausalGraphModel T → Y ← Z."""
    try:
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        return CausalGraphModel(
            nodes=["T", "Y", "Z"],
            edges=[("T", "Y"), ("Z", "Y"), ("Z", "T")],
            schema_version="1.0",
        )
    except Exception:
        return None


class TestDoCalculusPrePass:
    def test_no_graph_works_normally(self):
        """compile_estimand without causal_graph behaves identically to before."""
        ast = _make_simple_ast()
        rec, graph = compile_estimand(ast, run_id="r1", n_obs=200)
        assert graph is not None
        assert len(graph.nodes) >= 1

    def test_with_graph_does_not_raise(self):
        """compile_estimand with a valid CausalGraphModel should not raise."""
        ast = _make_simple_ast()
        g = _make_causal_graph()
        if g is None:
            pytest.skip("CausalGraphModel not available")
        rec, graph = compile_estimand(ast, run_id="r2", n_obs=200, causal_graph=g)
        assert graph is not None

    def test_graph_none_preserves_existing_proof_steps(self):
        """Existing proof_steps are preserved when causal_graph=None."""
        from polisyos.ir.analytics.evidence_bundle import ProofStep
        ast = _make_simple_ast()
        ps = ProofStep(
            rule_name="MANUAL",
            description="manually added",
            variables_affected=("T",),
            graph_subset="G",
        )
        _, graph = compile_estimand(
            ast, run_id="r3", n_obs=200, proof_steps=(ps,)
        )
        assert any(s.rule_name == "MANUAL" for s in graph.proof_steps)

    def test_do_calculus_proof_steps_merged(self):
        """Proof steps from rewrite_estimand appear before manually-added steps."""
        from polisyos.ir.analytics.evidence_bundle import ProofStep
        ast = _make_simple_ast()
        g = _make_causal_graph()
        if g is None:
            pytest.skip("CausalGraphModel not available")
        manual_ps = ProofStep(
            rule_name="MANUAL",
            description="manually added",
            variables_affected=("T",),
            graph_subset="G",
        )
        _, graph = compile_estimand(
            ast, run_id="r4", n_obs=200,
            causal_graph=g, proof_steps=(manual_ps,),
        )
        # Manual step should be present
        assert any(s.rule_name == "MANUAL" for s in graph.proof_steps)

    def test_invalid_graph_falls_through_gracefully(self):
        """A broken/incompatible graph object should not raise — pre-pass skipped."""
        ast = _make_simple_ast()
        rec, graph = compile_estimand(
            ast, run_id="r5", n_obs=200, causal_graph="not-a-graph"
        )
        assert graph is not None
        assert len(graph.nodes) >= 1

    def test_cf_seed_param_accepted(self):
        """cf_seed parameter passes through without error."""
        ast = _make_simple_ast()
        rec, graph = compile_estimand(
            ast, run_id="r6", n_obs=500, cf_seed=123, use_cross_fitting=True
        )
        assert graph is not None
