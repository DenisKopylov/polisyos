from __future__ import annotations

import sys
import types
from itertools import product

import pytest

from polisyos.foundry.methods.catalog.causal._id_contracts import IdentificationStatus
from polisyos.foundry.methods.catalog.causal.id_engine.core import (
    find_hedge,
    find_thicket,
    id_algorithm,
    id_with_oracle_fallback,
    idc_algorithm,
    tr_algorithm,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ProductNode,
    RatioNode,
    SideCondition,
    SideConditionKind,
    SumNode,
)
from polisyos.ir.analytics.transportability import SelectionDiagram, SNode


def _edge(source: str, target: str, *, bidirected: bool = False) -> CausalEdge:
    if bidirected:
        return CausalEdge(
            src=source,
            dst=target,
            mark_src=EdgeMark.ARROW,
            mark_dst=EdgeMark.ARROW,
        )
    return CausalEdge(
        src=source,
        dst=target,
        mark_src=EdgeMark.TAIL,
        mark_dst=EdgeMark.ARROW,
    )


def _graph(kind: str) -> CausalGraphModel:
    if kind == "confounding_on_m2":
        edges = [
            _edge("X", "M1"),
            _edge("M1", "Y"),
            _edge("M2", "Y"),
            _edge("X", "M2", bidirected=True),
        ]
    elif kind == "confounding_on_m1":
        edges = [
            _edge("X", "M2"),
            _edge("M1", "Y"),
            _edge("M2", "Y"),
            _edge("X", "M1", bidirected=True),
        ]
    elif kind == "both_mediators_confound_x":
        edges = [
            _edge("M1", "Y"),
            _edge("M2", "Y"),
            _edge("X", "M1", bidirected=True),
            _edge("X", "M2", bidirected=True),
        ]
    else:
        raise AssertionError(f"unknown graph: {kind}")
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M1", "M2", "Y"],
        edges=edges,
    )


def _conditional(variable: str, conditioning: tuple[str, ...], *, dataset: str) -> DistributionRef:
    return DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=(variable,),
        conditioning=conditioning,
        dataset_ref=dataset,
        side_conditions=(
            SideCondition(
                kind=SideConditionKind.POSITIVITY,
                variables=conditioning,
                description="Positivity required for conditioning variables",
            ),
        )
        if conditioning
        else (),
    )


def _expected_step4(kind: str, *, dataset: str) -> EstimandAST:
    mediator_one = (
        _conditional("M1", ("X",), dataset=dataset)
        if kind == "confounding_on_m2"
        else _conditional("M1", (), dataset=dataset)
    )
    mediator_two = (
        _conditional("M2", ("X",), dataset=dataset)
        if kind == "confounding_on_m1"
        else _conditional("M2", (), dataset=dataset)
    )
    return EstimandAST(
        query_str="P(Y|do(X))",
        root=SumNode(
            summation_vars=("M1", "M2"),
            operand=ProductNode(
                factors=(
                    _conditional("Y", ("M1", "M2", "X"), dataset=dataset),
                    mediator_one,
                    mediator_two,
                ),
            ),
        ),
        treatment="X",
        outcome="Y",
        all_variables=("M1", "M2", "X", "Y"),
        identification_method="id_step4_factorization",
    )


def _expected_step1(*, dataset: str) -> EstimandAST:
    return EstimandAST(
        query_str="P(Y|do(X))",
        root=DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=("Y",),
            dataset_ref=dataset,
        ),
        treatment="X",
        outcome="Y",
        all_variables=("M1", "M2", "X", "Y"),
        identification_method="id_step1",
    )


def _weighted_rows(
    probabilities: tuple[float, ...],
    equations,
) -> list[tuple[dict[str, int], float]]:
    rows: list[tuple[dict[str, int], float]] = []
    for bits in product((0, 1), repeat=len(probabilities)):
        weight = 1.0
        for bit, probability in zip(bits, probabilities, strict=True):
            weight *= probability if bit else 1.0 - probability
        rows.append((equations(*bits), weight))
    return rows


def _observational_rows(kind: str) -> list[tuple[dict[str, int], float]]:
    if kind == "confounding_on_m2":
        return _weighted_rows(
            (0.5, 0.25, 0.2),
            lambda u, ex, em1: {
                "X": u ^ ex,
                "M1": (u ^ ex) ^ em1,
                "M2": u,
                "Y": int(((u ^ ex) ^ em1) or u),
            },
        )
    if kind == "confounding_on_m1":
        return _weighted_rows(
            (0.5, 0.25, 0.2),
            lambda u, ex, em2: {
                "X": u ^ ex,
                "M1": u,
                "M2": (u ^ ex) ^ em2,
                "Y": int(u or ((u ^ ex) ^ em2)),
            },
        )
    return _weighted_rows(
        (0.5, 0.5),
        lambda u1, u2: {
            "X": int(u1 or u2),
            "M1": u1,
            "M2": u2,
            "Y": int(u1 or u2),
        },
    )


