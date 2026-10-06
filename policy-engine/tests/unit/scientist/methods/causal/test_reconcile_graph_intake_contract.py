"""Real graph jobs and fresh consumers distinguish current intake from cached markers."""

from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ReconcileCausalGraph
from polisyos.foundry.methods.catalog.causal.protocols import GraphReconciliationData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import CausalGraphModel, load_causal_graph_model
from polisyos.ir.analytics.literature import (
    LiteratureCausalPrior,
    LiteratureEdgePrior,
    persist_literature_causal_prior,
)
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_METHOD_RESULT_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _graph(*, reverse=False, graph_type="dag", marks=None, lag=None):
    edge = {
        "src": "Y" if reverse else "X",
        "dst": "X" if reverse else "Y",
        "lag": lag,
        "sources": ["data"],
        "data_confidence": 0.9,
        "combined_confidence": 0.9,
    }
    if marks is not None:
        edge.update({"mark_src": marks[0], "mark_dst": marks[1]})
    return CausalGraphModel.model_validate(
        {"graph_type": graph_type, "nodes": ["X", "Y"], "edges": [edge]}
    )


def _ctx(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="graph-intake")
    return ExecutionContext(store=store, run=run, logger=logging.getLogger("graph-intake"))


def _real_graph_job(ctx, graph):
    request = GraphReconciliationData(data_graph=graph)
    source = ctx.store.put_json(
        request.model_dump(mode="json"),
        PutOptions(
            kind="tests.synthetic.graph_reconciliation_input",
            media_type="application/json",
            schema=SchemaInfo(name="tests.GraphReconciliationData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    MethodRegistry.get_instance().register(ReconcileCausalGraph, override=True)
    result = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=ReconcileCausalGraph.signature.fqn,
            input_refs={"graph_reconciliation_data": source},
            seed=23,
        ),
        cas_root=ctx.store.root,
        method_state=request,
    )
    assert not result.issues and result.method_result_ref is not None, result.issues
    return result.method_result_ref


def _read(ctx, outcome):
    assert outcome.status == "ok", outcome.error
    ref = outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
    return ref, load_causal_graph_model(FileSystemCAS(ctx.store.root), ref)


def test_genuine_changed_source_job_reconciles_and_fresh_consumer_sees_current_edges(tmp_path):
    ctx = _ctx(tmp_path)
    first = _real_graph_job(ctx, _graph())
    state = ExperimentState(
        run_id="graph-intake", artifacts_index={ARTIFACT_CAUSAL_METHOD_RESULT_REF: first}
    )
    old = ReconcileCausalGraphNode().execute(ctx, state)
    old_ref, old_graph = _read(ctx, old)
    assert [(edge.src, edge.dst) for edge in old_graph.edges] == [("X", "Y")]
    current = _real_graph_job(ctx, _graph(reverse=True))
    replay = old.state.model_copy(deep=True)
    replay.artifacts_index[ARTIFACT_CAUSAL_METHOD_RESULT_REF] = current
    outcome = ReconcileCausalGraphNode().execute(ctx, replay)
    ref, graph = _read(ctx, outcome)
    assert [(edge.src, edge.dst) for edge in graph.edges] == [("Y", "X")]
    assert ref != old_ref
    assert any(
        item.artifact_id == current.artifact_id and item.role == "data_graph"
        for item in ctx.store.get_manifest(ref).inputs
    )


@pytest.mark.parametrize("mutation", ["prior", "config", "hint", "seed"])
def test_current_complete_request_not_old_cached_graph_controls_result_identity(tmp_path, mutation):
    ctx = _ctx(tmp_path)
    source = _real_graph_job(ctx, _graph())
    state = ExperimentState(
        run_id="graph-intake", params={"random_seed": 23},
        artifacts_index={ARTIFACT_CAUSAL_METHOD_RESULT_REF: source},
    )
    old = ReconcileCausalGraphNode().execute(ctx, state)
    _, original = _read(ctx, old)
    current = old.state.model_copy(deep=True)
    if mutation == "prior":
        prior = LiteratureCausalPrior(
            edges=[LiteratureEdgePrior(src="X", dst="Z", confidence=0.8)], skg_version_id=9
        )
        current.artifacts_index[ARTIFACT_LITERATURE_PRIOR_REF] = persist_literature_causal_prior(
            ctx.store, prior
        )
    elif mutation == "config":
        current.params["reconciliation_min_edge_confidence"] = 0.95
    elif mutation == "hint":
        current.params["llm_structural_hints"] = [{"src": "X", "dst": "Z", "confidence": 0.2}]
    else:
        current.params["random_seed"] = 24
    _, graph = _read(ctx, ReconcileCausalGraphNode().execute(ctx, current))
    assert graph.metadata["reconciliation_request_sha256"] != original.metadata[
        "reconciliation_request_sha256"
    ]
    if mutation == "config":
        assert not graph.edges
    elif mutation in ("prior", "hint"):
        assert any(edge.dst == "Z" for edge in graph.edges)
    else:
        assert graph.edges == original.edges  # STRICT_CPU has no numerical RNG.


def test_missing_cached_ref_refuses_before_new_input_can_claim_success(tmp_path):
    ctx = _ctx(tmp_path)
    missing = ArtifactRef.model_validate(
        {"artifact_id": "sha256:" + "f" * 64, "kind": "ir.causal_graph_model",
         "media_type": "application/json"}
    )
    state = ExperimentState(
        run_id="graph-intake", params={"data_causal_graph": _graph().model_dump(mode="json")},
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: missing},
    )
    outcome = ReconcileCausalGraphNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert not ctx.store.has(missing.artifact_id)


