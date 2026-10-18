"""Static-profile admission and native symbolic consumers, on finite graphs.

These controls establish graph/rewriting properties, not an identified real-data
effect or general completeness of ID/PAG/counterfactual identification.
"""

import gc
import sys
import weakref
from itertools import combinations, product

import pytest

from polisyos.foundry.methods.catalog.causal import admg_ops as ops
from polisyos.foundry.methods.catalog.causal import amn, ctf_calculus
from polisyos.foundry.methods.catalog.causal import do_calculus as do
from polisyos.foundry.methods.catalog.causal import sigma_calculus as sigma
from polisyos.foundry.methods.catalog.causal._id_contracts import CtfQuery, IdentificationStatus
from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult, core, transport
from polisyos.foundry.methods.catalog.causal.id_engine import counterfactual as ctf
from polisyos.foundry.methods.catalog.causal.measurement_error import identify_with_proxy
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
from polisyos.ir.analytics.mgraph import (
    MissingnessKind,
    build_mgraph,
    extract_mgraph_metadata,
)
from polisyos.ir.analytics.transportability import SelectionDiagram, SNode


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


def _selection_diagram_with_base_graph(graph: CausalGraphModel) -> SelectionDiagram:
    """Pass an already-built graph through the diagram's live-field admission path."""
    valid_base = _graph(nodes=list(graph.nodes), graph_type=GraphType.DAG)
    diagram = SelectionDiagram(
        base_graph=valid_base,
        s_nodes=[],
        source_context=ContextProfile(),
        target_context=ContextProfile(),
    )
    return diagram.model_copy(update={"base_graph": graph})


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
            selection_diagram=_selection_diagram_with_base_graph(g),
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
    if graph.graph_type in {GraphType.PAG, GraphType.CPDAG}:
        expected_error = ops.PartialGraphCompletionSemanticsError
        expected_message = "no admitted completion semantics"
    else:
        expected_error = ops.UnsupportedStaticADMGProfileError
        expected_message = "Unsupported static ADMG profile: edge"
    with pytest.raises(expected_error, match=expected_message):
        consumer(graph)
    assert graph.model_dump_json() == before


@pytest.mark.parametrize("policy", list(PAGIdentificationPolicy))
def test_id_refuses_before_pag_orientation_or_optimistic_commitment(policy):
    graph = _graph(
        [CausalEdge(src="Z", dst="Y", mark_src=EdgeMark.CIRCLE)], graph_type=GraphType.PAG
    ).model_copy(update={"pag_identification_policy": policy})
    with pytest.raises(
        ops.UnsupportedStaticADMGProfileError,
        match="Unsupported static ADMG profile",
    ):
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


# Direct scalar query entries must consult graph kind as well as endpoint marks.
# Raw endpoint-inspection helpers intentionally stay outside this query gate.
PARTIAL_GRAPH_CONSUMERS = [
    (
        "id",
        lambda g: core.id_algorithm(treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=g),
    ),
    (
        "find-hedge",
        lambda g: core.find_hedge(treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=g),
    ),
    (
        "find-thicket",
        lambda g: core.find_thicket(treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=g),
    ),
    (
        "tr",
        lambda g: core.tr_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            selection_diagram=_selection_diagram_with_base_graph(g),
        ),
    ),
    (
        "idc",
        lambda g: core.idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset(),
            graph=g,
        ),
    ),
    (
        "oracle-fallback",
        lambda g: core.id_with_oracle_fallback(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=g,
            oracle="y0",
            force_y0=True,
        ),
    ),
    (
        "z-id",
        lambda g: transport.z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset({"Z"}),
            graph=g,
        ),
    ),
    (
        "mz-id",
        lambda g: transport.mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[],
            graph=g,
        ),
    ),
    (
        "sid",
        lambda g: transport.sid_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=g,
            policy=StochasticPolicy(policy_type="soft"),
        ),
    ),
    (
        "conditional",
        lambda g: transport.conditional_intervention_id(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            condition_vars=frozenset(),
            graph=g,
        ),
    ),
    (
        "dynamic",
        lambda g: transport.dynamic_intervention_id(
            treatment_sequence=["X"], outcome="Y", time_points=[0], graph=g
        ),
    ),
    (
        "joint",
        lambda g: transport.joint_id_algorithm(
            treatments=frozenset({"X"}), outcomes=frozenset({"Y"}), graph=g
        ),
    ),
    (
        "multi-outcome",
        lambda g: transport.multi_outcome_id(treatment=frozenset({"X"}), outcomes=["Y"], graph=g),
    ),
    ("id-star", lambda g: ctf.id_star_algorithm(CtfQuery("Y", (("X", 1.0),)), g)),
    ("idc-star", lambda g: ctf.idc_star_algorithm(CtfQuery("Y", (("X", 1.0),)), g)),
    (
        "proxy",
        lambda g: identify_with_proxy(g, "X", "Y", {"Z": "Z_proxy"}),
    ),
    ("do-rewrite", lambda g: do.rewrite_estimand(_ast(), g, max_iterations=2)),
    (
        "sigma-rewrite",
        lambda g: sigma.rewrite_estimand_with_selection(_ast(), g, frozenset(), 2),
    ),
    ("ctf-rewrite", lambda g: ctf_calculus.rewrite_ctf_estimand(_ast(), g, 2)),
]