def _interventional_y1_probability(kind: str) -> float:
    if kind == "confounding_on_m2":
        rows = _weighted_rows(
            (0.5, 0.2),
            lambda u, em1: {
                "M1": 1 ^ em1,
                "M2": u,
                "Y": int((1 ^ em1) or u),
            },
        )
    elif kind == "confounding_on_m1":
        rows = _weighted_rows(
            (0.5, 0.2),
            lambda u, em2: {
                "M1": u,
                "M2": 1 ^ em2,
                "Y": int(u or (1 ^ em2)),
            },
        )
    else:
        rows = _weighted_rows(
            (0.5, 0.5),
            lambda u1, u2: {
                "M1": u1,
                "M2": u2,
                "Y": int(u1 or u2),
            },
        )
    return sum(weight for values, weight in rows if values["Y"] == 1)


def _eval_node(node, values: dict[str, int], rows: list[tuple[dict[str, int], float]]) -> float:
    if isinstance(node, DistributionRef):
        assert node.domain is DistributionDomain.SOURCE
        assert not node.intervention_set
        matching_condition = [
            (row, weight)
            for row, weight in rows
            if all(row[name] == values[name] for name in node.conditioning)
        ]
        denominator = sum(weight for _, weight in matching_condition)
        numerator = sum(
            weight
            for row, weight in matching_condition
            if all(row[name] == values[name] for name in node.variables)
        )
        return numerator / denominator
    if isinstance(node, ProductNode):
        result = 1.0
        for factor in node.factors:
            result *= _eval_node(factor, values, rows)
        return result
    if isinstance(node, SumNode):
        return sum(
            _eval_node(
                node.operand,
                {**values, **dict(zip(node.summation_vars, assignment, strict=True))},
                rows,
            )
            for assignment in product((0, 1), repeat=len(node.summation_vars))
        )
    raise AssertionError(f"unsupported AST node {type(node).__name__}")


@pytest.mark.parametrize(
    ("kind", "expected_effect"),
    [
        ("confounding_on_m2", 0.9),
        ("confounding_on_m1", 0.9),
        ("both_mediators_confound_x", 0.75),
    ],
)
def test_step4_composes_complete_normalized_ast_and_matches_independent_scm(
    kind: str,
    expected_effect: float,
) -> None:
    dataset = f"source-{kind}"
    result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=_graph(kind),
        dataset_ref=dataset,
    )

    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.hedge_certificate is None
    assert result.estimand_ast is not None
    assert result.estimand_ast.treatment == "X"
    assert result.estimand_ast.outcome == "Y"
    assert result.estimand_ast.all_variables == ("M1", "M2", "X", "Y")
    assert result.required_distributions == result.estimand_ast.collect_distribution_refs()
    expected_ast = (
        _expected_step1(dataset=dataset)
        if kind == "both_mediators_confound_x"
        else _expected_step4(kind, dataset=dataset)
    )
    assert result.estimand_ast.normalize().model_dump(mode="json") == (
        expected_ast.normalize().model_dump(mode="json")
    )

    rows = _observational_rows(kind)
    evaluated = _eval_node(result.estimand_ast.root, {"X": 1, "Y": 1}, rows)
    assert evaluated == pytest.approx(expected_effect)
    assert _interventional_y1_probability(kind) == pytest.approx(expected_effect)


def test_two_node_confounding_is_shrunk_to_observational_outcome_law() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[_edge("X", "Y", bidirected=True)],
    )
    result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        dataset_ref="source-two-node",
    )

    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.hedge_certificate is None
    assert result.estimand_ast is not None
    assert result.estimand_ast.root == DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        dataset_ref="source-two-node",
    )
    assert result.estimand_ast.treatment == "X"
    assert result.estimand_ast.outcome == "Y"
    assert result.estimand_ast.all_variables == ("X", "Y")


def test_bow_graph_remains_a_hedge_refusal_without_an_estimand() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[
            _edge("X", "Y"),
            _edge("X", "Y", bidirected=True),
        ],
    )
    result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
    )

    assert result.status is IdentificationStatus.HEDGE_FOUND
    assert result.estimand_ast is None
    assert result.hedge_certificate is not None
    assert result.hedge_certificate.treatment == frozenset({"X"})
    assert result.hedge_certificate.outcome == frozenset({"Y"})


def test_mediator_confounding_without_q_kernel_is_not_misidentified() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M", "Y"],
        edges=[
            _edge("X", "M"),
            _edge("M", "Y"),
            _edge("X", "M", bidirected=True),
        ],
    )
    result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
    )

    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert result.hedge_certificate is None
    assert result.trace


