from __future__ import annotations

from types import SimpleNamespace

from polisyos.core.artifacts import ensure_ir_artifact_store, profile_bound_ref
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.registry.refs import CausalGraphModelRef
from polisyos.scientist.nodes.builtins.causal.transport_resolution_inputs import (
    _resolve_causal_graph_source,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF
from polisyos.scientist.orchestration.engine.state import ExperimentState


def test_graph_source_resolver_preserves_exact_selected_manifest_profile(tmp_path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["policy", "outcome"],
        edges=[CausalEdge(src="policy", dst="outcome")],
    )
    base_ref = persist_causal_graph_model(store, graph)
    selected_ref = profile_bound_ref(store, base_ref)
    graph_ref = CausalGraphModelRef.model_validate(selected_ref.model_dump(mode="json"))
    assert graph_ref.manifest_profile_sha256 is not None
    state = ExperimentState(
        run_id="R_transport_candidate_graph_source",
        artifacts_index={
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
        },
    )
    resolved = _resolve_causal_graph_source(SimpleNamespace(store=store), state)

    assert resolved is not None
    resolved_ref, resolved_graph = resolved
    assert resolved_ref == graph_ref
    assert resolved_graph == graph
