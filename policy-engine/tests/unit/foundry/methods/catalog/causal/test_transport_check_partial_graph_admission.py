from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.foundry.methods.catalog.causal.transport_check import _legacy_pure_step
from polisyos.ir.analytics.causal import ProofBundle
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _check_typed_refusal(
    payload: Mapping[str, object],
    *,
    graph_type: GraphType,
    treatment: str,
    outcome: str,
) -> None:
    result = TransportabilityResult.model_validate(payload["transport_result"])
    _require(
        result.status is TransportabilityStatus.UNSUPPORTED,
        "partial graph must not produce an identified scalar result",
    )
    _require(
        result.unsupported_reason == "partial_graph_completion_semantics_not_established",
        "refusal must retain the specific unresolved-completion reason",
    )
    _require(
        result.transport_mode is TransportMode.NONE,
        "partial graph refusal must not carry a transport mode",
    )
    _require(result.source_graph_type is graph_type, "refusal must retain graph type")
    _require(
        result.query == f"P*({outcome}|do({treatment}))",
        "refusal must retain the requested query",
    )
    _require(result.pag_identification_policy is None, "refusal cannot claim a PAG policy")
    _require(result.id_confidence_under_pag is None, "refusal cannot claim PAG confidence")
    _require(result.pag_dag_sample_size is None, "refusal cannot claim sampled DAGs")
    _require(result.pag_transportable_count is None, "refusal cannot claim transport counts")
    _require(result.transport_formula is None, "refusal cannot carry a formula")
    _require("proof_bundle" in payload, "typed refusal must include a proof bundle")
    proof = ProofBundle.model_validate(payload["proof_bundle"])
    _require(proof.proof_status == "oracle_needed", "proof must remain candidate-grade")
    _require(proof.completeness_regime == "sound_incomplete", "proof must remain incomplete")
    _require(
        proof.metadata["reason"] == "partial_graph_completion_semantics_not_established",
        "proof must bind the refusal reason",
    )
    _require("negative_certificate" not in payload, "refusal is not a non-ID certificate")
    _require("recovery_plan" not in payload, "refusal does not invent a recovery plan")


def test_legacy_entry_refuses_fixed_and_ambiguous_queries_for_partial_graphs() -> None:
    graph_profiles = (
        (GraphType.PAG, EdgeMark.CIRCLE, EdgeMark.CIRCLE),
        (GraphType.CPDAG, EdgeMark.TAIL, EdgeMark.TAIL),
    )
    queries = (("X", "Y"), ("A", "B"))
    for graph_type, mark_src, mark_dst in graph_profiles:
        graph = CausalGraphModel(
            graph_type=graph_type,
            nodes=["X", "Y", "A", "B"],
            edges=[
                CausalEdge(src="X", dst="Y"),
                CausalEdge(
                    src="A",
                    dst="B",
                    mark_src=mark_src,
                    mark_dst=mark_dst,
                ),
            ],
        )
        source = ContextProfile(context_id="source")
        diagram = SelectionDiagram(
            base_graph=graph,
            s_nodes=[],
            source_context=source,
            target_context=source.model_copy(deep=True),
            context_distance=0.0,
        )
        for treatment, outcome in queries:
            payload = _legacy_pure_step(
                {
                    "selection_diagram": diagram.model_dump(mode="json"),
                    "query_treatment": treatment,
                    "query_outcome": outcome,
                },
                {
                    "pag_identification_policy": "probabilistic",
                    "pag_max_dag_samples": 20,
                },
            )
            _check_typed_refusal(
                payload,
                graph_type=graph_type,
                treatment=treatment,
                outcome=outcome,
            )
