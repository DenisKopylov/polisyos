"""admg_ops — pure graph algorithms for Acyclic Directed Mixed Graphs (ADMGs).

All functions are pure (no mutation) and operate on the existing CausalGraphModel
IR contract.  No NetworkX is used (Law G).  Internally we use plain Python dicts,
sets, and collections.deque for BFS / Kahn's algorithm.

Edge-mark conventions (from causal_graph.py EdgeMark enum):
    Directed edge (src → dst):  mark_src=TAIL,   mark_dst=ARROW
    Bidirected edge (src ↔ dst): mark_src=ARROW,  mark_dst=ARROW
    Undirected / PAG uncertain:  mark_src=CIRCLE, mark_dst=CIRCLE  (ignored by default)

These functions accept any CausalGraphModel (DAG, CPDAG, PAG) and interpret the
edge marks as above.  PAG-type graphs with ARROW/ARROW edges are treated as ADMGs.

Functions
---------
extract_directed_edges    – frozenset of (src, dst) tuples for all directed edges
extract_bidirected_edges  – frozenset of frozenset({u,v}) for all bidirected edges
ancestors                 – BFS upstream closure An(V) in G
descendants               – BFS downstream closure De(V) in G
do_operator               – mutilated graph G_{do(X)}: remove in-directed-edges to X
c_components              – c-component (district) decomposition via Union-Find
induced_subgraph          – subgraph on a node subset
m_separation              – m-separation for mixed graphs (Bayes Ball)
topological_order         – Kahn's algorithm (directed edges only)
"""

from __future__ import annotations

import hashlib
import weakref
from collections import deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel


# ---------------------------------------------------------------------------
# Shared caches for immutable graph instances
# ---------------------------------------------------------------------------


class CachedAdjacency:
    """One-pass adjacency pre-computation reused across graph primitives."""

    __slots__ = ("bi", "bidirected_edges", "circle_edges", "directed_edges", "fwd", "rev")

    def __init__(self, graph: CausalGraphModel) -> None:
        from polisyos.ir.analytics.causal_graph import EdgeMark

        fwd: dict[str, list[str]] = {n: [] for n in graph.nodes}
        rev: dict[str, list[str]] = {n: [] for n in graph.nodes}
        bi: dict[str, list[str]] = {n: [] for n in graph.nodes}
        dir_set: set[tuple[str, str]] = set()
        bi_set: set[frozenset[str]] = set()
        circle_edges: list[tuple[str, str]] = []

        for edge in graph.edges:
            if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
                fwd[edge.src].append(edge.dst)
                rev[edge.dst].append(edge.src)
                dir_set.add((edge.src, edge.dst))
            elif edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW:
                bi[edge.src].append(edge.dst)
                bi[edge.dst].append(edge.src)
                bi_set.add(frozenset({edge.src, edge.dst}))
            elif edge.mark_src is EdgeMark.CIRCLE or edge.mark_dst is EdgeMark.CIRCLE:
                circle_edges.append((edge.src, edge.dst))

        self.fwd = fwd
        self.rev = rev
        self.bi = bi
        self.directed_edges = frozenset(dir_set)
        self.bidirected_edges = frozenset(bi_set)
        self.circle_edges = tuple(circle_edges)


_ADJ_CACHE: dict[int, CachedAdjacency] = {}
_CC_CACHE: dict[int, tuple[frozenset[str], ...]] = {}
_GRAPH_REFS: dict[int, weakref.ReferenceType[Any]] = {}


def _purge_graph_cache(key: int) -> None:
    _ADJ_CACHE.pop(key, None)
    _CC_CACHE.pop(key, None)
    _GRAPH_REFS.pop(key, None)


def _ensure_cache_ref(graph: CausalGraphModel) -> None:
    key = id(graph)
    if key in _GRAPH_REFS:
        return

    def _cleanup(_: weakref.ReferenceType[Any], k: int = key) -> None:
        _purge_graph_cache(k)

    _GRAPH_REFS[key] = weakref.ref(graph, _cleanup)


def _get_cached_adjacency(graph: CausalGraphModel) -> CachedAdjacency:
    key = id(graph)
    cached = _ADJ_CACHE.get(key)
    if cached is not None:
        return cached
    _ensure_cache_ref(graph)
    adj = CachedAdjacency(graph)
    _ADJ_CACHE[key] = adj
    return adj


