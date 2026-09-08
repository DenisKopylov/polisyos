"""Public causal graph reconciliation module API."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal.admg_ops import tarjan_scc
from polisyos.foundry.methods.catalog.causal.composition_failure_cards import (
    build_composition_failure_cards,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    FragmentCompositionData,
    GraphReconciliationData,
    LLMStructuralHint,
)
from polisyos.ir.analytics.alignment_certification import (
    AlignmentOverallStatus,
    AlignmentReviewerState,
    AlignmentReviewStatus,
    AlignmentType,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
)
from polisyos.ir.analytics.cross_graph import (
    CompositionCertificate,
    CompositionPolicy,
    CycleScope,
    CycleType,
    completeness_scope_for_composition,
)
from polisyos.ir.analytics.literature import (
    LiteratureCausalPrior,
    ReconciliationDiagnostics,
)

LLM_PRIOR_CEILING = 0.3
LLM_OVERLAP_DISCOUNT = 0.5
LLM_REPLICATION_BONUS = 0.05

MAX_LAG_DEPTH = 2
MAX_LAGGED_EDGES = 10
MAX_CYCLES_TO_RESOLVE = 8

MAX_RECON_SOURCES = 128
MAX_RECON_EDGES = 4096
MAX_TRIANGLES = 20_000
TRIANGLE_BUDGET_MS = 250

RIDGE_EPSILON = 1.0e-6

_SUPPORTED_CYCLE_TYPES = {
    CycleType.SIMPLE_CYCLIC,
    CycleType.EQUILIBRIUM_CONTRACTIVE,
    CycleType.EQUILIBRIUM_LINEAR_STABLE,
}


@dataclass
class _MergedEdge:
    src: str
    dst: str
    lag: int | None = None
    sources: set[EdgeSource] = field(default_factory=set)
    data_confidence: float | None = None
    literature_confidence: float | None = None
    llm_confidence: float | None = None
    expert_confidence: float | None = None
    simulation_confidence: float | None = None
    unsupported_by_evidence: bool = False
    evidence_refs: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    combined_confidence: float = 0.0


def _cycle_contract_summary(fragment: Any) -> dict[str, Any]:
    witness_summary = [
        {
            "scc_id": witness.scc_id,
            "solver_kind": witness.solver_kind.value,
            "uniqueness_scope": witness.uniqueness_scope.value,
            "interventional_closure": witness.interventional_closure.value,
            "markov_semantics": witness.markov_semantics.value,
            "initial_condition_dependent": witness.initial_condition_dependent,
        }
        for witness in fragment.cycle_witnesses
    ]
    return {
        "fragment_id": fragment.fragment_id,
        "cycle_type": fragment.cycle_type.value,
        "cycle_scope": fragment.cycle_scope.value,
        "composition_policy": fragment.composition_policy.value,
        "graph_audit_guarantee": fragment.graph_audit_guarantee.value,
        "allowed_alignment_types": list(fragment.allowed_alignment_types),
        "witnesses": witness_summary,
    }


def _fragment_supports_cycle_aware_composition(fragment: Any) -> bool:
    if fragment.cycle_type not in _SUPPORTED_CYCLE_TYPES:
        return False
    if fragment.cycle_scope is not CycleScope.INTERNAL_SCC:
        return False
    if fragment.composition_policy is not CompositionPolicy.ALLOW:
        return False
    if not fragment.cycle_witnesses:
        return False
    return all(
        witness.markov_semantics.value == "sigma_separation"
        and witness.interventional_closure.value != "none"
        and not witness.initial_condition_dependent
        for witness in fragment.cycle_witnesses
    )


def _fragments_declare_cycles(fragments: list[Any]) -> bool:
    return any(fragment.cycle_type is not CycleType.ACYCLIC for fragment in fragments)


def _cycle_semantics_mode(fragments: list[Any]) -> str:
    cyclic_fragments = [
        fragment for fragment in fragments if fragment.cycle_type is not CycleType.ACYCLIC
    ]
    if not cyclic_fragments:
        return "none"
    if all(
        witness.markov_semantics.value == "sigma_separation"
        for fragment in cyclic_fragments
        for witness in fragment.cycle_witnesses
    ):
        return "sigma_separation"
    return "none"


def _effective_composition_graph_type(
    graphs: dict[str, CausalGraphModel],
    fragments: list[Any],
) -> GraphType:
    if any(graph.graph_type is GraphType.ADMG for graph in graphs.values()):
        return GraphType.ADMG
    if _fragments_declare_cycles(fragments):
        return GraphType.ADMG
    return GraphType.DAG


def _edge_fragment_ids(edge: CausalEdge) -> set[str]:
    raw = edge.metadata.get("contributing_fragment_ids", [])
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if str(item).strip()}


def _directed_sccs(nodes: set[str], edges: list[CausalEdge]) -> list[frozenset[str]]:
    directed_edges = [
        edge
        for edge in edges
        if edge.mark_src is EdgeMark.TAIL
        and edge.mark_dst is EdgeMark.ARROW
        and edge.lag in (None, 0)
    ]
    if not directed_edges:
        return []
    graph = CausalGraphModel.model_construct(
        schema_version="1.0",
        graph_type=GraphType.ADMG,
        nodes=sorted(nodes),
        edges=directed_edges,
        discovery_method="fragment_composition_cycle_check",
        metadata={},
    )
    return [component for component in tarjan_scc(graph) if len(component) > 1]


def _cross_fragment_cycle_components(
    nodes: set[str],
    edges: list[CausalEdge],
) -> list[dict[str, list[str]]]:
    components: list[dict[str, list[str]]] = []
    for component in _directed_sccs(nodes, edges):
        contributing_fragments: set[str] = set()
        for edge in edges:
            if edge.src in component and edge.dst in component:
                contributing_fragments.update(_edge_fragment_ids(edge))
        if len(contributing_fragments) <= 1:
            continue
        components.append(
            {
                "nodes": sorted(component),
                "fragment_ids": sorted(contributing_fragments),
            }
        )
    return components


def _evaluate_fragment_cycle_contracts(
    payload: FragmentCompositionData,
) -> tuple[list[str], bool, list[str], list[dict[str, Any]]]:
    """Evaluate declared cycle contracts before strict graph composition."""

    binding_alignment_types: dict[str, set[str]] = defaultdict(set)
    for entry in payload.interface_mapping.entries:
        for binding in entry.bindings:
            binding_alignment_types[binding.fragment_id].add(entry.alignment_type)

    blocking_reasons: list[str] = []
    needs_expert_review = False
    structural_assumptions: list[str] = []
    cycle_contracts: list[dict[str, Any]] = []
    research_only_types = {
        CycleType.DSCM_SEMANTICS,
        CycleType.FINITE_P_SEPARATION,
        CycleType.UNSUPPORTED,
    }

    for fragment in sorted(payload.fragments, key=lambda item: item.fragment_id):
        cycle_contracts.append(_cycle_contract_summary(fragment))

        used_alignment_types = binding_alignment_types.get(fragment.fragment_id, set())
        disallowed_alignment_types = sorted(
            alignment_type
            for alignment_type in used_alignment_types
            if alignment_type not in set(fragment.allowed_alignment_types)
        )
        if disallowed_alignment_types:
            blocking_reasons.append(
                "Fragment "
                f"{fragment.fragment_id} forbids alignment types under its declared cycle contract: "
                + ", ".join(disallowed_alignment_types)
                + "."
            )

        if fragment.cycle_type is CycleType.ACYCLIC:
            continue

        structural_assumptions.append(
            f"cycle_contract::{fragment.fragment_id}::{fragment.cycle_type.value}"
        )

        if fragment.composition_policy is CompositionPolicy.BLOCK:
            blocking_reasons.append(
                f"Fragment {fragment.fragment_id} declares composition_policy=block for cyclic semantics."
            )
        elif fragment.composition_policy is CompositionPolicy.ALLOW_BOUNDS_ONLY:
            blocking_reasons.append(
                "Fragment "
                f"{fragment.fragment_id} only permits bounds-only cyclic composition, which the strict composer "
                "does not implement."
            )
        elif fragment.composition_policy is CompositionPolicy.REQUIRE_HUMAN_REVIEW:
            needs_expert_review = True

        if fragment.cycle_scope is CycleScope.CROSS_FRAGMENT_SCC:
            blocking_reasons.append(
                f"Fragment {fragment.fragment_id} declares cross-fragment cyclic scope, which strict composition does not support."
            )

        if fragment.cycle_type in research_only_types:
            blocking_reasons.append(
                f"Fragment {fragment.fragment_id} declares research-only cycle semantics {fragment.cycle_type.value}."
            )

        if any(witness.initial_condition_dependent for witness in fragment.cycle_witnesses):
            blocking_reasons.append(
                f"Fragment {fragment.fragment_id} has initial-condition-dependent cycle witnesses."
            )

    return blocking_reasons, needs_expert_review, structural_assumptions, cycle_contracts


def _clamp_probability(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _edge_key(src: str, dst: str, lag: int | None) -> tuple[str, str, int]:
    return (str(src), str(dst), int(lag or 0))


def _combined_confidence(edge: _MergedEdge) -> float:
    confidences = [
        _clamp_probability(edge.data_confidence),
        _clamp_probability(edge.literature_confidence),
        _clamp_probability(edge.expert_confidence),
        _clamp_probability(edge.simulation_confidence),
        _clamp_probability(edge.llm_confidence),
    ]
    if all(value <= 0.0 for value in confidences):
        return 0.0
    product = 1.0
    for value in confidences:
        product *= 1.0 - value
    merged = 1.0 - product
    if edge.sources == {EdgeSource.LLM_PRIOR}:
        merged = min(merged, LLM_PRIOR_CEILING)
    return _clamp_probability(merged)


def _coerce_source_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _add_literature_edges(
    *,
    merged: dict[tuple[str, str, int], _MergedEdge],
    prior: LiteratureCausalPrior | None,
    min_edge_confidence: float,
) -> None:
    if prior is None:
        return
    for edge in prior.edges:
        if edge.confidence < min_edge_confidence:
            continue
        key = _edge_key(edge.src, edge.dst, None)
        current = merged.get(key)
        if current is None:
            current = _MergedEdge(src=edge.src, dst=edge.dst)
            merged[key] = current
        current.sources.add(EdgeSource.LITERATURE)
        current.literature_confidence = max(
            _clamp_probability(current.literature_confidence),
            _clamp_probability(edge.confidence),
        )
        current.evidence_refs.update(edge.article_refs)
        current.metadata.setdefault(
            "evidence_strength",
            edge.evidence_strength.value if edge.evidence_strength is not None else None,
        )
        current.metadata.setdefault(
            "evidence_strength_status", edge.evidence_strength_status.value
        )
        current.metadata.setdefault("scope_conditions", list(edge.scope_conditions))
        current.metadata.setdefault("direction", edge.direction.value)
        if edge.meta_effect_size is not None:
            current.metadata["meta_effect_size"] = float(edge.meta_effect_size)


def _add_data_edges(
    *,
    merged: dict[tuple[str, str, int], _MergedEdge],
    data_graph: CausalGraphModel,
    warnings: list[str],
) -> None:
    for edge in data_graph.edges:
        key = _edge_key(edge.src, edge.dst, edge.lag)
        reverse_key = _edge_key(edge.dst, edge.src, edge.lag)
        reverse = merged.get(reverse_key)
        if reverse is not None and EdgeSource.DATA not in reverse.sources:
            reverse.metadata["direction_conflict"] = True
            warnings.append(
                f"Direction conflict {edge.dst}->{edge.src} vs {edge.src}->{edge.dst}: data direction kept."
            )
            merged.pop(reverse_key, None)

        current = merged.get(key)
        if current is None:
            current = _MergedEdge(src=edge.src, dst=edge.dst, lag=edge.lag)
            merged[key] = current
        current.sources.add(EdgeSource.DATA)
        data_conf = edge.data_confidence
        if data_conf is None:
            data_conf = edge.combined_confidence
        current.data_confidence = max(
            _clamp_probability(current.data_confidence),
            _clamp_probability(data_conf),
        )
        current.evidence_refs.update(edge.evidence_refs)
        source_tags = _coerce_source_tags(edge.metadata.get("source_method_tags"))
        if source_tags:
            current.metadata["source_method_tags"] = sorted(
                set(_coerce_source_tags(current.metadata.get("source_method_tags")))
                | set(source_tags)
            )


def _add_llm_hints(
    *,
    merged: dict[tuple[str, str, int], _MergedEdge],
    llm_hints: list[LLMStructuralHint],
    warnings: list[str],
) -> None:
    for hint in llm_hints:
        key = _edge_key(hint.src, hint.dst, None)
        reverse_key = _edge_key(hint.dst, hint.src, None)
        reverse = merged.get(reverse_key)
        hint_confidence = min(LLM_PRIOR_CEILING, _clamp_probability(hint.confidence))

        if reverse is not None and (
            reverse.data_confidence is not None or reverse.literature_confidence is not None
        ):
            reverse.metadata["llm_disagreement"] = True
            warnings.append(
                f"LLM disagreement on {hint.src}->{hint.dst}; evidence-backed direction preserved."
            )
            continue

        current = merged.get(key)
        if current is None:
            current = _MergedEdge(src=hint.src, dst=hint.dst)
            merged[key] = current

        overlap_with_evidence = (
            current.data_confidence is not None or current.literature_confidence is not None
        )
        calibrated = hint_confidence
        if overlap_with_evidence:
            calibrated = min(
                LLM_PRIOR_CEILING,
                hint_confidence * LLM_OVERLAP_DISCOUNT + LLM_REPLICATION_BONUS,
            )
        current.sources.add(EdgeSource.LLM_PRIOR)
        current.llm_confidence = max(
            _clamp_probability(current.llm_confidence),
            _clamp_probability(calibrated),
        )
        if not overlap_with_evidence:
            current.unsupported_by_evidence = True
        if hint.rationale:
            current.metadata.setdefault("llm_rationale", str(hint.rationale))
        if hint.source_method_tags:
            current.metadata["source_method_tags"] = sorted(
                set(_coerce_source_tags(current.metadata.get("source_method_tags")))
                | {str(tag) for tag in hint.source_method_tags}
            )
        if hint.metadata:
            merged_meta = dict(current.metadata)
            merged_meta.update(dict(hint.metadata))
            current.metadata = merged_meta


def _materialize_edges(
    *,
    merged: dict[tuple[str, str, int], _MergedEdge],
    min_edge_confidence: float,
) -> list[CausalEdge]:
    output: list[CausalEdge] = []
    for value in merged.values():
        value.combined_confidence = _combined_confidence(value)
        if value.combined_confidence < min_edge_confidence:
            continue
        edge = CausalEdge(
            src=value.src,
            dst=value.dst,
            lag=value.lag,
            sources=sorted(value.sources, key=lambda item: item.value),
            data_confidence=value.data_confidence,
            literature_confidence=value.literature_confidence,
            llm_confidence=value.llm_confidence,
            expert_confidence=value.expert_confidence,
            simulation_confidence=value.simulation_confidence,
            combined_confidence=value.combined_confidence,
            unsupported_by_evidence=value.unsupported_by_evidence,
            evidence_refs=sorted(value.evidence_refs),
            metadata=dict(value.metadata),
        )
        output.append(edge)
    output.sort(key=lambda edge: (edge.src, edge.dst, int(edge.lag or 0)))
    return output


def _find_cycle(edges: list[CausalEdge]) -> list[int] | None:
    adjacency: dict[str, list[tuple[str, int]]] = defaultdict(list)
    nodes: set[str] = set()
    for idx, edge in enumerate(edges):
        nodes.add(edge.src)
        nodes.add(edge.dst)
        adjacency[edge.src].append((edge.dst, idx))
    color: dict[str, int] = dict.fromkeys(nodes, 0)  # 0=unseen, 1=active, 2=done
    parent_node: dict[str, str | None] = {}
    parent_edge: dict[str, int] = {}

    for start in sorted(nodes):
        if color[start] != 0:
            continue
        parent_node[start] = None
        stack: list[tuple[str, int]] = [(start, 0)]
        while stack:
            node, offset = stack[-1]
            if color[node] == 0:
                color[node] = 1
            neighbors = adjacency.get(node, [])
            if offset >= len(neighbors):
                color[node] = 2
                stack.pop()
                continue

            nxt, edge_idx = neighbors[offset]
            stack[-1] = (node, offset + 1)
            nxt_color = color.get(nxt, 0)
            if nxt_color == 0:
                parent_node[nxt] = node
                parent_edge[nxt] = edge_idx
                stack.append((nxt, 0))
                continue
            if nxt_color == 1:
                cycle_edges = [edge_idx]
                cur = node
                while cur != nxt:
                    parent_idx = parent_edge.get(cur)
                    if parent_idx is None:
                        break
                    cycle_edges.append(parent_idx)
                    parent = parent_node.get(cur)
                    if parent is None:
                        break
                    cur = parent
                return cycle_edges
    return None


def _edge_confidence(edge: CausalEdge) -> float:
    if edge.combined_confidence is not None:
        return float(edge.combined_confidence)
    for candidate in (
        edge.data_confidence,
        edge.literature_confidence,
        edge.llm_confidence,
    ):
        if candidate is not None:
            return float(candidate)
    return 0.0


def _break_cycles(
    edges: list[CausalEdge],
    *,
    max_lag_depth: int = MAX_LAG_DEPTH,
    max_lagged_edges: int = MAX_LAGGED_EDGES,
    max_cycles_to_resolve: int = MAX_CYCLES_TO_RESOLVE,
) -> tuple[list[CausalEdge], list[str]]:
    working = [edge.model_copy(deep=True) for edge in edges]
    warnings: list[str] = []
    lagged_edges = 0
    resolved_cycles = 0
    overflow_warned = False

    while True:
        cycle = _find_cycle(working)
        if cycle is None:
            break
        idx = min(cycle, key=lambda item: _edge_confidence(working[item]))
        target = working[idx]

        if resolved_cycles >= max_cycles_to_resolve:
            if not overflow_warned:
                warnings.append(
                    "Cycle resolution budget exceeded; switching to fallback edge removals."
                )
                overflow_warned = True
            removed = working.pop(idx)
            warnings.append(
                f"Removed edge {removed.src}->{removed.dst} during cycle fallback removal."
            )
            continue

        resolved_cycles += 1
        source_tags = {
            tag.strip().lower()
            for tag in _coerce_source_tags(target.metadata.get("source_method_tags"))
        }
        current_lag = int(target.lag or 0)
        if "time-series" in source_tags:
            removed = working.pop(idx)
            warnings.append(
                f"Skipped lagging for time-series edge {removed.src}->{removed.dst}; removed edge instead."
            )
            continue

        if current_lag >= max_lag_depth or lagged_edges >= max_lagged_edges:
            removed = working.pop(idx)
            warnings.append(
                f"Removed edge {removed.src}->{removed.dst} because lag constraints were exhausted."
            )
            continue

        new_lag = current_lag + 1
        lagged_edges += 1
        updated_metadata = dict(target.metadata)
        updated_metadata["lagged_src"] = f"{target.src}_t-{new_lag}"
        updated_metadata["cycle_resolved_via_lag"] = True
        working[idx] = target.model_copy(
            update={
                "src": f"{target.src}_t-{new_lag}",
                "lag": new_lag,
                "metadata": updated_metadata,
            }
        )

    return working, warnings


def _connected_components(nodes: list[str], edges: list[CausalEdge]) -> list[list[str]]:
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    for edge in edges:
        adjacency.setdefault(edge.src, set()).add(edge.dst)
        adjacency.setdefault(edge.dst, set()).add(edge.src)
    visited: set[str] = set()
    components: list[list[str]] = []
    for node in nodes:
        if node in visited:
            continue
        stack = [node]
        component: list[str] = []
        visited.add(node)
        while stack:
            cur = stack.pop()
            component.append(cur)
            for nxt in adjacency.get(cur, set()):
                if nxt in visited:
                    continue
                visited.add(nxt)
                stack.append(nxt)
        components.append(sorted(component))
    return components


def _triangle_coefficients(
    *,
    a: str,
    b: str,
    c: str,
    edge_lookup: dict[tuple[str, str], int],
) -> list[tuple[int, float]] | None:
    row: list[tuple[int, float]] = []

    if (a, b) in edge_lookup:
        row.append((edge_lookup[(a, b)], 1.0))
    elif (b, a) in edge_lookup:
        row.append((edge_lookup[(b, a)], -1.0))
    else:
        return None

    if (b, c) in edge_lookup:
        row.append((edge_lookup[(b, c)], 1.0))
    elif (c, b) in edge_lookup:
        row.append((edge_lookup[(c, b)], -1.0))
    else:
        return None

    if (a, c) in edge_lookup:
        row.append((edge_lookup[(a, c)], -1.0))
    elif (c, a) in edge_lookup:
        row.append((edge_lookup[(c, a)], 1.0))
    else:
        return None

    return row


def compute_reconciliation_diagnostics(
    edges: list[CausalEdge],
    *,
    max_recon_sources: int = MAX_RECON_SOURCES,
    max_recon_edges: int = MAX_RECON_EDGES,
    max_triangles: int = MAX_TRIANGLES,
    triangle_budget_ms: int = TRIANGLE_BUDGET_MS,
) -> ReconciliationDiagnostics:
    """Summarize where merged causal graphs disagree before downstream reconciliation audits."""
    if not edges:
        return ReconciliationDiagnostics()

    source_labels: set[str] = set()
    for edge in edges:
        source_labels |= {source.value for source in edge.sources}
        source_labels |= set(_coerce_source_tags(edge.metadata.get("source_method_tags")))

    diagnostics_truncated = False
    truncation_reasons: list[str] = []

    sampled_edges = list(edges)
    if len(sampled_edges) > max_recon_edges:
        diagnostics_truncated = True
        truncation_reasons.append("max_recon_edges_exceeded")
        sampled_edges = sorted(
            sampled_edges,
            key=lambda edge: _edge_confidence(edge),
            reverse=True,
        )[:max_recon_edges]

    if len(source_labels) > max_recon_sources:
        diagnostics_truncated = True
        truncation_reasons.append("max_recon_sources_exceeded")

    nodes = sorted({edge.src for edge in sampled_edges} | {edge.dst for edge in sampled_edges})
    node_index = {node: idx for idx, node in enumerate(nodes)}
    n_edges = len(sampled_edges)
    n_nodes = len(nodes)
    alpha = np.asarray([_edge_confidence(edge) for edge in sampled_edges], dtype=float)

    d0 = np.zeros((n_edges, n_nodes), dtype=float)
    for row, edge in enumerate(sampled_edges):
        d0[row, node_index[edge.src]] = -1.0
        d0[row, node_index[edge.dst]] = 1.0
    delta0 = d0.T

    components = _connected_components(nodes, sampled_edges)
    pin_rows = np.zeros((len(components), n_nodes), dtype=float)
    for idx, component in enumerate(components):
        if component:
            pin_rows[idx, node_index[component[0]]] = 1.0

    a_aug = np.vstack([d0, pin_rows]) if len(components) else d0
    b_aug = (
        np.concatenate([alpha, np.zeros(len(components), dtype=float)])
        if len(components)
        else alpha
    )

    try:
        phi, *_ = np.linalg.lstsq(a_aug, b_aug, rcond=None)
    except np.linalg.LinAlgError:
        ata = (a_aug.T @ a_aug) + (RIDGE_EPSILON * np.eye(n_nodes))
        atb = a_aug.T @ b_aug
        phi = np.linalg.solve(ata, atb)

    gradient = d0 @ phi
    residual = alpha - gradient

    undirected_neighbors: dict[str, set[str]] = {node: set() for node in nodes}
    edge_lookup: dict[tuple[str, str], int] = {}
    for idx, edge in enumerate(sampled_edges):
        if edge.lag not in (None, 0):
            continue
        undirected_neighbors[edge.src].add(edge.dst)
        undirected_neighbors[edge.dst].add(edge.src)
        current_idx = edge_lookup.get((edge.src, edge.dst))
        if current_idx is None or _edge_confidence(sampled_edges[current_idx]) < _edge_confidence(
            edge
        ):
            edge_lookup[(edge.src, edge.dst)] = idx

    triangle_rows: list[list[tuple[int, float]]] = []
    triangle_values: list[float] = []
    tri_start = time.perf_counter()
    stop_triangles = False

    for a in nodes:
        if stop_triangles:
            break
        for b in sorted(undirected_neighbors[a]):
            if b <= a:
                continue
            common = undirected_neighbors[a].intersection(undirected_neighbors[b])
            for c in sorted(common):
                if c <= b:
                    continue
                elapsed_ms = (time.perf_counter() - tri_start) * 1000.0
                if elapsed_ms > float(triangle_budget_ms):
                    diagnostics_truncated = True
                    truncation_reasons.append("triangle_budget_ms_exceeded")
                    stop_triangles = True
                    break
                if len(triangle_rows) >= max_triangles:
                    diagnostics_truncated = True
                    truncation_reasons.append("max_triangles_exceeded")
                    stop_triangles = True
                    break
                row = _triangle_coefficients(a=a, b=b, c=c, edge_lookup=edge_lookup)
                if row is None:
                    continue
                value = 0.0
                for edge_idx, coeff in row:
                    value += coeff * alpha[edge_idx]
                triangle_rows.append(row)
                triangle_values.append(value)

    n_triangles = len(triangle_rows)
    d1_shape = (n_triangles, n_edges)
    delta1_shape = (n_edges, n_triangles)
    curl_component = np.zeros(n_edges, dtype=float)
    delta1_dense: np.ndarray | None = None

    if triangle_rows:
        dense_budget = n_edges * n_triangles
        if dense_budget <= 2_000_000:
            d1 = np.zeros((n_triangles, n_edges), dtype=float)
            for row_idx, row in enumerate(triangle_rows):
                for edge_idx, coeff in row:
                    d1[row_idx, edge_idx] = coeff
            delta1_dense = d1.T
            rhs = d1 @ residual
            lhs = d1 @ delta1_dense
            if lhs.size > 0:
                lhs = lhs + (RIDGE_EPSILON * np.eye(lhs.shape[0]))
                try:
                    beta = np.linalg.solve(lhs, rhs)
                except np.linalg.LinAlgError:
                    beta, *_ = np.linalg.lstsq(lhs, rhs, rcond=None)
                curl_component = delta1_dense @ beta
            operators_d1: Any = d1.tolist() if dense_budget <= 4096 else {"omitted": True}
            operators_delta1: Any = (
                delta1_dense.tolist() if dense_budget <= 4096 else {"omitted": True}
            )
        else:
            diagnostics_truncated = True
            truncation_reasons.append("d1_dense_budget_exceeded")
            counts = np.zeros(n_edges, dtype=float)
            for value, row in zip(triangle_values, triangle_rows, strict=False):
                for edge_idx, coeff in row:
                    curl_component[edge_idx] += coeff * value / 3.0
                    counts[edge_idx] += 1.0
            mask = counts > 0
            curl_component[mask] = curl_component[mask] / counts[mask]
            operators_d1 = {"omitted": True}
            operators_delta1 = {"omitted": True}
    else:
        operators_d1 = []
        operators_delta1 = []

    harmonic = residual - curl_component
    cyclic_inconsistency_norm = float(
        np.linalg.norm(np.asarray(triangle_values, dtype=float))
    ) / max(1.0, float(np.sqrt(max(1, len(triangle_values)))))
    gradient_norm = float(np.linalg.norm(gradient)) / max(1.0, float(np.sqrt(max(1, n_edges))))
    curl_norm = float(np.linalg.norm(curl_component)) / max(1.0, float(np.sqrt(max(1, n_edges))))
    harmonic_norm = float(np.linalg.norm(harmonic)) / max(1.0, float(np.sqrt(max(1, n_edges))))

    disagreement_edges = sum(
        1
        for edge in sampled_edges
        if bool(edge.metadata.get("llm_disagreement"))
        or bool(edge.metadata.get("direction_conflict"))
    )
    disagreement_ratio = float(disagreement_edges) / max(1.0, float(len(sampled_edges)))
    irreducible_conflict_norm = max(harmonic_norm, disagreement_ratio)

    operators: dict[str, Any] = {
        "D0": d0.tolist() if (n_edges * n_nodes) <= 4096 else {"omitted": True},
        "D1": operators_d1,
        "delta^0": delta0.tolist() if (n_edges * n_nodes) <= 4096 else {"omitted": True},
        "delta^1": operators_delta1,
    }

    truncation_reason = None
    if diagnostics_truncated:
        truncation_reason = ",".join(sorted(set(truncation_reasons)))

    return ReconciliationDiagnostics(
        cyclic_inconsistency_norm=cyclic_inconsistency_norm,
        irreducible_conflict_norm=irreducible_conflict_norm,
        gradient_norm=gradient_norm,
        curl_norm=curl_norm,
        harmonic_norm=harmonic_norm,
        diagnostics_truncated=diagnostics_truncated,
        truncation_reason=truncation_reason,
        d0_shape=(n_edges, n_nodes),
        d1_shape=d1_shape,
        delta0_shape=(n_nodes, n_edges),
        delta1_shape=delta1_shape,
        n_components=len(components),
        n_sources=len(source_labels),
        n_edges=n_edges,
        n_triangles=n_triangles,
        operators=operators,
    )


@foundry_method(
    namespace="causal.prior",
    version="1.0.0",
    tags={"causal", "prior", "reconciliation"},
)
class ReconcileCausalGraph:
    """Merge data/literature/LLM priors into a reconciled causal graph."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="reconcile_causal_graph",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="graph_reconciliation_data",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("request", "json"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="reconciled_graph",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("artifact", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="min_edge_confidence", default=0.1),
            ParameterSpec(name="max_lag_depth", default=MAX_LAG_DEPTH),
            ParameterSpec(name="max_lagged_edges", default=MAX_LAGGED_EDGES),
            ParameterSpec(name="max_cycles_to_resolve", default=MAX_CYCLES_TO_RESOLVE),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Reconcile causal graph from data graph, literature priors, and LLM hints.",
        tags=frozenset({"causal", "prior", "reconciliation"}),
        assumptions={
            "merge_policy": "LITERATURE_FIRST with data override on directional conflicts.",
            "llm_calibration": "LLM hints are capped and discounted against existing evidence.",
            "cycle_handling": "Cycles are resolved via lagging first, removal as fallback.",
        },
        when_to_use="Merge data-driven causal discovery with literature priors and LLM structural hints; build reconciled DAG for SCM fitting",
        citations=(
            "Triantafillou, S. & Tsamardinos, I. (2015). Constraint-based causal discovery from multiple interventions over overlapping variable sets. JMLR, 16, 2147-2205.",
        ),
        when_not_to_use="Purely data-driven discovery without prior knowledge; single evidence source only",
        output_interpretation="Reconciled DAG with combined edge confidences. Diagnostics: cyclic inconsistency norm and irreducible conflict norm indicate evidence quality. needs_expert_review flag triggers human review.",
    )

    @staticmethod
    def pure_step(
        state: GraphReconciliationData | Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload = (
            state
            if isinstance(state, GraphReconciliationData)
            else GraphReconciliationData.model_validate(state)
        )
        min_edge_confidence = float(params.get("min_edge_confidence", payload.min_edge_confidence))
        max_lag_depth = int(params.get("max_lag_depth", payload.max_lag_depth))
        max_lagged_edges = int(params.get("max_lagged_edges", payload.max_lagged_edges))
        max_cycles_to_resolve = int(
            params.get("max_cycles_to_resolve", payload.max_cycles_to_resolve)
        )

        warnings: list[str] = []
        merged: dict[tuple[str, str, int], _MergedEdge] = {}

        _add_literature_edges(
            merged=merged,
            prior=payload.literature_prior,
            min_edge_confidence=min_edge_confidence,
        )
        _add_data_edges(merged=merged, data_graph=payload.data_graph, warnings=warnings)
        _add_llm_hints(merged=merged, llm_hints=payload.llm_hints, warnings=warnings)

        materialized = _materialize_edges(merged=merged, min_edge_confidence=min_edge_confidence)
        resolved_edges, cycle_warnings = _break_cycles(
            materialized,
            max_lag_depth=max_lag_depth,
            max_lagged_edges=max_lagged_edges,
            max_cycles_to_resolve=max_cycles_to_resolve,
        )
        warnings.extend(cycle_warnings)

        diagnostics = compute_reconciliation_diagnostics(resolved_edges)
        needs_expert_review = diagnostics.irreducible_conflict_norm > 0.5

        node_set = set(payload.data_graph.nodes)
        node_set |= {edge.src for edge in resolved_edges}
        node_set |= {edge.dst for edge in resolved_edges}
        metadata = dict(payload.data_graph.metadata)
        metadata.update(
            {
                "reconciliation_warnings": warnings,
                "reconciliation_diagnostics": diagnostics.model_dump(mode="json"),
                "needs_expert_review": needs_expert_review,
                "llm_prior_constants": {
                    "LLM_PRIOR_CEILING": LLM_PRIOR_CEILING,
                    "LLM_OVERLAP_DISCOUNT": LLM_OVERLAP_DISCOUNT,
                    "LLM_REPLICATION_BONUS": LLM_REPLICATION_BONUS,
                },
            }
        )

        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=sorted(node_set),
            edges=resolved_edges,
            discovery_method="reconciled_prior_graph",
            skg_version_id=(
                payload.literature_prior.skg_version_id
                if payload.literature_prior is not None
                else None
            ),
            metadata=metadata,
        )
        return {
            "reconciled_graph": graph,
            "diagnostics": diagnostics,
            "needs_expert_review": needs_expert_review,
            "warnings": warnings,
        }


