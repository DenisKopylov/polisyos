"""admg_ops — pure graph algorithms for Acyclic Directed Mixed Graphs (ADMGs).

All functions are pure (no mutation) and operate on the existing CausalGraphModel
IR contract.  No NetworkX is used (Law G).  Internally we use plain Python dicts,
sets, and collections.deque for BFS / Kahn's algorithm.

Edge-mark conventions (from causal_graph.py EdgeMark enum):
    Directed edge (src → dst):  mark_src=TAIL,   mark_dst=ARROW
    Bidirected edge (src ↔ dst): mark_src=ARROW,  mark_dst=ARROW
    Reverse directed storage:    mark_src=ARROW,  mark_dst=TAIL

Static causal primitives require fully resolved, contemporaneous directed or
bidirected edges. Unresolved endpoints and compact lagged relations are refused
before separation or graph surgery. Raw endpoint-inspection and orientation
utilities keep their separate structural purpose; they do not establish causal
identification for a partially oriented or temporal graph.

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
import json
from collections import OrderedDict, deque
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel


# ---------------------------------------------------------------------------
# Bounded content caches for canonical static graph profiles
# ---------------------------------------------------------------------------


class UnsupportedStaticADMGProfileError(ValueError):
    """A graph cannot enter the resolved static ADMG inference profile.

    This typed refusal is a limitation signal for higher-level consumers.
    Low-level static algorithms continue to raise a ValueError subtype.
    """

    limitation_code = "unsupported_static_admg_profile"

    def __init__(self, message: str, *, graph_type_label: str = "not_established") -> None:
        super().__init__(message)
        self.graph_type_label = graph_type_label


class PartialGraphCompletionSemanticsError(UnsupportedStaticADMGProfileError):
    """A partial-graph tag has no admitted completion semantics for scalar ID."""

    limitation_code = "partial_graph_completion_semantics_not_established"


class InvalidCausalGraphProfileError(UnsupportedStaticADMGProfileError):
    """The live graph cannot be rebuilt as its declared canonical IR profile."""

    limitation_code = "causal_graph_profile_invalid"


class CachedAdjacency:
    """Admit the resolved static profile and prepare its adjacency once."""

    __slots__ = (
        "bi",
        "bidirected_edges",
        "circle_edges",
        "content_key",
        "directed_edges",
        "fwd",
        "graph",
        "rev",
    )

    def __init__(self, graph: CausalGraphModel, content_key: str) -> None:
        from polisyos.ir.analytics.causal_graph import EdgeMark

        self.graph = graph
        self.content_key = content_key
        fwd: dict[str, list[str]] = {n: [] for n in graph.nodes}
        rev: dict[str, list[str]] = {n: [] for n in graph.nodes}
        bi: dict[str, list[str]] = {n: [] for n in graph.nodes}
        dir_set: set[tuple[str, str]] = set()
        bi_set: set[frozenset[str]] = set()
        circle_edges: list[tuple[str, str]] = []

        for edge in graph.edges:
            if edge.lag not in (None, 0):
                raise UnsupportedStaticADMGProfileError(
                    "Unsupported static ADMG profile: "
                    f"edge {edge.src!r}–{edge.dst!r} has lag={edge.lag!r}; "
                    "resolve the temporal graph before static causal inference."
                )
            if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
                fwd[edge.src].append(edge.dst)
                rev[edge.dst].append(edge.src)
                dir_set.add((edge.src, edge.dst))
            elif edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.TAIL:
                fwd[edge.dst].append(edge.src)
                rev[edge.src].append(edge.dst)
                dir_set.add((edge.dst, edge.src))
            elif edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW:
                bi[edge.src].append(edge.dst)
                bi[edge.dst].append(edge.src)
                bi_set.add(frozenset({edge.src, edge.dst}))
            else:
                raise UnsupportedStaticADMGProfileError(
                    "Unsupported static ADMG profile: "
                    f"edge {edge.src!r}–{edge.dst!r} has unresolved endpoints "
                    f"({edge.mark_src.value}, {edge.mark_dst.value}); "
                    "no equivalence-class separation or completion is assumed."
                )

        self.fwd = fwd
        self.rev = rev
        self.bi = bi
        self.directed_edges = frozenset(dir_set)
        self.bidirected_edges = frozenset(bi_set)
        self.circle_edges = tuple(circle_edges)


_STATIC_GRAPH_CACHE_CAPACITY = 128
_ADJ_CACHE: OrderedDict[str, CachedAdjacency] = OrderedDict()
_CC_CACHE: OrderedDict[str, tuple[frozenset[str], ...]] = OrderedDict()
_CacheValue = TypeVar("_CacheValue")


def _evict_lru_entries(cache: OrderedDict[str, _CacheValue]) -> None:
    """Keep each static graph cache within its declared entry capacity."""
    while len(cache) > _STATIC_GRAPH_CACHE_CAPACITY:
        cache.popitem(last=False)


def _graph_content_cache_key(graph: CausalGraphModel) -> str:
    """Hash the complete, canonical graph profile used by static consumers."""
    from polisyos.ir.analytics.causal_graph import graph_content_sha256

    try:
        return graph_content_sha256(graph)
    except (OverflowError, TypeError, ValueError) as exc:
        raise InvalidCausalGraphProfileError(
            "Unsupported static ADMG profile: graph fields lack a canonical content identity."
        ) from exc


def _canonical_snapshot_content_key(graph: CausalGraphModel) -> str:
    """Hash a snapshot that has already passed full canonical IR validation."""
    from pydantic import BaseModel

    from polisyos.ir.analytics.causal_graph import CausalGraphModel

    if type(graph) is not CausalGraphModel:
        raise InvalidCausalGraphProfileError(
            "Unsupported static ADMG profile: cache keys require a canonical graph snapshot."
        )
    try:
        payload = BaseModel.model_dump(graph, mode="json")
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
    except (OverflowError, TypeError, ValueError) as exc:
        raise InvalidCausalGraphProfileError(
            "Unsupported static ADMG profile: canonical graph lacks a content identity."
        ) from exc


def _validate_static_adjacency_profile(graph: CausalGraphModel) -> None:
    """Validate every edge profile before a content-cache lookup."""
    from polisyos.ir.analytics.causal_graph import EdgeMark

    for edge in graph.edges:
        if edge.lag not in (None, 0):
            raise UnsupportedStaticADMGProfileError(
                "Unsupported static ADMG profile: "
                f"edge {edge.src!r}–{edge.dst!r} has lag={edge.lag!r}; "
                "resolve the temporal graph before static causal inference."
            )
        marks = (edge.mark_src, edge.mark_dst)
        if marks not in {
            (EdgeMark.TAIL, EdgeMark.ARROW),
            (EdgeMark.ARROW, EdgeMark.TAIL),
            (EdgeMark.ARROW, EdgeMark.ARROW),
        }:
            raise UnsupportedStaticADMGProfileError(
                "Unsupported static ADMG profile: "
                f"edge {edge.src!r}–{edge.dst!r} has unresolved endpoints "
                f"({edge.mark_src.value}, {edge.mark_dst.value}); "
                "no equivalence-class separation or completion is assumed."
            )


def _get_cached_adjacency(graph: CausalGraphModel) -> CachedAdjacency:
    # Rebuild and admit the complete caller graph before deriving or consulting
    # a content key. No object identity, serializer override, or stale key can
    # bypass the current graph kind, endpoint, lag, or metadata fields.
    canonical = canonical_scalar_query_graph(graph)
    _validate_static_adjacency_profile(canonical)
    key = _canonical_snapshot_content_key(canonical)
    cached = _ADJ_CACHE.get(key)
    if cached is not None:
        # The caller was fully revalidated and hashed above. Cache values are
        # detached canonical snapshots created under this content key, so
        # rehashing the stored value would repeat the same O(n) canonical work.
        _ADJ_CACHE.move_to_end(key)
        return cached

    adjacency = CachedAdjacency(canonical, key)
    _ADJ_CACHE[key] = adjacency
    _evict_lru_entries(_ADJ_CACHE)
    return adjacency


def canonical_causal_graph_snapshot(graph: CausalGraphModel) -> CausalGraphModel:
    """Rebuild the complete live graph from declared IR fields.

    The detached result is the object downstream consumers must use. Every call
    rebuilds from current stored fields; adjacency reuse happens only after the
    complete current snapshot passes the static profile and content-key checks.
    """
    from polisyos.ir.analytics.causal_graph import (
        CausalGraphModel,
        _canonical_causal_graph,
    )

    try:
        canonical = _canonical_causal_graph(graph)
    except (TypeError, ValueError) as exc:
        raise InvalidCausalGraphProfileError(
            "Unsupported static ADMG profile: causal graph fields fail canonical IR validation."
        ) from exc
    if type(canonical) is not CausalGraphModel:
        raise InvalidCausalGraphProfileError(
            "Unsupported static ADMG profile: canonical graph has a noncanonical runtime type."
        )
    return canonical


def canonical_scalar_query_graph(graph: CausalGraphModel) -> CausalGraphModel:
    """Return the canonical graph snapshot or refuse an unadmitted partial tag.

    PAG and CPDAG completion semantics are not selected by endpoint orientation,
    policy labels, or a first completion. Full-law M-graph and other native
    query paths remain available because this boundary does not impose an ADMG
    or acyclicity restriction.
    """
    from polisyos.ir.analytics.causal_graph import GraphType

    canonical = canonical_causal_graph_snapshot(graph)
    if canonical.graph_type in {GraphType.PAG, GraphType.CPDAG}:
        label = canonical.graph_type.value
        raise PartialGraphCompletionSemanticsError(
            "Unsupported static ADMG profile: graph type "
            f"{label!r} has no admitted completion semantics for scalar identification.",
            graph_type_label=label,
        )
    return canonical


def _validate_static_admg(graph: CausalGraphModel) -> CausalGraphModel:
    """Admit a scalar query graph and return the exact cached snapshot."""
    return _get_cached_adjacency(graph).graph


def _validate_static_id_graph(graph: CausalGraphModel) -> CausalGraphModel:
    """Admit the resolved acyclic graph profile required by static ID methods.

    The sigma calculus retains its cyclic graph owner, and CausalEngine's
    validated dynamic reduction remains a separate route. Direct static ID
    methods require an acyclic directed component for a declared ADMG; DAG
    acyclicity is already enforced by canonical IR validation.
    """
    from polisyos.ir.analytics.causal_graph import GraphType

    canonical = _validate_static_admg(graph)
    if canonical.graph_type not in {GraphType.DAG, GraphType.ADMG}:
        raise UnsupportedStaticADMGProfileError(
            "Unsupported static ID profile: graph type "
            f"{canonical.graph_type.value!r} requires its dedicated query owner; "
            "M-graph identification requires full-law recovery inputs.",
            graph_type_label=canonical.graph_type.value,
        )
    if canonical.graph_type is GraphType.ADMG and has_directed_cycle(canonical):
        raise InvalidCausalGraphProfileError(
            "Unsupported static ADMG profile: declared ADMG has a directed cycle; "
            "static ID requires an acyclic directed component.",
            graph_type_label=canonical.graph_type.value,
        )
    return canonical


def canonical_scalar_selection_diagram(diagram: Any) -> Any:
    """Rebuild a direct TR query from the actual typed diagram fields.

    The scalar graph gate and the S-node set are one direct-query input. This
    returns a detached diagram whose graph and S-nodes are the exact values
    consumed by the transport identifier.
    """
    from polisyos.ir import ContextProfile, SelectionDiagram, SNode
    from polisyos.ir.analytics.causal_graph import (
        _canonical_model,
        _canonical_model_field_snapshot,
        _snapshot_canonical_value,
    )

    try:
        fields = _canonical_model_field_snapshot(diagram, SelectionDiagram)
        fields["base_graph"] = _validate_static_id_graph(fields["base_graph"])
        fields["s_nodes"] = [_canonical_model(node, SNode) for node in fields["s_nodes"]]
        graph_nodes = set(fields["base_graph"].nodes)
        unknown_targets = sorted({node.target_variable for node in fields["s_nodes"]} - graph_nodes)
        if unknown_targets:
            raise InvalidCausalGraphProfileError(
                "Unsupported static ADMG profile: S-node target(s) are absent from "
                f"the base graph nodes: {unknown_targets!r}.",
                graph_type_label=fields["base_graph"].graph_type.value,
            )

        context_fields: dict[str, dict[str, Any]] = {}
        for field_name in ("source_context", "target_context"):
            context = fields[field_name]
            if type(context) is not ContextProfile:
                raise ValueError("selection diagram context must have its canonical IR type")
            stored = object.__getattribute__(context, "__dict__")
            if type(stored) is not dict or set(stored) != set(ContextProfile.model_fields):
                raise ValueError("selection diagram context fields are not canonical")
            context_fields[field_name] = {
                name: _snapshot_canonical_value(stored[name])
                for name in ContextProfile.model_fields
            }
        fields.update(
            {
                name: ContextProfile.model_validate(payload, strict=True)
                for name, payload in context_fields.items()
            }
        )
        canonical = SelectionDiagram.model_validate(fields, strict=True)
    except UnsupportedStaticADMGProfileError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidCausalGraphProfileError(
            "Unsupported static ADMG profile: selection diagram fields fail canonical IR validation."
        ) from exc

    if type(canonical) is not SelectionDiagram:
        raise InvalidCausalGraphProfileError(
            "Unsupported static ADMG profile: canonical selection diagram has a noncanonical type."
        )
    return canonical


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
    Reverse storage is normalized. Compact lagged or unresolved edges refuse.
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

    All directed edges *into* any node in intervention_set are removed.  Any
    bidirected edge incident to an intervened node is removed as well: the
    latent cause remains represented for other nodes, but its influence on the
    replaced mechanism is cut.  Outgoing directed effects are preserved.

    Returns a new CausalGraphModel (immutable, since frozen=True).
    """
    from polisyos.ir.analytics.causal_graph import EdgeMark

    graph = _validate_static_admg(graph)
    kept_edges = []
    for e in graph.edges:
        # Remove directed edges INTO intervention nodes
        if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW:
            if e.dst in intervention_set:
                continue  # cut
        elif e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.TAIL:
            if e.src in intervention_set:
                continue  # cut reverse-stored incoming edge
        # Perfect intervention also cuts latent influence into action nodes.
        if e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.ARROW:
            if e.src in intervention_set or e.dst in intervention_set:
                continue  # cut action-incident bidirected edge
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
    """G_{X̄}: apply perfect-do surgery to nodes in *nodes*.

    This is the do-operator mutilation G_{do(X)}: cutting incoming directed
    and action-incident bidirected influences while preserving outgoing
    directed effects.

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

    graph = _validate_static_admg(graph)
    kept_edges = []
    for e in graph.edges:
        # Drop directed edges whose source is in the cut set
        if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW:
            if e.src in nodes:
                continue  # cut outgoing directed edge
        elif e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.TAIL:
            if e.dst in nodes:
                continue  # cut reverse-stored outgoing edge
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
    cached_adjacency = _get_cached_adjacency(graph)
    graph = cached_adjacency.graph
    key = cached_adjacency.content_key
    cached_components = _CC_CACHE.get(key)
    if cached_components is not None:
        _CC_CACHE.move_to_end(key)
        return list(cached_components)

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
    _evict_lru_entries(_CC_CACHE)
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
    graph = _validate_static_admg(graph)
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


def _m_separation_adjacency(
    graph: CausalGraphModel,
) -> dict[str, list[tuple[str, Any, Any]]]:
    """Build traversal entries carrying both endpoint marks for each edge."""
    from polisyos.ir.analytics.causal_graph import EdgeMark

    cached = _get_cached_adjacency(graph)
    graph = cached.graph
    adj: dict[str, list[tuple[str, Any, Any]]] = {n: [] for n in graph.nodes}

    for src, dst in cached.directed_edges:
        adj[src].append((dst, EdgeMark.TAIL, EdgeMark.ARROW))
        adj[dst].append((src, EdgeMark.ARROW, EdgeMark.TAIL))

    for pair in cached.bidirected_edges:
        src, dst = tuple(pair)
        adj[src].append((dst, EdgeMark.ARROW, EdgeMark.ARROW))
        adj[dst].append((src, EdgeMark.ARROW, EdgeMark.ARROW))

    return adj


def m_separation(
    graph: CausalGraphModel,
    x_set: frozenset[str],
    y_set: frozenset[str],
    z_set: frozenset[str],
) -> bool:
    """Test m-separation: X ⊥⊥ Y | Z in the mixed graph G.

    The traversal carries the mark at the node where each path arrives.  The
    mark on the next edge then determines whether that node is a collider;
    collider activation uses the directed ancestor closure of ``z_set``.
    """
    from polisyos.ir.analytics.causal_graph import EdgeMark

    graph = _validate_static_admg(graph)
    if x_set & y_set:
        return False
    if not x_set or not y_set:
        return True

    adj = _m_separation_adjacency(graph)
    an_z = ancestors(graph, z_set) if z_set else frozenset()

    # State is (node, incoming mark at node).  Keeping the actual endpoint mark
    # distinguishes parent/child arrival and bidirected collider passages.
    visited: set[tuple[str, Any | None]] = set()
    queue: deque[tuple[str, Any | None]] = deque()

    for source in x_set:
        if source in adj:
            state = (source, None)
            visited.add(state)
            queue.append(state)

    while queue:
        node, incoming_mark = queue.popleft()

        if node in y_set:
            return False  # found an open path → NOT m-separated

        for neighbor, mark_at_node, mark_at_neighbor in adj[node]:
            if incoming_mark is not None:
                is_collider = incoming_mark is EdgeMark.ARROW and mark_at_node is EdgeMark.ARROW
                if is_collider:
                    if node not in an_z:
                        continue
                elif node in z_set:
                    continue

            state = (neighbor, mark_at_neighbor)
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
    """Bayes Ball reachability closure on a resolved static ADMG.

    Returns all nodes reachable from *query_vars* after do(*intervened*),
    optionally conditioning on *conditioning*.

    Parameters
    ----------
    graph       : causal graph with resolved contemporaneous ADMG endpoints
    query_vars  : seed variables to propagate from
    intervened  : variables in do(·); their incoming directed edges are removed
    conditioning: variables Z to condition on (affects collider activation)
    """
    z_set: frozenset[str] = conditioning if conditioning is not None else frozenset()

    # Mutilated graph: remove incoming directed edges to intervened nodes
    g_mut = do_operator(graph, intervened)

    # Build adjacency for the mutilated graph — same structure as m_separation:
    # (neighbor, is_parent_of_current, is_bidirected)
    adj: dict[str, list[tuple[str, bool, bool]]] = {n: [] for n in g_mut.nodes}
    for src, dst in extract_directed_edges(g_mut):
        adj[src].append((dst, False, False))
        adj[dst].append((src, True, False))
    for pair in extract_bidirected_edges(g_mut):
        src, dst = tuple(pair)
        adj[src].append((dst, False, True))
        adj[dst].append((src, False, True))

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
        if e.lag is not None and e.lag > 0:
            continue
        if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW:
            source, target = e.src, e.dst
        elif e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.TAIL:
            source, target = e.dst, e.src
        else:
            continue
        fwd[source].append(target)
        indegree[target] += 1

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
    """Build forward adjacency from the shared admitted graph snapshot."""
    cached = _get_cached_adjacency(graph)
    return {node: list(cached.fwd[node]) for node in cached.graph.nodes}


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
    graph = _validate_static_admg(graph)
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

        if (edge.mark_src, edge.mark_dst) in (
            (EdgeMark.TAIL, EdgeMark.ARROW),
            (EdgeMark.ARROW, EdgeMark.TAIL),
        ):
            if edge.mark_src is EdgeMark.ARROW:
                src_label, dst_label = dst_label, src_label
            key = (src_label, dst_label)
            if key in seen_directed:
                continue
            seen_directed.add(key)
            condensed_edges.append(
                edge.model_copy(
                    update={
                        "src": src_label,
                        "dst": dst_label,
                        "mark_src": EdgeMark.TAIL,
                        "mark_dst": EdgeMark.ARROW,
                    }
                )
            )
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
    """Inspect resolved contemporaneous arrows without completing unknown marks.

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
        elif (
            e.mark_src is EdgeMark.ARROW
            and e.mark_dst is EdgeMark.TAIL
            and (e.lag is None or e.lag == 0)
        ):
            fwd[e.dst].append(e.src)

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
    from polisyos.ir.analytics.causal_graph import (
        CausalEdge,
        CausalGraphModel,
        EdgeMark,
        GraphType,
    )

    graph = _validate_static_admg(graph)
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
    # Build forward adjacency from the exact shared admitted snapshot.
    cached = _get_cached_adjacency(graph)
    fwd: dict[str, set[str]] = {
        node: set(cached.fwd[node]) | set(cached.bi[node]) for node in cached.graph.nodes
    }

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
    graph = _validate_static_admg(graph)
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