def _double_frontdoor_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M1", "M2", "Y"],
        edges=[
            _edge("X", "M1"),
            _edge("M1", "Y"),
            _edge("X", "M2"),
            _edge("M2", "Y"),
            _edge("X", "Y", bidirected=True),
        ],
    )


def _expected_y0_double_frontdoor(*, dataset: str) -> EstimandAST:
    return EstimandAST(
        query_str="P(Y|do(X))",
        root=SumNode(
            summation_vars=("M1", "M2"),
            operand=ProductNode(
                factors=(
                    DistributionRef(
                        domain=DistributionDomain.SOURCE,
                        variables=("M1",),
                        conditioning=("X",),
                        dataset_ref=dataset,
                    ),
                    DistributionRef(
                        domain=DistributionDomain.SOURCE,
                        variables=("M2",),
                        conditioning=("X",),
                        dataset_ref=dataset,
                    ),
                    SumNode(
                        summation_vars=("X",),
                        operand=ProductNode(
                            factors=(
                                DistributionRef(
                                    domain=DistributionDomain.SOURCE,
                                    variables=("X",),
                                    dataset_ref=dataset,
                                ),
                                DistributionRef(
                                    domain=DistributionDomain.SOURCE,
                                    variables=("Y",),
                                    conditioning=("M1", "M2", "X"),
                                    dataset_ref=dataset,
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        treatment="X",
        outcome="Y",
        all_variables=("M1", "M2", "X", "Y"),
        identification_method="y0_oracle",
    )


def _free_variables(node) -> set[str]:
    if isinstance(node, DistributionRef):
        return {*node.variables, *node.conditioning, *node.intervention_set}
    if isinstance(node, ProductNode):
        return set().union(*(_free_variables(factor) for factor in node.factors))
    if isinstance(node, SumNode):
        return _free_variables(node.operand) - set(node.summation_vars)
    if isinstance(node, RatioNode):
        return _free_variables(node.numerator) | _free_variables(node.denominator)
    raise AssertionError(f"unsupported AST node {type(node).__name__}")


def _double_frontdoor_observational_rows() -> list[tuple[dict[str, int], float]]:
    return _weighted_rows(
        (0.5, 0.25, 0.2, 0.3),
        lambda u, ex, em1, em2: {
            "X": u ^ ex,
            "M1": (u ^ ex) ^ em1,
            "M2": (u ^ ex) ^ em2,
            "Y": int(u or ((u ^ ex) ^ em1) or ((u ^ ex) ^ em2)),
        },
    )


def _double_frontdoor_do_y1_probability() -> float:
    rows = _weighted_rows(
        (0.5, 0.2, 0.3),
        lambda u, em1, em2: {
            "M1": 1 ^ em1,
            "M2": 1 ^ em2,
            "Y": int(u or (1 ^ em1) or (1 ^ em2)),
        },
    )
    return sum(weight for values, weight in rows if values["Y"] == 1)


def test_step6_requires_q_kernel_and_explicit_y0_fallback_preserves_full_formula() -> None:
    graph = _double_frontdoor_graph()
    dataset = "source-double-frontdoor"
    query = {
        "treatment": frozenset({"X"}),
        "outcome": frozenset({"Y"}),
        "graph": graph,
        "dataset_ref": dataset,
    }

    assert (
        find_hedge(
            treatment=query["treatment"],
            outcome=query["outcome"],
            graph=graph,
        )
        is None
    )
    assert (
        find_thicket(
            treatment=query["treatment"],
            outcome=query["outcome"],
            graph=graph,
        )
        == []
    )

    native = id_algorithm(**query)
    assert native.status is IdentificationStatus.ORACLE_NEEDED
    assert not any("Frontdoor shortcut" in trace for trace in native.trace)
    assert native.estimand_ast is None
    assert native.hedge_certificate is None
    assert any(step.rule_name == "ORACLE" for step in native.proof_steps)
    assert any("requires Q[Sj]" in trace for trace in native.trace)

    unbacked = id_with_oracle_fallback(**query, oracle="none")
    assert unbacked.status is IdentificationStatus.ORACLE_NEEDED
    assert unbacked.estimand_ast is None
    assert unbacked.hedge_certificate is None

    result = id_with_oracle_fallback(**query, oracle="y0")
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.algorithm_version.startswith("y0_")
    assert result.metadata["backend_id"] == "y0"
    assert result.metadata["backend_operation"] == "identify_outcomes"
    assert result.metadata["backend_call_attempted"] is True
    assert "oracle_y0:api_called:identify_outcomes" in result.trace
    assert result.estimand_ast is not None
    expected = _expected_y0_double_frontdoor(dataset=dataset)
    assert result.estimand_ast.normalize().model_dump(mode="json") == (
        expected.normalize().model_dump(mode="json")
    )
    assert result.required_distributions == result.estimand_ast.collect_distribution_refs()
    assert _free_variables(result.estimand_ast.root) == {"X", "Y"}

    rows = _double_frontdoor_observational_rows()
    evaluated = _eval_node(result.estimand_ast.root, {"X": 1, "Y": 1}, rows)
    do_probability = _double_frontdoor_do_y1_probability()
    assert do_probability == pytest.approx(0.97)
    assert evaluated == pytest.approx(do_probability)


def test_step5_q_factorization_retains_nonparent_predecessor_and_matches_scm() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M", "Y"],
        edges=[
            _edge("X", "M"),
            _edge("M", "Y"),
            _edge("M", "Y", bidirected=True),
        ],
    )
    dataset = "source-step5-q-kernel"
    result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        dataset_ref=dataset,
    )

    expected = EstimandAST(
        query_str="P(Y|do(X))",
        root=SumNode(
            summation_vars=("M",),
            operand=ProductNode(
                factors=(
                    _conditional("M", ("X",), dataset=dataset),
                    _conditional("Y", ("M", "X"), dataset=dataset),
                ),
            ),
        ),
        treatment="X",
        outcome="Y",
        all_variables=("M", "X", "Y"),
        identification_method="id_step5_ccomponent",
    )
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert result.estimand_ast.normalize().model_dump(mode="json") == (
        expected.normalize().model_dump(mode="json")
    )
    assert result.required_distributions == result.estimand_ast.collect_distribution_refs()
    assert _free_variables(result.estimand_ast.root) == {"X", "Y"}

    # X and U are independent fair bits; M=X xor U and Y=M xor U xor N.
    # Therefore do(X=x) gives P(Y=1) = .1 for x=0 and .9 for x=1.
    observational_rows = _weighted_rows(
        (0.5, 0.5, 0.1),
        lambda x, u, noise: {"X": x, "M": x ^ u, "Y": (x ^ u) ^ u ^ noise},
    )
    for x_value, expected_y1 in ((0, 0.1), (1, 0.9)):
        do_rows = _weighted_rows(
            (0.5, 0.1),
            lambda u, noise, x=x_value: {
                "X": x,
                "M": x ^ u,
                "Y": (x ^ u) ^ u ^ noise,
            },
        )
        direct_effect = sum(weight for values, weight in do_rows if values["Y"] == 1)
        formula_effect = _eval_node(
            result.estimand_ast.root,
            {"X": x_value, "Y": 1},
            observational_rows,
        )
        assert direct_effect == pytest.approx(expected_y1)
        assert formula_effect == pytest.approx(direct_effect)

        # The old parent-only Y kernel P(Y|M) predicts .5 at either treatment
        # level on this SCM, so this witness distinguishes the missing X factor.
        old_formula = SumNode(
            summation_vars=("M",),
            operand=ProductNode(
                factors=(
                    _conditional("M", ("X",), dataset=dataset),
                    _conditional("Y", ("M",), dataset=dataset),
                ),
            ),
        )
        assert _eval_node(
            old_formula,
            {"X": x_value, "Y": 1},
            observational_rows,
        ) == pytest.approx(0.5)


def test_dosearch_formula_remains_unidentified_without_typed_ast_importer(monkeypatch) -> None:
    formula = "P(X) * sum_m P(M|X) * P(Y|M)"
    graph = _double_frontdoor_graph()

    class _BackendResult:
        def rx2(self, key: str) -> list[str]:
            assert key == "formula"
            return [formula]

    class _Dosearch:
        def dosearch(self, **kwargs):
            assert kwargs["data"] == ["p(M1, M2, X, Y)"]
            return _BackendResult()

    rpy2 = types.ModuleType("rpy2")
    rpy2.__path__ = []
    robjects = types.ModuleType("rpy2.robjects")
    robjects.StrVector = list
    packages = types.ModuleType("rpy2.robjects.packages")
    packages.importr = lambda name: _Dosearch() if name == "dosearch" else None
    monkeypatch.setitem(sys.modules, "rpy2", rpy2)
    monkeypatch.setitem(sys.modules, "rpy2.robjects", robjects)
    monkeypatch.setitem(sys.modules, "rpy2.robjects.packages", packages)

    result = id_with_oracle_fallback(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        oracle="dosearch",
        dataset_ref="source-dosearch",
    )

    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert result.hedge_certificate is None
    assert result.algorithm_version == "dosearch_oracle"
    assert result.metadata["backend_id"] == "dosearch"
    assert result.metadata["backend_call_attempted"] is True
    assert result.metadata["backend_call_established"] is True
    assert result.metadata["backend_result"] == "formula_returned"
    assert result.metadata["backend_formula"] == formula
    assert result.metadata["gate_predicates"]["typed_formula_import"] == "not_established"
    assert result.required_distributions == []
    assert any(
        "returned_formula_cannot_be_imported_to_typed_ast" in trace for trace in result.trace
    )


def test_frontdoor_shortcut_rejects_extra_backdoor_and_bidirected_shapes() -> None:
    graphs = (
        CausalGraphModel(
            graph_type=GraphType.ADMG,
            nodes=["X", "M", "Y", "Z"],
            edges=[
                _edge("X", "M"),
                _edge("M", "Y"),
                _edge("X", "Y", bidirected=True),
                _edge("M", "Z", bidirected=True),
                _edge("Z", "Y"),
            ],
        ),
        CausalGraphModel(
            graph_type=GraphType.ADMG,
            nodes=["X", "M", "Y"],
            edges=[
                _edge("X", "Y"),
                _edge("X", "M", bidirected=True),
                _edge("M", "Y", bidirected=True),
            ],
        ),
    )
    for graph in graphs:
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        assert not any("Frontdoor shortcut" in trace for trace in result.trace)
        assert result.estimand_ast is None or (
            result.estimand_ast.identification_method != "frontdoor"
        )


def test_empty_intervention_returns_outcome_marginal_not_ancestor_conditional() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Z", "Y"],
        edges=[_edge("Z", "Y")],
    )
    result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        dataset_ref="source-empty-intervention",
    )
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert result.estimand_ast.root == DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        dataset_ref="source-empty-intervention",
    )

    rows = _weighted_rows(
        (0.5, 0.5, 0.2),
        lambda x, z, noise: {"X": x, "Z": z, "Y": int(z or noise)},
    )
    expected = sum(weight for values, weight in rows if values["Y"] == 1)
    assert expected == pytest.approx(0.6)
    assert _eval_node(result.estimand_ast.root, {"Y": 1}, rows) == pytest.approx(expected)


def test_recursive_c_component_shape_returns_valid_hedge_without_recursing() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "A", "Y"],
        edges=[
            _edge("X", "A"),
            _edge("A", "Y"),
            _edge("X", "A", bidirected=True),
            _edge("X", "Y", bidirected=True),
        ],
    )
    result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
    )

    assert result.status is IdentificationStatus.HEDGE_FOUND
    assert result.estimand_ast is None
    assert result.hedge_certificate is not None
    assert result.hedge_certificate.hedge_forest == frozenset({"X", "A", "Y"})
    assert result.hedge_certificate.c_component_witness == frozenset({"Y"})
    assert result.hedge_certificate.hedge_root == frozenset({"Y"})
    assert any("validated outer-query hedge" in trace for trace in result.trace)