def _composition_edge_key(edge: CausalEdge) -> tuple[str, str, str, str, int]:
    return (
        edge.src,
        edge.dst,
        edge.mark_src.value,
        edge.mark_dst.value,
        int(edge.lag or 0),
    )


def _merge_composed_edge(existing: CausalEdge | None, incoming: CausalEdge) -> CausalEdge:
    if existing is None:
        combined = (
            incoming.compute_combined_confidence()
            if incoming.sources
            else incoming.combined_confidence
        )
        return incoming.model_copy(update={"combined_confidence": combined})

    metadata = {**existing.metadata, **incoming.metadata}
    contributing_fragment_ids = sorted(_edge_fragment_ids(existing) | _edge_fragment_ids(incoming))
    if contributing_fragment_ids:
        metadata["contributing_fragment_ids"] = contributing_fragment_ids

    merged = CausalEdge(
        src=existing.src,
        dst=existing.dst,
        mark_src=existing.mark_src,
        mark_dst=existing.mark_dst,
        lag=existing.lag,
        sources=sorted(set(existing.sources) | set(incoming.sources), key=lambda item: item.value),
        data_confidence=max(
            value
            for value in (existing.data_confidence, incoming.data_confidence)
            if value is not None
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
            value
            for value in (existing.llm_confidence, incoming.llm_confidence)
            if value is not None
        )
        if any(value is not None for value in (existing.llm_confidence, incoming.llm_confidence))
        else None,
        expert_confidence=max(
            value
            for value in (existing.expert_confidence, incoming.expert_confidence)
            if value is not None
        )
        if any(
            value is not None for value in (existing.expert_confidence, incoming.expert_confidence)
        )
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
        unsupported_by_evidence=existing.unsupported_by_evidence
        and incoming.unsupported_by_evidence,
        evidence_refs=sorted(set(existing.evidence_refs) | set(incoming.evidence_refs)),
        metadata=metadata,
    )
    combined_confidence = (
        merged.compute_combined_confidence()
        if merged.sources
        else max(
            value
            for value in (existing.combined_confidence, incoming.combined_confidence)
            if value is not None
        )
        if any(
            value is not None
            for value in (existing.combined_confidence, incoming.combined_confidence)
        )
        else None
    )
    return merged.model_copy(update={"combined_confidence": combined_confidence})