@pytest.mark.parametrize("graph_type", [GraphType.PAG, GraphType.CPDAG])
@pytest.mark.parametrize("left,right", list(product(EdgeMark, repeat=2)))
def test_partial_graph_tags_refuse_direct_scalar_query_for_all_endpoint_pairs(
    graph_type, left, right
):
    # CPDAG rejects circles in the ordinary IR constructor; use the canonical
    # constructor for admitted profiles and a copied malformed profile only to
    # prove that strict admission rejects, rather than normalizes, bad IR.
    edge = CausalEdge(src="X", dst="Y", mark_src=left, mark_dst=right)
    try:
        graph = _graph([edge], nodes=("X", "Y", "Z"), graph_type=graph_type)
    except ValueError:
        graph = CausalGraphModel.model_construct(
            graph_type=graph_type,
            nodes=["X", "Y", "Z"],
            edges=[edge],
            schema_version="1.0",
            discovery_method="",
            skg_version_id=None,
            pag_identification_policy=PAGIdentificationPolicy.CONSERVATIVE,
            id_confidence_under_pag=None,
            metadata={},
        )
    if graph_type is GraphType.PAG:
        for _name, consumer in PARTIAL_GRAPH_CONSUMERS:
            with pytest.raises(
                ops.PartialGraphCompletionSemanticsError,
                match="no admitted completion semantics",
            ):
                consumer(graph)
    else:
        for _name, consumer in PARTIAL_GRAPH_CONSUMERS:
            with pytest.raises(ops.UnsupportedStaticADMGProfileError):
                consumer(graph)


@pytest.mark.parametrize("graph_type", [GraphType.PAG, GraphType.CPDAG])
@pytest.mark.parametrize("left,right", list(product(EdgeMark, repeat=2)))
def test_public_causal_engine_returns_typed_nonidentified_refusal_for_partial_graph(
    graph_type, left, right
):
    edge = CausalEdge(src="X", dst="Y", mark_src=left, mark_dst=right)
    try:
        graph = _graph([edge], nodes=("X", "Y"), graph_type=graph_type)
    except ValueError:
        graph = CausalGraphModel.model_construct(
            graph_type=graph_type,
            nodes=["X", "Y"],
            edges=[edge],
            schema_version="1.0",
            discovery_method="",
            skg_version_id=None,
            pag_identification_policy=PAGIdentificationPolicy.CONSERVATIVE,
            id_confidence_under_pag=None,
            metadata={},
        )
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine

    result = CausalEngine().identify("X", "Y", graph, oracle="y0")
    assert isinstance(result, IdentificationResult)
    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert result.hedge_certificate is None
    expected_reason = (
        "causal_graph_profile_invalid"
        if graph_type is GraphType.CPDAG and EdgeMark.CIRCLE in {left, right}
        else "partial_graph_completion_semantics_not_established"
    )
    assert result.metadata["limitation_code"] == expected_reason


def test_shared_cache_retains_the_exact_admitted_graph_snapshot():
    graph = _graph(
        [CausalEdge(src="X", dst="Y")],
        nodes=("X", "Y"),
        graph_type=GraphType.DAG,
    )

    cached = ops._get_cached_adjacency(graph)

    assert cached.graph is not graph
    assert cached.graph.model_dump(mode="json") == graph.model_dump(mode="json")
    assert cached.directed_edges == frozenset({("X", "Y")})


