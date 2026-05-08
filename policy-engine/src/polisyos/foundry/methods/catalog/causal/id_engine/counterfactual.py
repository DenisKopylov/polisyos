"""id_engine — Shpitser-Pearl ID algorithm for causal identification.

Implements the complete recursive ID algorithm (Tian & Pearl 2002; Shpitser &
Pearl 2006) plus the IDC extension for conditional interventional distributions
and the TR (Transportability) wrapper from Bareinboim & Pearl (2012).

All internal data-types (HedgeCertificate, IdentificationResult) are frozen
dataclasses rather than Pydantic models — they are internal algorithm state that
never crosses a JSON serialisation boundary directly.  At the boundary (in
SymbolicIdentifyV2.pure_step) they are converted to the existing IR contracts
(TransportabilityResult, EstimandAST).

Key functions
-------------
id_algorithm(treatment, outcome, graph)
    → IdentificationResult (IDENTIFIED | HEDGE_FOUND | PAG_AMBIGUOUS | ORACLE_NEEDED)

idc_algorithm(treatment, outcome, conditions, graph)
    → IdentificationResult via IDC reduction to two ID calls

tr_algorithm(treatment, outcome, selection_diagram)
    → IdentificationResult for transportability (augments graph with S-nodes)

id_with_oracle_fallback(treatment, outcome, graph, oracle)
    → IdentificationResult, trying oracle backends when native ID returns ORACLE_NEEDED

References
----------
Tian, J., Pearl, J. (2002). "A General Identification Condition for Causal Effects."
    AAAI 2002.
Shpitser, I., Pearl, J. (2006). "Identification of Joint Interventional Distributions
    in Recursive Semi-Markovian Causal Models." AAAI 2006.
Bareinboim, E., Pearl, J. (2012). "Transportability of Causal Effects: Completeness
    Results." AAAI 2012.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Literal

from polisyos.foundry.methods.catalog.causal._id_contracts import (
    CtfQuery,
    HedgeCertificate,
    IdentificationResult,
    IdentificationStatus,
    ProofStep,
    RequiredDataSpec,
    SourceDomain,
)
from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    augment_with_s_nodes,
    c_components,
    descendants,
    do_operator,
    extract_bidirected_edges,
    extract_directed_edges,
    induced_subgraph,
    m_separation,
    resolve_s_node_by_adjustment,
    topological_order,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import (
    ConditionalInterventionNode,
    CounterfactualNode,
    CrossWorldNode,
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ModifiedTreatmentPolicyNode,
    NestedCounterfactualNode,
    ProductNode,
    RatioNode,
    SideCondition,
    SideConditionKind,
    StochasticInterventionNode,
    StochasticPolicy,
    SumNode,
    make_frontdoor_estimand,
    make_z_transport_estimand,
)

# ---------------------------------------------------------------------------
# PAG-specific identification (Malinsky & Spirtes 2017)
# ---------------------------------------------------------------------------

from . import core as _core
from . import transport as _transport

globals().update({name: getattr(_core, name) for name in dir(_core) if not name.startswith("__")})
globals().update({name: getattr(_transport, name) for name in dir(_transport) if not name.startswith("__")})


def _has_bidirected_edge(graph: CausalGraphModel, left: str, right: str) -> bool:
    """Return True when the graph contains a latent-confounding edge left ↔ right."""
    for edge in graph.edges:
        if (
            {edge.src, edge.dst} == {left, right}
            and edge.mark_src is EdgeMark.ARROW
            and edge.mark_dst is EdgeMark.ARROW
        ):
            return True
    return False


@dataclasses.dataclass(frozen=True)
class _CtfWorldSpec:
    key: str
    intervention: tuple[tuple[str, float], ...]


@dataclasses.dataclass(frozen=True)
class _NormalizedCtfQuery:
    target_intervention: tuple[tuple[str, float], ...]
    evidence: tuple[tuple[str, float], ...]
    conditioning: tuple[str, ...]
    worlds: tuple[_CtfWorldSpec, ...]
    outcome_worlds: tuple[tuple[tuple[str, float], ...], ...]
    joint_worlds: bool = False


def _sorted_assignments(
    assignments: tuple[tuple[str, float], ...] | list[tuple[str, float]] | dict[str, float],
) -> tuple[tuple[str, float], ...]:
    if isinstance(assignments, dict):
        items = assignments.items()
    else:
        items = assignments
    return tuple(sorted((str(name), float(value)) for name, value in items))


def _format_assignment(value: float) -> str:
    return f"{value:g}"


def _infer_reference_intervention(
    assignments: tuple[tuple[str, float], ...],
) -> tuple[tuple[str, float], ...]:
    inferred: list[tuple[str, float]] = []
    for name, value in assignments:
        if value in (0.0, 1.0):
            inferred.append((name, 1.0 - value))
        else:
            return ()
    return tuple(inferred)


def _make_world_specs(
    interventions: tuple[tuple[tuple[str, float], ...], ...],
) -> tuple[_CtfWorldSpec, ...]:
    world_specs: list[_CtfWorldSpec] = []
    seen: set[tuple[tuple[str, float], ...]] = set()
    for intervention in interventions:
        if not intervention or intervention in seen:
            continue
        world_specs.append(
            _CtfWorldSpec(
                key=f"w{len(world_specs) + 1}",
                intervention=intervention,
            )
        )
        seen.add(intervention)
    return tuple(world_specs)


def _normalize_counterfactual_query(query: CtfQuery) -> _NormalizedCtfQuery:
    target_intervention = _sorted_assignments(query.intervention)
    reference_intervention = _sorted_assignments(query.reference_intervention)
    evidence = _sorted_assignments(query.evidence)
    conditioning = tuple(sorted(dict.fromkeys(query.conditioning)))
    kind = query.kind.lower()
    outcome_worlds: tuple[tuple[tuple[str, float], ...], ...] = (target_intervention,)
    world_interventions: tuple[tuple[tuple[str, float], ...], ...] = (target_intervention,)
    joint_worlds = False

    if kind == "pn":
        factual = reference_intervention or target_intervention
        alternate = _infer_reference_intervention(factual)
        if alternate:
            target_intervention = alternate
        outcome_worlds = (target_intervention,)
        world_interventions = (target_intervention, factual)
        evidence_dict = dict(evidence)
        for name, value in factual:
            evidence_dict.setdefault(name, value)
        evidence = _sorted_assignments(evidence_dict)
    elif kind == "ps":
        factual = reference_intervention or _infer_reference_intervention(target_intervention)
        outcome_worlds = (target_intervention,)
        world_interventions = (target_intervention, factual)
        if factual:
            evidence_dict = dict(evidence)
            for name, value in factual:
                evidence_dict.setdefault(name, value)
            evidence = _sorted_assignments(evidence_dict)
    elif kind == "pns":
        reference = reference_intervention or _infer_reference_intervention(target_intervention)
        if reference:
            outcome_worlds = (target_intervention, reference)
            world_interventions = (target_intervention, reference)
            joint_worlds = True
        else:
            outcome_worlds = (target_intervention,)
            world_interventions = (target_intervention,)
    elif kind == "ett" and reference_intervention:
        outcome_worlds = (target_intervention,)
        world_interventions = (target_intervention, reference_intervention)

    unique_worlds = _make_world_specs(world_interventions)

    return _NormalizedCtfQuery(
        target_intervention=target_intervention,
        evidence=evidence,
        conditioning=conditioning,
        worlds=unique_worlds,
        outcome_worlds=outcome_worlds,
        joint_worlds=joint_worlds,
    )


def _ctf_world_lookup(
    normalized_query: _NormalizedCtfQuery,
) -> dict[tuple[tuple[str, float], ...], str]:
    return {world.intervention: world.key for world in normalized_query.worlds}


def _ctf_node_name(
    variable: str,
    intervention: tuple[tuple[str, float], ...],
    world_lookup: dict[tuple[tuple[str, float], ...], str],
) -> str:
    if not intervention:
        return variable
    return f"{variable}__{world_lookup[intervention]}"


def _ctf_node_base(node: str) -> str:
    return node.split("__", 1)[0]


def _ctf_node_intervention(
    node: str,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> tuple[tuple[str, float], ...]:
    return intervention_by_node.get(node, ())


def _ctf_self_intervention_value(
    node: str,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> float | None:
    base = _ctf_node_base(node)
    for variable, value in _ctf_node_intervention(node, intervention_by_node):
        if variable == base:
            return float(value)
    return None


def _ctf_is_not_self_intervened(
    node: str,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> bool:
    return _ctf_self_intervention_value(node, intervention_by_node) is None


def _ctf_bidirected_neighbors(graph: CausalGraphModel, node: str) -> set[str]:
    return {
        edge.dst if edge.src == node else edge.src
        for edge in graph.edges
        if edge.mark_src is EdgeMark.ARROW
        and edge.mark_dst is EdgeMark.ARROW
        and node in {edge.src, edge.dst}
    }


def _ctf_parents(graph: CausalGraphModel, node: str) -> set[str]:
    return {
        edge.src
        for edge in graph.edges
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW and edge.dst == node
    }


def _ctf_sort_key(
    node: str,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> tuple[str, tuple[tuple[str, float], ...], str]:
    return (_ctf_node_base(node), _ctf_node_intervention(node, intervention_by_node), node)


def _ctf_has_same_confounders(graph: CausalGraphModel, left: str, right: str) -> bool:
    left_neighbors = _ctf_bidirected_neighbors(graph, left)
    right_neighbors = _ctf_bidirected_neighbors(graph, right)
    return right in left_neighbors or (not left_neighbors and not right_neighbors)


def _ctf_nodes_have_same_domain(
    graph: CausalGraphModel,
    left: str,
    right: str,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> bool:
    if not _ctf_has_same_confounders(graph, left, right):
        return False
    if _ctf_node_base(left) != _ctf_node_base(right):
        return False
    left_value = _ctf_self_intervention_value(left, intervention_by_node)
    right_value = _ctf_self_intervention_value(right, intervention_by_node)
    if left_value is None and right_value is None:
        return True
    if left_value is None or right_value is None:
        return False
    return left_value == right_value


def _ctf_nodes_attain_same_value(
    graph: CausalGraphModel,
    left: str,
    right: str,
    event_assignments: dict[str, float],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> bool:
    if left == right:
        return True
    if not _ctf_has_same_confounders(graph, left, right):
        return False
    if _ctf_node_base(left) != _ctf_node_base(right):
        return False
    if left in event_assignments and right in event_assignments:
        return event_assignments[left] == event_assignments[right]
    if left in event_assignments:
        right_value = _ctf_self_intervention_value(right, intervention_by_node)
        return right_value is not None and event_assignments[left] == right_value
    if right in event_assignments:
        left_value = _ctf_self_intervention_value(left, intervention_by_node)
        return left_value is not None and event_assignments[right] == left_value
    left_value = _ctf_self_intervention_value(left, intervention_by_node)
    right_value = _ctf_self_intervention_value(right, intervention_by_node)
    if left_value is not None or right_value is not None:
        return left_value is not None and right_value is not None and left_value == right_value
    return True


def _ctf_parents_attain_same_values(
    graph: CausalGraphModel,
    left: str,
    right: str,
    event_assignments: dict[str, float],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> bool:
    if not _ctf_has_same_confounders(graph, left, right):
        return False
    parents_left = _ctf_parents(graph, left)
    parents_right = _ctf_parents(graph, right)
    if parents_left == parents_right:
        return True
    remainder_left = sorted(
        parents_left - parents_right,
        key=lambda node: _ctf_sort_key(node, intervention_by_node),
    )
    remainder_right = sorted(
        parents_right - parents_left,
        key=lambda node: _ctf_sort_key(node, intervention_by_node),
    )
    if len(remainder_left) != len(remainder_right):
        return False
    return all(
        _ctf_nodes_attain_same_value(
            graph,
            left_parent,
            right_parent,
            event_assignments,
            intervention_by_node,
        )
        for left_parent, right_parent in zip(remainder_left, remainder_right)
    )


def _ctf_lemma24_holds(
    graph: CausalGraphModel,
    left: str,
    right: str,
    event_assignments: dict[str, float],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> bool:
    return (
        _ctf_node_base(left) == _ctf_node_base(right)
        and _ctf_is_not_self_intervened(left, intervention_by_node)
        == _ctf_is_not_self_intervened(right, intervention_by_node)
        and _ctf_parents_attain_same_values(
            graph,
            left,
            right,
            event_assignments,
            intervention_by_node,
        )
        and _ctf_nodes_have_same_domain(
            graph,
            left,
            right,
            intervention_by_node,
        )
    )


def _ctf_choose_merge_target(left: str, right: str) -> tuple[str, str]:
    if "__" not in left and "__" in right:
        return left, right
    if "__" not in right and "__" in left:
        return right, left
    return tuple(sorted((left, right)))  # type: ignore[return-value]


def _build_counterfactual_graph(
    graph: CausalGraphModel,
    normalized_query: _NormalizedCtfQuery,
) -> tuple[CausalGraphModel, dict[str, tuple[tuple[str, float], ...]]]:
    nodes = list(graph.nodes)
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]] = dict.fromkeys(graph.nodes, ())
    for world in normalized_query.worlds:
        for node in graph.nodes:
            world_node = f"{node}__{world.key}"
            nodes.append(world_node)
            intervention_by_node[world_node] = world.intervention

    seen_edges: set[tuple[str, str, EdgeMark, EdgeMark]] = set()
    edges: list[Any] = []

    def _add_edge(
        src: str,
        dst: str,
        mark_src: EdgeMark,
        mark_dst: EdgeMark,
    ) -> None:
        key = (src, dst, mark_src, mark_dst)
        if key in seen_edges or src == dst:
            return
        seen_edges.add(key)
        edges.append(
            CausalEdge(
                src=src,
                dst=dst,
                mark_src=mark_src,
                mark_dst=mark_dst,
            )
        )

    for edge in graph.edges:
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
            _add_edge(edge.src, edge.dst, EdgeMark.TAIL, EdgeMark.ARROW)
            for world in normalized_query.worlds:
                if edge.dst in dict(world.intervention):
                    continue
                _add_edge(
                    f"{edge.src}__{world.key}",
                    f"{edge.dst}__{world.key}",
                    EdgeMark.TAIL,
                    EdgeMark.ARROW,
                )
        elif edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW:
            _add_edge(edge.src, edge.dst, EdgeMark.ARROW, EdgeMark.ARROW)
            for world in normalized_query.worlds:
                if edge.src in dict(world.intervention) or edge.dst in dict(world.intervention):
                    continue
                _add_edge(
                    f"{edge.src}__{world.key}",
                    f"{edge.dst}__{world.key}",
                    EdgeMark.ARROW,
                    EdgeMark.ARROW,
                )

    base_bidirected_pairs = [
        tuple(sorted((edge.src, edge.dst)))
        for edge in graph.edges
        if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW
    ]

    for world in normalized_query.worlds:
        intervention_vars = {name for name, _ in world.intervention}
        for node in graph.nodes:
            if node in intervention_vars:
                continue
            _add_edge(node, f"{node}__{world.key}", EdgeMark.ARROW, EdgeMark.ARROW)
        for left, right in base_bidirected_pairs:
            if right not in intervention_vars:
                _add_edge(left, f"{right}__{world.key}", EdgeMark.ARROW, EdgeMark.ARROW)
            if left not in intervention_vars:
                _add_edge(right, f"{left}__{world.key}", EdgeMark.ARROW, EdgeMark.ARROW)

    for idx, left_world in enumerate(normalized_query.worlds):
        left_interventions = {name for name, _ in left_world.intervention}
        for right_world in normalized_query.worlds[idx + 1 :]:
            right_interventions = {name for name, _ in right_world.intervention}
            for node in graph.nodes:
                if node in left_interventions or node in right_interventions:
                    continue
                _add_edge(
                    f"{node}__{left_world.key}",
                    f"{node}__{right_world.key}",
                    EdgeMark.ARROW,
                    EdgeMark.ARROW,
                )
            for left, right in base_bidirected_pairs:
                if left not in left_interventions and right not in right_interventions:
                    _add_edge(
                        f"{left}__{left_world.key}",
                        f"{right}__{right_world.key}",
                        EdgeMark.ARROW,
                        EdgeMark.ARROW,
                    )
                if right not in left_interventions and left not in right_interventions:
                    _add_edge(
                        f"{right}__{left_world.key}",
                        f"{left}__{right_world.key}",
                        EdgeMark.ARROW,
                        EdgeMark.ARROW,
                    )

    cf_graph = CausalGraphModel.model_construct(
        schema_version=graph.schema_version,
        graph_type=GraphType.ADMG,
        nodes=nodes,
        edges=edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata={
            **dict(graph.metadata),
            "derived_view": "counterfactual_graph",
            "counterfactual_worlds": {
                world.key: dict(world.intervention) for world in normalized_query.worlds
            },
        },
    )
    return cf_graph, intervention_by_node


def _merge_counterfactual_nodes(
    graph: CausalGraphModel,
    *,
    keep: str,
    drop: str,
) -> CausalGraphModel:
    new_nodes = [node for node in graph.nodes if node != drop]
    seen: set[tuple[str, str, EdgeMark, EdgeMark, int | None]] = set()
    new_edges = []
    for edge in graph.edges:
        src = keep if edge.src == drop else edge.src
        dst = keep if edge.dst == drop else edge.dst
        if src == dst:
            continue
        key = (src, dst, edge.mark_src, edge.mark_dst, edge.lag)
        if key in seen:
            continue
        seen.add(key)
        new_edges.append(edge.model_copy(update={"src": src, "dst": dst}))
    return CausalGraphModel.model_construct(
        schema_version=graph.schema_version,
        graph_type=graph.graph_type,
        nodes=new_nodes,
        edges=new_edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata=dict(graph.metadata),
    )


def _reduce_counterfactual_graph(
    *,
    graph: CausalGraphModel,
    base_graph: CausalGraphModel,
    focus_nodes: set[str],
    event_assignments: dict[str, float],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> tuple[CausalGraphModel, set[str], dict[str, float], bool]:
    worlds = sorted(
        {intervention for intervention in intervention_by_node.values() if intervention}
    )
    world_lookup = {intervention: idx for idx, intervention in enumerate(worlds)}

    def _copy_name(node: str, intervention: tuple[tuple[str, float], ...]) -> str:
        if not intervention:
            return node
        return f"{node}__w{world_lookup[intervention] + 1}"

    current_graph = graph
    inconsistent = False

    for node in topological_order(base_graph):
        for intervention in worlds:
            copy_node = _copy_name(node, intervention)
            if (
                node in current_graph.nodes
                and copy_node in current_graph.nodes
                and _ctf_lemma24_holds(
                    current_graph,
                    node,
                    copy_node,
                    event_assignments,
                    intervention_by_node,
                )
            ):
                keep, drop = _ctf_choose_merge_target(node, copy_node)
                if (
                    keep in event_assignments
                    and drop in event_assignments
                    and event_assignments[keep] != event_assignments[drop]
                ):
                    inconsistent = True
                    break
                current_graph = _merge_counterfactual_nodes(current_graph, keep=keep, drop=drop)
                if drop in focus_nodes:
                    focus_nodes.discard(drop)
                    focus_nodes.add(keep)
                if drop in event_assignments:
                    event_assignments[keep] = event_assignments[drop]
                    del event_assignments[drop]
        if inconsistent:
            break
        for left_idx, left_intervention in enumerate(worlds):
            left_node = _copy_name(node, left_intervention)
            for right_intervention in worlds[left_idx + 1 :]:
                right_node = _copy_name(node, right_intervention)
                if (
                    left_node in current_graph.nodes
                    and right_node in current_graph.nodes
                    and _ctf_lemma24_holds(
                        current_graph,
                        left_node,
                        right_node,
                        event_assignments,
                        intervention_by_node,
                    )
                ):
                    keep, drop = _ctf_choose_merge_target(left_node, right_node)
                    if (
                        keep in event_assignments
                        and drop in event_assignments
                        and event_assignments[keep] != event_assignments[drop]
                    ):
                        inconsistent = True
                        break
                    current_graph = _merge_counterfactual_nodes(current_graph, keep=keep, drop=drop)
                    if drop in focus_nodes:
                        focus_nodes.discard(drop)
                        focus_nodes.add(keep)
                    if drop in event_assignments:
                        event_assignments[keep] = event_assignments[drop]
                        del event_assignments[drop]
            if inconsistent:
                break
        if inconsistent:
            break

    mentioned = frozenset(focus_nodes | set(event_assignments))
    if mentioned:
        an_mentioned = ancestors(current_graph, mentioned) | mentioned
        current_graph = induced_subgraph(current_graph, an_mentioned)
        focus_nodes = {node for node in focus_nodes if node in an_mentioned}
        event_assignments = {
            node: value for node, value in event_assignments.items() if node in an_mentioned
        }
    return current_graph, focus_nodes, event_assignments, inconsistent


def _counterfactual_conflicts(
    graph: CausalGraphModel,
    event_assignments: dict[str, float],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> list[tuple[str, float, float]]:
    conflicts: list[tuple[str, float, float]] = []
    for node in graph.nodes:
        if node not in event_assignments:
            continue
        self_value = _ctf_self_intervention_value(node, intervention_by_node)
        if self_value is not None and self_value != event_assignments[node]:
            conflicts.append((_ctf_node_base(node), self_value, event_assignments[node]))
    return conflicts


def _ctf_c_components(
    graph: CausalGraphModel,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> list[frozenset[str]]:
    non_self_nodes = frozenset(
        node for node in graph.nodes if _ctf_is_not_self_intervened(node, intervention_by_node)
    )
    if not non_self_nodes:
        return []
    return c_components(induced_subgraph(graph, non_self_nodes))


def _ctf_markov_pillow(
    graph: CausalGraphModel,
    district: frozenset[str],
) -> frozenset[str]:
    district_set = set(district)
    parents = {
        edge.src
        for edge in graph.edges
        if edge.mark_src is EdgeMark.TAIL
        and edge.mark_dst is EdgeMark.ARROW
        and edge.dst in district_set
        and edge.src not in district_set
    }
    return frozenset(parents)


def _ctf_reduction_treatment(
    graph: CausalGraphModel,
    district: frozenset[str],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> frozenset[str]:
    treatment: set[str] = set()
    for node in district:
        for variable, _ in intervention_by_node.get(node, ()):
            treatment.add(variable)
    for pillow_node in _ctf_markov_pillow(graph, district):
        treatment.add(_ctf_node_base(pillow_node))
    return frozenset(treatment)


def _format_counterfactual_query_str(
    outcome: str,
    intervention: tuple[tuple[str, float], ...],
    evidence: tuple[tuple[str, float], ...],
    conditioning: tuple[str, ...],
) -> str:
    head = _format_counterfactual_head(outcome, intervention)
    rhs_terms = [f"{name}={_format_assignment(value)}" for name, value in evidence] + list(
        conditioning
    )
    if rhs_terms:
        return f"P({head} | {', '.join(rhs_terms)})"
    return f"P({head})"


def _format_counterfactual_head(
    outcome: str,
    intervention: tuple[tuple[str, float], ...],
) -> str:
    intervention_str = ", ".join(
        f"{name}={_format_assignment(value)}" for name, value in intervention
    )
    if intervention_str:
        return f"{outcome}_{{{intervention_str}}}"
    return outcome


def _format_cross_world_query_str(
    outcome: str,
    interventions: tuple[tuple[tuple[str, float], ...], ...],
    evidence: tuple[tuple[str, float], ...],
    conditioning: tuple[str, ...],
) -> str:
    head = ", ".join(
        _format_counterfactual_head(outcome, intervention) for intervention in interventions
    )
    rhs_terms = [f"{name}={_format_assignment(value)}" for name, value in evidence] + list(
        conditioning
    )
    if rhs_terms:
        return f"P({head} | {', '.join(rhs_terms)})"
    return f"P({head})"


def _normalized_counterfactual_query_str(
    outcome: str,
    normalized_query: _NormalizedCtfQuery,
) -> str:
    if len(normalized_query.outcome_worlds) > 1:
        return _format_cross_world_query_str(
            outcome,
            normalized_query.outcome_worlds,
            normalized_query.evidence,
            normalized_query.conditioning,
        )
    return _format_counterfactual_query_str(
        outcome,
        normalized_query.target_intervention,
        normalized_query.evidence,
        normalized_query.conditioning,
    )


def _counterfactual_ast(
    *,
    query: CtfQuery,
    normalized_query: _NormalizedCtfQuery,
    identification_method: str,
) -> EstimandAST:
    evidence_vars = tuple(name for name, _ in normalized_query.evidence)
    conditioning = tuple(sorted({*normalized_query.conditioning, *evidence_vars}))
    query_str = _normalized_counterfactual_query_str(query.outcome, normalized_query)
    world_index_lookup = {
        world.intervention: idx for idx, world in enumerate(normalized_query.worlds)
    }
    cf_node = CounterfactualNode(
        variable=query.outcome,
        intervention=dict(normalized_query.target_intervention),
        conditioning=conditioning,
        world_index=world_index_lookup.get(normalized_query.target_intervention, 0),
        domain=DistributionDomain.SOURCE,
    )
    if query.kind.lower() == "nested":
        root = NestedCounterfactualNode(
            outer_variable=query.outcome,
            outer_intervention=dict(normalized_query.target_intervention),
            inner_counterfactual=cf_node,
            world_indices=(0,),
            domain=DistributionDomain.SOURCE,
        )
    elif len(normalized_query.outcome_worlds) > 1:
        root = CrossWorldNode(
            worlds=tuple(
                CounterfactualNode(
                    variable=query.outcome,
                    intervention=dict(outcome_world),
                    conditioning=conditioning,
                    world_index=world_index_lookup.get(outcome_world, idx),
                    domain=DistributionDomain.SOURCE,
                )
                for idx, outcome_world in enumerate(normalized_query.outcome_worlds)
            ),
            joint=normalized_query.joint_worlds,
        )
    else:
        root = cf_node
    all_vars = tuple(
        sorted(
            {
                query.outcome,
                *(
                    name
                    for outcome_world in normalized_query.outcome_worlds
                    for name, _ in outcome_world
                ),
                *(name for name, _ in normalized_query.evidence),
                *normalized_query.conditioning,
            }
        )
    )
    treatment_vars = tuple(
        sorted(
            {name for outcome_world in normalized_query.outcome_worlds for name, _ in outcome_world}
        )
    )
    treatment = (
        ",".join(treatment_vars)
        if len(treatment_vars) > 1
        else (treatment_vars[0] if treatment_vars else "counterfactual")
    )
    return EstimandAST(
        query_str=query_str,
        root=root,
        treatment=treatment,
        outcome=query.outcome,
        all_variables=all_vars,
        identification_method=identification_method,
    )


def _counterfactual_negative_certificate(
    *,
    query: CtfQuery,
    treatment: frozenset[str],
    graph: CausalGraphModel,
    description: str,
) -> HedgeCertificate:
    graph_nodes = frozenset(graph.nodes)
    return HedgeCertificate(
        treatment=treatment,
        outcome=frozenset({query.outcome}),
        hedge_forest=graph_nodes,
        hedge_root=graph_nodes,
        c_component_witness=graph_nodes,
        description=description,
    )


def id_star_algorithm(
    counterfactual_query: CtfQuery,
    graph: CausalGraphModel,
    _depth: int = 0,
    _trace: list[str] | None = None,
) -> IdentificationResult:
    """ID* counterfactual identification via G* reduction + Layer-2 subproblems."""
    trace = list(_trace or [])
    normalized_query = _normalize_counterfactual_query(counterfactual_query)
    treatment_vars = frozenset(name for name, _ in normalized_query.target_intervention)
    trace.append(
        f"[ID* depth={_depth}] kind={counterfactual_query.kind}, "
        f"outcome={counterfactual_query.outcome}, "
        f"target_intervention={list(normalized_query.target_intervention)}, "
        f"worlds={len(normalized_query.worlds)}"
    )
    proof_steps: list[ProofStep] = [
        ProofStep(
            rule_name="ID_STAR_STEP1",
            antecedent_vars=tuple(sorted(treatment_vars)),
            consequent_vars=(counterfactual_query.outcome,),
            applied_to_graph_state=(
                "Constructed G* from compact parallel worlds with Lemma-24/25 style node merging."
            ),
            depth=_depth,
        )
    ]

    cf_graph, intervention_by_node = _build_counterfactual_graph(graph, normalized_query)
    world_lookup = _ctf_world_lookup(normalized_query)
    focus_nodes = {
        _ctf_node_name(
            counterfactual_query.outcome,
            outcome_world,
            world_lookup,
        )
        for outcome_world in normalized_query.outcome_worlds
    }
    focus_nodes.update(normalized_query.conditioning)
    event_assignments = {
        _ctf_node_name(name, (), world_lookup): value for name, value in normalized_query.evidence
    }
    trace.append(
        f"[ID* depth={_depth}] raw G* has {len(cf_graph.nodes)} nodes and {len(cf_graph.edges)} edges"
    )
    cf_graph, focus_nodes, event_assignments, inconsistent = _reduce_counterfactual_graph(
        graph=cf_graph,
        base_graph=graph,
        focus_nodes=focus_nodes,
        event_assignments=event_assignments,
        intervention_by_node=intervention_by_node,
    )
    trace.append(
        f"[ID* depth={_depth}] reduced G* has {len(cf_graph.nodes)} nodes and {len(cf_graph.edges)} edges"
    )
    if inconsistent:
        cert = _counterfactual_negative_certificate(
            query=counterfactual_query,
            treatment=treatment_vars,
            graph=cf_graph,
            description="Counterfactual event became inconsistent during Lemma-24/25 merging.",
        )
        proof_steps.append(
            ProofStep(
                rule_name="ID_STAR_STEP5",
                antecedent_vars=tuple(sorted(treatment_vars)),
                consequent_vars=(counterfactual_query.outcome,),
                applied_to_graph_state="Merged counterfactual graph became inconsistent.",
                depth=_depth,
            )
        )
        return IdentificationResult(
            status=IdentificationStatus.HEDGE_FOUND,
            estimand_ast=None,
            hedge_certificate=cert,
            trace=[*trace, f"[ID* depth={_depth}] inconsistent after counterfactual graph merge"],
            required_distributions=[],
            algorithm_version="id_star_v2",
            proof_steps=proof_steps,
            query_str=_normalized_counterfactual_query_str(
                counterfactual_query.outcome,
                normalized_query,
            ),
        )

    districts = _ctf_c_components(cf_graph, intervention_by_node)
    proof_steps.append(
        ProofStep(
            rule_name="ID_STAR_STEP2",
            antecedent_vars=tuple(sorted(treatment_vars)),
            consequent_vars=(counterfactual_query.outcome,),
            applied_to_graph_state=(
                f"Partitioned G* into c-components: {[sorted(component) for component in districts]}"
            ),
            depth=_depth,
        )
    )
    if not districts:
        districts = [frozenset(focus_nodes)]

    relevant_districts = [district for district in districts if district & focus_nodes]
    if not relevant_districts:
        relevant_districts = list(districts)

    conflicts = _counterfactual_conflicts(cf_graph, event_assignments, intervention_by_node)
    if conflicts:
        cert = _counterfactual_negative_certificate(
            query=counterfactual_query,
            treatment=treatment_vars,
            graph=cf_graph,
            description=(
                "Counterfactual graph contains intervention/evidence conflicts: "
                + ", ".join(
                    f"{name}: do={_format_assignment(do_value)} vs ev={_format_assignment(ev_value)}"
                    for name, do_value, ev_value in conflicts
                )
            ),
        )
        proof_steps.append(
            ProofStep(
                rule_name="ID_STAR_STEP5",
                antecedent_vars=tuple(sorted(treatment_vars)),
                consequent_vars=(counterfactual_query.outcome,),
                applied_to_graph_state="Counterfactual graph contains intervention/evidence conflicts.",
                depth=_depth,
            )
        )
        return IdentificationResult(
            status=IdentificationStatus.HEDGE_FOUND,
            estimand_ast=None,
            hedge_certificate=cert,
            trace=[*trace, f"[ID* depth={_depth}] conflicts in G*: {conflicts}"],
            required_distributions=[],
            algorithm_version="id_star_v2",
            proof_steps=proof_steps,
            query_str=_normalized_counterfactual_query_str(
                counterfactual_query.outcome,
                normalized_query,
            ),
        )

    if len(relevant_districts) > 1:
        trace.append(
            f"[ID* depth={_depth}] G* disconnected into relevant districts "
            f"{[sorted(component) for component in relevant_districts]}"
        )
        proof_steps.append(
            ProofStep(
                rule_name="ID_STAR_STEP4",
                antecedent_vars=tuple(sorted(treatment_vars)),
                consequent_vars=(counterfactual_query.outcome,),
                applied_to_graph_state="Applied parallel-world factorisation across disconnected districts.",
                depth=_depth,
            )
        )

    required_distributions: list[DistributionRef] = []
    reduced_results: list[IdentificationResult] = []
    for district in relevant_districts:
        base_outcomes = frozenset(sorted({_ctf_node_base(node) for node in district}))
        district_treatment = _ctf_reduction_treatment(
            cf_graph,
            district,
            intervention_by_node,
        )
        trace.append(
            f"[ID* depth={_depth}] Layer-2 reduction on district "
            f"Y={sorted(base_outcomes)}, X={sorted(district_treatment)}"
        )
        base_result = id_algorithm(
            treatment=district_treatment,
            outcome=base_outcomes,
            graph=graph,
            _depth=_depth + 1,
            _trace=trace,
        )
        reduced_results.append(base_result)
        proof_steps.append(
            ProofStep(
                rule_name="ID_STAR_STEP3",
                antecedent_vars=tuple(sorted(district_treatment)),
                consequent_vars=tuple(sorted(base_outcomes)),
                applied_to_graph_state=(
                    f"Reduced district {sorted(district)} to Layer-2 ID with status={base_result.status.value}"
                ),
                depth=_depth,
            )
        )
        if base_result.status is not IdentificationStatus.IDENTIFIED:
            return IdentificationResult(
                status=base_result.status,
                estimand_ast=None,
                hedge_certificate=base_result.hedge_certificate,
                trace=[
                    *trace,
                    *base_result.trace,
                    f"[ID* depth={_depth}] district reduction failed",
                ],
                required_distributions=base_result.required_distributions,
                algorithm_version="id_star_v2",
                proof_steps=[*proof_steps, *base_result.proof_steps],
                query_str=_normalized_counterfactual_query_str(
                    counterfactual_query.outcome,
                    normalized_query,
                ),
            )
        required_distributions.extend(base_result.required_distributions)

    ast = _counterfactual_ast(
        query=counterfactual_query,
        normalized_query=normalized_query,
        identification_method=f"id_star_v2|kind={counterfactual_query.kind}",
    )
    proof_steps.append(
        ProofStep(
            rule_name="ID_STAR_STEP5",
            antecedent_vars=tuple(sorted(treatment_vars)),
            consequent_vars=(counterfactual_query.outcome,),
            applied_to_graph_state=(
                "Counterfactual query reduced to identified Layer-2 subproblems."
            ),
            depth=_depth,
        )
    )
    trace.append(f"[ID* depth={_depth}] identified {counterfactual_query.kind}")
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=[*trace, *(step for result in reduced_results for step in result.trace)],
        required_distributions=required_distributions,
        algorithm_version="id_star_v2",
        proof_steps=[
            *proof_steps,
            *(step for result in reduced_results for step in result.proof_steps),
        ],
        query_str=ast.query_str,
    )


def idc_star_algorithm(
    counterfactual_query: CtfQuery,
    graph: CausalGraphModel,
    _depth: int = 0,
    _trace: list[str] | None = None,
) -> IdentificationResult:
    """IDC* with counterfactual Rule-2 promotion before the ratio reduction."""
    trace = list(_trace or [])
    trace.append(f"[IDC* depth={_depth}] start")

    if not counterfactual_query.evidence:
        return dataclasses.replace(
            id_star_algorithm(counterfactual_query, graph, _depth=_depth + 1, _trace=trace),
            algorithm_version="idc_star_v2",
            trace=[*trace, "[IDC* depth=0] no evidence supplied; identical to ID*"],
        )

    normalized_query = _normalize_counterfactual_query(counterfactual_query)
    cf_graph, intervention_by_node = _build_counterfactual_graph(graph, normalized_query)
    world_lookup = _ctf_world_lookup(normalized_query)
    target_node = _ctf_node_name(
        counterfactual_query.outcome,
        normalized_query.target_intervention,
        world_lookup,
    )
    promoted_query = counterfactual_query
    promoted_intervention_map = dict(promoted_query.intervention)
    for condition_name, condition_value in normalized_query.evidence:
        condition_node = _ctf_node_name(condition_name, (), world_lookup)
        conditioned_nodes = frozenset(
            node
            for node in cf_graph.nodes
            if not _ctf_is_not_self_intervened(node, intervention_by_node)
        )
        modified_graph = CausalGraphModel.model_construct(
            schema_version=cf_graph.schema_version,
            graph_type=cf_graph.graph_type,
            nodes=list(cf_graph.nodes),
            edges=[
                edge
                for edge in cf_graph.edges
                if not (
                    edge.mark_src is EdgeMark.TAIL
                    and edge.mark_dst is EdgeMark.ARROW
                    and edge.src == condition_node
                )
            ],
            discovery_method=cf_graph.discovery_method,
            skg_version_id=cf_graph.skg_version_id,
            pag_identification_policy=cf_graph.pag_identification_policy,
            id_confidence_under_pag=cf_graph.id_confidence_under_pag,
            metadata=dict(cf_graph.metadata),
        )
        if (
            condition_node in modified_graph.nodes
            and target_node in modified_graph.nodes
            and condition_name not in promoted_intervention_map
            and m_separation(
                modified_graph,
                frozenset({target_node}),
                frozenset({condition_node}),
                conditioned_nodes,
            )
        ):
            promoted_map = dict(promoted_query.intervention)
            promoted_map[condition_name] = condition_value
            promoted_query = dataclasses.replace(
                promoted_query,
                intervention=_sorted_assignments(promoted_map),
                evidence=tuple(
                    (name, value)
                    for name, value in promoted_query.evidence
                    if name != condition_name
                ),
            )
            trace.append(
                f"[IDC* depth={_depth}] Rule-2 promoted {condition_name}={_format_assignment(condition_value)} to intervention"
            )
            return idc_star_algorithm(
                promoted_query,
                graph,
                _depth=_depth + 1,
                _trace=trace,
            )

    numerator_query = promoted_query
    conflicting_treatment_evidence = {
        name
        for name, value in promoted_query.evidence
        if name in promoted_intervention_map
        and float(promoted_intervention_map[name]) != float(value)
    }
    if conflicting_treatment_evidence:
        trace.append(
            f"[IDC* depth={_depth}] preserving conflicting treatment evidence in the conditioning event: "
            f"{sorted(conflicting_treatment_evidence)}"
        )
        numerator_query = dataclasses.replace(
            promoted_query,
            evidence=tuple(
                (name, value)
                for name, value in promoted_query.evidence
                if name not in conflicting_treatment_evidence
            ),
        )

    numerator = id_star_algorithm(numerator_query, graph, _depth=_depth + 1, _trace=trace)
    if numerator.status is not IdentificationStatus.IDENTIFIED:
        return numerator

    evidence_vars = tuple(sorted(name for name, _ in promoted_query.evidence))
    if len(promoted_query.evidence) == 1:
        evidence_var, _ = promoted_query.evidence[0]
        denominator_query = CtfQuery(
            outcome=evidence_var,
            intervention=(),
            conditioning=promoted_query.conditioning,
            kind="generic",
        )
        denominator_result = id_star_algorithm(
            denominator_query,
            graph,
            _depth=_depth + 1,
            _trace=list(trace),
        )
        if denominator_result.status is not IdentificationStatus.IDENTIFIED:
            return denominator_result
        assert denominator_result.estimand_ast is not None
        denominator_root = denominator_result.estimand_ast.root
        denominator_all_vars = denominator_result.estimand_ast.all_variables
    else:
        denominator_root = DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=evidence_vars,
            intervention_set=(),
            conditioning=tuple(sorted(promoted_query.conditioning)),
        )
        denominator_all_vars = tuple(sorted({*evidence_vars, *promoted_query.conditioning}))

    assert numerator.estimand_ast is not None
    ratio_ast = EstimandAST(
        query_str=_format_counterfactual_query_str(
            counterfactual_query.outcome,
            _normalize_counterfactual_query(promoted_query).target_intervention,
            _sorted_assignments(promoted_query.evidence),
            tuple(sorted(promoted_query.conditioning)),
        ),
        root=RatioNode(
            numerator=numerator.estimand_ast.root,
            denominator=denominator_root,
        ),
        treatment=numerator.estimand_ast.treatment,
        outcome=numerator.estimand_ast.outcome,
        all_variables=tuple(sorted({*numerator.estimand_ast.all_variables, *denominator_all_vars})),
        identification_method="idc_star_v2",
    )
    proof_steps = [
        ProofStep(
            rule_name="IDC_STAR_RATIO",
            antecedent_vars=evidence_vars,
            consequent_vars=(counterfactual_query.outcome,),
            applied_to_graph_state="Constructed IDC* after Rule-2 promotion and counterfactual ratio reduction.",
            depth=_depth,
        ),
    ]
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ratio_ast,
        hedge_certificate=None,
        trace=[*trace, *numerator.trace, "[IDC* depth=0] identified via ratio construction"],
        required_distributions=numerator.required_distributions,
        algorithm_version="idc_star_v2",
        proof_steps=[*proof_steps, *numerator.proof_steps],
        query_str=ratio_ast.query_str,
    )


__all__ = [name for name in globals() if not name.startswith("__")]