def test_native_id_fails_closed_for_excluded_outcome_mechanism() -> None:
    base_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[_edge("X", "Y")],
    )
    augmented_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "S_Y"],
        edges=[_edge("X", "Y"), _edge("S_Y", "Y")],
    )

    direct_result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=augmented_graph,
        available_vars=frozenset({"X", "Y"}),
    )
    diagram = SelectionDiagram(
        base_graph=base_graph,
        s_nodes=[
            SNode(
                target_variable="Y",
                context_dimension="outcome_mechanism",
                source_value=0.0,
                target_value=1.0,
                delta=1.0,
                severity="high",
            )
        ],
        source_context=ContextProfile(),
        target_context=ContextProfile(),
    )
    transport_result = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=diagram,
        dataset_ref="source-only",
    )

    for result in (direct_result, transport_result):
        assert result.status is IdentificationStatus.ORACLE_NEEDED
        assert result.estimand_ast is None

    assert any("full observed-node kernel" in trace for trace in direct_result.trace)
    assert any("s_admissibility" in trace for trace in transport_result.trace)

    # Two SCMs agree on the source graph and source observations, yet have
    # different target intervention distributions after the Y mechanism shifts.
    source_observations = {0: 0, 1: 1}
    source_only_estimate = tuple(float(source_observations[x] == 1) for x in (0, 1))
    target_intervention = tuple(float((1 - x) == 1) for x in (0, 1))
    assert source_only_estimate == (0.0, 1.0)
    assert target_intervention == (1.0, 0.0)
    assert source_only_estimate != target_intervention

    # A shift into the intervened treatment mechanism is cut by do(X), so
    # the native kernel may still use the unchanged source outcome mechanism.
    treatment_shift = SelectionDiagram(
        base_graph=base_graph,
        s_nodes=[
            SNode(
                target_variable="X",
                context_dimension="treatment_mechanism",
                source_value=0.0,
                target_value=1.0,
                delta=1.0,
                severity="high",
            )
        ],
        source_context=ContextProfile(),
        target_context=ContextProfile(),
    )
    treatment_shift_result = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=treatment_shift,
        dataset_ref="source-outcome-mechanism",
    )
    assert treatment_shift_result.status is IdentificationStatus.IDENTIFIED
    assert treatment_shift_result.estimand_ast is not None
    assert treatment_shift_result.estimand_ast.root == DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        conditioning=("X",),
        dataset_ref="source-outcome-mechanism",
    )


