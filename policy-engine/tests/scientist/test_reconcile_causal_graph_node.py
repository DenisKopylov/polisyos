from __future__ import annotations

import logging

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeSource, GraphType, load_causal_graph_model
from polisyos.ir.analytics.literature import (
    LiteratureCausalPrior,
    LiteratureEdgePrior,
    persist_literature_causal_prior,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import (
    ReconcileCausalGraphNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LITERATURE_PRIOR_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)


def _build_ctx(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_phase9_recon")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.phase9.recon"))
    return ctx


def test_reconcile_causal_graph_node_persists_graph_and_params(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    prior = LiteratureCausalPrior(
        edges=[LiteratureEdgePrior(src="tax", dst="employment", confidence=0.7)],
        skg_version_id=2,
    )
    prior_ref = persist_literature_causal_prior(ctx.store, prior)
    data_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tax", "employment"],
        edges=[
            CausalEdge(
                src="tax",
                dst="employment",
                sources=[EdgeSource.DATA],
                data_confidence=0.85,
                combined_confidence=0.85,
            )
        ],
    )
    state = ExperimentState(
        run_id="R_phase9_recon",
        artifacts_index={ARTIFACT_LITERATURE_PRIOR_REF: prior_ref},
        params={
            "data_causal_graph": data_graph.model_dump(mode="json"),
            "llm_structural_hints": [
                {"src": "employment", "dst": "tax", "confidence": 0.9},
            ],
        },
    )

    outcome = ReconcileCausalGraphNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in outcome.state.artifacts_index
    assert outcome.state.params["needs_expert_review"] is True
    assert "reconciliation_diagnostics" in outcome.state.params
    graph_ref = outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
    graph = load_causal_graph_model(ctx.store, graph_ref)
    assert graph.metadata["needs_expert_review"] is True


def test_reconcile_causal_graph_node_skips_without_data_graph(tmp_path) -> None:
    ctx = _build_ctx(tmp_path)
    state = ExperimentState(run_id="R_phase9_recon_skip")

    outcome = ReconcileCausalGraphNode().execute(ctx, state)

    assert outcome.status == "skip"