def test_canonical_scalar_admission_preserves_resolved_and_sigma_controls():
    from polisyos.foundry.methods.catalog.causal.admg_ops import canonical_scalar_query_graph

    dag = _graph(
        [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
        nodes=("X", "Y"),
        graph_type=GraphType.DAG,
    )
    admg = _graph(
        [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)],
        nodes=("X", "Y"),
        graph_type=GraphType.ADMG,
    )
    assert canonical_scalar_query_graph(dag).graph_type is GraphType.DAG
    assert canonical_scalar_query_graph(admg).graph_type is GraphType.ADMG
    admg_chain = _graph(
        [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
        nodes=("X", "Y"),
        graph_type=GraphType.ADMG,
    )
    assert (
        core.id_algorithm(treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=dag).status
        is IdentificationStatus.IDENTIFIED
    )
    assert (
        core.id_algorithm(
            treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=admg_chain
        ).status
        is IdentificationStatus.IDENTIFIED
    )

    cyclic_sigma = _graph(
        [
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="Y", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
        nodes=("X", "Y"),
        graph_type=GraphType.ADMG,
    )
    # The shared graph-kind gate does not impose a DAG/topological restriction
    # on the existing sigma/cyclic owner.
    assert not ops.m_separation(cyclic_sigma, frozenset({"X"}), frozenset({"Y"}), frozenset())
    sigma.apply_sigma_rule1(
        _ref(conditions=("X",)), cyclic_sigma, frozenset({"X"}), frozenset({"X"})
    )


@pytest.mark.parametrize("source_type", [GraphType.DAG, GraphType.ADMG])
def test_model_copy_profile_mutations_are_rebuilt_before_scalar_use(source_type):
    """Copy updates cannot forge graph-kind or endpoint admission."""
    directed = _graph(
        [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
        nodes=("X", "Y"),
        graph_type=source_type,
    )
    partial_tag = directed.model_copy(update={"graph_type": GraphType.PAG})
    with pytest.raises(ops.PartialGraphCompletionSemanticsError):
        core.id_algorithm(treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=partial_tag)

    forged_endpoint = directed.model_copy(
        update={
            "edges": [
                CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)
            ]
        }
    )
    with pytest.raises(ops.UnsupportedStaticADMGProfileError):
        core.id_algorithm(
            treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=forged_endpoint
        )


def test_scalar_snapshot_gate_uses_ir_fields_not_model_dump_override():
    class ForgedDumpGraph(CausalGraphModel):
        def model_dump(self, *args, **kwargs):
            return {
                "graph_type": "dag",
                "nodes": ["X", "Y"],
                "edges": [],
            }

    forged = ForgedDumpGraph(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
    )
    with pytest.raises(ops.UnsupportedStaticADMGProfileError):
        core.id_algorithm(treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=forged)


@pytest.mark.parametrize("graph_type", [GraphType.PAG, GraphType.CPDAG])
def test_oracle_fallback_never_receives_partial_graph_without_completion_semantics(
    graph_type, monkeypatch
):
    graph = _graph(
        [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
        nodes=("X", "Y"),
        graph_type=graph_type,
    )

    def oracle_must_not_run(**_kwargs):
        raise AssertionError("partial-graph admission must run before Y0")

    monkeypatch.setattr(core, "_oracle_y0", oracle_must_not_run)
    with pytest.raises(ops.UnsupportedStaticADMGProfileError):
        core.id_with_oracle_fallback(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
            oracle="y0",
            force_y0=True,
        )


def test_mgraph_query_dispatch_remains_outside_static_partial_graph_gate():
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
    from polisyos.ir.analytics.mgraph import MissingnessKind, build_mgraph

    graph = build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        missingness_map={"X": MissingnessKind.MCAR},
    )
    result = CausalEngine().identify("X", "Y", graph)
    assert not (
        isinstance(result, IdentificationResult)
        and result.metadata.get("limitation_code")
        == "partial_graph_completion_semantics_not_established"
    )


def test_remove_static_id_profile_gate_reopens_fully_oriented_pag_identification(
    monkeypatch,
):
    """The failure is tied to the actual profile premise, not refusal markers."""
    graph = _graph(
        [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
        nodes=("X", "Y"),
        graph_type=GraphType.PAG,
    )

    # The shared cache boundary refuses even a fully oriented PAG tag before
    # endpoint-only extraction can return a scalar adjacency view.
    with pytest.raises(ops.PartialGraphCompletionSemanticsError):
        ops.extract_directed_edges(graph)

    # Keep canonical field rebuilding and endpoint validation, but remove both
    # graph-kind premises: the canonical query tag refusal and the shared
    # static-ID profile allowlist. The live cache and method calls remain intact.
    monkeypatch.setattr(
        ops,
        "canonical_scalar_query_graph",
        ops.canonical_causal_graph_snapshot,
    )
    assert ops.extract_directed_edges(graph) == frozenset({("X", "Y")})
    monkeypatch.setattr(core, "_validate_static_id_graph", ops._validate_static_admg)
    result = core.id_algorithm(treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=graph)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None


class _HiddenFalseSNodes(list):
    def __bool__(self) -> bool:
        return False


def test_direct_tr_consumes_canonical_selection_diagram_fields():
    graph = _graph(
        [CausalEdge(src="X", dst="M"), CausalEdge(src="M", dst="Y")],
        nodes=("X", "M", "Y"),
        graph_type=GraphType.DAG,
    )
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[
            SNode(
                target_variable="M",
                context_dimension="institutional_quality",
                source_value=0.8,
                target_value=0.4,
                delta=0.4,
                severity="medium",
            )
        ],
        source_context=ContextProfile(context_id="source"),
        target_context=ContextProfile(context_id="target"),
    )
    admitted = ops.canonical_scalar_selection_diagram(diagram)
    assert len(admitted.s_nodes) == 1
    assert admitted.s_nodes[0].target_variable == "M"
    result = core.tr_algorithm(
        treatment=frozenset({"X"}), outcome=frozenset({"Y"}), selection_diagram=diagram
    )
    assert any("s_nodes=['M']" in line for line in result.trace)

    hidden = diagram.model_copy(update={"s_nodes": _HiddenFalseSNodes(diagram.s_nodes)})
    with pytest.raises(ops.InvalidCausalGraphProfileError):
        core.tr_algorithm(
            treatment=frozenset({"X"}), outcome=frozenset({"Y"}), selection_diagram=hidden
        )


def _mnar_mgraph():
    return build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        missingness_map={"X": MissingnessKind.MNAR},
    )


def _cyclic_frontdoor_admg():
    return _graph(
        [
            CausalEdge(src="X", dst="M"),
            CausalEdge(src="M", dst="Y"),
            CausalEdge(src="Y", dst="X"),
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.ARROW,
                mark_dst=EdgeMark.ARROW,
            ),
        ],
        nodes=("X", "M", "Y"),
        graph_type=GraphType.ADMG,
    )


