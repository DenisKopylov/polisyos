"""Static-profile admission and native symbolic consumers, on finite graphs.

These controls establish graph/rewriting properties, not an identified real-data
effect or general completeness of ID/PAG/counterfactual identification.
"""

import sys
from itertools import combinations, product

import pytest

from polisyos.foundry.methods.catalog.causal import admg_ops as ops
from polisyos.foundry.methods.catalog.causal import amn, ctf_calculus
from polisyos.foundry.methods.catalog.causal import do_calculus as do
from polisyos.foundry.methods.catalog.causal import sigma_calculus as sigma
from polisyos.foundry.methods.catalog.causal._id_contracts import CtfQuery, IdentificationStatus
from polisyos.foundry.methods.catalog.causal.id_engine import core, transport
from polisyos.foundry.methods.catalog.causal.id_engine import counterfactual as ctf
from polisyos.foundry.methods.catalog.causal.pag_completion import apply_pag_orientation_rules
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    PAGIdentificationPolicy,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.estimand import (
    CounterfactualNode,
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    RatioNode,
    StochasticPolicy,
)
from polisyos.ir.analytics.transportability import SelectionDiagram


def _graph(edges=(), *, nodes=("Y", "Z", "C", "D", "T"), graph_type=GraphType.ADMG):
    return CausalGraphModel(graph_type=graph_type, nodes=nodes, edges=list(edges))


def _ref(*, actions=(), conditions=()):
    return DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        intervention_set=actions,
        conditioning=conditions,
    )


def _ast(ref=None):
    return EstimandAST(
        query_str="P(Y|do(Z))",
        root=ref or _ref(),
        treatment="Z",
        outcome="Y",
        all_variables=("Y", "Z", "C", "D", "T"),
    )


SUPPORTED = {
    (EdgeMark.TAIL, EdgeMark.ARROW),
    (EdgeMark.ARROW, EdgeMark.TAIL),
    (EdgeMark.ARROW, EdgeMark.ARROW),
}
UNRESOLVED = [pair for pair in product(EdgeMark, repeat=2) if pair not in SUPPORTED]
UNSUPPORTED = (
    [
        pytest.param(
            _graph(
                [CausalEdge(src="Y", dst="Z", mark_src=left, mark_dst=right)],
                graph_type=GraphType.CPDAG if left is right is EdgeMark.TAIL else GraphType.PAG,
            ),
            id=f"{left.value}-{right.value}",
        )
        for left, right in UNRESOLVED
    ]
    + [
        pytest.param(_graph([CausalEdge(src="Y", dst="Z", lag=lag)]), id=f"lag-{lag}")
        for lag in (1, 2)
    ]
    + [pytest.param(_graph([CausalEdge(src="Y", dst="Y", lag=1)]), id="self-lag-1")]
)