def _derived_graph_model(
    *,
    graph: CausalGraphModel,
    nodes: list[str],
    edges: list[CausalEdge],
) -> CausalGraphModel:
    """Construct a derived immutable graph without repeating full validation."""
    from polisyos.ir.analytics.causal_graph import CausalGraphModel

    return CausalGraphModel.model_construct(
        schema_version=graph.schema_version,
        graph_type=graph.graph_type,
        nodes=nodes,
        edges=edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata=dict(graph.metadata),
    )


# ---------------------------------------------------------------------------
# Edge extraction helpers
# ---------------------------------------------------------------------------


def extract_directed_edges(graph: CausalGraphModel) -> frozenset[tuple[str, str]]:
    """Return all directed edges as frozenset of (src, dst) pairs.

    A directed edge has mark_src=TAIL, mark_dst=ARROW.
    Lagged edges (edge.lag is not None and edge.lag > 0) are included.
    """
    return _get_cached_adjacency(graph).directed_edges


def extract_bidirected_edges(graph: CausalGraphModel) -> frozenset[frozenset[str]]:
    """Return all bidirected edges as frozenset of frozenset({u, v}).

    A bidirected (confounding) edge has mark_src=ARROW, mark_dst=ARROW,
    representing a latent common cause between src and dst.
    """
    return _get_cached_adjacency(graph).bidirected_edges


# ---------------------------------------------------------------------------
# Ancestor / descendant closure (BFS on directed edges)
# ---------------------------------------------------------------------------


def ancestors(
    graph: CausalGraphModel,
    variables: frozenset[str],
    *,
    include_self: bool = True,
) -> frozenset[str]:
    """Return An(variables) — all ancestors reachable via directed edges going *into* each node.

    Traversal goes *backward* along directed edges (parent → child reversed),
    i.e. we follow edges src→dst in reverse: dst→src.

    Parameters
    ----------
    graph:        input graph
    variables:    seed set
    include_self: if True (default), variables themselves are in the returned set
    """
    rev = _get_cached_adjacency(graph).rev

    visited: set[str] = set()
    queue: deque[str] = deque()
    for v in variables:
        if v not in visited:
            visited.add(v)
            queue.append(v)
    while queue:
        node = queue.popleft()
        for parent in rev.get(node, []):
            if parent not in visited:
                visited.add(parent)
                queue.append(parent)
    if not include_self:
        visited -= set(variables)
    return frozenset(visited)


def descendants(
    graph: CausalGraphModel,
    variables: frozenset[str],
    *,
    include_self: bool = True,
) -> frozenset[str]:
    """Return De(variables) — descendants reachable via outgoing directed edges."""
    fwd = _get_cached_adjacency(graph).fwd

    visited: set[str] = set()
    queue: deque[str] = deque()
    for v in variables:
        if v not in visited:
            visited.add(v)
            queue.append(v)
    while queue:
        node = queue.popleft()
        for child in fwd.get(node, []):
            if child not in visited:
                visited.add(child)
                queue.append(child)
    if not include_self:
        visited -= set(variables)
    return frozenset(visited)


# ---------------------------------------------------------------------------
# Mutilated graph (do-operator)
# ---------------------------------------------------------------------------


def do_operator(
    graph: CausalGraphModel,
    intervention_set: frozenset[str],
) -> CausalGraphModel:
    """Return the mutilated graph G_{\\overline{X}} after do(X = intervention_set).

    All directed edges *into* any node in intervention_set are removed.
    Bidirected edges (latent common causes) from nodes in X are KEPT — the latent
    variable is still present; only the mechanism is cut.

    Returns a new CausalGraphModel (immutable, since frozen=True).
    """
    from polisyos.ir.analytics.causal_graph import EdgeMark

    kept_edges = []
    for e in graph.edges:
        # Remove directed edges INTO intervention nodes
        if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW:
            if e.dst in intervention_set:
                continue  # cut
        kept_edges.append(e)

    return _derived_graph_model(
        graph=graph,
        nodes=list(graph.nodes),
        edges=kept_edges,
    )


# ---------------------------------------------------------------------------
# Graph mutilation helpers (named for do-calculus rule descriptions)
# ---------------------------------------------------------------------------


def remove_incoming_edges(
    graph: CausalGraphModel,
    nodes: frozenset[str],
) -> CausalGraphModel:
    """G_{X̄}: remove all incoming directed edges to nodes in *nodes*.

    This is the do-operator mutilation G_{do(X)}: cutting the mechanisms of
    variables in *nodes* by removing their incoming directed edges.

    Provided as a named alias for :func:`do_operator` so that do-calculus rule
    descriptions can use the standard notation explicitly.
    """
    return do_operator(graph, nodes)


