"""pag_completion — PAG orientation rules and validity checking.

All functions are pure (no mutation).  They accept CausalGraphModel and return
new CausalGraphModel instances.  Implements a subset of Zhang (2008) FCI
orientation rules R1–R3 sufficient for the PAG consensus pipeline.

Reference: Zhang, J. (2008). On the completeness of orientation rules for
           causal discovery in the presence of latent confounders and
           selection bias.  Artificial Intelligence 172(16-17), 1873–1896.

Functions
---------
extract_unshielded_triples  – list all (A, B, C) where A-B-C but A not adj C
cpdag_to_pag                – formal CPDAG → PAG upcast (undirected → CIRCLE-CIRCLE)
apply_pag_orientation_rules – Zhang R1–R3 until fixpoint
validate_pag                – semantic validity checks; returns list of violations
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel


# ---------------------------------------------------------------------------
# Unshielded triple detection
# ---------------------------------------------------------------------------


def extract_unshielded_triples(
    graph: CausalGraphModel,
) -> list[tuple[str, str, str]]:
    """Return all unshielded triples (A, B, C) where A-B-C but A not adjacent to C.

    A triple is *unshielded* iff:
      - A and B are adjacent (any edge between them)
      - B and C are adjacent (any edge between them)
      - A and C are NOT adjacent

    Both (A, B, C) and (C, B, A) are returned as distinct triples, since the
    orientation rules may apply differently depending on which end carries
    the arrowhead.
    """

    # Build adjacency set once
    adj_pairs: set[frozenset[str]] = set()
    for e in graph.edges:
        adj_pairs.add(frozenset({e.src, e.dst}))

    # Build per-node neighbor list
    neighbors: dict[str, list[str]] = {n: [] for n in graph.nodes}
    for e in graph.edges:
        if e.dst not in neighbors[e.src]:
            neighbors[e.src].append(e.dst)
        if e.src not in neighbors[e.dst]:
            neighbors[e.dst].append(e.src)

    results: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for b in graph.nodes:
        nbrs = neighbors[b]
        for i, a in enumerate(nbrs):
            for c in nbrs[i + 1 :]:
                if frozenset({a, c}) not in adj_pairs:
                    # Unshielded triple a-b-c
                    if (a, b, c) not in seen:
                        results.append((a, b, c))
                        seen.add((a, b, c))
                    if (c, b, a) not in seen:
                        results.append((c, b, a))
                        seen.add((c, b, a))

    return results


# ---------------------------------------------------------------------------
# CPDAG → PAG upcast
# ---------------------------------------------------------------------------


def cpdag_to_pag(cpdag: CausalGraphModel) -> CausalGraphModel:
    """Convert a CPDAG to PAG form for use in consensus mark merging.

    CPDAG semantics:
      TAIL-ARROW (→): identified causal direction
      TAIL-TAIL (—): undirected (direction unknown within equivalence class)

    PAG semantics:
      TAIL-ARROW (→): this direction holds in ALL DAGs in the equivalence class
      CIRCLE-CIRCLE (o-o): fully uncertain (could be →, ←, or ↔)

    Conversion rules:
      (TAIL, ARROW) → (TAIL, ARROW)   — identified direction, unchanged
      (ARROW, TAIL) → (ARROW, TAIL)   — reversed directed, unchanged
      (TAIL, TAIL)  → (CIRCLE, CIRCLE) — undirected becomes uncertain
      anything else → (CIRCLE, CIRCLE) — conservative fallback

    If the input is already a PAG, it is returned unchanged.
    """
    from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark, GraphType

    if cpdag.graph_type is GraphType.PAG:
        return cpdag

    new_edges: list[CausalEdge] = []
    for e in cpdag.edges:
        if (e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW) or (
            e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.TAIL
        ):
            # Identified direction — keep as-is
            new_edges.append(e)
        elif e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.TAIL:
            # Undirected CPDAG edge → fully uncertain PAG edge
            new_edges.append(
                e.model_copy(update={"mark_src": EdgeMark.CIRCLE, "mark_dst": EdgeMark.CIRCLE})
            )
        else:
            # Any other combination (shouldn't occur in valid CPDAG, but be conservative)
            new_edges.append(
                e.model_copy(update={"mark_src": EdgeMark.CIRCLE, "mark_dst": EdgeMark.CIRCLE})
            )

    return CausalGraphModel(
        schema_version=cpdag.schema_version,
        graph_type=GraphType.PAG,
        nodes=list(cpdag.nodes),
        edges=new_edges,
        discovery_method=cpdag.discovery_method,
        skg_version_id=cpdag.skg_version_id,
        pag_identification_policy=cpdag.pag_identification_policy,
        id_confidence_under_pag=None,
        metadata=dict(cpdag.metadata),
    )


# ---------------------------------------------------------------------------
# Internal helpers for orientation rule application
# ---------------------------------------------------------------------------


def _get_edge_marks(
    lookup: dict[tuple[str, str], CausalEdge],
    u: str,
    v: str,
) -> tuple | None:
    """Return (mark at u-end, mark at v-end) for the u-v edge, or None if absent.

    If edge (u, v) exists: return (mark_src, mark_dst).
    If edge (v, u) exists: return (mark_dst, mark_src)  — swapped to u's perspective.
    Otherwise: None.
    """
    if (u, v) in lookup:
        e = lookup[(u, v)]
        return (e.mark_src, e.mark_dst)
    if (v, u) in lookup:
        e = lookup[(v, u)]
        return (e.mark_dst, e.mark_src)
    return None


def _set_edge_marks(
    lookup: dict[tuple[str, str], CausalEdge],
    u: str,
    v: str,
    mark_at_u: object,
    mark_at_v: object,
) -> bool:
    """Update the u-v (or v-u) edge in lookup with new mark values.

    Returns True if a mark actually changed (used to count changed marks per
    iteration for the fixpoint check).
    """
    if (u, v) in lookup:
        e = lookup[(u, v)]
        if e.mark_src == mark_at_u and e.mark_dst == mark_at_v:
            return False
        lookup[(u, v)] = e.model_copy(update={"mark_src": mark_at_u, "mark_dst": mark_at_v})
        return True
    if (v, u) in lookup:
        e = lookup[(v, u)]
        # For the (v, u) entry, u-end is mark_dst and v-end is mark_src
        if e.mark_dst == mark_at_u and e.mark_src == mark_at_v:
            return False
        lookup[(v, u)] = e.model_copy(update={"mark_dst": mark_at_u, "mark_src": mark_at_v})
        return True
    return False


def _rebuild_graph(
    original: CausalGraphModel,
    lookup: dict[tuple[str, str], CausalEdge],
) -> CausalGraphModel:
    """Rebuild a CausalGraphModel from the mutable edge lookup."""
    from polisyos.ir.analytics.causal_graph import CausalGraphModel

    return CausalGraphModel(
        schema_version=original.schema_version,
        graph_type=original.graph_type,
        nodes=list(original.nodes),
        edges=list(lookup.values()),
        discovery_method=original.discovery_method,
        skg_version_id=original.skg_version_id,
        pag_identification_policy=original.pag_identification_policy,
        id_confidence_under_pag=original.id_confidence_under_pag,
        metadata=dict(original.metadata),
    )


# ---------------------------------------------------------------------------
# PAG orientation rules (Zhang 2008, R1–R3)
# ---------------------------------------------------------------------------


def apply_pag_orientation_rules(
    pag: CausalGraphModel,
    *,
    max_iter: int = 10,
) -> tuple[CausalGraphModel, list[str]]:
    """Apply Zhang (2008) PAG orientation rules R1–R3 until fixpoint.

    Iterates over unshielded triples and directed paths, resolving CIRCLE
    marks into TAIL or ARROW.  Stops when no mark changes occur in an
    iteration, or after *max_iter* passes.

    Parameters
    ----------
    pag      : input PAG (graph_type must be PAG)
    max_iter : maximum orientation passes before giving up

    Returns
    -------
    (oriented_pag, warnings)
        oriented_pag : new CausalGraphModel with CIRCLE marks resolved where possible
        warnings     : non-empty if max_iter was reached without convergence
    """
    from polisyos.ir.analytics.causal_graph import EdgeMark, GraphType

    if pag.graph_type is not GraphType.PAG:
        # Cannot apply PAG rules to a non-PAG; return unchanged
        return pag, [
            f"apply_pag_orientation_rules: graph_type={pag.graph_type.value}, expected PAG — skipping"
        ]

    # Build a mutable edge lookup keyed by canonical (src, dst) pairs
    lookup: dict[tuple[str, str], CausalEdge] = {(e.src, e.dst): e for e in pag.edges}

    current_graph = pag
    warnings: list[str] = []

    for iteration in range(max_iter):
        changed = 0

        # Refresh triple list from current state of graph
        triples = extract_unshielded_triples(current_graph)

        # ---------------------------------------------------------------
        # R1: Non-collider propagation
        # If α *→ β o-* γ and α not adjacent to γ, orient β → γ
        # ---------------------------------------------------------------
        for alpha, beta, gamma in triples:
            marks_ab = _get_edge_marks(lookup, alpha, beta)  # (mark@alpha, mark@beta)
            marks_bg = _get_edge_marks(lookup, beta, gamma)  # (mark@beta, mark@gamma)
            if marks_ab is None or marks_bg is None:
                continue
            # α *→ β: mark at β-end of α-β edge is ARROW
            if marks_ab[1] is not EdgeMark.ARROW:
                continue
            # β o-* γ: mark at β-end of β-γ edge is CIRCLE
            if marks_bg[0] is not EdgeMark.CIRCLE:
                continue
            # Orient β → γ
            if _set_edge_marks(lookup, beta, gamma, EdgeMark.TAIL, EdgeMark.ARROW):
                changed += 1

        # ---------------------------------------------------------------
        # R2: Acyclicity
        # If α → β → γ and α o-* γ, orient α → γ
        # ---------------------------------------------------------------
        # Collect all directed edges (TAIL, ARROW) from current lookup
        directed: list[tuple[str, str]] = [
            (src, dst)
            for (src, dst), e in lookup.items()
            if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW
        ]
        # Build forward adjacency for directed edges
        fwd_adj: dict[str, list[str]] = {n: [] for n in current_graph.nodes}
        for src, dst in directed:
            fwd_adj[src].append(dst)

        for alpha, gamma in [
            (u, v) for (u, v), e in lookup.items() if _get_edge_marks(lookup, u, v) is not None
        ]:
            marks_ag = _get_edge_marks(lookup, alpha, gamma)
            if marks_ag is None:
                continue
            # α o-* γ: mark at α-end is CIRCLE
            if marks_ag[0] is not EdgeMark.CIRCLE:
                continue
            # Look for intermediate β: α → β → γ
            for beta in fwd_adj.get(alpha, []):
                if beta == gamma:
                    continue
                if gamma in fwd_adj.get(beta, []):
                    # Found α → β → γ → orient α → γ
                    if _set_edge_marks(lookup, alpha, gamma, EdgeMark.TAIL, EdgeMark.ARROW):
                        changed += 1
                    break  # only need one such β

        # ---------------------------------------------------------------
        # R3: V-structure extension
        # If α *→ δ ←* γ (collider at δ), δ o-* β, α o-* β, γ o-* β,
        # α not adj γ, then orient δ → β.
        # ---------------------------------------------------------------
        # Build directed-children index for O(1) intersection in R3.
        # fwd_adj already maps parent → [children] from directed (TAIL→ARROW) edges.
        fwd_adj_set: dict[str, set[str]] = {k: set(v) for k, v in fwd_adj.items()}

        for alpha, beta, gamma in triples:
            # α not adj γ is guaranteed by unshielded triple
            # Check α o-* β: mark at α-end of α-β edge is CIRCLE
            marks_ab = _get_edge_marks(lookup, alpha, beta)
            marks_gb = _get_edge_marks(lookup, gamma, beta)
            if marks_ab is None or marks_gb is None:
                continue
            # α o-* β
            if marks_ab[0] is not EdgeMark.CIRCLE:
                continue
            # γ o-* β
            if marks_gb[0] is not EdgeMark.CIRCLE:
                continue

            # Candidate δ: nodes where α → δ AND γ → δ (intersection via adjacency index)
            children_alpha = fwd_adj_set.get(alpha, set())
            children_gamma = fwd_adj_set.get(gamma, set())
            common_children = children_alpha & children_gamma - {alpha, beta, gamma}

            for delta in common_children:
                marks_db = _get_edge_marks(lookup, delta, beta)  # (mark@delta, mark@beta)
                if marks_db is None:
                    continue
                # δ o-* β: mark at δ-end is CIRCLE
                if marks_db[0] is not EdgeMark.CIRCLE:
                    continue
                # Orient δ → β
                if _set_edge_marks(lookup, delta, beta, EdgeMark.TAIL, EdgeMark.ARROW):
                    changed += 1

        # Rebuild graph with updated edges for next iteration's triple detection
        current_graph = _rebuild_graph(pag, lookup)

        if changed == 0:
            break  # fixpoint reached
    else:
        # max_iter exhausted without convergence
        n_circles = sum(
            1
            for e in current_graph.edges
            if e.mark_src is EdgeMark.CIRCLE or e.mark_dst is EdgeMark.CIRCLE
        )
        warnings.append(
            f"pag_orientation_max_iter_reached: {n_circles} circle marks remain "
            f"after {max_iter} iterations"
        )

    return current_graph, warnings


# ---------------------------------------------------------------------------
# PAG validity checker
# ---------------------------------------------------------------------------


def validate_pag(pag: CausalGraphModel) -> list[str]:
    """Validate a PAG for formal correctness.

    Returns a list of human-readable violation strings.  An empty list means
    the PAG passes all checks.

    Checks performed:
      1. graph_type must be GraphType.PAG
      2. No almost-directed cycles: if a directed path α →…→ β exists,
         then any edge β *→ α (with ARROW at α-end) is forbidden.
      3. Ambiguous non-collider triples: for each unshielded triple (α, β, γ)
         that is not a collider (not both β-ends are ARROW), if both β-end
         marks are CIRCLE the triple is ambiguously oriented (informational).
    """
    from polisyos.foundry.methods.catalog.causal.admg_ops import has_directed_path
    from polisyos.ir.analytics.causal_graph import EdgeMark, GraphType

    violations: list[str] = []

    # Check 1: graph_type
    if pag.graph_type is not GraphType.PAG:
        violations.append(f"graph_type_not_pag: got {pag.graph_type.value}")
        return violations  # remaining checks assume PAG type

    # Check 2: almost-directed cycles
    # For each edge ending in ARROW at node α (i.e. some β *→ α):
    # if there is also a directed path α → … → β, that's an almost-directed cycle.
    for e in pag.edges:
        # The edge goes (e.src, e.dst); mark_dst is at e.dst-end
        if e.mark_dst is EdgeMark.ARROW:
            # Arrow pointing into e.dst from e.src side: e.src *→ e.dst
            # Check: is there a directed path from e.dst back to e.src?
            if has_directed_path(pag, e.dst, e.src):
                violations.append(f"almost_directed_cycle: {e.dst}->...-> {e.src} *-> {e.dst}")
        if e.mark_src is EdgeMark.ARROW:
            # Arrow pointing into e.src: e.dst *→ e.src
            if has_directed_path(pag, e.src, e.dst):
                violations.append(f"almost_directed_cycle: {e.src}->...-> {e.dst} *-> {e.src}")

    # Check 3: ambiguous non-collider triples (informational)
    triples = extract_unshielded_triples(pag)
    lookup: dict[tuple[str, str], CausalEdge] = {(e.src, e.dst): e for e in pag.edges}

    for alpha, beta, gamma in triples:
        marks_ab = _get_edge_marks(lookup, alpha, beta)  # (mark@alpha, mark@beta)
        marks_bg = _get_edge_marks(lookup, beta, gamma)  # (mark@beta, mark@gamma)
        if marks_ab is None or marks_bg is None:
            continue
        mark_at_beta_from_a = marks_ab[1]  # mark at β from the α-β edge
        mark_at_beta_from_g = marks_bg[0]  # mark at β from the β-γ edge

        # Collider: both β-ends are ARROW
        is_collider = (
            mark_at_beta_from_a is EdgeMark.ARROW and mark_at_beta_from_g is EdgeMark.ARROW
        )
        if not is_collider:
            # Non-collider or undecided; if both β-ends are CIRCLE → ambiguous
            if mark_at_beta_from_a is EdgeMark.CIRCLE and mark_at_beta_from_g is EdgeMark.CIRCLE:
                violations.append(f"ambiguous_noncollider_triple: ({alpha}, {beta}, {gamma})")

    # Deduplicate (almost-directed cycle violations may appear twice due to both
    # endpoints being checked)
    seen: set[str] = set()
    unique: list[str] = []
    for v in violations:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


__all__ = [
    "apply_pag_orientation_rules",
    "cpdag_to_pag",
    "extract_unshielded_triples",
    "validate_pag",
]