def _directed_cycle_present(edges: list[CausalEdge]) -> bool:
    adjacency: dict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set()
    for edge in edges:
        if edge.mark_src is not EdgeMark.TAIL or edge.mark_dst is not EdgeMark.ARROW:
            continue
        if edge.lag not in (None, 0):
            continue
        adjacency[edge.src].add(edge.dst)
        nodes.add(edge.src)
        nodes.add(edge.dst)

    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> bool:
        if node in active:
            return True
        if node in visited:
            return False
        visited.add(node)
        active.add(node)
        for nxt in sorted(adjacency.get(node, set())):
            if visit(nxt):
                return True
        active.remove(node)
        return False

    for node in sorted(nodes):
        if visit(node):
            return True
    return False


def _allowed_graph_types(graphs: dict[str, CausalGraphModel]) -> GraphType:
    return (
        GraphType.ADMG
        if any(graph.graph_type is GraphType.ADMG for graph in graphs.values())
        else GraphType.DAG
    )


def _structural_assumptions_for_composition(
    graph_type: GraphType,
    *,
    allow_cycle_aware_sigma: bool = False,
) -> list[str]:
    assumptions = [
        "observed_interface_stitching_only",
        "namespace_non_interface_nodes_by_fragment",
        "stable_fragment_id_fold_order",
    ]
    if graph_type is GraphType.ADMG:
        assumptions.append(
            "cycle_aware_sigma_view"
            if allow_cycle_aware_sigma
            else "admg_directed_component_acyclic"
        )
    return assumptions