def remove_outgoing_edges(
    graph: CausalGraphModel,
    nodes: frozenset[str],
) -> CausalGraphModel:
    """G_{Z̲}: remove all outgoing directed edges *from* nodes in *nodes*.

    Used to construct G_{X̄Z̲} for do-calculus Rule 2::

        G_{X̄Z̲} = remove_outgoing_edges(remove_incoming_edges(G, X), Z)

    Bidirected edges (latent common causes) are kept intact — they represent
    the existence of a latent common cause, not a mechanism to be cut.

    Returns a new CausalGraphModel (immutable, frozen=True).
    """
    from polisyos.ir.analytics.causal_graph import EdgeMark

    kept_edges = []
    for e in graph.edges:
        # Drop directed edges whose source is in the cut set
        if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW:
            if e.src in nodes:
                continue  # cut outgoing directed edge
        kept_edges.append(e)

    return _derived_graph_model(
        graph=graph,
        nodes=list(graph.nodes),
        edges=kept_edges,
    )


# ---------------------------------------------------------------------------
# C-components (districts) via Union-Find on bidirected edges
# ---------------------------------------------------------------------------


def c_components(graph: CausalGraphModel) -> list[frozenset[str]]:
    """Compute the c-component (district) decomposition of the graph.

    Two nodes are in the same c-component iff they are connected by a path
    composed entirely of bidirected (confounding) edges.

    Nodes with no bidirected edges each form singleton c-components.

    Returns list of frozensets (one per component), sorted largest-first.
    """
    key = id(graph)
    cached_components = _CC_CACHE.get(key)
    if cached_components is not None:
        return list(cached_components)

    _ensure_cache_ref(graph)
    bi_edges = extract_bidirected_edges(graph)

    # Union-Find with path compression
    parent: dict[str, str] = {n: n for n in graph.nodes}
    rank: dict[str, int] = dict.fromkeys(graph.nodes, 0)

    def find(x: str) -> str:
        root = x
        while parent[root] != root:
            root = parent[root]
        # path compression
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx == ry:
            return
        if rank[rx] < rank[ry]:
            rx, ry = ry, rx
        parent[ry] = rx
        if rank[rx] == rank[ry]:
            rank[rx] += 1

    for pair in bi_edges:
        u, v = tuple(pair)  # frozenset has exactly 2 elements
        union(u, v)

    # Collect components
    comp: dict[str, set[str]] = {}
    for node in graph.nodes:
        root = find(node)
        comp.setdefault(root, set()).add(node)

    result = sorted([frozenset(s) for s in comp.values()], key=len, reverse=True)
    _CC_CACHE[key] = tuple(result)
    return result


def districts(
    graph: CausalGraphModel,
    node_subset: frozenset[str] | None = None,
) -> list[frozenset[str]]:
    """Formal districts (Lee & Richardson 2006) in an ADMG.

    A district is a connected component of bidirected edges in the induced
    subgraph G[node_subset].  When node_subset is None this is equivalent to
    c_components() over all graph nodes.

    The key difference from c_components(): districts are parameterised by a
    node subset (typically an ancestral set), which matters for identification
    in ancestral Markov models where the relevant c-component structure is
    computed relative to a restricted vertex set.

    Parameters
    ----------
    graph       : the full ADMG / PAG
    node_subset : optional restriction; if None, uses all graph nodes
    """
    if node_subset is None:
        return c_components(graph)
    sub = induced_subgraph(graph, node_subset)
    return c_components(sub)


# ---------------------------------------------------------------------------
# Induced subgraph
# ---------------------------------------------------------------------------


def induced_subgraph(
    graph: CausalGraphModel,
    node_subset: frozenset[str],
) -> CausalGraphModel:
    """Return the subgraph induced by node_subset.

    Only nodes in node_subset and edges with both endpoints in node_subset
    are retained.  graph_type is preserved.
    """
    kept_nodes = [n for n in graph.nodes if n in node_subset]
    kept_edges = [e for e in graph.edges if e.src in node_subset and e.dst in node_subset]
    return _derived_graph_model(
        graph=graph,
        nodes=kept_nodes,
        edges=kept_edges,
    )


# ---------------------------------------------------------------------------
# m-separation (Bayes Ball algorithm for mixed graphs)
# ---------------------------------------------------------------------------


