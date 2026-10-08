"""Actual partial-query engine audit, CAS and separate fresh-process consumer."""

from __future__ import annotations

import json
import subprocess
import sys

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.ir.analytics.causal import load_proof_bundle
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    load_causal_graph_model,
    persist_causal_graph_model,
)


def test_actual_engine_audit_preserves_partial_query_in_fresh_cas_and_child(tmp_path):
    graph = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_dst="tail")],
    )
    store = FileSystemCAS(tmp_path / "cas")
    graph_ref = persist_causal_graph_model(store, graph)
    engine = CausalEngine(artifact_store=store)
    result = engine.identify("X", "Y", graph, dataset_ref="observed-law")
    audit = engine.audit(result, None, run_id="partial-query-fixture", graph=graph)
    assert audit.identification_status == "pag_ambiguous"
    assert audit.proof_bundle_ref is not None
    fresh = FileSystemCAS(store.root)
    proof = load_proof_bundle(fresh, audit.proof_bundle_ref)
    basis = proof.metadata["partial_graph_query"]
    assert proof.proof_status == "oracle_needed" and proof.estimand_ast is None
    assert basis["disposition"] == "conditional" and basis["admitted_completions"] == 2
    assert basis["authority_eligible"] is False and basis["limitation"]
    assert load_causal_graph_model(fresh, graph_ref) == graph
    script = """
import json,os,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import load_proof_bundle
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.registry.refs import ProofBundleRef,CausalGraphModelRef
store=FileSystemCAS(sys.argv[1])
proof=load_proof_bundle(store,ProofBundleRef.model_validate_json(sys.argv[2]))
graph=load_causal_graph_model(store,CausalGraphModelRef.model_validate_json(sys.argv[3]))
assert proof.proof_status=='oracle_needed' and proof.estimand_ast is None
assert proof.metadata['partial_graph_query']['disposition']=='conditional'
assert proof.metadata['partial_graph_query']['authority_eligible'] is False
assert graph.graph_type.value=='cpdag' and graph.edges[0].mark_dst.value=='tail'
print(json.dumps({'pid':os.getpid(),'profile':graph.graph_type.value,'limitation':proof.metadata['partial_graph_query']['limitation']}))
"""
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(store.root),
            audit.proof_bundle_ref.model_dump_json(),
            graph_ref.model_dump_json(),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    readback = json.loads(child.stdout.splitlines()[-1])
    assert readback["profile"] == "cpdag" and readback["limitation"] == basis["limitation"]


def test_common_functional_positive_is_persisted_with_bounded_complete_family(tmp_path):
    graph = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["X", "Y", "Z"],
        edges=[CausalEdge(src="Y", dst="Z", mark_dst="tail")],
    )
    store = FileSystemCAS(tmp_path / "cas")
    engine = CausalEngine(artifact_store=store)
    result = engine.identify("X", "Y", graph, dataset_ref="observed-law")
    audit = engine.audit(result, None, run_id="same-functional-fixture", graph=graph)
    proof = load_proof_bundle(FileSystemCAS(store.root), audit.proof_bundle_ref)
    assert proof.proof_status == "identified" and proof.estimand_ast is not None
    basis = proof.metadata["partial_graph_query"]
    assert basis["coverage"] == "exhaustive_for_declared_profile"
    assert basis["authority_eligible"] is False and basis["admitted_completions"] == 2
    assert "separate" in basis["limitation"]
