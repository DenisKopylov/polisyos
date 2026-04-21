from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.proof_trace_composability import (
    check_proof_trace_composability,
    proof_ancestor_signature,
    proof_composability_cache_key,
    proof_district_signature,
    proof_support_projection_hash,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.proof_composability import (
    ProofComposabilityStatus,
    ProofGraphWitness,
    ProofObligationKind,
    ProofReplayStepStatus,
    ProofWitnessIndex,
)


def _edge(src: str, dst: str) -> CausalEdge:
    return CausalEdge(src=src, dst=dst)


def _bidirected(src: str, dst: str) -> CausalEdge:
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)


def _graph(nodes: list[str], edges: list[CausalEdge]) -> CausalGraphModel:
    return CausalGraphModel(graph_type=GraphType.ADMG, nodes=nodes, edges=edges)


def _msep_witness(
    graph: CausalGraphModel,
    *,
    projection_hash: str | None = None,
) -> ProofGraphWitness:
    support = ("X", "Y")
    return ProofGraphWitness(
        witness_id="w_msep",
        obligation_kind=ProofObligationKind.M_SEPARATION,
        support_vars=support,
        projection_hash=projection_hash
        or proof_support_projection_hash(graph, support_vars=support),
        ancestor_signature=proof_ancestor_signature(graph, support_vars=support),
        district_signature=proof_district_signature(graph, support_vars=support),
        metadata={"x_set": ["X"], "y_set": ["Y"], "z_set": []},
    )


def test_composability_reusable_when_witness_projection_and_signatures_match() -> None:
    source_graph = _graph(["X", "Y"], [])
    composed_graph = _graph(["X", "Y", "W"], [])
    index = ProofWitnessIndex(
        witnesses=(_msep_witness(source_graph),),
        step_to_witness_ids={"s1": ("w_msep",)},
        proof_support_projection_hash="support-hash",
    )

    certificate = check_proof_trace_composability(
        witness_index=index,
        composed_graph=composed_graph,
        source_fragment_id="fragment_a",
        checked_query="P(Y|do(X))",
        interface_vars=("X",),
    )

    assert certificate.status is ProofComposabilityStatus.REUSABLE
    assert certificate.step_statuses["s1"] is ProofReplayStepStatus.VALID
    assert certificate.preserved_witness_ids == ("w_msep",)
    assert certificate.broken_witness_ids == ()
    assert certificate.projection_preservation_passed is True


def test_composability_rederive_when_m_separation_witness_breaks() -> None:
    source_graph = _graph(["X", "Y"], [])
    composed_graph = _graph(["X", "Y", "Z"], [_edge("X", "Z"), _edge("Z", "Y")])
    index = ProofWitnessIndex(
        witnesses=(_msep_witness(source_graph),),
        step_to_witness_ids={"s1": ("w_msep",)},
    )

    certificate = check_proof_trace_composability(
        witness_index=index,
        composed_graph=composed_graph,
        source_fragment_id="fragment_a",
        checked_query="P(Y|do(X))",
    )

    assert certificate.status is ProofComposabilityStatus.REDERIVE
    assert certificate.step_statuses["s1"] is ProofReplayStepStatus.INVALID
    assert certificate.broken_witness_ids == ("w_msep",)
    assert any(
        "obligation_broken_after_composition" in reason
        for reason in certificate.invalidation_reasons
    )


def test_composability_rederive_when_district_signature_changes() -> None:
    source_graph = _graph(["X", "Y"], [])
    composed_graph = _graph(["X", "Y"], [_bidirected("X", "Y")])
    witness = ProofGraphWitness(
        witness_id="w_district",
        obligation_kind=ProofObligationKind.DISTRICT_FACTORIZATION,
        support_vars=("X", "Y"),
        projection_hash=proof_support_projection_hash(source_graph, support_vars=("X", "Y")),
        ancestor_signature=proof_ancestor_signature(source_graph, support_vars=("X", "Y")),
        district_signature=proof_district_signature(source_graph, support_vars=("X", "Y")),
    )
    index = ProofWitnessIndex(
        witnesses=(witness,),
        step_to_witness_ids={"s1": ("w_district",)},
    )

    certificate = check_proof_trace_composability(
        witness_index=index,
        composed_graph=composed_graph,
        source_fragment_id="fragment_a",
        checked_query="P(Y|do(X))",
    )

    assert certificate.status is ProofComposabilityStatus.REDERIVE
    assert certificate.broken_witness_ids == ("w_district",)
    assert certificate.new_district_links == (("X", "Y"),)


def test_composability_revalidate_when_hash_changes_but_obligation_still_holds() -> None:
    source_graph = _graph(["X", "Y"], [])
    index = ProofWitnessIndex(
        witnesses=(_msep_witness(source_graph, projection_hash="stale-hash"),),
        step_to_witness_ids={"s1": ("w_msep",)},
    )

    certificate = check_proof_trace_composability(
        witness_index=index,
        composed_graph=source_graph,
        source_fragment_id="fragment_a",
        checked_query="P(Y|do(X))",
    )

    assert certificate.status is ProofComposabilityStatus.REVALIDATE
    assert certificate.step_statuses["s1"] is ProofReplayStepStatus.VALID
    assert certificate.projection_preservation_passed is False
    assert certificate.broken_witness_ids == ()


def test_proof_composability_cache_key_includes_witness_projection_hashes() -> None:
    key_a = proof_composability_cache_key(
        query="P(Y|do(X))",
        theorem_family="id_v1",
        proof_trace_hash="trace-1",
        witness_projection_hashes=("a", "b"),
        interface_signature=("X", "Y"),
    )
    key_b = proof_composability_cache_key(
        query="P(Y|do(X))",
        theorem_family="id_v1",
        proof_trace_hash="trace-1",
        witness_projection_hashes=("a", "changed"),
        interface_signature=("X", "Y"),
    )

    assert key_a.startswith("proof-replay:")
    assert key_a != key_b
