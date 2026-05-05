"""Tests for EstimandCompiler with knowledge_base wiring and ExecutorGraph output."""

import dataclasses

import pytest
from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    EstimatorRecommendation,
    ExecutorGraph,
    ExecutorNode,
    compile_estimand,
    compile_to_method_dag_nodes,
    recommend_estimator,
)
from polisyos.ir.analytics.estimand import (
    make_backdoor_estimand,
    make_frontdoor_estimand,
    make_transport_reweight_estimand,
)
from polisyos.ir.analytics.knowledge_base import (
    DataKnowledgeBase,
    DatasetEntry,
    DistributionAvailability,
)


def make_full_kb(ast):
    """KB with all distributions AVAILABLE."""
    entries = []
    for dr in ast.collect_distribution_refs():
        entries.append(
            DatasetEntry(
                dataset_ref=dr.dataset_ref or "default_ds",
                variables=dr.variables,
                domain=dr.domain,
                availability=DistributionAvailability.AVAILABLE,
                n_obs=1000,
                quality_score=1.0,
            )
        )
    return DataKnowledgeBase(datasets=tuple(entries))


def make_missing_kb():
    """KB with no datasets — everything UNAVAILABLE."""
    return DataKnowledgeBase(datasets=())


class TestKnowledgeBaseWiring:
    def test_full_kb_confidence_within_bounds(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        kb = make_full_kb(ast)
        rec = recommend_estimator(ast, n_obs=500, covariate_dim=3, knowledge_base=kb)
        assert 0.0 <= rec.confidence <= 1.0

    def test_missing_data_reduces_confidence(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        kb_none = make_missing_kb()
        kb_full = make_full_kb(ast)
        rec_none = recommend_estimator(ast, n_obs=500, covariate_dim=3, knowledge_base=kb_none)
        rec_full = recommend_estimator(ast, n_obs=500, covariate_dim=3, knowledge_base=kb_full)
        # Missing KB should either reduce confidence or add warning
        assert rec_none.confidence <= rec_full.confidence or "WARN" in rec_none.notes

    def test_none_kb_baseline_unchanged(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        rec1 = recommend_estimator(ast, n_obs=500, covariate_dim=3, knowledge_base=None)
        rec2 = recommend_estimator(ast, n_obs=500, covariate_dim=3, knowledge_base=None)
        assert rec1.confidence == rec2.confidence
        assert rec1.strategy == rec2.strategy

    def test_recommend_returns_estimator_recommendation(self):
        ast = make_backdoor_estimand(treatment="X", outcome="Y", adjustment_set=("Z",))
        rec = recommend_estimator(ast, n_obs=200, covariate_dim=2, knowledge_base=None)
        assert isinstance(rec, EstimatorRecommendation)


class TestExecutorGraph:
    def test_compile_returns_executor_graph(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        rec = recommend_estimator(ast, n_obs=500, covariate_dim=3, knowledge_base=None)
        eg = compile_to_method_dag_nodes(
            ast, rec, run_id="test-run", use_cross_fitting=False, knowledge_base=None
        )
        assert isinstance(eg, ExecutorGraph)

    def test_nodes_nonempty_for_backdoor(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        rec = recommend_estimator(ast, n_obs=500, covariate_dim=3, knowledge_base=None)
        eg = compile_to_method_dag_nodes(
            ast, rec, run_id="r1", use_cross_fitting=False, knowledge_base=None
        )
        assert len(eg.nodes) > 0

    def test_all_nodes_are_executor_nodes(self):
        ast = make_backdoor_estimand(treatment="X", outcome="Y", adjustment_set=("Z",))
        rec = recommend_estimator(ast, n_obs=200, covariate_dim=2, knowledge_base=None)
        eg = compile_to_method_dag_nodes(
            ast, rec, run_id="r2", use_cross_fitting=False, knowledge_base=None
        )
        for node in eg.nodes:
            assert isinstance(node, ExecutorNode)

    def test_edges_are_tuples_of_pairs(self):
        ast = make_backdoor_estimand(treatment="X", outcome="Y", adjustment_set=("Z",))
        rec = recommend_estimator(ast, n_obs=200, covariate_dim=2, knowledge_base=None)
        eg = compile_to_method_dag_nodes(
            ast, rec, run_id="r3", use_cross_fitting=False, knowledge_base=None
        )
        for edge in eg.edges:
            assert len(edge) == 2
            assert isinstance(edge[0], str) and isinstance(edge[1], str)

    def test_nuisance_schedule_subset_of_node_ids(self):
        ast = make_backdoor_estimand(treatment="X", outcome="Y", adjustment_set=("Z",))
        rec = recommend_estimator(ast, n_obs=200, covariate_dim=2, knowledge_base=None)
        eg = compile_to_method_dag_nodes(
            ast, rec, run_id="r4", use_cross_fitting=True, knowledge_base=None
        )
        node_ids = {n.node_id for n in eg.nodes}
        for nid in eg.nuisance_schedule:
            assert nid in node_ids

    def test_to_method_dag_dicts_backward_compat(self):
        ast = make_backdoor_estimand(treatment="X", outcome="Y", adjustment_set=("Z",))
        rec = recommend_estimator(ast, n_obs=200, covariate_dim=2, knowledge_base=None)
        eg = compile_to_method_dag_nodes(
            ast, rec, run_id="r5", use_cross_fitting=False, knowledge_base=None
        )
        dicts = eg.to_method_dag_dicts()
        assert isinstance(dicts, list)
        assert len(dicts) == len(eg.nodes)
        for d in dicts:
            assert isinstance(d, dict)
            assert "node_id" in d

    def test_executor_graph_is_frozen(self):
        ast = make_backdoor_estimand(treatment="X", outcome="Y", adjustment_set=("Z",))
        rec = recommend_estimator(ast, n_obs=200, covariate_dim=2, knowledge_base=None)
        eg = compile_to_method_dag_nodes(
            ast, rec, run_id="r6", use_cross_fitting=False, knowledge_base=None
        )
        with pytest.raises((AttributeError, TypeError, dataclasses.FrozenInstanceError)):
            eg.run_id = "mutated"


class TestCompileEstimandEndToEnd:
    def test_backdoor_pipeline(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds1"
        )
        rec, eg = compile_estimand(
            ast,
            run_id="e2e-1",
            n_obs=500,
            covariate_dim=3,
            use_cross_fitting=False,
            knowledge_base=None,
        )
        assert isinstance(rec, EstimatorRecommendation)
        assert isinstance(eg, ExecutorGraph)
        assert len(eg.nodes) > 0

    def test_frontdoor_pipeline(self):
        ast = make_frontdoor_estimand(treatment="X", outcome="Y", mediator="M", dataset_ref="ds1")
        rec, eg = compile_estimand(
            ast,
            run_id="e2e-2",
            n_obs=500,
            covariate_dim=2,
            use_cross_fitting=False,
            knowledge_base=None,
        )
        assert isinstance(eg, ExecutorGraph)

    def test_transport_pipeline(self):
        ast = make_transport_reweight_estimand(
            treatment="X",
            outcome="Y",
            reweighting_vars=("Z",),
            source_dataset_ref="src",
            target_dataset_ref="tgt",
        )
        rec, eg = compile_estimand(
            ast,
            run_id="e2e-3",
            n_obs=300,
            covariate_dim=2,
            use_cross_fitting=False,
            knowledge_base=None,
        )
        assert isinstance(eg, ExecutorGraph)

    def test_compile_with_kb(self):
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=("Z",), dataset_ref="ds_kb"
        )
        kb = make_full_kb(ast)
        rec, eg = compile_estimand(
            ast,
            run_id="kb-1",
            n_obs=500,
            covariate_dim=3,
            use_cross_fitting=False,
            knowledge_base=kb,
        )
        assert isinstance(eg, ExecutorGraph)
        assert isinstance(rec, EstimatorRecommendation)
