"""Public causal query preservation module API."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Literal

from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    d_separation,
    descendants,
    induced_subgraph,
    m_separation,
    remove_outgoing_edges,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.cross_graph import CompositionCertificate, InterfaceMapping, SCMFragment

QueryPreservationStatus = Literal["preserved", "broken", "unknown"]


@dataclass(frozen=True)
class _ResolvedVariable:
    composed_node: str | None
    local_nodes: dict[str, str]


@dataclass(frozen=True)
class _GraphicalObligation:
    kind: Literal["backdoor_adjustment"]
    treatment: str
    outcome: str
    conditioning: frozenset[str]


@dataclass(frozen=True)
class GraphicalObligationTrace:
    """Graphical obligation trace public type."""
    kind: str
    treatment: str
    outcome: str
    conditioning: tuple[str, ...]
    holds_in_source: bool | None = None
    holds_in_composed: bool | None = None


@dataclass(frozen=True)
class QueryPreservationTrace:
    """Query preservation trace public type."""
    fingerprint: str
    status: QueryPreservationStatus
    reason_code: str
    source_fragment_id: str | None = None
    query_semantics: str = ""
    obligations_checked: tuple[GraphicalObligationTrace, ...] = ()
    witness_fragment_ids: tuple[str, ...] = ()
    source_witness_kind: str = ""
    assumption_boundary: str | None = None


def check_query_preservation(
    query: CausalQuery,
    *,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment] | None,
    fragment_graphs: Mapping[str, CausalGraphModel] | None,
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> QueryPreservationStatus:
    """Check query preservation helper."""
    evaluation = _evaluate_query_preservation(
        query,
        composed_graph=composed_graph,
        fragments=fragments or (),
        fragment_graphs=fragment_graphs or {},
        interface_mapping=interface_mapping,
        composition_certificate=composition_certificate,
    )
    return evaluation.status


def check_query_preservation_batch(
    queries: Sequence[CausalQuery],
    *,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment] | None,
    fragment_graphs: Mapping[str, CausalGraphModel] | None,
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> dict[str, QueryPreservationStatus]:
    """Check query preservation batch helper."""
    evaluations = evaluate_query_preservation_batch(
        queries,
        composed_graph=composed_graph,
        fragments=fragments or (),
        fragment_graphs=fragment_graphs or {},
        interface_mapping=interface_mapping,
        composition_certificate=composition_certificate,
    )
    return {
        fingerprint: evaluation.status
        for fingerprint, evaluation in sorted(evaluations.items())
    }


def evaluate_query_preservation(
    query: CausalQuery,
    *,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment] | None,
    fragment_graphs: Mapping[str, CausalGraphModel] | None,
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> QueryPreservationTrace:
    """Evaluate query preservation helper."""
    return _evaluate_query_preservation(
        query,
        composed_graph=composed_graph,
        fragments=fragments or (),
        fragment_graphs=fragment_graphs or {},
        interface_mapping=interface_mapping,
        composition_certificate=composition_certificate,
    )


def evaluate_query_preservation_batch(
    queries: Sequence[CausalQuery],
    *,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment] | None,
    fragment_graphs: Mapping[str, CausalGraphModel] | None,
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> dict[str, QueryPreservationTrace]:
    """Evaluate query preservation batch helper."""
    evaluations = [
        _evaluate_query_preservation(
            query,
            composed_graph=composed_graph,
            fragments=fragments or (),
            fragment_graphs=fragment_graphs or {},
            interface_mapping=interface_mapping,
            composition_certificate=composition_certificate,
        )
        for query in queries
    ]
    return {
        evaluation.fingerprint: evaluation
        for evaluation in sorted(evaluations, key=lambda item: item.fingerprint)
    }


def update_query_preservation_cache(
    composition_certificate: CompositionCertificate,
    *,
    queries: Sequence[CausalQuery],
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment] | None,
    fragment_graphs: Mapping[str, CausalGraphModel] | None,
    interface_mapping: InterfaceMapping,
) -> tuple[CompositionCertificate, dict[str, QueryPreservationStatus]]:
    """Update query preservation cache helper."""
    checked = dict(composition_certificate.checked_queries)
    evaluations = list(
        evaluate_query_preservation_batch(
            queries,
            composed_graph=composed_graph,
            fragments=fragments or (),
            fragment_graphs=fragment_graphs or {},
            interface_mapping=interface_mapping,
            composition_certificate=composition_certificate,
        ).values()
    )
    for evaluation in evaluations:
        checked[evaluation.fingerprint] = evaluation.status

    updated_certificate = composition_certificate.model_copy(
        update={"checked_queries": dict(sorted(checked.items()))}
    )
    return (
        updated_certificate,
        {
            evaluation.fingerprint: evaluation.status
            for evaluation in sorted(evaluations, key=lambda item: item.fingerprint)
        },
    )


def _evaluate_query_preservation(
    query: CausalQuery,
    *,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment],
    fragment_graphs: Mapping[str, CausalGraphModel],
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> QueryPreservationTrace:
    fingerprint = _query_fingerprint(
        query=query,
        composed_graph=composed_graph,
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        interface_mapping=interface_mapping,
        composition_certificate=composition_certificate,
    )
    cached = composition_certificate.checked_queries.get(fingerprint)
    if cached is not None:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status=cached,
            reason_code="cached",
            query_semantics=_query_semantics(query),
        )

    obligations = _graphical_obligations_for_query(query)
    if not obligations:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="unsupported_query_type",
            query_semantics=_query_semantics(query),
        )

    query_variables = sorted(
        {
            obligation.treatment
            for obligation in obligations
        }
        | {
            obligation.outcome
            for obligation in obligations
        }
        | {
            variable
            for obligation in obligations
            for variable in obligation.conditioning
        }
    )
    resolutions = _build_variable_resolutions(
        query_variables=query_variables,
        composed_graph=composed_graph,
        fragment_graphs=fragment_graphs,
        interface_mapping=interface_mapping,
    )
    if set(query_variables) - set(resolutions):
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="unresolved_query_variable",
            query_semantics=_query_semantics(query),
        )

    composed_obligations = _resolve_composed_obligations(obligations, resolutions)
    if composed_obligations is None:
        return QueryPreservationTrace(
            fingerprint=fingerprint,
            status="unknown",
            reason_code="unresolved_composed_node",
            query_semantics=_query_semantics(query),
        )

    fragment_ids = sorted(fragment_graphs)
    topology = _fragment_topology(
        fragment_ids=fragment_ids,
        interface_mapping=interface_mapping,
        composition_certificate=composition_certificate,
    )

    obligation_traces: list[GraphicalObligationTrace] = []
    witness_sets: list[tuple[str, ...]] = []
    witness_kind = ""
    source_fragment_id: str | None = None

    for obligation, composed_obligation in zip(obligations, composed_obligations, strict=False):
        witness_candidates = _candidate_witness_fragment_sets(
            obligation=obligation,
            resolutions=resolutions,
            fragment_ids=fragment_ids,
            topology=topology,
        )
        if not witness_candidates:
            return QueryPreservationTrace(
                fingerprint=fingerprint,
                status="unknown",
                reason_code="missing_obligation_witness",
                query_semantics=_query_semantics(query),
                obligations_checked=tuple(obligation_traces),
                witness_fragment_ids=tuple(sorted({item for group in witness_sets for item in group})),
            )

        evaluated_candidates: list[tuple[tuple[str, ...], GraphicalObligationTrace, str | None]] = []
        for witness_fragment_ids in witness_candidates:
            witness_graph = _build_witness_graph(
                witness_fragment_ids=witness_fragment_ids,
                fragment_graphs=fragment_graphs,
                interface_mapping=interface_mapping,
            )
            if witness_graph is None:
                continue
            holds_in_source = _obligation_holds(witness_graph, composed_obligation)
            holds_in_composed = _obligation_holds(composed_graph, composed_obligation)
            evaluated_candidates.append(
                (
                    witness_fragment_ids,
                    GraphicalObligationTrace(
                        kind=composed_obligation.kind,
                        treatment=composed_obligation.treatment,
                        outcome=composed_obligation.outcome,
                        conditioning=tuple(sorted(composed_obligation.conditioning)),
                        holds_in_source=holds_in_source,
                        holds_in_composed=holds_in_composed,
                    ),
                    _assumption_boundary_for_obligation(
                        obligation=composed_obligation,
                        witness_graph=witness_graph,
                        composed_graph=composed_graph,
                        interface_mapping=interface_mapping,
                    ),
                )
            )

        if not evaluated_candidates:
            return QueryPreservationTrace(
                fingerprint=fingerprint,
                status="unknown",
                reason_code="missing_obligation_witness",
                query_semantics=_query_semantics(query),
                obligations_checked=tuple(obligation_traces),
                witness_fragment_ids=tuple(sorted({item for group in witness_sets for item in group})),
            )

        supporting_candidates = [
            item for item in evaluated_candidates if item[1].holds_in_source is True
        ]
        if supporting_candidates:
            chosen_witness, obligation_trace, assumption_boundary = next(
                (
                    item
                    for item in supporting_candidates
                    if item[2] is None
                ),
                supporting_candidates[0],
            )
        else:
            chosen_witness, obligation_trace, assumption_boundary = evaluated_candidates[0]

        witness_fragment_ids = chosen_witness
        witness_sets.append(witness_fragment_ids)
        obligation_traces.append(obligation_trace)

        if obligation_trace.holds_in_source is not True:
            combined_witness = tuple(sorted({item for group in witness_sets for item in group}))
            return QueryPreservationTrace(
                fingerprint=fingerprint,
                status="unknown",
                reason_code="source_obligation_not_supported",
                source_fragment_id=witness_fragment_ids[0] if len(witness_fragment_ids) == 1 else None,
                query_semantics=_query_semantics(query),
                obligations_checked=tuple(obligation_traces),
                witness_fragment_ids=combined_witness,
                source_witness_kind=_witness_kind(combined_witness),
            )

        if assumption_boundary is not None:
            combined_witness = tuple(sorted({item for group in witness_sets for item in group}))
            return QueryPreservationTrace(
                fingerprint=fingerprint,
                status="unknown",
                reason_code="latent_bridge_research_boundary",
                source_fragment_id=witness_fragment_ids[0] if len(witness_fragment_ids) == 1 else None,
                query_semantics=_query_semantics(query),
                obligations_checked=tuple(obligation_traces),
                witness_fragment_ids=combined_witness,
                source_witness_kind=_witness_kind(combined_witness),
                assumption_boundary=assumption_boundary,
            )

        if obligation_trace.holds_in_composed is not True:
            combined_witness = tuple(sorted({item for group in witness_sets for item in group}))
            return QueryPreservationTrace(
                fingerprint=fingerprint,
                status="broken",
                reason_code="obligation_broken_after_composition",
                source_fragment_id=witness_fragment_ids[0] if len(witness_fragment_ids) == 1 else None,
                query_semantics=_query_semantics(query),
                obligations_checked=tuple(obligation_traces),
                witness_fragment_ids=combined_witness,
                source_witness_kind=_witness_kind(combined_witness),
            )

        if not witness_kind:
            witness_kind = _witness_kind(witness_fragment_ids)
        if source_fragment_id is None and len(witness_fragment_ids) == 1:
            source_fragment_id = witness_fragment_ids[0]

    combined_witness = tuple(sorted({item for group in witness_sets for item in group}))
    return QueryPreservationTrace(
        fingerprint=fingerprint,
        status="preserved",
        reason_code="evaluated",
        source_fragment_id=source_fragment_id if len(combined_witness) == 1 else None,
        query_semantics=_query_semantics(query),
        obligations_checked=tuple(obligation_traces),
        witness_fragment_ids=combined_witness,
        source_witness_kind=_witness_kind(combined_witness),
    )


def _graphical_obligations_for_query(query: CausalQuery) -> tuple[_GraphicalObligation, ...]:
    if query.query_type not in {QueryType.INTERVENTIONAL, QueryType.SOFT_INTERVENTION}:
        return ()
    treatment = str(query.treatment_variable).strip()
    outcome = str(query.outcome_variable).strip()
    conditioning = frozenset(
        str(variable).strip()
        for variable in query.condition
        if str(variable).strip()
    )
    if not treatment or not outcome or treatment == outcome:
        return ()
    return (
        _GraphicalObligation(
            kind="backdoor_adjustment",
            treatment=treatment,
            outcome=outcome,
            conditioning=conditioning,
        ),
    )


def _query_semantics(query: CausalQuery) -> str:
    if query.intervention_spec is not None:
        return f"{query.query_type.value}:{query.intervention_spec.type.value}"
    return query.query_type.value


def _resolve_composed_obligations(
    obligations: Sequence[_GraphicalObligation],
    resolutions: Mapping[str, _ResolvedVariable],
) -> tuple[_GraphicalObligation, ...] | None:
    resolved: list[_GraphicalObligation] = []
    for obligation in obligations:
        treatment = resolutions[obligation.treatment].composed_node
        outcome = resolutions[obligation.outcome].composed_node
        conditioning = {
            resolutions[variable].composed_node
            for variable in obligation.conditioning
        }
        if treatment is None or outcome is None or None in conditioning:
            return None
        resolved.append(
            _GraphicalObligation(
                kind=obligation.kind,
                treatment=treatment,
                outcome=outcome,
                conditioning=frozenset(str(variable) for variable in conditioning if variable),
            )
        )
    return tuple(resolved)


def _build_variable_resolutions(
    *,
    query_variables: Sequence[str],
    composed_graph: CausalGraphModel,
    fragment_graphs: Mapping[str, CausalGraphModel],
    interface_mapping: InterfaceMapping,
) -> dict[str, _ResolvedVariable]:
    binding_keys = {
        (binding.fragment_id, binding.variable_name)
        for entry in interface_mapping.entries
        for binding in entry.bindings
    }
    interface_by_canonical = {
        entry.canonical_node_id: entry for entry in interface_mapping.entries
    }
    interface_by_variable_name: dict[str, list[tuple[str, str, str]]] = {}
    for entry in interface_mapping.entries:
        for binding in entry.bindings:
            interface_by_variable_name.setdefault(binding.variable_name, []).append(
                (entry.canonical_node_id, binding.fragment_id, binding.variable_name)
            )

    non_interface_nodes: dict[str, list[tuple[str, str, str]]] = {}
    for fragment_id, graph in fragment_graphs.items():
        for node in graph.nodes:
            if (fragment_id, node) in binding_keys:
                continue
            non_interface_nodes.setdefault(node, []).append(
                (f"{fragment_id}::{node}", fragment_id, node)
            )

    resolutions: dict[str, _ResolvedVariable] = {}
    composed_nodes = set(composed_graph.nodes)
    for variable in query_variables:
        token = str(variable).strip()
        if not token:
            continue
        entry = interface_by_canonical.get(token)
        if entry is not None:
            resolutions[token] = _ResolvedVariable(
                composed_node=entry.canonical_node_id,
                local_nodes={binding.fragment_id: binding.variable_name for binding in entry.bindings},
            )
            continue

        if token in composed_nodes and "::" in token:
            fragment_id, local_name = token.split("::", 1)
            if fragment_id in fragment_graphs and local_name in fragment_graphs[fragment_id].nodes:
                resolutions[token] = _ResolvedVariable(
                    composed_node=token,
                    local_nodes={fragment_id: local_name},
                )
                continue

        interface_candidates = interface_by_variable_name.get(token, [])
        unique_interface_nodes = {item[0] for item in interface_candidates}
        if len(unique_interface_nodes) == 1:
            canonical_node = next(iter(unique_interface_nodes))
            local_nodes = {
                fragment_id: variable_name
                for _, fragment_id, variable_name in interface_candidates
            }
            resolutions[token] = _ResolvedVariable(
                composed_node=canonical_node,
                local_nodes=local_nodes,
            )
            continue

        non_interface_candidates = non_interface_nodes.get(token, [])
        if len(non_interface_candidates) == 1:
            composed_node, fragment_id, local_name = non_interface_candidates[0]
            resolutions[token] = _ResolvedVariable(
                composed_node=composed_node,
                local_nodes={fragment_id: local_name},
            )

    return resolutions


def _fragment_topology(
    *,
    fragment_ids: Sequence[str],
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> dict[str, set[str]]:
    adjacency = {fragment_id: set() for fragment_id in fragment_ids}

    for raw_pair in composition_certificate.metadata.get("selected_stitch_pairs", []):
        if not isinstance(raw_pair, (list, tuple)) or len(raw_pair) != 2:
            continue
        left = str(raw_pair[0]).strip()
        right = str(raw_pair[1]).strip()
        if left in adjacency and right in adjacency and left != right:
            adjacency[left].add(right)
            adjacency[right].add(left)

    if any(adjacency.values()):
        return adjacency

    for entry in interface_mapping.entries:
        fragment_group = sorted({binding.fragment_id for binding in entry.bindings})
        for left, right in combinations(fragment_group, 2):
            adjacency.setdefault(left, set()).add(right)
            adjacency.setdefault(right, set()).add(left)
    return adjacency


def _candidate_witness_fragment_sets(
    *,
    obligation: _GraphicalObligation,
    resolutions: Mapping[str, _ResolvedVariable],
    fragment_ids: Sequence[str],
    topology: Mapping[str, set[str]],
) -> list[tuple[str, ...]]:
    variables = [obligation.treatment, obligation.outcome, *sorted(obligation.conditioning)]
    candidate_sets = {
        variable: set(resolutions[variable].local_nodes)
        for variable in variables
    }
    candidates: list[tuple[str, ...]] = []
    for size in range(1, len(fragment_ids) + 1):
        for subset in combinations(fragment_ids, size):
            subset_set = set(subset)
            if not all(candidate_sets[variable] & subset_set for variable in variables):
                continue
            if _subset_connected(subset_set, topology):
                candidates.append(tuple(subset))
        if candidates:
            return candidates
    return []


def _subset_connected(
    subset: set[str],
    topology: Mapping[str, set[str]],
) -> bool:
    if not subset:
        return False
    if len(subset) == 1:
        return True
    start = next(iter(sorted(subset)))
    visited = {start}
    frontier = [start]
    while frontier:
        current = frontier.pop()
        for neighbor in sorted(topology.get(current, set()) & subset):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            frontier.append(neighbor)
    return visited == subset


def _build_witness_graph(
    *,
    witness_fragment_ids: Sequence[str],
    fragment_graphs: Mapping[str, CausalGraphModel],
    interface_mapping: InterfaceMapping,
) -> CausalGraphModel | None:
    if not witness_fragment_ids:
        return None
    if any(fragment_id not in fragment_graphs for fragment_id in witness_fragment_ids):
        return None

    binding_to_node = {
        (binding.fragment_id, binding.variable_name): entry.canonical_node_id
        for entry in interface_mapping.entries
        for binding in entry.bindings
    }
    graph_type = (
        GraphType.ADMG
        if any(fragment_graphs[fragment_id].graph_type is GraphType.ADMG for fragment_id in witness_fragment_ids)
        else GraphType.DAG
    )
    node_set: set[str] = set()
    merged_edges: dict[tuple[str, str, str, str, int], CausalEdge] = {}

    for fragment_id in sorted(witness_fragment_ids):
        graph = fragment_graphs[fragment_id]
        node_map = {
            node: binding_to_node.get((fragment_id, node), f"{fragment_id}::{node}")
            for node in graph.nodes
        }
        node_set.update(node_map.values())
        for edge in graph.edges:
            remapped = edge.model_copy(
                update={
                    "src": node_map[edge.src],
                    "dst": node_map[edge.dst],
                }
            )
            if remapped.src == remapped.dst:
                continue
            edge_key = _witness_edge_key(remapped)
            merged_edges[edge_key] = _merge_witness_edge(merged_edges.get(edge_key), remapped)

    return CausalGraphModel(
        graph_type=graph_type,
        nodes=sorted(node_set),
        edges=[merged_edges[key] for key in sorted(merged_edges)],
        discovery_method="query_preservation_witness",
        metadata={"witness_fragment_ids": list(sorted(witness_fragment_ids))},
    )


def _witness_edge_key(edge: CausalEdge) -> tuple[str, str, str, str, int]:
    return (
        edge.src,
        edge.dst,
        edge.mark_src.value,
        edge.mark_dst.value,
        int(edge.lag or 0),
    )


def _merge_witness_edge(existing: CausalEdge | None, incoming: CausalEdge) -> CausalEdge:
    if existing is None:
        combined = incoming.compute_combined_confidence() if incoming.sources else incoming.combined_confidence
        return incoming.model_copy(update={"combined_confidence": combined})

    merged = CausalEdge(
        src=existing.src,
        dst=existing.dst,
        mark_src=existing.mark_src,
        mark_dst=existing.mark_dst,
        lag=existing.lag,
        sources=sorted(set(existing.sources) | set(incoming.sources), key=lambda item: item.value),
        data_confidence=max(
            value for value in (existing.data_confidence, incoming.data_confidence) if value is not None
        )
        if any(value is not None for value in (existing.data_confidence, incoming.data_confidence))
        else None,
        literature_confidence=max(
            value
            for value in (existing.literature_confidence, incoming.literature_confidence)
            if value is not None
        )
        if any(
            value is not None
            for value in (existing.literature_confidence, incoming.literature_confidence)
        )
        else None,
        llm_confidence=max(
            value for value in (existing.llm_confidence, incoming.llm_confidence) if value is not None
        )
        if any(value is not None for value in (existing.llm_confidence, incoming.llm_confidence))
        else None,
        expert_confidence=max(
            value for value in (existing.expert_confidence, incoming.expert_confidence) if value is not None
        )
        if any(value is not None for value in (existing.expert_confidence, incoming.expert_confidence))
        else None,
        simulation_confidence=max(
            value
            for value in (existing.simulation_confidence, incoming.simulation_confidence)
            if value is not None
        )
        if any(
            value is not None
            for value in (existing.simulation_confidence, incoming.simulation_confidence)
        )
        else None,
        unsupported_by_evidence=existing.unsupported_by_evidence and incoming.unsupported_by_evidence,
        evidence_refs=sorted(set(existing.evidence_refs) | set(incoming.evidence_refs)),
        metadata={**existing.metadata, **incoming.metadata},
    )
    combined_confidence = (
        merged.compute_combined_confidence()
        if merged.sources
        else max(
            value
            for value in (existing.combined_confidence, incoming.combined_confidence)
            if value is not None
        )
        if any(value is not None for value in (existing.combined_confidence, incoming.combined_confidence))
        else None
    )
    return merged.model_copy(update={"combined_confidence": combined_confidence})


def _assumption_boundary_for_obligation(
    *,
    obligation: _GraphicalObligation,
    witness_graph: CausalGraphModel,
    composed_graph: CausalGraphModel,
    interface_mapping: InterfaceMapping,
) -> str | None:
    latent_nodes = {
        entry.canonical_node_id
        for entry in interface_mapping.entries
        if entry.alignment_type == "latent_bridge"
    }
    if not latent_nodes:
        return None
    witness_nodes = _obligation_relevant_nodes(witness_graph, obligation)
    composed_nodes = _obligation_relevant_nodes(composed_graph, obligation)
    if latent_nodes & witness_nodes:
        return "latent_bridge"
    if latent_nodes & composed_nodes:
        return "latent_bridge"
    return None


def _obligation_holds(
    graph: CausalGraphModel,
    obligation: _GraphicalObligation,
) -> bool:
    if obligation.kind != "backdoor_adjustment":
        return False
    seed = frozenset(
        {obligation.treatment, obligation.outcome, *obligation.conditioning}
    )
    if not seed.issubset(set(graph.nodes)):
        return False
    forbidden_adjustment = descendants(
        graph,
        frozenset({obligation.treatment}),
        include_self=False,
    )
    if obligation.conditioning & forbidden_adjustment:
        return False

    mutilated = remove_outgoing_edges(graph, frozenset({obligation.treatment}))
    relevant_nodes = ancestors(mutilated, seed) | seed
    relevant_graph = induced_subgraph(mutilated, relevant_nodes)
    return _separation_holds(
        relevant_graph,
        treatment=obligation.treatment,
        outcome=obligation.outcome,
        conditioning=obligation.conditioning,
    )


def _obligation_relevant_nodes(
    graph: CausalGraphModel,
    obligation: _GraphicalObligation,
) -> frozenset[str]:
    seed = frozenset({obligation.treatment, obligation.outcome, *obligation.conditioning})
    if not seed.issubset(set(graph.nodes)):
        return frozenset()
    mutilated = remove_outgoing_edges(graph, frozenset({obligation.treatment}))
    return frozenset(ancestors(mutilated, seed) | seed)


def _separation_holds(
    graph: CausalGraphModel,
    *,
    treatment: str,
    outcome: str,
    conditioning: frozenset[str],
) -> bool:
    if not {treatment, outcome, *conditioning}.issubset(set(graph.nodes)):
        return False
    if graph.graph_type is GraphType.DAG:
        return d_separation(
            graph,
            frozenset({treatment}),
            frozenset({outcome}),
            conditioning,
        )
    if graph.graph_type is GraphType.ADMG:
        return m_separation(
            graph,
            frozenset({treatment}),
            frozenset({outcome}),
            conditioning,
        )
    raise ValueError(f"unsupported graph type for query preservation: {graph.graph_type}")


def _witness_kind(witness_fragment_ids: Sequence[str]) -> str:
    return "single_fragment" if len(witness_fragment_ids) == 1 else "stitched_subgraph"


def _query_fingerprint(
    *,
    query: CausalQuery,
    composed_graph: CausalGraphModel,
    fragments: Sequence[SCMFragment],
    fragment_graphs: Mapping[str, CausalGraphModel],
    interface_mapping: InterfaceMapping,
    composition_certificate: CompositionCertificate,
) -> str:
    payload = {
        "query": query.model_dump(mode="json"),
        "composition": {
            "composed_graph": _graph_signature(composed_graph),
            "source_fragment_ids": sorted(composition_certificate.source_fragment_refs),
            "source_fragment_graph_ids": sorted(composition_certificate.source_fragment_graph_refs),
            "fragments": [
                {
                    "fragment_id": fragment.fragment_id,
                    "fragment_graph": _graph_signature(fragment_graphs[fragment.fragment_id]),
                }
                for fragment in sorted(fragments, key=lambda item: item.fragment_id)
                if fragment.fragment_id in fragment_graphs
            ],
            "fragment_graphs": {
                fragment_id: _graph_signature(graph)
                for fragment_id, graph in sorted(fragment_graphs.items())
            },
            "interface_mapping": interface_mapping.model_dump(mode="json"),
        },
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _graph_signature(graph: CausalGraphModel) -> dict[str, object]:
    return {
        "graph_type": graph.graph_type.value,
        "nodes": list(graph.nodes),
        "edges": [
            _edge_signature(edge)
            for edge in sorted(
                graph.edges,
                key=lambda item: (
                    item.src,
                    item.dst,
                    item.mark_src.value,
                    item.mark_dst.value,
                    int(item.lag or 0),
                ),
            )
        ],
    }


def _edge_signature(edge: CausalEdge) -> dict[str, object]:
    return {
        "src": edge.src,
        "dst": edge.dst,
        "mark_src": edge.mark_src.value,
        "mark_dst": edge.mark_dst.value,
        "lag": int(edge.lag or 0),
    }


__all__ = [
    "GraphicalObligationTrace",
    "QueryPreservationTrace",
    "QueryPreservationStatus",
    "evaluate_query_preservation",
    "evaluate_query_preservation_batch",
    "check_query_preservation",
    "check_query_preservation_batch",
    "update_query_preservation_cache",
]