CYCLIC_ADMG_ID_CONSUMERS = [
    (
        "id",
        lambda graph: core.id_algorithm(
            treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=graph
        ),
    ),
    (
        "idc",
        lambda graph: core.idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset({"M"}),
            graph=graph,
        ),
    ),
    (
        "oracle-fallback",
        lambda graph: core.id_with_oracle_fallback(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
            oracle="none",
        ),
    ),
    (
        "find-hedge",
        lambda graph: core.find_hedge(
            treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=graph
        ),
    ),
    (
        "find-thicket",
        lambda graph: core.find_thicket(
            treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=graph
        ),
    ),
    (
        "tr",
        lambda graph: core.tr_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            selection_diagram=SelectionDiagram(
                base_graph=graph,
                s_nodes=[],
                source_context=ContextProfile(),
                target_context=ContextProfile(),
            ),
        ),
    ),
    (
        "z-id",
        lambda graph: transport.z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset({"M"}),
            graph=graph,
        ),
    ),
    (
        "mz-id",
        lambda graph: transport.mz_id_algorithm(
            treatment=frozenset({"X"}), outcome=frozenset({"Y"}), source_domains=[], graph=graph
        ),
    ),
    (
        "sid",
        lambda graph: transport.sid_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            policy=StochasticPolicy(policy_type="soft"),
            graph=graph,
        ),
    ),
    (
        "conditional-id",
        lambda graph: transport.conditional_intervention_id(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            condition_vars=frozenset({"M"}),
            graph=graph,
        ),
    ),
    (
        "dynamic-id",
        lambda graph: transport.dynamic_intervention_id(
            treatment_sequence=["X"], outcome="Y", time_points=[0], graph=graph
        ),
    ),
    (
        "joint-id",
        lambda graph: transport.joint_id_algorithm(
            treatments=frozenset({"X"}), outcomes=frozenset({"Y"}), graph=graph
        ),
    ),
    (
        "multi-outcome-id",
        lambda graph: transport.multi_outcome_id(
            treatment=frozenset({"X"}), outcomes=["Y"], graph=graph
        ),
    ),
    ("id-star", lambda graph: ctf.id_star_algorithm(CtfQuery("Y", (("X", 1.0),)), graph)),
    ("idc-star", lambda graph: ctf.idc_star_algorithm(CtfQuery("Y", (("X", 1.0),)), graph)),
    (
        "proxy-id",
        lambda graph: identify_with_proxy(graph, "X", "Y", {"M": "M_proxy"}),
    ),
]