# The public inference entries/builders below are real direct calls, including
# no-op requests that formerly escaped admission. Raw orientation is separate.
CONSUMERS = [
    ("msep", lambda g: ops.m_separation(g, frozenset({"Y"}), frozenset({"Z"}), frozenset())),
    ("msep-empty", lambda g: ops.m_separation(g, frozenset(), frozenset(), frozenset())),
    (
        "msep-overlap",
        lambda g: ops.m_separation(g, frozenset({"Y"}), frozenset({"Y"}), frozenset()),
    ),
    ("ancestors-empty", lambda g: ops.ancestors(g, frozenset())),
    ("descendants-empty", lambda g: ops.descendants(g, frozenset())),
    ("directed-extractor", lambda g: ops.extract_directed_edges(g)),
    ("bidirected-extractor", lambda g: ops.extract_bidirected_edges(g)),
    ("c-components", lambda g: ops.c_components(g)),
    ("dsep-empty", lambda g: ops.d_separation(g, frozenset(), frozenset(), frozenset())),
    ("markov-boundary", lambda g: ops.markov_boundary(g, "Y")),
    ("tarjan-scc", lambda g: ops.tarjan_scc(g)),
    ("s-reachable-empty", lambda g: ops.s_reachable(g, frozenset(), frozenset())),
    ("project-erases-edge", lambda g: ops.project_to_subgraph(g, frozenset({"T"}))),
    ("districts-restrict", lambda g: ops.districts(g, frozenset({"T"}))),
    ("do-empty", lambda g: ops.do_operator(g, frozenset())),
    ("do-erases-edge", lambda g: ops.do_operator(g, frozenset({"Y", "Z"}))),
    ("outgoing-erases-edge", lambda g: ops.remove_outgoing_edges(g, frozenset({"Y", "Z"}))),
    ("induced-erases-edge", lambda g: ops.induced_subgraph(g, frozenset({"T"}))),
    ("condense-erases-edge", lambda g: ops.condense_graph(g, [frozenset(g.nodes)])),
    ("selection-empty", lambda g: ops.augment_with_s_nodes(g, frozenset())),
    ("selection-remove-noop", lambda g: ops.resolve_s_node_by_adjustment(g, "T", frozenset())),
    ("closure-empty", lambda g: ops.reachable_closure(g, frozenset(), frozenset())),
    ("rule1", lambda g: do.apply_rule1(_ref(conditions=("Z",)), g, frozenset({"Z"}))),
    ("rule1-empty", lambda g: do.apply_rule1(_ref(), g, frozenset())),
    ("rule2-empty", lambda g: do.apply_rule2(_ref(), g, frozenset())),
    ("rule3-empty", lambda g: do.apply_rule3(_ref(), g, frozenset())),
    ("do-rewrite-zero", lambda g: do.rewrite_estimand(_ast(), g, max_iterations=0)),
    ("sigma1-empty", lambda g: sigma.apply_sigma_rule1(_ref(), g, frozenset(), frozenset())),
    ("sigma2-empty", lambda g: sigma.apply_sigma_rule2(_ref(), g, frozenset(), frozenset())),
    ("sigma3-empty", lambda g: sigma.apply_sigma_rule3(_ref(), g, frozenset(), frozenset())),
    ("sigma-builder-empty", lambda g: sigma._build_sigma_graph(g, frozenset())),
    (
        "sigma-rewrite-zero",
        lambda g: sigma.rewrite_estimand_with_selection(_ast(), g, frozenset(), 0),
    ),
    ("sigma-identify-zero", lambda g: sigma.sigma_identify(_ast(), g, max_iterations=0)),
    ("sigma-z-identify-zero", lambda g: sigma.sigma_z_identify(_ast(), g, max_iterations=0)),
    (
        "id-empty-action",
        lambda g: core.id_algorithm(treatment=frozenset(), outcome=frozenset({"Y"}), graph=g),
    ),
    (
        "idc-empty-action",
        lambda g: core.idc_algorithm(
            treatment=frozenset(), outcome=frozenset({"Y"}), conditions=frozenset({"Z"}), graph=g
        ),
    ),
    (
        "oracle-fallback",
        lambda g: core.id_with_oracle_fallback(
            treatment=frozenset(), outcome=frozenset({"Y"}), graph=g, oracle="none"
        ),
    ),
    (
        "find-hedge",
        lambda g: core.find_hedge(treatment=frozenset(), outcome=frozenset({"Y"}), graph=g),
    ),
    (
        "find-thicket",
        lambda g: core.find_thicket(treatment=frozenset(), outcome=frozenset({"Y"}), graph=g),
    ),
    (
        "transport-diagram-before-augmentation",
        lambda g: core.tr_algorithm(
            treatment=frozenset(),
            outcome=frozenset({"Y"}),
            selection_diagram=SelectionDiagram(
                base_graph=g,
                s_nodes=[],
                source_context=ContextProfile(),
                target_context=ContextProfile(),
            ),
        ),
    ),
    ("id-star", lambda g: ctf.id_star_algorithm(CtfQuery("Y", (("Z", 1.0),)), g)),
    ("idc-star-no-evidence", lambda g: ctf.idc_star_algorithm(CtfQuery("Y", (("Z", 1.0),)), g)),
    (
        "idc-star-evidence",
        lambda g: ctf.idc_star_algorithm(CtfQuery("Y", (("Z", 1.0),), evidence=(("C", 0.0),)), g),
    ),
    (
        "counterfactual-builder",
        lambda g: ctf._build_counterfactual_graph(
            g, ctf._normalize_counterfactual_query(CtfQuery("Y", (("Z", 1.0),)))
        ),
    ),
    (
        "z-id-noop",
        lambda g: transport.z_id_algorithm(
            treatment=frozenset(), outcome=frozenset({"Y"}), z_interventions=frozenset(), graph=g
        ),
    ),
    (
        "mz-id-no-sources",
        lambda g: transport.mz_id_algorithm(
            treatment=frozenset(), outcome=frozenset({"Y"}), source_domains=[], graph=g
        ),
    ),
    (
        "sid",
        lambda g: transport.sid_algorithm(
            treatment=frozenset(),
            outcome=frozenset({"Y"}),
            policy=StochasticPolicy(policy_type="soft"),
            graph=g,
        ),
    ),
    (
        "conditional-id",
        lambda g: transport.conditional_intervention_id(
            treatment=frozenset(), outcome=frozenset({"Y"}), condition_vars=frozenset(), graph=g
        ),
    ),
    (
        "dynamic-id-empty",
        lambda g: transport.dynamic_intervention_id(
            treatment_sequence=[], outcome="Y", time_points=[], graph=g
        ),
    ),
    (
        "joint-id-empty",
        lambda g: transport.joint_id_algorithm(
            treatments=frozenset(), outcomes=frozenset(), graph=g
        ),
    ),
    (
        "multi-outcome-id-empty",
        lambda g: transport.multi_outcome_id(treatment=frozenset(), outcomes=[], graph=g),
    ),
    (
        "ctf-rule1-empty",
        lambda g: ctf_calculus.apply_ctf_rule1(
            CounterfactualNode(variable="Y", intervention={}), g, frozenset()
        ),
    ),
    (
        "ctf-rule2-empty",
        lambda g: ctf_calculus.apply_ctf_rule2(
            CounterfactualNode(variable="Y", intervention={}), g, frozenset()
        ),
    ),
    (
        "ctf-rule3-empty",
        lambda g: ctf_calculus.apply_ctf_rule3(
            CounterfactualNode(variable="Y", intervention={}), g, frozenset()
        ),
    ),
    ("ctf-rewrite-nonctf", lambda g: ctf_calculus.rewrite_ctf_estimand(_ast(), g, 0)),
    ("amn-builder-empty", lambda g: amn.build_amn(g, {})),
    (
        "amn-dsep-empty",
        lambda g: amn.amn_d_separation(
            g,
            amn.AMNMetadata(
                worlds=[], world_partition={}, counterfactual_interventions={}, bridge_edges=[]
            ),
            frozenset(),
            frozenset(),
            frozenset(),
        ),
    ),
    (
        "amn-independence-empty",
        lambda g: amn.amn_ctf_independence(g, frozenset(), frozenset(), frozenset()),
    ),
    ("amn-projection-noop", lambda g: amn.amn_ancestral_projection(g)),
    (
        "amn-faithfulness-before-sampling",
        lambda g: amn.verify_ctf_faithfulness(g, None, n_samples=0),
    ),
]


