"""Resolved original graph bytes and exact lineage for finite CPDAG proof readers."""

import hashlib

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.ir.analytics.causal import (
    ProofBundle,
    load_proof_bundle,
    persist_proof_bundle,
    proof_bundle_from_identification_result,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.artifacts import InputRef, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ProofBundleRef


def _fixture(tmp_path, common=False):
    store = FileSystemCAS(tmp_path / "cas")
    graph = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["X", "Y", "Z"] if common else ["X", "Y"],
        edges=[CausalEdge(src="Y" if common else "X", dst="Z" if common else "Y", mark_dst="tail")],
    )
    graph_ref = persist_causal_graph_model(store, graph)
    result = CausalEngine().identify("X", "Y", graph, dataset_ref="observed-law")
    proof = proof_bundle_from_identification_result(result, graph_ref=str(graph_ref.artifact_id))
    return store, graph, graph_ref, proof


def _raw_proof(store, proof, inputs):
    """Create a valid CAS object bypassing the public proof writer, for reader negatives."""
    return ProofBundleRef.model_validate(
        put_json_artifact(
            store,
            proof.model_dump(mode="json"),
            kind="ir.proof_bundle",
            schema_name="ir.proof_bundle",
            schema_version="1.0",
            inputs=inputs,
            canon_spec=CanonSpec(forbid_floats=False),
        )
    )


@pytest.mark.parametrize("common", [False, True])
def test_exact_graph_bytes_and_manifest_are_bound_for_both_dispositions(tmp_path, common):
    store, _, graph_ref, proof = _fixture(tmp_path, common)
    ref = persist_proof_bundle(store, proof)
    fresh = FileSystemCAS(store.root)
    loaded = load_proof_bundle(fresh, ref)
    assert loaded == proof
    assert (
        hashlib.sha256(fresh.get_bytes(graph_ref.artifact_id)).hexdigest()
        == loaded.metadata["partial_graph_query"]["graph_payload_sha256"]
    )
    assert [
        (str(item.artifact_id), item.role) for item in fresh.get_manifest(ref.artifact_id).inputs
    ] == [(str(graph_ref.artifact_id), "causal_graph")]


@pytest.mark.parametrize(
    "damage",
    ["missing", "nonexistent", "wrong_graph", "wrong_hash", "malformed_hash", "wrong_type"],
)
def test_public_writer_refuses_unresolved_or_changed_graph_basis_before_proof_write(
    tmp_path, damage
):
    store, _, _, proof = _fixture(tmp_path)
    basis = dict(proof.metadata["partial_graph_query"])
    if damage == "missing":
        proof = proof.model_copy(update={"graph_ref": None})
    elif damage == "nonexistent":
        proof = proof.model_copy(update={"graph_ref": "sha256:" + "0" * 64})
    elif damage == "wrong_graph":
        other = persist_causal_graph_model(
            store,
            CausalGraphModel(
                graph_type=GraphType.DAG, nodes=["X", "Y"], edges=[CausalEdge(src="Y", dst="X")]
            ),
        )
        proof = proof.model_copy(update={"graph_ref": str(other.artifact_id)})
    elif damage == "wrong_type":
        other = ProofBundleRef.model_validate(
            put_json_artifact(
                store,
                {"fixture": "not a graph"},
                kind="ir.proof_bundle",
                schema_name="ir.proof_bundle",
                schema_version="1.0",
                canon_spec=CanonSpec(forbid_floats=False),
            )
        )
        proof = proof.model_copy(update={"graph_ref": str(other.artifact_id)})
    else:
        basis["graph_payload_sha256"] = "f" * 64 if damage == "wrong_hash" else "not-a-content-hash"
        proof = proof.model_copy(
            update={"metadata": {**proof.metadata, "partial_graph_query": basis}}
        )
    before = set(map(str, store.iter_artifact_ids()))
    with pytest.raises((ValueError, FileNotFoundError)):
        persist_proof_bundle(store, proof)
    assert set(map(str, store.iter_artifact_ids())) == before


@pytest.mark.parametrize(
    "damage",
    ["missing_ref", "wrong_ref", "stale_hash", "no_input", "wrong_input", "duplicate_input"],
)
def test_fresh_reader_refuses_retained_marker_proof_with_wrong_graph_or_lineage(tmp_path, damage):
    store, _, graph_ref, proof = _fixture(tmp_path)
    inputs = [InputRef(artifact_id=graph_ref.artifact_id, role="causal_graph")]
    other = persist_causal_graph_model(
        store, CausalGraphModel(graph_type=GraphType.DAG, nodes=["X", "Y"], edges=[])
    )
    if damage == "missing_ref":
        proof = proof.model_copy(update={"graph_ref": None})
    elif damage == "wrong_ref":
        proof = proof.model_copy(update={"graph_ref": str(other.artifact_id)})
    elif damage == "stale_hash":
        basis = {**proof.metadata["partial_graph_query"], "graph_payload_sha256": "f" * 64}
        proof = proof.model_copy(
            update={"metadata": {**proof.metadata, "partial_graph_query": basis}}
        )
    elif damage == "no_input":
        inputs = []
    elif damage == "wrong_input":
        inputs = [InputRef(artifact_id=other.artifact_id, role="causal_graph")]
    else:
        inputs = inputs * 2
    assert (
        proof.proof_status == "oracle_needed"
        and proof.metadata["partial_graph_query"]["authority_eligible"] is False
    )
    ref = _raw_proof(store, proof, inputs)
    with pytest.raises(ValueError):
        load_proof_bundle(FileSystemCAS(store.root), ref)


@pytest.mark.parametrize("duplicate", [False, True])
def test_writer_refuses_wrong_or_duplicate_explicit_graph_input(tmp_path, duplicate):
    store, _, graph_ref, proof = _fixture(tmp_path)
    if duplicate:
        inputs = [InputRef(artifact_id=graph_ref.artifact_id, role="causal_graph")] * 2
    else:
        inputs = [InputRef(artifact_id="sha256:" + "0" * 64, role="causal_graph")]
    with pytest.raises(ValueError):
        persist_proof_bundle(store, proof, inputs=inputs)


@pytest.mark.parametrize("damage", ["altered_bytes", "missing_bytes"])
def test_actual_graph_blob_damage_is_refused_by_fresh_cas_reader(tmp_path, damage):
    store, _, graph_ref, proof = _fixture(tmp_path)
    ref = persist_proof_bundle(store, proof)
    blob, _ = store._paths(graph_ref.artifact_id)
    if damage == "altered_bytes":
        blob.write_bytes(b'{"retained":"graph profile marker"}')
    else:
        # No deletion: rename the reproducible adversarial input within this isolated fixture.
        blob.rename(blob.with_suffix(".missing-fixture"))
    with pytest.raises((ValueError, FileNotFoundError)):
        load_proof_bundle(FileSystemCAS(store.root), ref)


def test_unrelated_legacy_proof_compatibility_is_preserved(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    proof = ProofBundle(
        proof_status="oracle_needed",
        proof_stratum="A2_oracle_backed",
        theorem_family="legacy",
        completeness_regime="sound_incomplete",
        implementation_coverage="legacy",
        metadata={"legacy_profile": "ordinary"},
    )
    assert load_proof_bundle(FileSystemCAS(store.root), persist_proof_bundle(store, proof)) == proof