def test_selected_y0_missing_is_explicit_oracle_needed(monkeypatch) -> None:
    for module_name in ("y0", "y0.algorithm", "y0.algorithm.identify", "y0.dsl"):
        monkeypatch.setitem(sys.modules, module_name, None)
    result = id_with_oracle_fallback(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=_double_frontdoor_graph(),
        oracle="y0",
        dataset_ref="source-y0-unavailable",
    )

    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert result.hedge_certificate is None
    assert result.required_distributions == []
    assert result.algorithm_version == "y0_api_unavailable"
    assert result.metadata["backend_id"] == "y0"
    assert result.metadata["backend_call_attempted"] is False
    assert result.metadata["backend_call_established"] is False
    assert result.metadata["gate_predicates"]["backend_operation_result"] == "not_established"
    assert any("oracle_y0:limited:api_error:ModuleNotFoundError" in trace for trace in result.trace)


def test_tr_algorithm_refuses_selection_node_name_collision() -> None:
    base_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "S_Y"],
        edges=[_edge("X", "Y")],
    )
    diagram = SelectionDiagram(
        base_graph=base_graph,
        s_nodes=[
            SNode(
                target_variable="Y",
                context_dimension="outcome_mechanism",
                source_value=0.0,
                target_value=1.0,
                delta=1.0,
                severity="high",
            )
        ],
        source_context=ContextProfile(),
        target_context=ContextProfile(),
    )

    result = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=diagram,
        dataset_ref="source-colliding-selection-name",
    )

    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert result.hedge_certificate is None
    assert result.required_distributions == []
    assert any("names collide with base graph nodes ['S_Y']" in trace for trace in result.trace)
    assert any(step.rule_name == "ORACLE" for step in result.proof_steps)


