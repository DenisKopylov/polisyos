"""Scalable proof-kernel identification backend for path-specific effects.

This module is deliberately separate from ``path_specific.py``:

- ``path_specific.py`` remains the single-mediator NDE/NIE estimation backend;
- this module handles symbolic/path-specific identification decisions,
  district-local compilation diagnostics, and width-aware fallback behavior.

The implementation is conservative but production-oriented:

- supports DAG/ADMG inputs;
- normalizes general path policies into a canonical query object;
- detects recanting witness / recanting district style conflicts;
- records a district-local compilation plan with an explicit width proxy;
- falls back to support-implied bounds when exact identification is blocked
  and a bounded outcome support is declared.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Literal

from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    descendants,
    districts,
    extract_directed_edges,
    induced_subgraph,
    topological_order,
)
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationStatus,
    id_algorithm,
    idc_algorithm,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType
from polisyos.ir.analytics.estimand import (
    ConditionalInterventionNode,
    DistributionDomain,
    DistributionRef,
    EdgeInterventionAssignment,
    EdgeInterventionNode,
    EstimandAST,
    ProductNode,
    SumNode,
)
from polisyos.ir.analytics.interventions import PathIntervention
from polisyos.ir.analytics.mediation_effects import PathSpecificQuery
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    BoundsBundle,
    PartialIdentificationResult,
    bounds_bundle_from_partial_identification_result,
)
from polisyos.ir.analytics.path_specific_identification import (
    PathSpecificCompilationPlan,
    PathSpecificDecisionMode,
    PathSpecificDistrictFactor,
    PathSpecificDistrictLabel,
    PathSpecificIdentificationReport,
    PathSpecificWitness,
    PathSpecificWitnessKind,
)


def _normalize_path_intervention(
    intervention: PathIntervention,
    *,
    outcome: str,
    conditioning: tuple[str, ...] = (),
) -> tuple[str, PathSpecificQuery]:
    paths = tuple(intervention.active_paths) + tuple(intervention.frozen_paths)
    if not paths:
        raise ValueError("path intervention requires at least one active or frozen path")
    treatment = paths[0][0]
    for path in paths:
        if path[0] != treatment:
            raise ValueError("all path-specific paths must share the same treatment/source node")
        if path[-1] != outcome:
            raise ValueError("all path-specific paths must terminate at the requested outcome")
    mediators = tuple(
        sorted(
            {
                *intervention.natural_value_vars,
                *(node for path in paths for node in path[1:-1]),
            }
        )
    )
    query = PathSpecificQuery(
        treatment=treatment,
        outcome=outcome,
        mediators=mediators,
        active_paths=intervention.active_paths,
        fixed_paths=intervention.frozen_paths,
        conditioning=conditioning,
        metadata={
            "source": "path_intervention",
            "natural_value_vars": list(intervention.natural_value_vars),
        },
    )
    return treatment, query


def _path_policy_hash(query: PathSpecificQuery) -> str:
    payload = {
        "treatment": query.treatment,
        "outcome": query.outcome,
        "mediators": query.mediators,
        "active_paths": query.active_paths,
        "fixed_paths": query.fixed_paths,
        "conditioning": query.conditioning,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _frontier_assignments(
    query: PathSpecificQuery,
) -> tuple[tuple[str, str, Literal["active", "frozen"]], ...]:
    assignments: dict[tuple[str, str], set[str]] = defaultdict(set)
    for label, paths in (("active", query.active_paths), ("frozen", query.fixed_paths)):
        for path in paths:
            if len(path) < 2:
                continue
            assignments[(path[0], path[1])].add(label)
    ordered: list[tuple[str, str, Literal["active", "frozen"]]] = []
    for edge in sorted(assignments):
        labels = assignments[edge]
        for label in sorted(labels):
            ordered.append((edge[0], edge[1], label))  # type: ignore[arg-type]
    return tuple(ordered)


def _edge_conflicts(
    query: PathSpecificQuery,
) -> list[PathSpecificWitness]:
    edge_labels: dict[tuple[str, str], set[str]] = defaultdict(set)
    for label, paths in (("active", query.active_paths), ("frozen", query.fixed_paths)):
        for path in paths:
            for src, dst in zip(path[:-1], path[1:], strict=False):
                edge_labels[(src, dst)].add(label)
    conflicts: list[PathSpecificWitness] = []
    for edge, labels in sorted(edge_labels.items()):
        if len(labels) > 1:
            conflicts.append(
                PathSpecificWitness(
                    kind=PathSpecificWitnessKind.EDGE_INCONSISTENCY,
                    detail=(
                        f"Edge {edge[0]}->{edge[1]} appears in both active and frozen path sets."
                    ),
                    edges=(edge,),
                    variables=edge,
                    metadata={"labels": sorted(labels)},
                )
            )
    return conflicts


def _relevant_subgraph(
    graph: CausalGraphModel,
    *,
    treatment: str,
    outcome: str,
    query: PathSpecificQuery,
) -> tuple[CausalGraphModel, tuple[str, ...], tuple[str, ...]]:
    conditioning_nodes = frozenset(query.conditioning)
    path_nodes = frozenset(
        {
            treatment,
            outcome,
            *conditioning_nodes,
            *query.mediators,
            *(node for path in query.active_paths + query.fixed_paths for node in path),
        }
    )
    ancestral = ancestors(graph, frozenset({outcome, *conditioning_nodes})) | path_nodes
    descendants_from_sources = (
        descendants(graph, frozenset({treatment, *conditioning_nodes}))
        | frozenset({treatment, *conditioning_nodes})
    )
    relevant = tuple(sorted((ancestral & descendants_from_sources) | path_nodes))
    subgraph = induced_subgraph(graph, frozenset(relevant))
    return subgraph, tuple(sorted(ancestral)), relevant


def _conditioning_witnesses(
    graph: CausalGraphModel,
    *,
    treatment: str,
    outcome: str,
    conditioning: tuple[str, ...],
) -> tuple[PathSpecificWitness, ...]:
    if not conditioning:
        return ()
    directed_descendants = descendants(graph, frozenset({treatment}))
    witnesses: list[PathSpecificWitness] = []
    for variable in conditioning:
        if variable not in graph.nodes:
            witnesses.append(
                PathSpecificWitness(
                    kind=PathSpecificWitnessKind.UNSUPPORTED_CONDITIONING,
                    detail=(
                        f"Conditioning variable {variable} is not present in the graph."
                    ),
                    variables=(variable,),
                    metadata={"reason": "missing_from_graph"},
                )
            )
            continue
        if variable in {treatment, outcome}:
            witnesses.append(
                PathSpecificWitness(
                    kind=PathSpecificWitnessKind.UNSUPPORTED_CONDITIONING,
                    detail=(
                        f"Conditioning on {variable} is not certified because it matches "
                        "the treatment or outcome variable."
                    ),
                    variables=(variable,),
                    metadata={"reason": "endpoint_conditioning"},
                )
            )
            continue
        if variable in directed_descendants:
            witnesses.append(
                PathSpecificWitness(
                    kind=PathSpecificWitnessKind.UNSUPPORTED_CONDITIONING,
                    detail=(
                        f"Conditioning variable {variable} is post-treatment, so the "
                        "po-calculus reduction is not certified for this path query."
                    ),
                    variables=(variable,),
                    metadata={"reason": "post_treatment_conditioning"},
                )
            )
    return tuple(witnesses)


def _merge_distribution_refs(
    *groups: tuple[DistributionRef, ...] | list[DistributionRef],
) -> tuple[DistributionRef, ...]:
    merged: dict[str, DistributionRef] = {}
    for group in groups:
        for ref in group:
            key = json.dumps(ref.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
            merged[key] = ref
    return tuple(merged[key] for key in sorted(merged))


def _node_path_labels(query: PathSpecificQuery) -> dict[str, set[str]]:
    labels: dict[str, set[str]] = defaultdict(set)
    for label, paths in (("active", query.active_paths), ("frozen", query.fixed_paths)):
        for path in paths:
            for node in path[1:-1]:
                labels[node].add(label)
    return labels


def _directed_parents_by_node(graph: CausalGraphModel) -> dict[str, set[str]]:
    parents: dict[str, set[str]] = {node: set() for node in graph.nodes}
    for src, dst in extract_directed_edges(graph):
        parents.setdefault(dst, set()).add(src)
    return parents


def _reachable_avoiding_node(
    graph: CausalGraphModel,
    *,
    start: str,
    target: str,
    forbidden: str,
) -> bool:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for src, dst in extract_directed_edges(graph):
        adjacency[src].append(dst)
    stack = [start]
    seen: set[str] = set()
    while stack:
        node = stack.pop()
        if node in seen or node == forbidden:
            continue
        seen.add(node)
        if node == target:
            return True
        stack.extend(adjacency.get(node, ()))
    return False


def _district_factor_plan(
    *,
    district: tuple[str, ...],
    parents_by_node: dict[str, set[str]],
    frontier: tuple[tuple[str, str, Literal["active", "frozen"]], ...],
    node_labels: dict[str, set[str]],
) -> PathSpecificDistrictFactor:
    frontier_assignments = tuple(
        sorted(item for item in frontier if item[1] in district)
    )
    labels = {
        assignment[2]
        for assignment in frontier_assignments
    }
    labels.update(label for node in district for label in node_labels.get(node, ()))
    if "active" in labels and "frozen" in labels:
        district_label = PathSpecificDistrictLabel.MIXED
    elif "active" in labels:
        district_label = PathSpecificDistrictLabel.ACTIVE
    elif "frozen" in labels:
        district_label = PathSpecificDistrictLabel.FROZEN
    else:
        district_label = PathSpecificDistrictLabel.NATURAL
    parents = sorted(
        {
            parent
            for node in district
            for parent in parents_by_node.get(node, set())
            if parent not in district
        }
    )
    return PathSpecificDistrictFactor(
        district=district,
        label=district_label,
        parents=tuple(parents),
        frontier_assignments=frontier_assignments,
        local_width_bound=max(1, len(district), len(frontier_assignments)),
    )


def _recanting_witnesses(
    graph: CausalGraphModel,
    query: PathSpecificQuery,
    district_partition: tuple[tuple[str, ...], ...],
) -> tuple[PathSpecificWitness, ...]:
    node_labels = _node_path_labels(query)
    witnesses: list[PathSpecificWitness] = []
    for node, labels in sorted(node_labels.items()):
        if {"active", "frozen"}.issubset(labels):
            witnesses.append(
                PathSpecificWitness(
                    kind=PathSpecificWitnessKind.RECANTING_WITNESS,
                    detail=(
                        f"Node {node} lies on both active and frozen treatment paths."
                    ),
                    variables=(node,),
                )
            )
    active_internal = {
        node
        for path in query.active_paths
        for node in path[1:-1]
    }
    frozen_internal = {
        node
        for path in query.fixed_paths
        for node in path[1:-1]
    }
    for node in sorted(active_internal | frozen_internal):
        active_bypass = bool(query.fixed_paths) and any(
            node not in path[1:-1] for path in query.fixed_paths
        )
        frozen_bypass = bool(query.active_paths) and any(
            node not in path[1:-1] for path in query.active_paths
        )
        if (
            node in active_internal
            and active_bypass
            and _reachable_avoiding_node(
                graph,
                start=query.treatment,
                target=query.outcome,
                forbidden=node,
            )
            and not any(
                item.kind is PathSpecificWitnessKind.RECANTING_WITNESS
                and item.variables == (node,)
                for item in witnesses
            )
        ):
            witnesses.append(
                PathSpecificWitness(
                    kind=PathSpecificWitnessKind.RECANTING_WITNESS,
                    detail=(
                        f"Node {node} is bypassed by an alternate frozen path from "
                        f"{query.treatment} to {query.outcome}."
                    ),
                    variables=(node,),
                    metadata={"bypass_type": "frozen"},
                )
            )
        if (
            node in frozen_internal
            and frozen_bypass
            and _reachable_avoiding_node(
                graph,
                start=query.treatment,
                target=query.outcome,
                forbidden=node,
            )
            and not any(
                item.kind is PathSpecificWitnessKind.RECANTING_WITNESS
                and item.variables == (node,)
                for item in witnesses
            )
        ):
            witnesses.append(
                PathSpecificWitness(
                    kind=PathSpecificWitnessKind.RECANTING_WITNESS,
                    detail=(
                        f"Node {node} is bypassed by an alternate active path from "
                        f"{query.treatment} to {query.outcome}."
                    ),
                    variables=(node,),
                    metadata={"bypass_type": "active"},
                )
            )
    for district in district_partition:
        district_labels = {
            label
            for node in district
            for label in node_labels.get(node, set())
        }
        if len(district) > 1 and {"active", "frozen"}.issubset(district_labels):
            witnesses.append(
                PathSpecificWitness(
                    kind=PathSpecificWitnessKind.RECANTING_DISTRICT,
                    detail=(
                        "A bidirected district carries both active and frozen treatment "
                        "labels, so district-local path semantics are inconsistent."
                    ),
                    district=district,
                    variables=district,
                    metadata={"district_labels": sorted(district_labels)},
                )
            )
    return tuple(witnesses)


def _sort_district_factors(
    graph: CausalGraphModel,
    factors: list[PathSpecificDistrictFactor],
) -> tuple[PathSpecificDistrictFactor, ...]:
    try:
        order = {node: index for index, node in enumerate(topological_order(graph))}
    except ValueError:
        return tuple(sorted(factors, key=lambda item: item.district))
    return tuple(
        sorted(
            factors,
            key=lambda item: min(order.get(node, 10**9) for node in item.district),
        )
    )


def _compiled_ast(
    *,
    query_str: str,
    treatment: str,
    outcome: str,
    relevant_nodes: tuple[str, ...],
    conditioning: tuple[str, ...],
    district_factors: tuple[PathSpecificDistrictFactor, ...],
    dataset_ref: str | None,
    experimental_labels: frozenset[PathSpecificDistrictLabel] = frozenset(),
    experimental_dataset_ref: str | None = None,
) -> EstimandAST:
    factor_nodes = []
    for factor in district_factors:
        domain = (
            DistributionDomain.EXPERIMENTAL
            if factor.label in experimental_labels
            else DistributionDomain.SOURCE
        )
        factor_dataset_ref = (
            experimental_dataset_ref
            if domain is DistributionDomain.EXPERIMENTAL and experimental_dataset_ref is not None
            else dataset_ref
        )
        base = DistributionRef(
            domain=domain,
            variables=factor.district,
            conditioning=factor.parents,
            dataset_ref=factor_dataset_ref,
        )
        if factor.frontier_assignments:
            wrapped = EdgeInterventionNode(
                assignments=tuple(
                    EdgeInterventionAssignment(
                        source=src,
                        target=dst,
                        value_expr=(
                            "active_treatment"
                            if label == "active"
                            else "reference_treatment"
                        ),
                    )
                    for src, dst, label in factor.frontier_assignments
                ),
                inner_node=base,
                domain=domain,
                dataset_ref=factor_dataset_ref,
            )
            factor_nodes.append(wrapped)
        else:
            factor_nodes.append(base)
    if len(factor_nodes) == 1:
        root = factor_nodes[0]
    else:
        root = ProductNode(factors=tuple(factor_nodes))
    sum_vars = tuple(
        sorted(
            node
            for node in relevant_nodes
            if node not in {treatment, outcome, *conditioning}
        )
    )
    if sum_vars:
        root = SumNode(summation_vars=sum_vars, operand=root)
    if conditioning:
        root = ConditionalInterventionNode(
            treatment=treatment,
            outcome=outcome,
            condition_vars=conditioning,
            inner_do_node=root,
            dataset_ref=dataset_ref,
        )
    return EstimandAST(
        query_str=query_str,
        root=root,
        treatment=treatment,
        outcome=outcome,
        all_variables=tuple(sorted(relevant_nodes)),
        identification_method="path_specific_compiled",
    )


def _resolve_outcome_support(
    graph: CausalGraphModel,
    *,
    outcome: str,
    explicit_support: tuple[float, float] | None = None,
) -> tuple[float, float] | None:
    if explicit_support is not None:
        return explicit_support
    metadata = dict(graph.metadata or {})
    raw = metadata.get("outcome_support")
    candidate: Any = None
    if isinstance(raw, dict):
        candidate = raw.get(outcome)
    elif raw is not None:
        candidate = raw
    if not isinstance(candidate, (tuple, list)) or len(candidate) != 2:
        return None
    lower = float(candidate[0])
    upper = float(candidate[1])
    if lower > upper:
        return None
    return (lower, upper)


def _support_bounds_bundle(
    *,
    graph: CausalGraphModel,
    outcome: str,
    support: tuple[float, float] | None,
    metadata: dict[str, Any] | None = None,
) -> BoundsBundle | None:
    resolved = _resolve_outcome_support(graph, outcome=outcome, explicit_support=support)
    if resolved is None:
        return None
    lower, upper = resolved
    partial = PartialIdentificationResult(
        method=BoundMethod.MANSKI,
        lower_bound=lower - upper,
        upper_bound=upper - lower,
        confidence=1.0,
        assumptions_used=[f"{outcome} in [{lower}, {upper}]"],
        display_label="Support-implied path-specific bounds",
        bounds_type="manski",
    )
    return bounds_bundle_from_partial_identification_result(
        partial,
        estimand_type="path_specific_effect",
        warnings=[
            "Point identification failed; returned support-implied outer bounds.",
        ],
        metadata=dict(metadata or {}),
    )


def _surrogate_experimental_ref(
    available_experimental_distributions: tuple[str, ...],
) -> str | None:
    if len(available_experimental_distributions) == 1:
        return available_experimental_distributions[0]
    return None


def identify_path_specific(
    *,
    graph: CausalGraphModel,
    intervention: PathIntervention,
    outcome: str,
    query_str: str,
    dataset_ref: str | None = None,
    conditioning: tuple[str, ...] = (),
    available_experimental_distributions: tuple[str, ...] = (),
    width_budget: int | None = None,
    outcome_support: tuple[float, float] | None = None,
) -> PathSpecificIdentificationReport:
    """Return a typed path-specific identification decision.

    The routine is intentionally conservative. Exact point identification is
    emitted only when:

    - the graph class is supported (DAG/ADMG, acyclic directed part);
    - the path policy is edge-consistent;
    - no recanting witness / district conflict is detected;
    - the base total effect is observationally identifiable;
    - the intrinsic district/frontier width stays within the declared budget.
    """

    if graph.graph_type not in {GraphType.DAG, GraphType.ADMG}:
        dummy_query = PathSpecificQuery(
            treatment=intervention.active_paths[0][0] if intervention.active_paths else "path",
            outcome=outcome,
            active_paths=intervention.active_paths,
            fixed_paths=intervention.frozen_paths,
        )
        return PathSpecificIdentificationReport(
            mode=PathSpecificDecisionMode.BLOCKED_WITH_WITNESS,
            treatment=dummy_query.treatment,
            outcome=outcome,
            semantic_query=dummy_query,
            witnesses=(
                PathSpecificWitness(
                    kind=PathSpecificWitnessKind.UNSUPPORTED_GRAPH_SEMANTICS,
                    detail=(
                        "Path-specific proof backend currently supports only DAG/ADMG inputs."
                    ),
                    metadata={"graph_type": graph.graph_type.value},
                ),
            ),
            proof_trace=(
                "path_id_scale: rejected graph outside DAG/ADMG coverage",
            ),
            constructive_message=(
                "Reduce the query to a DAG/ADMG view or use a counterfactual backend "
                "with explicit support for the graph class."
            ),
            metadata={"graph_type": graph.graph_type.value},
        )

    normalized_conditioning = tuple(dict.fromkeys(conditioning))
    treatment, query = _normalize_path_intervention(
        intervention,
        outcome=outcome,
        conditioning=normalized_conditioning,
    )
    policy_hash = _path_policy_hash(query)
    proof_trace: list[str] = [
        "path_id_scale: normalized path intervention into canonical policy",
    ]
    fallback_trace: list[str] = []
    conditioning_witnesses = _conditioning_witnesses(
        graph,
        treatment=treatment,
        outcome=outcome,
        conditioning=query.conditioning,
    )
    if conditioning_witnesses:
        return PathSpecificIdentificationReport(
            mode=PathSpecificDecisionMode.BLOCKED_WITH_WITNESS,
            treatment=treatment,
            outcome=outcome,
            semantic_query=query,
            witnesses=conditioning_witnesses,
            proof_trace=tuple(proof_trace),
            fallback_trace=("path_id_scale: blocked on unsupported conditioning pattern",),
            constructive_message=(
                "Restrict conditioning to pre-treatment variables or route the query "
                "through a counterfactual backend with explicit post-treatment support."
            ),
            metadata={
                "path_policy_hash": policy_hash,
                "conditioning": list(query.conditioning),
            },
        )
    if query.conditioning:
        proof_trace.append(
            "path_id_scale: certified pre-treatment conditioning for IDC-style reduction"
        )

    edge_conflicts = _edge_conflicts(query)
    if edge_conflicts:
        return PathSpecificIdentificationReport(
            mode=PathSpecificDecisionMode.BLOCKED_WITH_WITNESS,
            treatment=treatment,
            outcome=outcome,
            semantic_query=query,
            witnesses=tuple(edge_conflicts),
            proof_trace=tuple(proof_trace),
            fallback_trace=("path_id_scale: edge inconsistency detected",),
            constructive_message=(
                "Make each treatment edge either active or frozen, but not both, "
                "before requesting a path-specific effect."
            ),
            metadata={"path_policy_hash": policy_hash},
        )

    subgraph, ancestral_nodes, relevant_nodes = _relevant_subgraph(
        graph,
        treatment=treatment,
        outcome=outcome,
        query=query,
    )
    proof_trace.append(
        "path_id_scale: restricted to ancestral path-relevant ADMG subgraph"
    )
    frontier = _frontier_assignments(query)
    district_partition = tuple(tuple(sorted(item)) for item in districts(subgraph))
    parents_by_node = _directed_parents_by_node(subgraph)
    node_labels = _node_path_labels(query)
    district_factors = _sort_district_factors(
        subgraph,
        [
            _district_factor_plan(
                district=district,
                parents_by_node=parents_by_node,
                frontier=frontier,
                node_labels=node_labels,
            )
            for district in district_partition
        ],
    )
    intrinsic_width_bound = max(
        1,
        *(factor.local_width_bound for factor in district_factors),
    )
    compilation = PathSpecificCompilationPlan(
        path_policy_hash=policy_hash,
        relevant_nodes=relevant_nodes,
        ancestral_nodes=ancestral_nodes,
        treatment_frontier=frontier,
        district_partition=district_partition,
        district_factors=district_factors,
        intrinsic_width_bound=intrinsic_width_bound,
    )

    if width_budget is not None and intrinsic_width_bound > width_budget:
        bounds_bundle = _support_bounds_bundle(
            graph=graph,
            outcome=outcome,
            support=outcome_support,
            metadata={
                "path_policy_hash": policy_hash,
                "blocking_witness": "width_budget_exceeded",
                "intrinsic_width_bound": intrinsic_width_bound,
                "width_budget": width_budget,
            },
        )
        witness = PathSpecificWitness(
            kind=PathSpecificWitnessKind.WIDTH_BUDGET_EXCEEDED,
            detail=(
                f"Intrinsic district/frontier width {intrinsic_width_bound} exceeds "
                f"the configured budget {width_budget}."
            ),
            metadata={
                "intrinsic_width_bound": intrinsic_width_bound,
                "width_budget": width_budget,
            },
        )
        fallback_trace.append("path_id_scale: width-aware fallback selected")
        return PathSpecificIdentificationReport(
            mode=(
                PathSpecificDecisionMode.BOUNDED
                if bounds_bundle is not None
                else PathSpecificDecisionMode.BLOCKED_WITH_WITNESS
            ),
            treatment=treatment,
            outcome=outcome,
            semantic_query=query,
            compilation_plan=compilation,
            witnesses=(witness,),
            bounds_bundle=bounds_bundle,
            proof_trace=tuple(proof_trace),
            fallback_trace=tuple(fallback_trace),
            constructive_message=(
                "Simplify the path policy, tighten the relevant subgraph, or increase the "
                "width budget if exact compilation is required."
            ),
            metadata={
                "path_policy_hash": policy_hash,
                "intrinsic_width_bound": intrinsic_width_bound,
                "width_budget": width_budget,
            },
        )

    witnesses = _recanting_witnesses(subgraph, query, district_partition)
    if witnesses:
        bounds_bundle = _support_bounds_bundle(
            graph=graph,
            outcome=outcome,
            support=outcome_support,
            metadata={
                "path_policy_hash": policy_hash,
                "blocking_witness": witnesses[0].kind.value,
            },
        )
        fallback_trace.append("path_id_scale: recanting conflict detected")
        return PathSpecificIdentificationReport(
            mode=(
                PathSpecificDecisionMode.BOUNDED
                if bounds_bundle is not None
                else PathSpecificDecisionMode.BLOCKED_WITH_WITNESS
            ),
            treatment=treatment,
            outcome=outcome,
            semantic_query=query,
            compilation_plan=compilation,
            witnesses=witnesses,
            bounds_bundle=bounds_bundle,
            proof_trace=tuple(
                [
                    *proof_trace,
                    "path_id_scale: recanting witness/district screening failed",
                ]
            ),
            fallback_trace=tuple(fallback_trace),
            constructive_message=(
                "Collect mediator-channel experiments, relax the path policy, or use "
                "bounds instead of a point-identified path-specific estimand."
            ),
            metadata={"path_policy_hash": policy_hash},
        )

    if query.conditioning:
        base_id = idc_algorithm(
            treatment=frozenset({treatment}),
            outcome=frozenset({outcome}),
            conditions=frozenset(query.conditioning),
            graph=subgraph,
            dataset_ref=dataset_ref,
        )
    else:
        base_id = id_algorithm(
            treatment=frozenset({treatment}),
            outcome=frozenset({outcome}),
            graph=subgraph,
            dataset_ref=dataset_ref,
        )
    if base_id.status is not IdentificationStatus.IDENTIFIED:
        required = tuple(base_id.required_distributions)
        fallback_trace.append("path_id_scale: base interventional ID failed")
        if available_experimental_distributions:
            surrogate_compiled = _compiled_ast(
                query_str=query_str,
                treatment=treatment,
                outcome=outcome,
                relevant_nodes=relevant_nodes,
                conditioning=query.conditioning,
                district_factors=district_factors,
                dataset_ref=dataset_ref,
                experimental_labels=frozenset(
                    {
                        PathSpecificDistrictLabel.ACTIVE,
                        PathSpecificDistrictLabel.FROZEN,
                        PathSpecificDistrictLabel.MIXED,
                    }
                ),
                experimental_dataset_ref=_surrogate_experimental_ref(
                    available_experimental_distributions
                ),
            )
            surrogate_required = _merge_distribution_refs(
                tuple(surrogate_compiled.collect_distribution_refs()),
                tuple(required),
            )
            compilation = compilation.model_copy(
                update={
                    "compiled_estimand_ast": surrogate_compiled,
                    "required_distributions": surrogate_required,
                }
            )
            witness = PathSpecificWitness(
                kind=PathSpecificWitnessKind.TOTAL_EFFECT_NOT_IDENTIFIED,
                detail=(
                    "Observational identification failed on the relevant ADMG, so "
                    "the path query requires surrogate experimental factors."
                ),
                variables=(treatment, outcome),
                metadata={"base_identification_status": base_id.status.value},
            )
            return PathSpecificIdentificationReport(
                mode=PathSpecificDecisionMode.EXACT_WITH_EXPERIMENTS,
                treatment=treatment,
                outcome=outcome,
                semantic_query=query,
                compilation_plan=compilation,
                witnesses=(witness,),
                required_distributions=compilation.required_distributions,
                proof_trace=tuple(
                    [
                        *proof_trace,
                        "path_id_scale: compiled hybrid source/experimental path formula",
                        *(
                            [
                                "path_id_scale: wrapped hybrid path estimand in ConditionalInterventionNode"
                            ]
                            if query.conditioning
                            else []
                        ),
                    ]
                ),
                fallback_trace=tuple(fallback_trace),
                constructive_message=(
                    "Observational point identification failed, but declared surrogate "
                    "experiments may rescue the nested counterfactual query."
                ),
                metadata={
                    "path_policy_hash": policy_hash,
                    "available_experimental_distributions": list(
                        available_experimental_distributions
                    ),
                    "experimental_binding_status": (
                        "single_ref_bound"
                        if _surrogate_experimental_ref(
                            available_experimental_distributions
                        )
                        is not None
                        else "unbound_required"
                    ),
                    "base_identification_status": base_id.status.value,
                },
            )
        bounds_bundle = _support_bounds_bundle(
            graph=graph,
            outcome=outcome,
            support=outcome_support,
            metadata={
                "path_policy_hash": policy_hash,
                "base_identification_status": base_id.status.value,
            },
        )
        witness = PathSpecificWitness(
            kind=PathSpecificWitnessKind.TOTAL_EFFECT_NOT_IDENTIFIED,
            detail=(
                "The corresponding interventional total effect is not observationally "
                "identified on the relevant ADMG subgraph."
            ),
            variables=(treatment, outcome),
            metadata={"base_identification_status": base_id.status.value},
        )
        return PathSpecificIdentificationReport(
            mode=(
                PathSpecificDecisionMode.BOUNDED
                if bounds_bundle is not None
                else PathSpecificDecisionMode.BLOCKED_WITH_WITNESS
            ),
            treatment=treatment,
            outcome=outcome,
            semantic_query=query,
            compilation_plan=compilation,
            witnesses=(witness,),
            required_distributions=required,
            bounds_bundle=bounds_bundle,
            proof_trace=tuple(proof_trace),
            fallback_trace=tuple(fallback_trace),
            constructive_message=(
                "Provide the missing experimental distributions or accept partial "
                "identification via bounds."
            ),
            metadata={
                "path_policy_hash": policy_hash,
                "base_identification_status": base_id.status.value,
            },
        )

    compiled = _compiled_ast(
        query_str=query_str,
        treatment=treatment,
        outcome=outcome,
        relevant_nodes=relevant_nodes,
        conditioning=query.conditioning,
        district_factors=district_factors,
        dataset_ref=dataset_ref,
    )
    compiled_required = _merge_distribution_refs(
        tuple(compiled.collect_distribution_refs()),
        tuple(base_id.required_distributions),
    )
    compilation = compilation.model_copy(
        update={
            "compiled_estimand_ast": compiled,
            "required_distributions": compiled_required,
        }
    )
    proof_trace.extend(
        [
            "path_id_scale: recanting screening passed",
            "path_id_scale: compiled district-local symbolic plan",
        ]
    )
    if query.conditioning:
        proof_trace.append(
            "path_id_scale: wrapped compiled path estimand in ConditionalInterventionNode"
        )
    return PathSpecificIdentificationReport(
        mode=PathSpecificDecisionMode.EXACT_IDENTIFIED,
        treatment=treatment,
        outcome=outcome,
        semantic_query=query,
        compilation_plan=compilation,
        required_distributions=compilation.required_distributions,
        proof_trace=tuple(proof_trace),
        constructive_message=(
            "Exact identification succeeded via district-local path compilation."
        ),
        metadata={
            "path_policy_hash": policy_hash,
            "intrinsic_width_bound": intrinsic_width_bound,
            "conditioning": list(query.conditioning),
        },
    )


__all__ = ["identify_path_specific"]