def m_separation(
    graph: CausalGraphModel,
    x_set: frozenset[str],
    y_set: frozenset[str],
    z_set: frozenset[str],
) -> bool:
    """Test m-separation: X ⊥⊥ Y | Z in the mixed graph G.

    Uses the Bayes Ball algorithm adapted for ADMGs (Richardson & Spirtes 2002).
    Returns True iff X and Y are m-separated by Z.

    This handles:
    - Directed edges (TAIL→ARROW): d-separation rules
    - Bidirected edges (ARROW↔ARROW): latent common cause paths

    CIRCLE marks (PAG uncertainty) are treated as both directed and bidirected
    (conservative: if either interpretation creates a path, not m-separated).
    """
    cached = _get_cached_adjacency(graph)

    # Build adjacency for path traversal
    # Each entry: (neighbor, is_parent_of_node, is_bidirected)
    adj: dict[str, list[tuple[str, bool, bool]]] = {n: [] for n in graph.nodes}
    for src, dst in cached.directed_edges:
        # src → dst: src is parent of dst
        adj[src].append((dst, False, False))
        adj[dst].append((src, True, False))
    for pair in cached.bidirected_edges:
        src, dst = tuple(pair)
        adj[src].append((dst, False, True))
        adj[dst].append((src, False, True))
    for src, dst in cached.circle_edges:
        # PAG uncertainty — add both directed and bidirected interpretations.
        adj[src].append((dst, False, False))
        adj[dst].append((src, True, False))
        adj[src].append((dst, False, True))
        adj[dst].append((src, False, True))

    # Ancestors of Z in the directed graph (for collider activation)
    an_z = ancestors(graph, z_set)

    # Bayes Ball reachability: (node, arrived_via_child)
    # arrived_via_child=True means we arrived at node coming from a child of node
    visited: set[tuple[str, bool]] = set()
    queue: deque[tuple[str, bool]] = deque()

    for x in x_set:
        # Start from x, not arriving from a child (i.e., top-down pass)
        state = (x, False)
        if state not in visited:
            visited.add(state)
            queue.append(state)

    while queue:
        node, via_child = queue.popleft()

        if node in y_set:
            return False  # found path → NOT m-separated

        for neighbor, is_parent, is_bidirected in adj[node]:
            if is_bidirected:
                # Bidirected edges are always active (unless... collider rules apply)
                # For ADMG: bidirected edge is active if neighbor not in Z
                # and if the "latent" activation passes through
                if neighbor not in z_set:
                    state = (neighbor, False)
                    if state not in visited:
                        visited.add(state)
                        queue.append(state)
            elif is_parent:
                # We arrived at node from its child; now going to a parent of node
                # This is a "v-structure" (collider) path: child → node ← parent
                # Collider is ACTIVE only if node (or descendant) in Z
                if node in z_set or node in an_z:
                    state = (neighbor, False)
                    if state not in visited:
                        visited.add(state)
                        queue.append(state)
            else:
                # We arrived at node from its parent; going to a child
                # OR we arrived via bidirected; going to child
                # Active iff node not in Z (not conditioned upon / not blocking)
                if node not in z_set:
                    state = (neighbor, True)
                    if state not in visited:
                        visited.add(state)
                        queue.append(state)

    return True  # no path found → m-separated


def d_separation(
    graph: CausalGraphModel,
    x_set: frozenset[str],
    y_set: frozenset[str],
    z_set: frozenset[str],
) -> bool:
    """d-separation for DAGs: X ⊥⊥ Y | Z in G.

    Wrapper over :func:`m_separation` that validates no bidirected edges exist.
    For mixed graphs (ADMGs, PAGs) use :func:`m_separation` directly.

    Raises
    ------
    ValueError
        If *graph* contains bidirected (ARROW↔ARROW) edges.
    """
    if extract_bidirected_edges(graph):
        raise ValueError(
            "d_separation() requires a pure DAG (no bidirected edges). "
            "Use m_separation() for ADMGs or graphs with latent common causes."
        )
    return m_separation(graph, x_set, y_set, z_set)


def markov_boundary(
    graph: CausalGraphModel,
    node: str,
) -> frozenset[str]:
    """Return the Markov boundary of *node*: parents ∪ children ∪ co-parents.

    The Markov boundary is the minimal set M such that::

        node ⊥⊥ (V \\ M \\ {node}) | M

    Operates on directed edges only (TAIL→ARROW marks).  Bidirected edges are
    not considered (use the full graph's m-separation oracle for that case).

    Parameters
    ----------
    graph : CausalGraphModel
    node  : target variable name

    Returns
    -------
    frozenset[str]
        Markov boundary members (node itself is excluded from the result).
    """
    dir_edges = extract_directed_edges(graph)

    parents: set[str] = set()
    children: set[str] = set()
    for src, dst in dir_edges:
        if dst == node:
            parents.add(src)
        if src == node:
            children.add(dst)

    # Co-parents: nodes that share at least one directed child with *node*
    co_parents: set[str] = set()
    for src, dst in dir_edges:
        if dst in children and src != node:
            co_parents.add(src)

    return frozenset(parents | children | co_parents)