@pytest.mark.parametrize(
    "name,consumer", CYCLIC_ADMG_ID_CONSUMERS, ids=[name for name, _ in CYCLIC_ADMG_ID_CONSUMERS]
)
def test_static_id_consumers_refuse_cyclic_admg_before_shortcuts(name, consumer):
    with pytest.raises(ops.UnsupportedStaticADMGProfileError, match="directed cycle"):
        consumer(_cyclic_frontdoor_admg())


def test_cyclic_admg_refuses_before_selected_oracle_fallback(monkeypatch):
    def oracle_must_not_run(**_kwargs):
        raise AssertionError("cyclic ADMG must be refused before an oracle fallback")

    monkeypatch.setattr(core, "_oracle_y0", oracle_must_not_run)
    with pytest.raises(ops.UnsupportedStaticADMGProfileError, match="directed cycle"):
        core.id_with_oracle_fallback(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=_cyclic_frontdoor_admg(),
            oracle="y0",
            force_y0=True,
        )


@pytest.mark.parametrize(
    "name,consumer",
    CYCLIC_ADMG_ID_CONSUMERS,
    ids=[name for name, _ in CYCLIC_ADMG_ID_CONSUMERS],
)
def test_static_id_consumers_refuse_mgraph_without_full_law_inputs(name, consumer):
    with pytest.raises(
        ops.UnsupportedStaticADMGProfileError,
        match="full-law recovery inputs",
    ):
        consumer(_mnar_mgraph())


def test_mnar_mgraph_routes_to_full_law_owner_not_scalar_id():
    graph = _mnar_mgraph()
    with pytest.raises(
        ops.UnsupportedStaticADMGProfileError,
        match="full-law recovery inputs",
    ):
        core.id_algorithm(treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=graph)

    from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        full_law_identify,
    )

    full_law = full_law_identify(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        mgraph_meta=extract_mgraph_metadata(graph),
    )
    assert full_law.status is IdentificationStatus.NOT_RECOVERABLE
    assert full_law.estimand_ast is None


def test_direct_tr_refuses_s_node_targets_outside_base_graph():
    graph = _graph(
        [CausalEdge(src="X", dst="Y")],
        nodes=("X", "Y"),
        graph_type=GraphType.DAG,
    )
    valid = SelectionDiagram(
        base_graph=graph,
        s_nodes=[
            SNode(
                target_variable="Y",
                context_dimension="institutional_quality",
                source_value=0.8,
                target_value=0.4,
                delta=0.4,
                severity="medium",
            )
        ],
        source_context=ContextProfile(context_id="source"),
        target_context=ContextProfile(context_id="target"),
    )
    unknown_target = SNode(
        target_variable="GHOST",
        context_dimension="institutional_quality",
        source_value=0.8,
        target_value=0.4,
        delta=0.4,
        severity="medium",
    )
    malformed_diagrams = (
        valid.model_copy(update={"s_nodes": [unknown_target]}),
        SelectionDiagram(
            base_graph=graph,
            s_nodes=[unknown_target],
            source_context=valid.source_context,
            target_context=valid.target_context,
        ),
    )

    for diagram in malformed_diagrams:
        with pytest.raises(ops.InvalidCausalGraphProfileError, match="S-node target"):
            core.tr_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                selection_diagram=diagram,
            )


