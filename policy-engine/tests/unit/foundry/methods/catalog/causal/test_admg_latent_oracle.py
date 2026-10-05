"""Bounded ADMG differential oracles using latent DAG moralization.

This independent reference uses ancestor restriction and moralization rather
than the runtime's endpoint-state traversal. It establishes finite synthetic
graph properties, without claiming a NetworkX/PAG backend or real-data result.
"""

from itertools import combinations, permutations, product

from polisyos.foundry.methods.catalog.causal.admg_ops import do_operator, m_separation
from polisyos.foundry.methods.catalog.causal.do_calculus import apply_rule1, apply_rule3
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import DistributionDomain, DistributionRef


def _latent_edges(graph: CausalGraphModel) -> list[tuple[str, str]]:
    """Expand each bidirected relation into an independent latent common cause."""
    edges: list[tuple[str, str]] = []
    for index, edge in enumerate(graph.edges):
        if edge.mark_src is EdgeMark.TAIL:
            edges.append((edge.src, edge.dst))
        else:
            latent = f"latent_{index}"
            edges.extend([(latent, edge.src), (latent, edge.dst)])
    return edges


def _dag_separator(
    edges: list[tuple[str, str]],
    x: str,
    y: str,
    conditioned: frozenset[str],
) -> bool:
    """Apply the ancestral moral-graph characterization of DAG d-separation."""
    parents: dict[str, set[str]] = {}
    for source, target in edges:
        parents.setdefault(target, set()).add(source)
    ancestral = {x, y, *conditioned}
    pending = list(ancestral)
    while pending:
        for parent in parents.get(pending.pop(), set()):
            if parent not in ancestral:
                ancestral.add(parent)
                pending.append(parent)
    moral: dict[str, set[str]] = {node: set() for node in ancestral}
    for child in ancestral:
        family = parents.get(child, set()) & ancestral
        for source in family:
            moral[source].add(child)
            moral[child].add(source)
        for left, right in combinations(family, 2):
            moral[left].add(right)
            moral[right].add(left)
    visited = set(conditioned)
    pending = [x]
    while pending:
        node = pending.pop()
        if node in visited:
            continue
        if node == y:
            return False
        visited.add(node)
        pending.extend(moral[node] - visited)
    return True


def _three_node_admgs() -> list[CausalGraphModel]:
    """Enumerate the complete 25 acyclic directed × 8 bidirected domain."""
    nodes = ("A", "B", "C")
    ordered_pairs = tuple(permutations(nodes, 2))
    unordered_pairs = tuple(combinations(nodes, 2))
    graphs = []
    for directed_mask in product((False, True), repeat=len(ordered_pairs)):
        directed = [edge for edge, present in zip(ordered_pairs, directed_mask) if present]
        if not any(
            all(order.index(source) < order.index(target) for source, target in directed)
            for order in permutations(nodes)
        ):
            continue
        for bidirected_mask in product((False, True), repeat=len(unordered_pairs)):
            edges = [CausalEdge(src=source, dst=target) for source, target in directed]
            edges.extend(
                CausalEdge(src=source, dst=target, mark_src=EdgeMark.ARROW)
                for (source, target), present in zip(unordered_pairs, bidirected_mask)
                if present
            )
            graphs.append(CausalGraphModel(graph_type=GraphType.ADMG, nodes=nodes, edges=edges))
    return graphs


def test_b216_complete_three_node_domain_matches_latent_dag_oracle() -> None:
    """All 2400 ordered separation queries match independent moralization."""
    graphs = _three_node_admgs()
    assert len(graphs) == 200
    query_count = 0
    for graph in graphs:
        for x, y in permutations(graph.nodes, 2):
            remaining = frozenset(graph.nodes) - {x, y}
            for conditioned in (frozenset(), remaining):
                expected = _dag_separator(_latent_edges(graph), x, y, conditioned)
                actual = m_separation(graph, frozenset({x}), frozenset({y}), conditioned)
                assert actual == expected, (graph.model_dump(), x, y, conditioned)
                query_count += 1
    assert query_count == 2400


def test_b217_perfect_do_matches_latent_dag_for_all_action_sets() -> None:
    """Every surgery in the finite domain cuts only incoming causal influence."""
    graph_count = 0
    for graph in _three_node_admgs():
        latent_edges = _latent_edges(graph)
        for action_mask in product((False, True), repeat=len(graph.nodes)):
            action = frozenset(node for node, present in zip(graph.nodes, action_mask) if present)
            actual_graph = do_operator(graph, action)
            expected_edges = [
                (source, target) for source, target in latent_edges if target not in action
            ]
            for x, y in permutations(graph.nodes, 2):
                conditioned = frozenset(graph.nodes) - {x, y}
                for condition in (frozenset(), conditioned):
                    assert m_separation(
                        actual_graph, frozenset({x}), frozenset({y}), condition
                    ) == (_dag_separator(expected_edges, x, y, condition)), (
                        graph.model_dump(),
                        action,
                        x,
                        y,
                        condition,
                    )
        graph_count += 1
    assert graph_count == 200


def test_graph_oracle_distinguishes_fork_from_collider_at_rule_consumer() -> None:
    """The same skeleton has opposite Rule 1 admissibility under arrow reversal."""
    reference = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        conditioning=("X",),
    )
    fork = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=("X", "M", "Y"),
        edges=[CausalEdge(src="M", dst="X"), CausalEdge(src="M", dst="Y")],
    )
    collider = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=fork.nodes,
        edges=[CausalEdge(src="X", dst="M"), CausalEdge(src="Y", dst="M")],
    )
    assert apply_rule1(reference, fork, frozenset({"X"})) is None
    result = apply_rule1(reference, collider, frozenset({"X"}))
    assert result is not None
    assert result[0].conditioning == ()
    # A pure confounding action is removable only after correct latent surgery.
    confounded = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=("X", "Y"),
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW)],
    )
    intervention = reference.model_copy(update={"conditioning": (), "intervention_set": ("X",)})
    removed = apply_rule3(intervention, confounded, frozenset({"X"}))
    assert removed is not None
    assert removed[0].intervention_set == ()