@pytest.mark.parametrize("graph_type,marks", [("pag", ("circle", "circle")),
                                             ("cpdag", ("tail", "tail")),
                                             ("admg", ("arrow", "arrow"))])
def test_unresolved_or_mixed_endpoints_refuse_before_node_persists_oriented_dag(
    tmp_path, graph_type, marks
):
    ctx = _ctx(tmp_path)
    graph = _graph(graph_type=graph_type, marks=marks)
    state = ExperimentState(
        run_id="graph-intake", params={"data_causal_graph": graph.model_dump(mode="json")}
    )
    outcome = ReconcileCausalGraphNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF not in outcome.state.artifacts_index
    assert graph.edges[0].mark_src.value == marks[0]
    assert graph.edges[0].mark_dst.value == marks[1]


def test_temporal_serialization_stays_readable_but_static_intake_refuses(tmp_path):
    graph = _graph(lag=1)
    legacy = ReconcileCausalGraph.pure_step(GraphReconciliationData(data_graph=graph), {})
    assert legacy["reconciled_graph"].edges[0].lag == 1
    ctx = _ctx(tmp_path)
    state = ExperimentState(
        run_id="graph-intake", params={"data_causal_graph": graph.model_dump(mode="json")}
    )
    outcome = ReconcileCausalGraphNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF not in outcome.state.artifacts_index


def test_explicit_static_profile_rejects_cycle_generated_lag_without_changing_legacy_math():
    graph = CausalGraphModel.model_validate(
        {"graph_type": "cpdag", "nodes": ["X", "Y"],
         "edges": [{"src": "X", "dst": "Y", "combined_confidence": 0.9},
                   {"src": "Y", "dst": "X", "combined_confidence": 0.8}]}
    )
    legacy = ReconcileCausalGraph.pure_step(GraphReconciliationData(data_graph=graph), {})
    assert any(edge.lag for edge in legacy["reconciled_graph"].edges)
    with pytest.raises(ValueError, match="static|lag"):
        ReconcileCausalGraph.pure_step(
            GraphReconciliationData(data_graph=graph), {"static_intake": True}
        )