def test_native_id_refuses_any_omitted_graph_node_across_bidirected_paths() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["U", "X", "M", "Y"],
        edges=[
            _edge("U", "X"),
            _edge("X", "M"),
            _edge("M", "Y"),
            _edge("X", "Y", bidirected=True),
            _edge("U", "M", bidirected=True),
        ],
    )
    result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        available_vars=frozenset({"X", "M", "Y"}),
    )

    # Independent finite SCM: W,L iid Bernoulli(.5), U=W, X=U xor L,
    # M=X xor W, Y=M xor L. Source observations have Y=0, so the old
    # reduced-frontdoor expression is 0. Under do(X=x), Y=x xor W xor L
    # and P(Y=1)=.5 for both x. The omitted U remains coupled to M.
    worlds = tuple(product((0, 1), repeat=2))
    source_rows = []
    for u, latent_x_y in worlds:
        x = u ^ latent_x_y
        mediator = x ^ u
        y = mediator ^ latent_x_y
        source_rows.append((x, mediator, y))

    actual_do_risks = tuple(
        sum((x ^ u ^ latent_x_y) == 1 for u, latent_x_y in worlds) / len(worlds) for x in (0, 1)
    )
    assert actual_do_risks == (0.5, 0.5)
    assert all(y == 0 for _, _, y in source_rows)

    # This is precisely the false classical frontdoor value seen after U is
    # dropped from the observational kernel.
    false_frontdoor_risk = 0.0
    for mediator in (0, 1):
        for x in (0, 1):
            p_mediator_given_x = sum(
                m == mediator for observed_x, m, _ in source_rows if observed_x == x
            ) / sum(observed_x == x for observed_x, _, _ in source_rows)
            inner = 0.0
            for source_x in (0, 1):
                matching = [
                    y
                    for observed_x, m, y in source_rows
                    if observed_x == source_x and m == mediator
                ]
                p_x = sum(observed_x == source_x for observed_x, _, _ in source_rows) / len(
                    source_rows
                )
                inner += (sum(y == 1 for y in matching) / len(matching)) * p_x
            false_frontdoor_risk += p_mediator_given_x * inner

    assert false_frontdoor_risk == 0.0
    assert false_frontdoor_risk != actual_do_risks[0]
    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert any(
        "complete graph-node profile" in step.applied_to_graph_state for step in result.proof_steps
    )


def test_native_id_refuses_even_an_isolated_omitted_graph_node() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "U"],
        edges=[_edge("X", "Y")],
    )
    result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        available_vars=frozenset({"X", "Y"}),
    )

    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert any("full observed-node kernel" in trace for trace in result.trace)