@pytest.mark.parametrize("graph", UNSUPPORTED)
@pytest.mark.parametrize("name,consumer", CONSUMERS, ids=[name for name, _ in CONSUMERS])
def test_static_profile_refuses_original_graph_before_surgery_rewrite_or_noop(
    graph, name, consumer
):
    before = graph.model_dump_json()
    with pytest.raises(ValueError, match="Unsupported static ADMG profile: edge"):
        consumer(graph)
    assert graph.model_dump_json() == before


@pytest.mark.parametrize("policy", list(PAGIdentificationPolicy))
def test_id_refuses_before_pag_orientation_or_optimistic_commitment(policy):
    graph = _graph(
        [CausalEdge(src="Z", dst="Y", mark_src=EdgeMark.CIRCLE)], graph_type=GraphType.PAG
    ).model_copy(update={"pag_identification_policy": policy})
    with pytest.raises(ValueError, match="Unsupported static ADMG profile"):
        core.id_algorithm(treatment=frozenset({"Z"}), outcome=frozenset({"Y"}), graph=graph)
    # Raw endpoint/orientation utilities still accept this representation.
    oriented, _steps = apply_pag_orientation_rules(graph)
    assert oriented.nodes == graph.nodes
    assert ops.is_adjacent(graph, "Z", "Y")
    assert not ops.has_directed_path(graph, "Z", "Y")