def reachable_closure(
    graph: CausalGraphModel,
    query_vars: frozenset[str],
    intervened: frozenset[str],
    conditioning: frozenset[str] | None = None,
) -> frozenset[str]:
    """PAG-compatible Bayes Ball reachability closure.

    Returns all nodes reachable from *query_vars* after do(*intervened*),
    optionally conditioning on *conditioning*.

    CIRCLE marks are treated conservatively: each edge with a CIRCLE mark
    contributes both a directed AND a bidirected path entry, so the returned
    set is the union of reachable nodes across all DAGs in the PAG equivalence
    class.  This makes the function safe to use for PAG-ID feasibility checks
    (B3) where we must handle mark uncertainty.

    Parameters
    ----------
    graph       : the causal graph (DAG / CPDAG / PAG)
    query_vars  : seed variables to propagate from
    intervened  : variables in do(·); their incoming directed edges are removed
    conditioning: variables Z to condition on (affects collider activation)
    """
    from polisyos.ir.analytics.causal_graph import EdgeMark

    z_set: frozenset[str] = conditioning if conditioning is not None else frozenset()

    # Mutilated graph: remove incoming directed edges to intervened nodes
    g_mut = do_operator(graph, intervened)

    # Build adjacency for the mutilated graph — same structure as m_separation:
    # (neighbor, is_parent_of_current, is_bidirected)
    adj: dict[str, list[tuple[str, bool, bool]]] = {n: [] for n in g_mut.nodes}
    for e in g_mut.edges:
        if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW:
            adj[e.src].append((e.dst, False, False))
            adj[e.dst].append((e.src, True, False))
        elif e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.ARROW:
            adj[e.src].append((e.dst, False, True))
            adj[e.dst].append((e.src, False, True))
        elif e.mark_src is EdgeMark.CIRCLE or e.mark_dst is EdgeMark.CIRCLE:
            # Conservative: CIRCLE could be TAIL or ARROW → add both orientations
            adj[e.src].append((e.dst, False, False))
            adj[e.dst].append((e.src, True, False))
            adj[e.src].append((e.dst, False, True))
            adj[e.dst].append((e.src, False, True))

    an_z: frozenset[str] = ancestors(g_mut, z_set) if z_set else frozenset()

    # Bayes Ball state: (node, arrived_via_child)
    visited: set[tuple[str, bool]] = set()
    queue: deque[tuple[str, bool]] = deque()
    reachable: set[str] = set()

    for v in query_vars:
        if v in g_mut.nodes:
            state = (v, False)
            if state not in visited:
                visited.add(state)
                queue.append(state)
                reachable.add(v)

    while queue:
        node, via_child = queue.popleft()
        reachable.add(node)

        for neighbor, is_parent, is_bidirected in adj[node]:
            if is_bidirected:
                if neighbor not in z_set:
                    state = (neighbor, False)
                    if state not in visited:
                        visited.add(state)
                        queue.append(state)
            elif is_parent:
                # Arriving at node from its child → this is a collider position
                # Collider active only if node (or descendant) is conditioned upon
                if node in z_set or node in an_z:
                    state = (neighbor, False)
                    if state not in visited:
                        visited.add(state)
                        queue.append(state)
            else:
                # Arriving at node from its parent → non-collider / fork
                # Active iff node is not conditioned upon
                if node not in z_set:
                    state = (neighbor, True)
                    if state not in visited:
                        visited.add(state)
                        queue.append(state)

    return frozenset(reachable)


# ---------------------------------------------------------------------------
# Topological order (directed edges only, Kahn's algorithm)
# ---------------------------------------------------------------------------


