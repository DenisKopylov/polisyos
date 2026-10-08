"""Exhaustive query checks for a finite static CPDAG completion profile.

This internal adapter reuses the maintained DAG g-formula on every consistent
DAG extension. It does not orient a PAG, infer graph authority, or compare
numerical estimates as a substitute for symbolic identification.
"""

from __future__ import annotations

import hashlib
from itertools import combinations, product
from typing import Any

from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.foundry.methods.catalog.causal._id_contracts import (
    IdentificationResult,
    IdentificationStatus,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark, GraphType

_PROFILE = "static_cpdag_consistent_extensions_at_most_four_nodes_v1"


def _colliders(arcs: set[tuple[str, str]], skeleton: set[frozenset[str]]) -> set[tuple[str, ...]]:
    colliders: set[tuple[str, ...]] = set()
    for centre in {dst for _, dst in arcs}:
        parents = sorted(src for src, dst in arcs if dst == centre)
        for left, right in combinations(parents, 2):
            if frozenset((left, right)) not in skeleton:
                colliders.add((left, centre, right))
    return colliders


def _consistent_extensions(graph: CausalGraphModel) -> tuple[list[CausalGraphModel], int]:
    """Enumerate the entire declared family, never a sample of its members."""
    if graph.graph_type is not GraphType.CPDAG or len(graph.nodes) > 4:
        raise ValueError("requires static CPDAG with at most four observed nodes")
    if "mgraph" in graph.metadata:
        raise ValueError("CPDAG declaration contradicts supplied MGraph contract")
    fixed: set[tuple[str, str]] = set()
    unresolved = []
    skeleton: set[frozenset[str]] = set()
    for edge in graph.edges:
        if edge.lag not in (None, 0):
            raise ValueError("temporal edges are outside the static completion profile")
        pair = frozenset((edge.src, edge.dst))
        if pair in skeleton:
            raise ValueError("parallel edges are outside the causally sufficient CPDAG profile")
        skeleton.add(pair)
        marks = (edge.mark_src, edge.mark_dst)
        if marks == (EdgeMark.TAIL, EdgeMark.ARROW):
            fixed.add((edge.src, edge.dst))
        elif marks == (EdgeMark.ARROW, EdgeMark.TAIL):
            fixed.add((edge.dst, edge.src))
        elif marks == (EdgeMark.TAIL, EdgeMark.TAIL):
            unresolved.append(edge)
        else:
            raise ValueError("requires fixed arrows or tail-tail CPDAG endpoints")
    known_colliders = _colliders(fixed, skeleton)
    extensions: list[CausalGraphModel] = []
    for choices in product((False, True), repeat=len(unresolved)):
        arcs = set(fixed)
        arcs.update(
            (edge.dst, edge.src) if reverse else (edge.src, edge.dst)
            for edge, reverse in zip(unresolved, choices, strict=True)
        )
        if _colliders(arcs, skeleton) != known_colliders:
            continue
        from polisyos.ir.analytics.causal_graph import CausalEdge

        try:
            extension = CausalGraphModel(
                graph_type=GraphType.DAG,
                nodes=list(graph.nodes),
                edges=[CausalEdge(src=src, dst=dst) for src, dst in sorted(arcs)],
                discovery_method="complete_consistent_cpdag_extension",
            )
        except ValueError:
            # The typed DAG constructor independently refuses directed cycles.
            continue
        extensions.append(extension)
    if not extensions:
        raise ValueError("no acyclic extension preserves fixed arrows and unshielded colliders")
    return extensions, 2 ** len(unresolved)


def _identify_partial_cpdag(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    dataset_ref: str | None,
    unsupported_query: bool,
) -> IdentificationResult:
    """Return a common functional or explicit conditional completion candidates."""
    from polisyos.foundry.methods.catalog.causal.admg_ops import descendants
    from polisyos.foundry.methods.catalog.causal.id_engine.core import _dag_g_formula
    from polisyos.ir.analytics.estimand import DistributionDomain

    query = f"P({','.join(sorted(outcome))}|do({','.join(sorted(treatment))}))"
    basis = {
        "profile": _PROFILE,
        "graph_payload_sha256": hashlib.sha256(
            to_canonical_bytes(graph.model_dump(mode="json"), spec=CanonSpec(forbid_floats=False))
        ).hexdigest(),
        "query": {"treatment": sorted(treatment), "outcome": sorted(outcome)},
        "scope": "declared static causally sufficient CPDAG; no source/assumption authority",
        "comparison": (
            "exact canonical equality or no directed treatment/outcome path in every completion "
            "is sufficient; inequality is conditional"
        ),
        "authority_eligible": False,
    }
    try:
        if (
            unsupported_query
            or len(treatment) != 1
            or len(outcome) != 1
            or treatment & outcome
            or not (treatment | outcome) <= set(graph.nodes)
        ):
            raise ValueError(
                "requires one disjoint treatment/outcome and ordinary unconditional do"
            )
        extensions, assignments = _consistent_extensions(graph)
    except ValueError as exc:
        return IdentificationResult(
            status=IdentificationStatus.PAG_AMBIGUOUS,
            estimand_ast=None,
            hedge_certificate=None,
            trace=[f"CPDAG completion query refused: {exc}"],
            required_distributions=[],
            query_str=query,
            algorithm_version=_PROFILE,
            metadata={
                "partial_graph_query": {
                    **basis,
                    "disposition": "unsupported",
                    "coverage": "not_established",
                    "limitation": str(exc),
                }
            },
        )
    results = [
        _dag_g_formula(
            treatment=treatment,
            outcome=outcome,
            graph=extension,
            available_vars=frozenset(extension.nodes),
            dataset_ref=dataset_ref,
            domain=DistributionDomain.SOURCE,
            depth=0,
            trace=[],
        )
        for extension in extensions
    ]
    candidates: list[dict[str, Any]] = []
    for extension, result in zip(extensions, results, strict=True):
        candidates.append(
            {
                "arcs": [[edge.src, edge.dst] for edge in extension.edges],
                "status": result.status.value,
                "estimand": result.estimand_ast.model_dump(mode="json")
                if result.estimand_ast is not None
                else None,
            }
        )
    canonical = [
        result.estimand_ast.canonical_bytes()
        if result.status is IdentificationStatus.IDENTIFIED and result.estimand_ast is not None
        else None
        for result in results
    ]
    common = canonical[0] is not None and all(value == canonical[0] for value in canonical)
    no_effect = all(not outcome & descendants(extension, treatment) for extension in extensions)
    common_ast = results[0].estimand_ast if common else None
    common_distributions = results[0].required_distributions if common else []
    if no_effect:
        # In every admitted DAG, intervention onX has no directed path toY.
        # Reuse the same exact g-formula on its observational marginal target.
        # This theorem does not depend on matching sampled numerical answers.
        marginal = _dag_g_formula(
            treatment=treatment,
            outcome=outcome,
            graph=CausalGraphModel(
                graph_type=GraphType.DAG, nodes=sorted(treatment | outcome), edges=[]
            ),
            available_vars=treatment | outcome,
            dataset_ref=dataset_ref,
            domain=DistributionDomain.SOURCE,
            depth=0,
            trace=[],
        )
        common = True
        common_ast = marginal.estimand_ast
        common_distributions = marginal.required_distributions
    limitation = (
        "Common functional only within the complete declared CPDAG family; "
        "source, graph assumptions and protected causal admission remain separate."
        if common
        else "Completion-specific functionals; no unconditional identification is emitted. "
        "Distinct symbolic forms are not a universal proof of functional nonequivalence."
    )
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED if common else IdentificationStatus.PAG_AMBIGUOUS,
        estimand_ast=common_ast,
        hedge_certificate=None,
        trace=[
            f"Exhausted {assignments} orientations; {len(extensions)} consistent DAG extensions",
            "Computed every maintained DAG g-formula; checked canonical equality and no-effect",
            limitation,
        ],
        required_distributions=common_distributions,
        query_str=query,
        algorithm_version=_PROFILE,
        metadata={
            "partial_graph_query": {
                **basis,
                "disposition": "common_functional" if common else "conditional",
                "coverage": "exhaustive_for_declared_profile",
                "orientation_assignments_checked": assignments,
                "admitted_completions": len(extensions),
                "all_completions_no_directed_effect": no_effect,
                "completions": candidates,
                "limitation": limitation,
            }
        },
    )


__all__: list[str] = []