def test_tr_nonintervened_bidirected_collider_uses_s_admissibility_source_law() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y", "Z"],
        edges=[_edge("X", "Y"), _edge("Z", "Y", bidirected=True)],
    )
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[
            SNode(
                target_variable="Z",
                context_dimension="programmatic",
                source_value=0.0,
                target_value=1.0,
                delta=1.0,
                severity="medium",
            )
        ],
        source_context=ContextProfile(),
        target_context=ContextProfile(),
    )

    result = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=diagram,
        dataset_ref="source-s-admissible",
    )

    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    refs = result.estimand_ast.collect_distribution_refs()
    assert refs
    assert all(ref.domain is DistributionDomain.SOURCE for ref in refs)
    assert all(ref.dataset_ref == "source-s-admissible" for ref in refs)
    assert result.metadata["backend_id"] == (
        "transport_engine.solve_transportability:s_admissibility_source_id_v1"
    )
    assert result.metadata["gate_predicates"] == {
        "s_admissibility": "recomputed",
        "source_effect_identification": "recomputed",
        "source_graph_binding": "recomputed",
        "transport_result_query_identity": "recomputed",
    }
    assert any(step.rule_name == "S_ADMISSIBILITY" for step in result.proof_steps)


def test_tr_nonintervened_directed_selection_path_fails_closed() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y", "Z"],
        edges=[_edge("X", "Y"), _edge("Z", "Y")],
    )
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[
            SNode(
                target_variable="Z",
                context_dimension="programmatic",
                source_value=0.0,
                target_value=1.0,
                delta=1.0,
                severity="medium",
            )
        ],
        source_context=ContextProfile(),
        target_context=ContextProfile(),
    )

    result = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=diagram,
        dataset_ref="source-confounded-selection",
    )

    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert result.metadata["gate_predicates"]["s_admissibility"] == "recomputed_false"
    assert any("s_admissibility" in trace for trace in result.trace)


@pytest.mark.parametrize(
    ("treatment", "outcome"),
    [
        (frozenset({"X", "Z"}), frozenset({"Y"})),
        (frozenset({"X"}), frozenset({"missing"})),
        (frozenset({"X"}), frozenset({"X"})),
        (frozenset({"X"}), frozenset()),
    ],
)
def test_r5_native_query_identity_refusals(treatment, outcome) -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[_edge("X", "Y")],
    )

    result = id_algorithm(
        treatment=treatment,
        outcome=outcome,
        graph=graph,
    )

    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert any("query admission" in trace for trace in result.trace)


def test_r5_empty_treatment_remains_supported_as_marginal_query() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[_edge("X", "Y")],
    )

    result = id_algorithm(
        treatment=frozenset(),
        outcome=frozenset({"Y"}),
        graph=graph,
    )

    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert result.estimand_ast.root == DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        conditioning=(),
        dataset_ref=None,
    )


def test_r5_tr_query_identity_is_checked_before_selection_shortcuts() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[_edge("X", "Y")],
    )
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[],
        source_context=ContextProfile(),
        target_context=ContextProfile(),
    )

    result = tr_algorithm(
        treatment=frozenset({"X", "Z"}),
        outcome=frozenset({"Y"}),
        selection_diagram=diagram,
    )

    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert any("query admission" in trace for trace in result.trace)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("query", "P*(Y|do(Z))"),
        ("source_graph_type", GraphType.DAG),
        ("source_context_id", "stale-source-context"),
        ("target_context_id", "stale-target-context"),
    ],
)
def test_r5_tr_refuses_transport_result_with_mismatched_binding(field, value, monkeypatch) -> None:
    from polisyos.foundry.methods.catalog.causal import transport_engine

    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y", "Z"],
        edges=[_edge("X", "Y"), _edge("Z", "Y", bidirected=True)],
    )
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[
            SNode(
                target_variable="Z",
                context_dimension="programmatic",
                source_value=0.0,
                target_value=1.0,
                delta=1.0,
                severity="medium",
            )
        ],
        source_context=ContextProfile(),
        target_context=ContextProfile(),
    )
    original = transport_engine.solve_transportability

    def mismatched_binding(**kwargs):
        result = original(**kwargs)
        return result.model_copy(update={field: value})

    monkeypatch.setattr(transport_engine, "solve_transportability", mismatched_binding)

    result = tr_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        selection_diagram=diagram,
    )

    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert result.metadata["gate_predicates"]["transport_result_query_identity"] == (
        "recomputed_false"
    )