def test_raw_cpdag_endpoint_inspection_remains_callable():
    graph = _graph(
        [CausalEdge(src="Y", dst="Z", mark_dst=EdgeMark.TAIL)], graph_type=GraphType.CPDAG
    )
    assert ops.extract_undirected_edges(graph) == frozenset({frozenset({"Y", "Z"})})
    assert ops.is_adjacent(graph, "Y", "Z")
    assert set(ops.topological_order(graph)) == set(graph.nodes)


def test_forward_reverse_and_latent_known_edges_keep_static_semantics():
    forward = _graph(
        [CausalEdge(src="Z", dst="Y"), CausalEdge(src="Y", dst="C", mark_src=EdgeMark.ARROW)]
    )
    reverse = _graph(
        [
            CausalEdge(src="Y", dst="Z", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.TAIL),
            CausalEdge(src="Y", dst="C", mark_src=EdgeMark.ARROW),
        ]
    )
    for graph in (forward, reverse):
        assert ops.extract_directed_edges(graph) == frozenset({("Z", "Y")})
        assert ops.ancestors(graph, frozenset({"Y"})) == frozenset({"Z", "Y"})
        assert ops.descendants(graph, frozenset({"Z"})) == frozenset({"Z", "Y"})
        assert not ops.m_separation(graph, frozenset({"Z"}), frozenset({"Y"}), frozenset())
        assert ops.extract_directed_edges(ops.do_operator(graph, frozenset({"Y"}))) == frozenset()
        assert ops.extract_bidirected_edges(ops.do_operator(graph, frozenset({"Y"}))) == frozenset()
        assert (
            ops.extract_directed_edges(ops.remove_outgoing_edges(graph, frozenset({"Z"})))
            == frozenset()
        )
        assert ops.extract_bidirected_edges(
            ops.remove_outgoing_edges(graph, frozenset({"Z"}))
        ) == frozenset({frozenset({"Y", "C"})})
        assert ops.has_directed_path(graph, "Z", "Y")
        assert ops.topological_order(graph).index("Z") < ops.topological_order(graph).index("Y")
        condensed = ops.condense_graph(graph, [frozenset({node}) for node in graph.nodes])
        assert ops.extract_directed_edges(condensed) == frozenset({("Z", "Y")})
    query = ctf._normalize_counterfactual_query(CtfQuery("Y", (("C", 1.0),)))
    fwd_world, _ = ctf._build_counterfactual_graph(forward, query)
    rev_world, _ = ctf._build_counterfactual_graph(reverse, query)
    assert ops.extract_directed_edges(fwd_world) == ops.extract_directed_edges(rev_world)
    assert ops.extract_bidirected_edges(fwd_world) == ops.extract_bidirected_edges(rev_world)


# Independent graph-theoretic examples: the arrow reversal opens a fork and
# closes a collider; conditioning on a collider descendant reopens that path.
CASES = [
    ("fork", [("C", "Y"), ("C", "Z")], (), False, False, True),
    ("blocked-fork", [("C", "Y"), ("C", "Z")], ("C",), True, True, True),
    ("collider", [("Y", "C"), ("Z", "C"), ("C", "D")], (), True, True, True),
    ("conditioned-descendant", [("Y", "C"), ("Z", "C"), ("C", "D")], ("D",), False, True, False),
]