def topological_order(graph: CausalGraphModel) -> list[str]:
    """Return a topological ordering of nodes using directed edges only.

    Uses Kahn's algorithm (same BFS pattern as _has_directed_cycle in causal_graph.py).
    Raises ValueError if the directed subgraph contains a cycle.

    Lagged edges (edge.lag > 0) are excluded (time-unrolled DAGs are acyclic in time
    but contemporaneous edges define the topological structure).
    """
    from polisyos.ir.analytics.causal_graph import EdgeMark

    indegree: dict[str, int] = dict.fromkeys(graph.nodes, 0)
    fwd: dict[str, list[str]] = {n: [] for n in graph.nodes}

    for e in graph.edges:
        if e.mark_src is not EdgeMark.TAIL or e.mark_dst is not EdgeMark.ARROW:
            continue
        if e.lag is not None and e.lag > 0:
            continue
        fwd[e.src].append(e.dst)
        indegree[e.dst] += 1

    queue: deque[str] = deque(n for n, d in indegree.items() if d == 0)
    # Deterministic order: sort queue entries for stable output
    queue = deque(sorted(queue))
    order: list[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        children = sorted(fwd[node])  # sorted for determinism
        for child in children:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if len(order) != len(graph.nodes):
        raise ValueError("Graph contains a directed cycle; topological_order requires a DAG.")
    return order


# ---------------------------------------------------------------------------
# Helper: build simple adjacency dict (directed edges only)
# ---------------------------------------------------------------------------


def _directed_adjacency(graph: CausalGraphModel) -> dict[str, list[str]]:
    """Build forward adjacency dict for directed edges (src → [children])."""
    adj: dict[str, list[str]] = {n: [] for n in graph.nodes}
    for src, dst in extract_directed_edges(graph):
        adj[src].append(dst)
    return adj


def tarjan_scc(graph: CausalGraphModel) -> list[frozenset[str]]:
    """Return strongly connected components of the directed subgraph.

    Components are sorted largest-first and then lexicographically for
    deterministic output.
    """
    adj = _directed_adjacency(graph)
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    components: list[frozenset[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlink[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for child in adj.get(node, []):
            if child not in indices:
                visit(child)
                lowlink[node] = min(lowlink[node], lowlink[child])
            elif child in on_stack:
                lowlink[node] = min(lowlink[node], indices[child])

        if lowlink[node] == indices[node]:
            component: list[str] = []
            while stack:
                popped = stack.pop()
                on_stack.remove(popped)
                component.append(popped)
                if popped == node:
                    break
            components.append(frozenset(component))

    for node in graph.nodes:
        if node not in indices:
            visit(node)

    return sorted(components, key=lambda comp: (-len(comp), tuple(sorted(comp))))


def _scc_label(component: frozenset[str]) -> str:
    if len(component) == 1:
        return next(iter(component))
    digest = hashlib.sha1("|".join(sorted(component)).encode("utf-8")).hexdigest()[:10]
    return f"SCC_{digest}"


def condense_graph(
    graph: CausalGraphModel,
    sccs: list[frozenset[str]],
) -> CausalGraphModel:
    """Collapse each SCC into a meta-node and preserve inter-component edges."""
    from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark, GraphType

    node_to_comp: dict[str, frozenset[str]] = {}
    condensed_nodes: list[str] = []
    comp_to_label: dict[frozenset[str], str] = {}
    for comp in sccs:
        label = _scc_label(comp)
        comp_to_label[comp] = label
        condensed_nodes.append(label)
        for node in comp:
            node_to_comp[node] = comp

    seen_directed: set[tuple[str, str]] = set()
    seen_bidirected: set[frozenset[str]] = set()
    condensed_edges: list[CausalEdge] = []

    for edge in graph.edges:
        src_comp = node_to_comp[edge.src]
        dst_comp = node_to_comp[edge.dst]
        src_label = comp_to_label[src_comp]
        dst_label = comp_to_label[dst_comp]
        if src_label == dst_label:
            continue

        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
            key = (src_label, dst_label)
            if key in seen_directed:
                continue
            seen_directed.add(key)
            condensed_edges.append(edge.model_copy(update={"src": src_label, "dst": dst_label}))
        elif edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW:
            key = frozenset({src_label, dst_label})
            if key in seen_bidirected:
                continue
            seen_bidirected.add(key)
            condensed_edges.append(edge.model_copy(update={"src": src_label, "dst": dst_label}))

    return CausalGraphModel.model_construct(
        schema_version=graph.schema_version,
        graph_type=GraphType.ADMG,
        nodes=condensed_nodes,
        edges=condensed_edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata={
            **dict(graph.metadata),
            "derived_view": "condensed_scc",
            "source_graph_nodes": list(graph.nodes),
            "source_graph_edges": len(graph.edges),
        },
    )


def has_directed_cycle(graph: CausalGraphModel) -> bool:
    """Return True when the directed subgraph contains a cycle."""
    try:
        topological_order(graph)
    except ValueError:
        return True
    return False


# ---------------------------------------------------------------------------
# PAG / CPDAG helpers used by pag_completion.py
# ---------------------------------------------------------------------------


def extract_undirected_edges(graph: CausalGraphModel) -> frozenset[frozenset[str]]:
    """Return TAIL-TAIL edges as frozenset of frozenset({u, v}).

    These are undirected edges as they appear in CPDAGs (directions unresolved
    within the Markov equivalence class).  They are *not* allowed in valid PAGs
    (uncertainty is represented as CIRCLE-CIRCLE there), so this function is
    primarily used by cpdag_to_pag() for the upcast step.
    """
    from polisyos.ir.analytics.causal_graph import EdgeMark

    result: set[frozenset[str]] = set()
    for e in graph.edges:
        if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.TAIL:
            result.add(frozenset({e.src, e.dst}))
    return frozenset(result)


def is_adjacent(graph: CausalGraphModel, a: str, b: str) -> bool:
    """Return True if any edge exists between a and b (either direction).

    O(|E|) scan.  For small graphs (< 200 nodes, < 10 000 edges) this is
    fast enough; for very large graphs callers should pre-build an adjacency
    set.
    """
    for e in graph.edges:
        if (e.src == a and e.dst == b) or (e.src == b and e.dst == a):
            return True
    return False


def has_directed_path(graph: CausalGraphModel, src: str, dst: str) -> bool:
    """Return True if a directed path src →…→ dst exists using TAIL→ARROW edges.

    BFS on directed edges (TAIL→ARROW), excluding lagged edges (lag > 0).
    A node is not considered reachable from itself (returns False for src == dst).
    """
    from polisyos.ir.analytics.causal_graph import EdgeMark

    if src == dst:
        return False

    fwd: dict[str, list[str]] = {n: [] for n in graph.nodes}
    for e in graph.edges:
        if (
            e.mark_src is EdgeMark.TAIL
            and e.mark_dst is EdgeMark.ARROW
            and (e.lag is None or e.lag == 0)
        ):
            fwd[e.src].append(e.dst)

    visited: set[str] = {src}
    queue: deque[str] = deque([src])
    while queue:
        node = queue.popleft()
        for child in fwd.get(node, []):
            if child == dst:
                return True
            if child not in visited:
                visited.add(child)
                queue.append(child)
    return False


# ---------------------------------------------------------------------------
# S-node (selection variable) graph operations for transportability
# ---------------------------------------------------------------------------


def augment_with_s_nodes(
    graph: CausalGraphModel,
    s_var_names: frozenset[str],
) -> CausalGraphModel:
    """Return a new graph augmented with selection nodes S_v → v for each v.

    For each variable name v in *s_var_names*, adds:
    - A node ``"S_" + v`` (if not already present)
    - A directed edge ``S_v → v`` (TAIL→ARROW, if not already present)

    The augmented graph preserves the base graph type for DAG/ADMG inputs and
    only keeps ``GraphType.PAG`` when the input graph is already a PAG. This
    avoids spurious PAG ambiguity in fully specified transport diagrams that
    contain no uncertain edge marks.

    Used by :func:`tr_algorithm` to encode selection diagrams as augmented
    graphs before running the ID algorithm.

    Parameters
    ----------
    graph       : base causal graph
    s_var_names : set of mechanism-shifted variable names (the *target* of each
                  S-node, not the S-node name itself)

    Returns
    -------
    CausalGraphModel
        New graph with S-nodes and edges added (original is unchanged).
    """
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

    existing_nodes = set(graph.nodes)
    existing_edge_pairs = {(e.src, e.dst) for e in graph.edges}

    extra_nodes: list[str] = []
    extra_edges: list[CausalEdge] = []

    for v in sorted(s_var_names):  # sorted for determinism
        s_name = f"S_{v}"
        if s_name not in existing_nodes:
            extra_nodes.append(s_name)
        if (s_name, v) not in existing_edge_pairs:
            extra_edges.append(
                CausalEdge(
                    src=s_name,
                    dst=v,
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                )
            )

    # Use full CausalGraphModel() constructor (not model_construct) because new
    # S-nodes and edges are added — Pydantic validation ensures they are well-formed.
    # This is acceptable: augment_with_s_nodes is not on the hot path (called once
    # during transportability setup, not during ID algorithm recursion).
    return CausalGraphModel(
        schema_version=graph.schema_version,
        graph_type=graph.graph_type if graph.graph_type is not None else GraphType.ADMG,
        nodes=list(graph.nodes) + extra_nodes,
        edges=list(graph.edges) + extra_edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata=dict(graph.metadata),
    )


def s_reachable(
    graph: CausalGraphModel,
    target_vars: frozenset[str],
    s_node_names: frozenset[str],
) -> frozenset[str]:
    """Return the subset of *target_vars* reachable from any S-node in *s_node_names*.

    Reachability is via directed OR bidirected edges (both mechanisms can
    propagate the effect of a mechanism shift).  This is used by the S-trimming
    lemma to determine which S-nodes actually have a path to the outcome set.

    Parameters
    ----------
    graph        : the (possibly augmented) causal graph
    target_vars  : the variables we want to check reachability to (e.g. outcome)
    s_node_names : set of S-node identifiers to propagate from (e.g. ``{"S_X", "S_Z"}``)

    Returns
    -------
    frozenset[str]
        Subset of *target_vars* that are reachable from at least one S-node.
    """
    # Build forward adjacency combining directed AND bidirected edges
    fwd: dict[str, set[str]] = {n: set() for n in graph.nodes}
    for src, dst in extract_directed_edges(graph):
        fwd[src].add(dst)
    for pair in extract_bidirected_edges(graph):
        u, v = tuple(pair)
        fwd[u].add(v)
        fwd[v].add(u)

    visited: set[str] = set()
    queue: deque[str] = deque()
    for s in s_node_names:
        if s in fwd and s not in visited:
            visited.add(s)
            queue.append(s)

    while queue:
        node = queue.popleft()
        for neighbor in fwd.get(node, set()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return frozenset(target_vars & visited)


def resolve_s_node_by_adjustment(
    graph: CausalGraphModel,
    s_var_name: str,
    adjustment_set: frozenset[str],
) -> CausalGraphModel:
    """Return a new graph with the S-node for *s_var_name* removed.

    Removes node ``"S_" + s_var_name`` and ALL its incident edges from *graph*.
    This is a pure structural operation — the caller is responsible for
    verifying that adjustment is valid (e.g. via m-separation) before calling.

    If ``"S_" + s_var_name`` is not present in the graph, the original graph is
    returned unchanged (no-op).

    Parameters
    ----------
    graph          : the augmented causal graph (with S-nodes)
    s_var_name     : the *target* variable name (not the S-node name; e.g. ``"X"``)
    adjustment_set : (unused by this function) kept for API clarity; callers
                     pass the Z set they used to justify the removal

    Returns
    -------
    CausalGraphModel
        New graph without the S-node and its edges (original is unchanged).
    """
    s_name = f"S_{s_var_name}"
    if s_name not in graph.nodes:
        return graph  # no-op

    kept_nodes = [n for n in graph.nodes if n != s_name]
    kept_edges = [e for e in graph.edges if e.src != s_name and e.dst != s_name]

    return _derived_graph_model(
        graph=graph,
        nodes=kept_nodes,
        edges=kept_edges,
    )


def project_to_subgraph(
    graph: CausalGraphModel,
    variable_subset: frozenset[str],
    *,
    keep_s_nodes: bool = True,
) -> CausalGraphModel:
    """Return the subgraph induced by *variable_subset*, optionally retaining S-nodes.

    Parameters
    ----------
    graph           : the (possibly augmented) causal graph
    variable_subset : the domain variables to project onto
    keep_s_nodes    : if True (default), all S-nodes (nodes prefixed with ``"S_"``)
                      that are in the original graph are also included in the
                      projection (transport-safe default).  If False, only the
                      variables in *variable_subset* are kept (clean observational
                      subgraph).

    Returns
    -------
    CausalGraphModel
        Induced subgraph on the effective subset.
    """
    if keep_s_nodes:
        s_node_names = frozenset(n for n in graph.nodes if n.startswith("S_"))
        effective_subset = variable_subset | s_node_names
    else:
        effective_subset = variable_subset

    return induced_subgraph(graph, effective_subset)


__all__ = [
    "extract_directed_edges",
    "extract_bidirected_edges",
    "extract_undirected_edges",
    "is_adjacent",
    "has_directed_path",
    "ancestors",
    "descendants",
    "tarjan_scc",
    "condense_graph",
    "has_directed_cycle",
    "do_operator",
    "remove_incoming_edges",
    "remove_outgoing_edges",
    "c_components",
    "districts",
    "induced_subgraph",
    "m_separation",
    "d_separation",
    "markov_boundary",
    "reachable_closure",
    "topological_order",
    # S-node / selection-variable graph operations (transportability)
    "augment_with_s_nodes",
    "s_reachable",
    "resolve_s_node_by_adjustment",
    "project_to_subgraph",
]
