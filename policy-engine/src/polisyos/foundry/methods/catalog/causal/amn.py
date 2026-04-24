"""AMN (Ancestral Multi-world Network) derived graph builder."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from itertools import combinations
from typing import Any

from pydantic import BaseModel, ConfigDict

from polisyos.foundry.methods.catalog.causal.admg_ops import m_separation
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType


class AMNMetadata(BaseModel):
    """Metadata describing a derived AMN view over a base graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    worlds: list[str]
    world_partition: dict[str, list[str]]
    counterfactual_interventions: dict[str, dict[str, float]]
    bridge_edges: list[tuple[str, str]]


def _source_graph_hash(graph: CausalGraphModel) -> str:
    payload = graph.model_dump(mode="json")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _infer_shared_exogenous(graph: CausalGraphModel) -> list[str]:
    node_set = set(graph.nodes)
    candidates: Any = (
        graph.metadata.get("shared_exogenous")
        or graph.metadata.get("exogenous_nodes")
        or graph.metadata.get("exogenous_vars")
    )
    if isinstance(candidates, Iterable) and not isinstance(candidates, (str, bytes)):
        exogenous = [str(v) for v in candidates if str(v) in node_set]
        if exogenous:
            return sorted(set(exogenous))
    return sorted(n for n in graph.nodes if n.startswith("U_"))


def _world_node(node: str, world: str, shared_exogenous: set[str]) -> str:
    if node in shared_exogenous:
        return node
    return f"{node}__{world}"


def build_amn(
    graph: CausalGraphModel,
    interventions: dict[str, dict[str, float]],
) -> tuple[CausalGraphModel, AMNMetadata]:
    """Build a derived AMN graph and metadata for multi-world counterfactuals."""
    if interventions:
        worlds = sorted(interventions)
    else:
        worlds = ["w0"]
        interventions = {"w0": {}}

    shared_exogenous = set(_infer_shared_exogenous(graph))
    amn_nodes: list[str] = []
    world_partition: dict[str, list[str]] = {}
    for world in worlds:
        world_nodes: list[str] = []
        for node in graph.nodes:
            if node in shared_exogenous:
                if node not in amn_nodes:
                    amn_nodes.append(node)
                continue
            world_node = f"{node}__{world}"
            amn_nodes.append(world_node)
            world_nodes.append(world_node)
        world_partition[world] = world_nodes

    seen: set[tuple[Any, ...]] = set()
    amn_edges: list[CausalEdge] = []
    for world in worlds:
        for edge in graph.edges:
            src = _world_node(edge.src, world, shared_exogenous)
            dst = _world_node(edge.dst, world, shared_exogenous)
            key = (
                src,
                dst,
                edge.mark_src,
                edge.mark_dst,
                edge.lag,
                tuple(edge.sources),
                edge.data_confidence,
                edge.literature_confidence,
                edge.llm_confidence,
                edge.expert_confidence,
                edge.simulation_confidence,
                edge.combined_confidence,
                edge.unsupported_by_evidence,
                tuple(edge.evidence_refs),
                edge.p_value,
                tuple(sorted(edge.metadata.items())),
            )
            if key in seen:
                continue
            seen.add(key)
            amn_edges.append(edge.model_copy(update={"src": src, "dst": dst}))

    bridge_edges: list[tuple[str, str]] = []
    intervened_vars: set[str] = set()
    amn_node_set = set(amn_nodes)
    for world_data in interventions.values():
        intervened_vars.update(world_data.keys())

    for variable in sorted(intervened_vars):
        candidate_nodes = [
            f"{variable}__{world}" for world in worlds if f"{variable}__{world}" in amn_node_set
        ]
        for left, right in combinations(candidate_nodes, 2):
            bridge_edges.append((left, right))
            amn_edges.append(
                CausalEdge(
                    src=left,
                    dst=right,
                    mark_src=EdgeMark.ARROW,
                    mark_dst=EdgeMark.ARROW,
                )
            )

    meta = AMNMetadata(
        worlds=worlds,
        world_partition=world_partition,
        counterfactual_interventions={k: dict(v) for k, v in interventions.items()},
        bridge_edges=bridge_edges,
    )

    amn_graph = CausalGraphModel(
        schema_version=graph.schema_version,
        graph_type=GraphType.ADMG,
        nodes=amn_nodes,
        edges=amn_edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata={
            **dict(graph.metadata),
            "derived_view": "amn",
            "source_graph_hash": _source_graph_hash(graph),
            "amn_metadata": meta.model_dump(mode="json"),
        },
    )
    return amn_graph, meta


def amn_d_separation(
    graph: CausalGraphModel,
    meta: AMNMetadata,
    x_set: frozenset[str],
    y_set: frozenset[str],
    z_set: frozenset[str],
) -> bool:
    """Cross-world d-separation check on an AMN graph.

    The AMN is an ADMG (may contain bidirected bridge edges), so the actual
    oracle is m-separation.
    """
    _ = meta
    node_set = set(graph.nodes)
    missing = (x_set | y_set | z_set) - node_set
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Unknown AMN nodes in separation query: {missing_list}")
    return m_separation(graph, x_set, y_set, z_set)