@pytest.mark.parametrize("name,edges,w,rule1,rule2,rule3", CASES, ids=[case[0] for case in CASES])
def test_actual_do_and_sigma_rules_walk_fork_collider_and_conditioned_descendant(
    name, edges, w, rule1, rule2, rule3
):
    graph = _graph([CausalEdge(src=a, dst=b) for a, b in edges], graph_type=GraphType.DAG)
    observed = _ref(conditions=("Z", *w))
    action = _ref(actions=("Z",), conditions=w)
    for function, reference, expected in [
        (do.apply_rule1, observed, rule1),
        (do.apply_rule2, action, rule2),
        (do.apply_rule3, action, rule3),
    ]:
        result = function(reference, graph, frozenset({"Z"}))
        assert (result is not None) is expected, (name, function.__name__, result)
        if result:
            rewritten, proof = result
            assert proof.rule_name in {"RULE1", "RULE2", "RULE3"}
            assert rewritten != reference
    for function, reference, expected in [
        (sigma.apply_sigma_rule1, observed, rule1),
        (sigma.apply_sigma_rule2, action, rule2),
        (sigma.apply_sigma_rule3, action, rule3),
    ]:
        # Selection of isolated T does not open any path in the known examples.
        result = function(reference, graph, frozenset({"Z"}), frozenset({"T"}))
        assert (result is not None) is expected, (name, function.__name__, result)


@pytest.mark.parametrize("name,edges,w,_r1,_r2,_r3", CASES, ids=[case[0] for case in CASES])
def test_actual_idc_is_two_id_consumers_and_preserves_requested_conditioning(
    name, edges, w, _r1, _r2, _r3
):
    graph = _graph([CausalEdge(src=a, dst=b) for a, b in edges], graph_type=GraphType.DAG)
    conditions = frozenset({"Z", *w})
    # Observe the real installed code object, without replacing ID or separator.
    calls = []
    previous = sys.getprofile()

    def record(frame, event, arg):
        if event == "call" and frame.f_code is core.id_algorithm.__code__:
            calls.append((frame.f_locals["treatment"], frame.f_locals["outcome"]))

    try:
        sys.setprofile(record)
        result = core.idc_algorithm(
            treatment=frozenset(), outcome=frozenset({"Y"}), conditions=conditions, graph=graph
        )
    finally:
        sys.setprofile(previous)
    assert calls == [(frozenset(), conditions | {"Y"}), (frozenset(), conditions)]
    assert result.status is IdentificationStatus.IDENTIFIED
    assert isinstance(result.estimand_ast.root, RatioNode)
    numerator, denominator = (
        result.estimand_ast.root.numerator,
        result.estimand_ast.root.denominator,
    )
    assert set(numerator.variables) == conditions | {"Y"}
    assert set(denominator.variables) == conditions
    assert any(step.rule_name == "IDC_DECOMPOSE" for step in result.proof_steps)
    # This is a consumer-walk witness, not an oracle for general ID formulas.


def _independent_latent_moral_separator(graph, x, y, conditioned):
    """Ancestral moralization, independent of endpoint-state traversal."""
    edges = []
    for index, edge in enumerate(graph.edges):
        if (edge.mark_src, edge.mark_dst) == (EdgeMark.TAIL, EdgeMark.ARROW):
            edges.append((edge.src, edge.dst))
        elif (edge.mark_src, edge.mark_dst) == (EdgeMark.ARROW, EdgeMark.TAIL):
            edges.append((edge.dst, edge.src))
        else:
            assert (edge.mark_src, edge.mark_dst) == (EdgeMark.ARROW, EdgeMark.ARROW)
            edges.extend([(f"latent_{index}", edge.src), (f"latent_{index}", edge.dst)])
    parents = {}
    for source, target in edges:
        parents.setdefault(target, set()).add(source)
    ancestral = set(x | y | conditioned)
    pending = list(ancestral)
    while pending:
        for parent in parents.get(pending.pop(), set()):
            if parent not in ancestral:
                ancestral.add(parent)
                pending.append(parent)
    moral = {node: set() for node in ancestral}
    for child in ancestral:
        family = parents.get(child, set()) & ancestral
        for parent in family:
            moral[parent].add(child)
            moral[child].add(parent)
        for left, right in combinations(family, 2):
            moral[left].add(right)
            moral[right].add(left)
    visited = set(conditioned)
    pending = list(x)
    while pending:
        node = pending.pop()
        if node in visited:
            continue
        if node in y:
            return False
        visited.add(node)
        pending.extend(moral[node] - visited)
    return True