def _dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        token = str(value).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        output.append(token)
    return output


@foundry_method(
    namespace="causal.composition",
    version="1.0.0",
    tags={"causal", "composition", "scm"},
)
class ComposeSCMFragments:
    """Strictly compose verified SCM fragments into a single DAG/ADMG."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="compose_scm_fragments",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="fragment_composition_data",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("request", "json"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="composed_graph",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("artifact", "json"),
                )
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Strictly compose verified SCM fragments into a single DAG/ADMG, including declared internal cyclic SCCs.",
        tags=frozenset({"causal", "composition", "scm"}),
        assumptions={
            "alignment": "Only verified interface mappings are used to stitch fragments.",
            "structure": "Composition rejects unsupported cross-fragment cycles and only accepts declared internal cyclic SCCs with auditable witnesses.",
            "repair": "No lagging, removal, or latent synthesis fallback is attempted.",
        },
        when_to_use="Compose SCM fragments after semantic alignment has already been verified.",
        citations=(
            "Pearl, J. (2009). Causality: Models, Reasoning, and Inference. Cambridge University Press.",
            "Bareinboim, E. & Pearl, J. (2016). Causal inference and the data-fusion problem. PNAS, 113(27), 7345-7352.",
        ),
        when_not_to_use="Use legacy prior reconciliation for data/literature/LLM edge fusion or any graph repair workflow.",
        output_interpretation="Returns composed_graph when structure is preserved and a CompositionCertificate describing preserved, deferred, or broken status, including cycle-contract metadata for feedback loops.",
    )

    @staticmethod
    def pure_step(
        state: FragmentCompositionData | Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload = (
            state
            if isinstance(state, FragmentCompositionData)
            else FragmentCompositionData.model_validate(state)
        )
        declared_cycle_semantics = _fragments_declare_cycles(payload.fragments)
        cycle_semantics_mode = _cycle_semantics_mode(payload.fragments)
        graph_type = _effective_composition_graph_type(payload.fragment_graphs, payload.fragments)
        structural_assumptions = _structural_assumptions_for_composition(
            graph_type,
            allow_cycle_aware_sigma=declared_cycle_semantics
            and cycle_semantics_mode == "sigma_separation",
        )
        warnings = list(payload.alignment_report.ontology_mismatch_warnings)
        blocking_reasons: list[str] = []
        needs_expert_review = False
        selected_stitch_pairs = [
            tuple(pair)
            for pair in payload.alignment_report.metadata.get("selected_stitch_pairs", [])
            if isinstance(pair, (list, tuple)) and len(pair) == 2
        ]
        disconnected_fragment_ids = [
            str(fragment_id)
            for fragment_id in payload.alignment_report.metadata.get(
                "disconnected_fragment_ids", []
            )
            if str(fragment_id).strip()
        ]
        boundary_interface_variables = dict(
            payload.alignment_report.metadata.get("boundary_interface_variables", {})
        )
        if payload.direct_stitch_pairs:
            expected_pairs = sorted(
                tuple(sorted((str(left), str(right))))
                for left, right in payload.direct_stitch_pairs
            )
            observed_pairs = sorted(
                tuple(sorted((str(left), str(right)))) for left, right in selected_stitch_pairs
            )
            if observed_pairs and observed_pairs != expected_pairs:
                blocking_reasons.append(
                    "Alignment topology does not match requested direct stitch pairs."
                )

        if payload.alignment_report.overall_status is AlignmentOverallStatus.INCOMPATIBLE:
            if payload.alignment_report.incompatible_pairs:
                for left, right in payload.alignment_report.incompatible_pairs:
                    blocking_reasons.append(
                        f"Incompatible interface pair blocks composition: {left} <-> {right}."
                    )
            elif disconnected_fragment_ids:
                blocking_reasons.append(
                    "Fragment stitch topology is disconnected and cannot produce one composed bundle."
                )
            else:
                blocking_reasons.append("Alignment report contains incompatible interface pairs.")
        if disconnected_fragment_ids:
            for fragment_id in disconnected_fragment_ids:
                blocking_reasons.append(
                    f"Fragment {fragment_id} has no admissible stitch partner in the selected topology."
                )
        if (
            len(payload.fragments) > 1
            and not payload.interface_mapping.entries
            and not blocking_reasons
        ):
            blocking_reasons.append("Missing alignment coverage for fragment composition.")

        binding_to_node: dict[tuple[str, str], str] = {}
        for entry in payload.interface_mapping.entries:
            if not entry.observed:
                blocking_reasons.append(
                    f"Interface {entry.interface_id} contains unobserved bindings and cannot be composed."
                )
            if entry.alignment_type == AlignmentType.INCOMPATIBLE.value:
                blocking_reasons.append(
                    f"Interface {entry.interface_id} is marked incompatible and cannot be composed."
                )
            if entry.reviewer == AlignmentReviewerState.PENDING_REVIEW.value:
                needs_expert_review = True
            for binding in entry.bindings:
                binding_to_node[(binding.fragment_id, binding.variable_name)] = (
                    entry.canonical_node_id
                )

        for certificate in payload.alignment_report.per_variable_certificates:
            if certificate.reviewer is AlignmentReviewerState.PENDING_REVIEW:
                needs_expert_review = True

        for _frag in payload.fragments:
            for _var_name in sorted(_frag.latent_summary):
                if _var_name in _frag.interface_variables:
                    needs_expert_review = True
                    blocking_reasons.append(f"unobserved interface variable: {_var_name}")

        (
            cycle_blocking_reasons,
            cycle_review_required,
            cycle_assumptions,
            cycle_contracts,
        ) = _evaluate_fragment_cycle_contracts(payload)
        blocking_reasons.extend(cycle_blocking_reasons)
        needs_expert_review = needs_expert_review or cycle_review_required
        structural_assumptions = _dedupe_preserve([*structural_assumptions, *cycle_assumptions])

        structure_status = "valid"
        composed_graph: CausalGraphModel | None = None
        # Always attempt structural composition; only graph-level structural violations (cycles,
        # bad edge marks, self-loops) prevent graph assembly here.  Alignment / topology blocking
        # reasons mark the certificate broken/deferred but do not suppress the composed graph —
        # that decision is made by the caller (e.g. ReconcileCausalGraphNode) based on certificate
        # status.
        merged_edges: dict[tuple[str, str, str, str, int], CausalEdge] = {}
        node_set: set[str] = set()
        structural_violations: list[str] = []
        for fragment in sorted(payload.fragments, key=lambda item: item.fragment_id):
            graph = payload.fragment_graphs[fragment.fragment_id]
            node_map: dict[str, str] = {}
            for node in graph.nodes:
                mapped_node = binding_to_node.get((fragment.fragment_id, node))
                node_map[node] = mapped_node or f"{fragment.fragment_id}::{node}"
                node_set.add(node_map[node])

            for edge in graph.edges:
                edge_metadata = dict(edge.metadata)
                contributing_fragment_ids = {
                    fragment.fragment_id,
                    *(
                        str(item)
                        for item in edge_metadata.get("contributing_fragment_ids", [])
                        if str(item).strip()
                    ),
                }
                edge_metadata["contributing_fragment_ids"] = sorted(contributing_fragment_ids)
                remapped = edge.model_copy(
                    update={
                        "src": node_map[edge.src],
                        "dst": node_map[edge.dst],
                        "metadata": edge_metadata,
                    }
                )
                if remapped.src == remapped.dst:
                    structural_violations.append(
                        f"Composition collapsed {fragment.fragment_id}:{edge.src}->{edge.dst} into a self-loop."
                    )
                    continue
                edge_key = _composition_edge_key(remapped)
                merged_edges[edge_key] = _merge_composed_edge(merged_edges.get(edge_key), remapped)

        merged_edge_list = [merged_edges[key] for key in sorted(merged_edges)]
        if graph_type is GraphType.DAG and any(
            edge.mark_src is not EdgeMark.TAIL or edge.mark_dst is not EdgeMark.ARROW
            for edge in merged_edge_list
        ):
            structural_violations.append("DAG composition produced non-directed edges.")
        if graph_type is GraphType.ADMG and any(
            (edge.mark_src, edge.mark_dst)
            not in {
                (EdgeMark.TAIL, EdgeMark.ARROW),
                (EdgeMark.ARROW, EdgeMark.ARROW),
            }
            for edge in merged_edge_list
        ):
            structural_violations.append(
                "ADMG composition produced unsupported edge endpoint marks."
            )
        directed_cycle_present = _directed_cycle_present(merged_edge_list)
        cross_fragment_cycle_components = (
            _cross_fragment_cycle_components(node_set, merged_edge_list)
            if directed_cycle_present
            else []
        )
        if cross_fragment_cycle_components:
            summary = ", ".join(
                f"{'/'.join(item['fragment_ids'])} via {','.join(item['nodes'])}"
                for item in cross_fragment_cycle_components
            )
            structural_violations.append(
                f"Fragment composition introduces a cross-fragment directed cycle SCC: {summary}."
            )
        elif directed_cycle_present and not declared_cycle_semantics:
            structural_violations.append("Fragment composition introduces a directed cycle.")
        elif directed_cycle_present and cycle_semantics_mode != "sigma_separation":
            structural_violations.append(
                "Fragment composition introduces a directed cycle without a sigma-separation-capable cycle contract."
            )
        elif directed_cycle_present:
            structural_assumptions = _dedupe_preserve(
                [*structural_assumptions, "internal_scc_condensation_acyclic"]
            )

        blocking_reasons.extend(structural_violations)

        if not structural_violations:
            composed_graph = CausalGraphModel(
                graph_type=graph_type,
                nodes=sorted(node_set),
                edges=merged_edge_list,
                discovery_method="scm_fragment_composition",
                metadata={
                    "source_fragment_ids": sorted(
                        fragment.fragment_id for fragment in payload.fragments
                    ),
                    "interface_mapping_entry_ids": [
                        entry.interface_id for entry in payload.interface_mapping.entries
                    ],
                    "cycle_contracts": cycle_contracts,
                    "cycle_semantics_mode": cycle_semantics_mode,
                    "directed_cycle_present": directed_cycle_present,
                    "cross_fragment_cycle_components": cross_fragment_cycle_components,
                    "supported_cycle_fragment_ids": sorted(
                        fragment.fragment_id
                        for fragment in payload.fragments
                        if _fragment_supports_cycle_aware_composition(fragment)
                    ),
                },
            )

        if blocking_reasons:
            structure_status = "invalid"

        review_status = (
            "pending_review"
            if (
                needs_expert_review
                or payload.alignment_report.review_status is AlignmentReviewStatus.PENDING_REVIEW
            )
            else "clear"
        )
        certificate_status = (
            "broken"
            if structure_status == "invalid"
            else "deferred"
            if review_status == "pending_review"
            else "preserved"
        )

        completeness_fields = completeness_scope_for_composition(
            graph_type_value=graph_type.value,
            alignment_types=[entry.alignment_type for entry in payload.interface_mapping.entries],
            binding_observed_flags=[entry.observed for entry in payload.interface_mapping.entries],
            reviewers=[entry.reviewer for entry in payload.interface_mapping.entries],
            review_status=review_status,
            structure_status=structure_status,
            cycle_semantics_mode=cycle_semantics_mode,
            directed_cycle_present=directed_cycle_present,
        )

        certificate = CompositionCertificate(
            structure_status=structure_status,
            review_status=review_status,
            status=certificate_status,
            composed_graph_ref=None,
            interface_mapping_ref=str(
                payload.metadata.get("interface_mapping_ref", "pending://interface_mapping")
            ),
            alignment_report_ref=str(
                payload.metadata.get("alignment_report_ref", "pending://alignment_report")
            ),
            checked_queries={},
            newly_required_assumptions=_dedupe_preserve(
                [*structural_assumptions, *payload.alignment_report.alignment_assumptions]
            ),
            structural_assumptions=structural_assumptions,
            alignment_assumptions=list(payload.alignment_report.alignment_assumptions),
            source_fragment_refs=dict(sorted(payload.source_fragment_refs.items())),
            source_fragment_graph_refs=dict(sorted(payload.source_fragment_graph_refs.items())),
            failure_card_bundle_ref=None,
            blocking_reasons=_dedupe_preserve(blocking_reasons),
            metadata={
                "graph_type": graph_type.value,
                "source_fragment_ids": sorted(
                    fragment.fragment_id for fragment in payload.fragments
                ),
                "incompatible_pairs": [
                    list(pair) for pair in payload.alignment_report.incompatible_pairs
                ],
                "selected_stitch_pairs": [list(pair) for pair in selected_stitch_pairs],
                "boundary_interface_variables": boundary_interface_variables,
                "disconnected_fragment_ids": disconnected_fragment_ids,
                "cycle_contracts": cycle_contracts,
                "cycle_semantics_mode": cycle_semantics_mode,
                "directed_cycle_present": directed_cycle_present,
                "cross_fragment_cycle_components": cross_fragment_cycle_components,
                "supported_cycle_fragment_ids": sorted(
                    fragment.fragment_id
                    for fragment in payload.fragments
                    if _fragment_supports_cycle_aware_composition(fragment)
                ),
                **completeness_fields,
            },
        )
        failure_cards = build_composition_failure_cards(
            alignment_report=payload.alignment_report,
            interface_mapping=payload.interface_mapping,
            composition_certificate=certificate,
        )

        return {
            "composed_graph": composed_graph,
            "composition_certificate": certificate,
            "needs_expert_review": needs_expert_review,
            "blocking_reasons": _dedupe_preserve(blocking_reasons),
            "warnings": _dedupe_preserve(warnings),
            "failure_cards": failure_cards,
        }


__all__ = [
    "LLM_OVERLAP_DISCOUNT",
    "LLM_PRIOR_CEILING",
    "LLM_REPLICATION_BONUS",
    "MAX_CYCLES_TO_RESOLVE",
    "MAX_LAGGED_EDGES",
    "MAX_LAG_DEPTH",
    "MAX_RECON_EDGES",
    "MAX_RECON_SOURCES",
    "MAX_TRIANGLES",
    "TRIANGLE_BUDGET_MS",
    "ComposeSCMFragments",
    "ReconcileCausalGraph",
    "compute_reconciliation_diagnostics",
]