def amn_ctf_independence(
    amn: CausalGraphModel,
    x_vars: frozenset[str],
    y_vars: frozenset[str],
    z_vars: frozenset[str],
) -> bool:
    """Test counterfactual independence in the AMN via d-separation.

    Equivalent to ``amn_d_separation`` but accepts the AMN graph directly
    (without requiring explicit ``AMNMetadata``).  The AMN is an ADMG, so the
    oracle is m-separation.
    """
    node_set = set(amn.nodes)
    missing = (x_vars | y_vars | z_vars) - node_set
    if missing:
        raise ValueError(f"Unknown AMN nodes: {', '.join(sorted(missing))}")
    return m_separation(amn, x_vars, y_vars, z_vars)


def amn_ancestral_projection(
    amn: CausalGraphModel,
    target_vars: frozenset[str] | None = None,
) -> CausalGraphModel:
    """Project AMN to ancestral subgraph, removing non-ancestral nodes.

    If *target_vars* is ``None`` all nodes are kept (identity).  Otherwise
    the projection retains only ancestors of *target_vars* (including
    *target_vars* themselves), preserving all independences relevant to those
    variables while reducing graph size.
    """
    from polisyos.foundry.methods.catalog.causal.admg_ops import (
        ancestors,
        induced_subgraph,
    )

    if target_vars is None:
        return amn

    node_set = set(amn.nodes)
    missing = target_vars - node_set
    if missing:
        raise ValueError(f"Unknown AMN nodes for projection: {', '.join(sorted(missing))}")

    keep = ancestors(amn, target_vars) | target_vars
    return induced_subgraph(amn, keep)


def verify_ctf_faithfulness(
    amn: CausalGraphModel,
    scm: Any,
    n_samples: int = 5000,
    *,
    alpha: float = 0.05,
    rng: Any | None = None,
) -> bool:
    """Monte Carlo verification that graphical independences hold in simulated data.

    For each pair of non-adjacent nodes in the AMN, checks whether the
    conditional independence implied by d-separation is consistent with
    samples drawn from *scm*.  Returns ``True`` when **no** independence is
    violated at significance level *alpha* (after Bonferroni correction).

    This is a diagnostic tool — not required on the critical path.

    Parameters
    ----------
    amn : CausalGraphModel
        The AMN graph.
    scm : object
        Must expose ``sample(n, rng=...) -> dict[str, np.ndarray]``.
    n_samples : int
        Number of Monte Carlo samples to draw.
    alpha : float
        Significance level for independence tests (before Bonferroni).
    rng : optional
        Numpy random generator.
    """
    import numpy as _np

    if rng is None:
        rng = _np.random.default_rng(42)

    data = scm.sample(n_samples, rng=rng)

    adjacent_pairs: set[frozenset[str]] = set()
    for edge in amn.edges:
        adjacent_pairs.add(frozenset({edge.src, edge.dst}))

    node_list = list(amn.nodes)
    tests: list[tuple[str, str, frozenset[str]]] = []
    for i, a in enumerate(node_list):
        for b in node_list[i + 1 :]:
            if frozenset({a, b}) in adjacent_pairs:
                continue
            others = frozenset(node_list) - {a, b}
            if m_separation(amn, frozenset({a}), frozenset({b}), others):
                tests.append((a, b, others))

    if not tests:
        return True

    corrected_alpha = alpha / max(len(tests), 1)

    for a, b, z_set in tests:
        if a not in data or b not in data:
            continue
        arr_a = _np.asarray(data[a], dtype=float).ravel()
        arr_b = _np.asarray(data[b], dtype=float).ravel()
        n = min(len(arr_a), len(arr_b))
        if n < 10:
            continue

        if z_set:
            available_z = [v for v in z_set if v in data]
            if available_z:
                z_matrix = _np.column_stack(
                    [_np.asarray(data[v], dtype=float).ravel()[:n] for v in available_z]
                )
                full = _np.column_stack([arr_a[:n], arr_b[:n], z_matrix[:n]])
                cov = _np.cov(full, rowvar=False) + 1e-12 * _np.eye(full.shape[1])
                try:
                    prec = _np.linalg.inv(cov)
                    denom = _np.sqrt(abs(prec[0, 0] * prec[1, 1]))
                    partial_corr = -prec[0, 1] / max(denom, 1e-15)
                except _np.linalg.LinAlgError:
                    continue
            else:
                partial_corr = float(_np.corrcoef(arr_a[:n], arr_b[:n])[0, 1])
        else:
            partial_corr = float(_np.corrcoef(arr_a[:n], arr_b[:n])[0, 1])

        t_stat = (
            abs(partial_corr)
            * _np.sqrt(max(n - 2, 1))
            / max(_np.sqrt(1.0 - partial_corr**2), 1e-15)
        )
        from scipy.stats import t as t_dist

        p_value = float(2.0 * (1.0 - t_dist.cdf(abs(t_stat), df=max(n - 2, 1))))
        if p_value < corrected_alpha:
            return False

    return True


__all__ = [
    "AMNMetadata",
    "amn_ancestral_projection",
    "amn_ctf_independence",
    "amn_d_separation",
    "build_amn",
    "verify_ctf_faithfulness",
]
