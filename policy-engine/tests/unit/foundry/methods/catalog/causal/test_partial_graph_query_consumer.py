"""Actual partial-query engine audit, CAS and separate fresh-process consumer."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.ir.analytics.causal import load_proof_bundle
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    load_causal_graph_model,
)


def test_actual_engine_audit_preserves_partial_query_in_fresh_cas_and_child(tmp_path):
    graph = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_dst="tail")],
    )
    store = FileSystemCAS(tmp_path / "cas")
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
    from polisyos.ir.registry.refs import CausalGraphModelRef

    assert proof.graph_ref is not None
    graph_ref = CausalGraphModelRef(artifact_id=proof.graph_ref)
    assert load_causal_graph_model(fresh, graph_ref) == graph
    assert (
        hashlib.sha256(fresh.get_bytes(proof.graph_ref)).hexdigest()
        == basis["graph_payload_sha256"]
    )
    lineage = fresh.get_manifest(audit.proof_bundle_ref.artifact_id).inputs
    assert [(str(item.artifact_id), item.role) for item in lineage] == [
        (proof.graph_ref, "causal_graph")
    ]
    script = """
import hashlib,json,os,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import load_proof_bundle
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.registry.refs import ProofBundleRef,CausalGraphModelRef
store=FileSystemCAS(sys.argv[1])
proof=load_proof_bundle(store,ProofBundleRef.model_validate_json(sys.argv[2]))
graph=load_causal_graph_model(store,CausalGraphModelRef(artifact_id=proof.graph_ref))
assert graph.model_dump(mode='json')==json.loads(sys.argv[3])
assert hashlib.sha256(store.get_bytes(proof.graph_ref)).hexdigest()==proof.metadata['partial_graph_query']['graph_payload_sha256']
lineage=store.get_manifest(ProofBundleRef.model_validate_json(sys.argv[2]).artifact_id).inputs
assert [(str(entry.artifact_id),entry.role) for entry in lineage]==[(proof.graph_ref,'causal_graph')]
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
            graph.model_dump_json(),
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
    assert proof.graph_ref is not None
    from polisyos.ir.registry.refs import CausalGraphModelRef

    fresh = FileSystemCAS(store.root)
    assert load_causal_graph_model(fresh, CausalGraphModelRef(artifact_id=proof.graph_ref)) == graph
    assert (
        hashlib.sha256(fresh.get_bytes(proof.graph_ref)).hexdigest()
        == basis["graph_payload_sha256"]
    )
    lineage = fresh.get_manifest(audit.proof_bundle_ref.artifact_id).inputs
    assert [(str(entry.artifact_id), entry.role) for entry in lineage] == [
        (proof.graph_ref, "causal_graph")
    ]
    script = """
import hashlib,json,os,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import load_proof_bundle
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.registry.refs import ProofBundleRef,CausalGraphModelRef
store=FileSystemCAS(sys.argv[1])
proof=load_proof_bundle(store,ProofBundleRef.model_validate_json(sys.argv[2]))
graph=load_causal_graph_model(store,CausalGraphModelRef(artifact_id=proof.graph_ref))
assert graph.model_dump(mode='json')==json.loads(sys.argv[3])
assert proof.proof_status=='identified' and proof.estimand_ast is not None
assert proof.metadata['partial_graph_query']['disposition']=='common_functional'
assert proof.metadata['partial_graph_query']['authority_eligible'] is False
assert hashlib.sha256(store.get_bytes(proof.graph_ref)).hexdigest()==proof.metadata['partial_graph_query']['graph_payload_sha256']
print(json.dumps({'pid':os.getpid(),'profile':graph.graph_type.value}))
"""
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(store.root),
            audit.proof_bundle_ref.model_dump_json(),
            graph.model_dump_json(),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(child.stdout.splitlines()[-1])["profile"] == "cpdag"


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_actual_audit_refuses_missing_or_changed_original_graph_before_proof_publication(
    tmp_path, damage
):
    graph = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_dst="tail")],
    )
    store = FileSystemCAS(tmp_path / "cas")
    engine = CausalEngine(artifact_store=store)
    result = engine.identify("X", "Y", graph, dataset_ref="observed-law")
    supplied = (
        None
        if damage == "missing"
        else CausalGraphModel(
            graph_type=GraphType.DAG, nodes=["X", "Y"], edges=[CausalEdge(src="Y", dst="X")]
        )
    )
    with pytest.raises(ValueError):
        engine.audit(result, None, run_id="changed-original-fixture", graph=supplied)
    assert not any(
        store.get_manifest(ref).kind == "ir.proof_bundle" for ref in store.iter_artifact_ids()
    )