@pytest.mark.parametrize("name,edges,w,_r1,_r2,_r3", CASES, ids=[case[0] for case in CASES])
def test_actual_idc_star_separator_calls_match_independent_latent_moralization(
    name, edges, w, _r1, _r2, _r3
):
    graph = _graph([CausalEdge(src=a, dst=b) for a, b in edges], graph_type=GraphType.DAG)
    calls = []
    previous = sys.getprofile()

    def record(frame, event, value):
        if event == "return" and frame.f_code is ops.m_separation.__code__:
            inputs = frame.f_locals
            expected = _independent_latent_moral_separator(
                inputs["graph"], inputs["x_set"], inputs["y_set"], inputs["z_set"]
            )
            calls.append((value, expected))

    try:
        sys.setprofile(record)
        # Actual IDC* invokes its separator; ordinary IDC above invokes two ID
        # calls. No separator or method result is replaced in either witness.
        result = ctf.idc_star_algorithm(
            CtfQuery("Y", (("T", 1.0),), evidence=(("Z", 1.0), *[(node, 1.0) for node in w])), graph
        )
    finally:
        sys.setprofile(previous)
    assert calls, (name, result.trace)
    assert all(actual is expected for actual, expected in calls), (name, calls)


def test_actual_bow_graph_is_not_identified_by_sid_or_conditional_id():
    # One unobserved common cause is represented by X↔Y, rather than making
    # U an observed collider joined by two distinct bidirected relations.
    graph = _graph(
        [CausalEdge(src="Z", dst="Y"), CausalEdge(src="Z", dst="Y", mark_src=EdgeMark.ARROW)],
        nodes=("Z", "Y"),
    )
    assert not _independent_latent_moral_separator(
        graph, frozenset({"Z"}), frozenset({"Y"}), frozenset()
    )
    intervention = ops.do_operator(graph, frozenset({"Z"}))
    assert not ops.extract_bidirected_edges(intervention)
    for result in [
        transport.sid_algorithm(
            treatment=frozenset({"Z"}),
            outcome=frozenset({"Y"}),
            graph=graph,
            policy=StochasticPolicy(policy_type="soft"),
        ),
        transport.conditional_intervention_id(
            treatment=frozenset({"Z"}),
            outcome=frozenset({"Y"}),
            condition_vars=frozenset(),
            graph=graph,
        ),
    ]:
        assert result.status is not IdentificationStatus.IDENTIFIED
        assert result.estimand_ast is None


def test_native_disjoint_amn_crossworld_separation_matches_independent_oracle():
    base = _graph(
        [CausalEdge(src="U", dst="Z"), CausalEdge(src="U", dst="Y"), CausalEdge(src="Z", dst="Y")],
        nodes=("U", "Z", "Y"),
    )
    base = base.model_copy(update={"metadata": {"shared_exogenous": ["U"]}})
    graph, metadata = amn.build_amn(base, {"w0": {"Z": 0.0}, "w1": {"Z": 1.0}})
    x, y = frozenset({"Z__w0"}), frozenset({"Y__w1"})
    for conditioned, expected in [(frozenset({"U"}), False), (frozenset({"U", "Z__w1"}), True)]:
        assert not (x & y or x & conditioned or y & conditioned)
        assert _independent_latent_moral_separator(graph, x, y, conditioned) is expected
        assert amn.amn_d_separation(graph, metadata, x, y, conditioned) is expected