def test_adjacency_cache_revalidates_full_content_before_reuse():
    ops._ADJ_CACHE.clear()
    ops._CC_CACHE.clear()
    graph = _graph(
        [CausalEdge(src="Y", dst="Z", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
        nodes=("Y", "Z"),
        graph_type=GraphType.ADMG,
    )
    first = ops._get_cached_adjacency(graph)
    first_key = first.content_key
    first_components = ops.c_components(graph)
    _ = first.graph.kuzu_node_rows
    _ = first.graph.kuzu_edge_rows
    assert ops._get_cached_adjacency(graph) is first

    equivalent = _graph(
        [CausalEdge(src="Y", dst="Z", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
        nodes=("Y", "Z"),
        graph_type=GraphType.ADMG,
    )
    assert equivalent is not graph
    assert ops._get_cached_adjacency(equivalent) is first
    assert ops.c_components(equivalent) == first_components
    assert ops._ADJ_CACHE[first_key] is first
    assert ops._CC_CACHE[first_key] == tuple(first_components)

    original_edges = graph.edges
    cache_sizes = (len(ops._ADJ_CACHE), len(ops._CC_CACHE))
    object.__setattr__(
        graph,
        "edges",
        [CausalEdge(src="Y", dst="Z", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE)],
    )
    with pytest.raises(ops.UnsupportedStaticADMGProfileError):
        ops._get_cached_adjacency(graph)
    assert (len(ops._ADJ_CACHE), len(ops._CC_CACHE)) == cache_sizes
    object.__setattr__(graph, "edges", [CausalEdge(src="Y", dst="Z", lag=1)])
    with pytest.raises(ops.UnsupportedStaticADMGProfileError, match="lag=1"):
        ops._get_cached_adjacency(graph)
    assert (len(ops._ADJ_CACHE), len(ops._CC_CACHE)) == cache_sizes
    object.__setattr__(graph, "edges", original_edges)
    assert ops._get_cached_adjacency(graph) is first

    object.__setattr__(
        graph,
        "edges",
        [CausalEdge(src="Y", dst="Z", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.TAIL)],
    )
    reversed_marks = ops._get_cached_adjacency(graph)
    assert reversed_marks is not first
    assert reversed_marks.content_key != first_key
    object.__setattr__(graph, "edges", [CausalEdge(src="Y", dst="Z", lag=0)])
    lagged_zero = ops._get_cached_adjacency(graph)
    assert lagged_zero is not first
    assert lagged_zero.content_key != reversed_marks.content_key
    object.__setattr__(graph, "edges", original_edges)
    assert ops._get_cached_adjacency(graph) is first

    original_graph_type = graph.graph_type
    object.__setattr__(graph, "graph_type", GraphType.DAG)
    changed_kind = ops._get_cached_adjacency(graph)
    assert changed_kind is not first
    assert changed_kind.content_key != first_key
    type_cache_sizes = (len(ops._ADJ_CACHE), len(ops._CC_CACHE))
    object.__setattr__(graph, "graph_type", GraphType.PAG)
    with pytest.raises(ops.PartialGraphCompletionSemanticsError):
        ops._get_cached_adjacency(graph)
    assert (len(ops._ADJ_CACHE), len(ops._CC_CACHE)) == type_cache_sizes
    object.__setattr__(graph, "graph_type", original_graph_type)
    assert ops._get_cached_adjacency(graph) is first

    original_metadata = graph.metadata
    object.__setattr__(graph, "metadata", {"cache-content-probe": "changed"})
    changed = ops._get_cached_adjacency(graph)
    assert changed is not first
    assert changed.content_key != first_key
    assert changed.content_key in ops._ADJ_CACHE
    ops.c_components(graph)
    assert changed.content_key in ops._CC_CACHE
    object.__setattr__(graph, "metadata", original_metadata)
    assert ops._get_cached_adjacency(graph) is first

    unique = _graph(
        [CausalEdge(src="A", dst="B", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
        nodes=("A", "B"),
        graph_type=GraphType.DAG,
    )
    object.__setattr__(unique, "metadata", {"unique-cache-source": True})
    unique_key = ops._get_cached_adjacency(unique).content_key
    ops.c_components(unique)
    source_ref = weakref.ref(unique)
    del unique
    gc.collect()
    assert source_ref() is None
    assert unique_key in ops._ADJ_CACHE
    assert unique_key in ops._CC_CACHE
