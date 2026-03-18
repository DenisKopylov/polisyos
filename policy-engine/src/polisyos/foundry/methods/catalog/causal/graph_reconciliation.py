from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
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
from polisyos.foundry.methods.catalog.causal.protocols import (
    GraphReconciliationData,
    LLMStructuralHint,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeSource, GraphType
from polisyos.ir.analytics.literature import (
    LiteratureCausalPrior,
    LiteratureEdgePrior,
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
        current.metadata.setdefault("evidence_strength", edge.evidence_strength.value)
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
    color: dict[str, int] = {node: 0 for node in nodes}  # 0=unseen, 1=active, 2=done
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
        source_tags = {tag.strip().lower() for tag in _coerce_source_tags(target.metadata.get("source_method_tags"))}
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
    b_aug = np.concatenate([alpha, np.zeros(len(components), dtype=float)]) if len(components) else alpha

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
        if current_idx is None or _edge_confidence(sampled_edges[current_idx]) < _edge_confidence(edge):
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
    cyclic_inconsistency_norm = (
        float(np.linalg.norm(np.asarray(triangle_values, dtype=float)))
        / max(1.0, float(np.sqrt(max(1, len(triangle_values)))))
    )
    gradient_norm = float(np.linalg.norm(gradient)) / max(1.0, float(np.sqrt(max(1, n_edges))))
    curl_norm = float(np.linalg.norm(curl_component)) / max(1.0, float(np.sqrt(max(1, n_edges))))
    harmonic_norm = float(np.linalg.norm(harmonic)) / max(1.0, float(np.sqrt(max(1, n_edges))))

    disagreement_edges = sum(
        1
        for edge in sampled_edges
        if bool(edge.metadata.get("llm_disagreement")) or bool(edge.metadata.get("direction_conflict"))
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
        namespace="placeholder",
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
                payload.literature_prior.skg_version_id if payload.literature_prior is not None else None
            ),
            metadata=metadata,
        )
        return {
            "reconciled_graph": graph,
            "diagnostics": diagnostics,
            "needs_expert_review": needs_expert_review,
            "warnings": warnings,
        }


__all__ = [
    "LLM_PRIOR_CEILING",
    "LLM_OVERLAP_DISCOUNT",
    "LLM_REPLICATION_BONUS",
    "MAX_LAG_DEPTH",
    "MAX_LAGGED_EDGES",
    "MAX_CYCLES_TO_RESOLVE",
    "MAX_RECON_SOURCES",
    "MAX_RECON_EDGES",
    "MAX_TRIANGLES",
    "TRIANGLE_BUDGET_MS",
    "compute_reconciliation_diagnostics",
    "ReconcileCausalGraph",
]