def test_r5_oracle_fallback_refuses_invalid_query_before_y0(monkeypatch) -> None:
    import polisyos.foundry.methods.catalog.causal.id_engine.core as id_core

    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[_edge("X", "Y")],
    )

    def unexpected_oracle_call(**kwargs):
        raise AssertionError("invalid query reached the Y0 oracle")

    monkeypatch.setattr(id_core, "_oracle_y0", unexpected_oracle_call)
    result = id_with_oracle_fallback(
        treatment=frozenset({"X", "missing"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        oracle="y0",
        force_y0=True,
    )

    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert result.metadata["backend_id"] == "id_with_oracle_fallback"
    assert result.metadata["gate_predicates"]["query_identity"] == ("recomputed_false")


@pytest.mark.parametrize(
    ("treatment", "outcome", "conditions", "gate"),
    [
        (frozenset({"X"}), frozenset(), frozenset({"Y"}), "query_shape"),
        (frozenset({"X"}), frozenset(), frozenset(), "query_shape"),
        (frozenset({"missing"}), frozenset({"Y"}), frozenset(), "query_identity"),
        (frozenset({"X"}), frozenset({"missing"}), frozenset(), "query_identity"),
        (frozenset({"X"}), frozenset({"Y"}), frozenset({"missing"}), "query_identity"),
        (frozenset({"X"}), frozenset({"X"}), frozenset(), "query_shape"),
        (frozenset({"X"}), frozenset({"Y"}), frozenset({"X"}), "query_shape"),
        (frozenset({"X"}), frozenset({"Y"}), frozenset({"Y"}), "query_shape"),
        (frozenset({"X"}), frozenset({"Y"}), {"Y"}, "query_shape"),
        (None, frozenset({"Y"}), frozenset(), "query_shape"),
        (frozenset({"X"}), None, frozenset(), "query_shape"),
        (frozenset({"X"}), frozenset({"Y"}), None, "query_shape"),
    ],
)
def test_r6_idc_admits_all_query_roles_before_reduction(
    treatment, outcome, conditions, gate
) -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[_edge("X", "Y")],
    )

    result = idc_algorithm(
        treatment=treatment,
        outcome=outcome,
        conditions=conditions,
        graph=graph,
        dataset_ref="r6-idc-query-admission",
    )

    assert result.status is IdentificationStatus.ORACLE_NEEDED
    assert result.estimand_ast is None
    assert result.hedge_certificate is None
    assert result.metadata["backend_id"] == "idc_algorithm"
    assert result.metadata["gate_predicates"] == {gate: "recomputed_false"}
    assert any(
        "idc_algorithm: ORACLE_NEEDED: query admission failed:" in trace for trace in result.trace
    )


@pytest.mark.parametrize(
    ("treatment", "outcome", "conditions"),
    [
        (frozenset({"X"}), frozenset({"Y"}), frozenset()),
        (frozenset(), frozenset({"Y"}), frozenset()),
        (frozenset(), frozenset({"Y"}), frozenset({"X"})),
    ],
)
def test_r6_idc_keeps_empty_treatment_and_empty_condition_supported(
    treatment, outcome, conditions
) -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[_edge("X", "Y")],
    )

    result = idc_algorithm(
        treatment=treatment,
        outcome=outcome,
        conditions=conditions,
        graph=graph,
        dataset_ref="r6-idc-valid-query",
    )

    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None


def test_r6_public_id_owner_entrypoints_admit_before_shortcuts(monkeypatch) -> None:
    import polisyos.foundry.methods.catalog.causal.id_engine as public_id_engine
    import polisyos.foundry.methods.catalog.causal.id_engine.api as public_id_api
    import polisyos.foundry.methods.catalog.causal.id_engine.core as id_core

    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[_edge("X", "Y")],
    )
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[],
        source_context=ContextProfile(),
        target_context=ContextProfile(),
    )

    def unexpected_oracle_call(**kwargs):
        raise AssertionError("invalid public query reached the Y0 oracle")

    monkeypatch.setattr(id_core, "_oracle_y0", unexpected_oracle_call)
    facades = (public_id_engine, public_id_api)
    for facade in facades:
        cases = (
            (
                "id_algorithm",
                lambda facade=facade: facade.id_algorithm(
                    treatment=frozenset({"missing"}),
                    outcome=frozenset({"Y"}),
                    graph=graph,
                ),
            ),
            (
                "idc_algorithm",
                lambda facade=facade: facade.idc_algorithm(
                    treatment=frozenset({"X"}),
                    outcome=frozenset(),
                    conditions=frozenset({"Y"}),
                    graph=graph,
                ),
            ),
            (
                "tr_algorithm",
                lambda facade=facade: facade.tr_algorithm(
                    treatment=frozenset({"missing"}),
                    outcome=frozenset({"Y"}),
                    selection_diagram=diagram,
                ),
            ),
            (
                "id_with_oracle_fallback",
                lambda facade=facade: facade.id_with_oracle_fallback(
                    treatment=frozenset({"missing"}),
                    outcome=frozenset({"Y"}),
                    graph=graph,
                    oracle="y0",
                    force_y0=True,
                ),
            ),
        )

        for owner, call in cases:
            result = call()
            assert result.status is IdentificationStatus.ORACLE_NEEDED
            assert result.estimand_ast is None
            assert result.metadata["backend_id"] == owner
            assert any("query admission failed" in trace for trace in result.trace)
