from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.catalog.causal.ctf_calculus import (
    _build_amn_for_ast,
    apply_ctf_rule1,
    apply_ctf_rule2,
    apply_ctf_rule3,
)
from polisyos.foundry.methods.catalog.causal.ctf_transport import (
    build_ctf_selection_diagram,
    ctf_transportability,
)
from polisyos.foundry.methods.catalog.causal.cyclic_id import cyclic_id_algorithm
from polisyos.foundry.methods.catalog.causal.id_engine import (
    CtfQuery,
    IdentificationStatus,
    SourceDomain,
    id_algorithm,
    id_star_algorithm,
    idc_algorithm,
    idc_star_algorithm,
    mz_id_algorithm,
    z_id_algorithm,
)
from polisyos.foundry.methods.catalog.causal.path_specific import _recanting_witness_check
from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
    RecoverabilityStatus,
    full_law_identify,
)
from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
    test_recoverability as recoverability_test,
)
from polisyos.foundry.methods.catalog.causal.sigma_calculus import (
    apply_sigma_rule1,
    apply_sigma_rule2,
    apply_sigma_rule3,
)
from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.estimand import (
    CounterfactualNode,
    CrossWorldNode,
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    NestedCounterfactualNode,
)
from polisyos.ir.analytics.mgraph import MissingnessKind, build_mgraph, extract_mgraph_metadata
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate
from polisyos.ir.analytics.transportability import (
    SNode,
    SNodeOrigin,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
    build_selection_diagram,
)


def _edge(src: str, dst: str, *, bidirected: bool = False) -> CausalEdge:
    if bidirected:
        return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def _dag(edges: list[tuple[str, str]], *, extra_nodes: tuple[str, ...] = ()) -> CausalGraphModel:
    nodes = sorted({node for edge in edges for node in edge} | set(extra_nodes))
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[_edge(src, dst) for src, dst in edges],
    )


def _admg(
    nodes: list[str],
    edges: list[CausalEdge],
    *,
    metadata: dict | None = None,
) -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=nodes,
        edges=edges,
        metadata=metadata or {},
    )


def _canon(text: str | None) -> str | None:
    if text is None:
        return None
    return text.replace(" ", "").replace(".0", "")


def _latex(result: object) -> str | None:
    ast = getattr(result, "estimand_ast", None) or getattr(result, "recovery_estimand", None)
    if ast is None:
        return None
    return ast.to_latex()


def _rule_names(result: object) -> list[str]:
    return [step.rule_name for step in getattr(result, "proof_steps", [])]


def _assert_rule_subsequence(result: object, expected: tuple[str, ...]) -> None:
    actual = _rule_names(result)
    idx = 0
    for rule_name in actual:
        if idx < len(expected) and rule_name == expected[idx]:
            idx += 1
    assert idx == len(expected), f"expected subsequence {expected}, got {actual}"


def _source_context() -> ContextProfile:
    return ContextProfile(
        context_id="DE",
        income_level=IncomeLevel.HIGH,
        institutional_quality=0.85,
    )


def _target_context() -> ContextProfile:
    return ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        institutional_quality=0.35,
    )


def _transport_result(
    diagram,
    *,
    treatment: str,
    outcome: str,
    params: dict | None = None,
) -> TransportabilityResult:
    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": treatment,
            "query_outcome": outcome,
        },
        params or {},
    )
    return TransportabilityResult.model_validate(payload["transport_result"])


ID_CASES = (
    (
        "direct_dag",
        lambda: id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=_dag([("X", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        r"P(Y \mid X)",
        ("G_FORMULA",),
    ),
    (
        "mediated_dag",
        lambda: id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=_dag([("X", "M"), ("M", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        r"\sum_{M} P(M \mid X) \cdot P(Y \mid M)",
        ("G_FORMULA",),
    ),
    (
        "backdoor_dag",
        lambda: id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        r"\sum_{Z} P(Z) \cdot P(Y \mid X, Z)",
        ("G_FORMULA",),
    ),
    (
        "ancestral_collapse",
        lambda: id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=_dag([("X", "Y")], extra_nodes=("W",)),
        ),
        IdentificationStatus.IDENTIFIED,
        r"P(Y \mid X)",
        ("ANCESTRAL_COLLAPSE", "G_FORMULA"),
    ),
    (
        "napkin_observed_confounder",
        lambda: id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=_dag([("U", "X"), ("U", "Y"), ("X", "M"), ("M", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        r"\sum_{M, U} P(U) \cdot P(M \mid X) \cdot P(Y \mid M, U)",
        ("G_FORMULA",),
    ),
    (
        "frontdoor_admg",
        lambda: id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=_admg(
                ["X", "M", "Y"],
                [_edge("X", "M"), _edge("M", "Y"), _edge("X", "Y", bidirected=True)],
            ),
        ),
        IdentificationStatus.IDENTIFIED,
        r"\sum_{M} P(M \mid X) \cdot \sum_{X} P(Y \mid M, X) \cdot P(X)",
        ("FRONTDOOR",),
    ),
    (
        "bow_arc_hedge",
        lambda: id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=_admg(
                ["X", "Y"],
                [_edge("X", "Y"), _edge("X", "Y", bidirected=True)],
            ),
        ),
        IdentificationStatus.HEDGE_FOUND,
        None,
        ("HEDGE",),
    ),
    (
        "confounded_backdoor_hedge",
        lambda: id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=_admg(
                ["X", "Y", "Z"],
                [
                    _edge("Z", "X"),
                    _edge("Z", "Y"),
                    _edge("X", "Y"),
                    _edge("X", "Y", bidirected=True),
                ],
            ),
        ),
        IdentificationStatus.HEDGE_FOUND,
        None,
        ("C_COMPONENT", "HEDGE"),
    ),
)


@pytest.mark.parametrize(
    ("_name", "runner", "expected_status", "expected_formula", "expected_trace"),
    ID_CASES,
    ids=[case[0] for case in ID_CASES],
)
def test_symbolic_gold_id_cases(
    _name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_formula: str | None,
    expected_trace: tuple[str, ...],
) -> None:
    result = runner()

    assert result.status is expected_status
    if expected_formula is not None:
        assert result.estimand_ast is not None
        assert _canon(result.estimand_ast.to_latex()) == _canon(expected_formula)
    else:
        assert result.estimand_ast is None
    _assert_rule_subsequence(result, expected_trace)

    if result.status is IdentificationStatus.HEDGE_FOUND:
        assert result.hedge_certificate is not None
        assert result.hedge_certificate.hedge_root == frozenset({"Y"})
        assert "NOT identifiable" in result.hedge_certificate.description


IDC_CASES = (
    (
        "idc_backdoor",
        lambda: idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset({"Z"}),
            graph=_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")]),
        ),
        r"\frac{P(Z) \cdot P(Y \mid X, Z)}{P(Z)}",
    ),
    (
        "idc_mediated",
        lambda: idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset({"M"}),
            graph=_dag([("X", "M"), ("M", "Y")]),
        ),
        r"\frac{P(M \mid X) \cdot P(Y \mid M)}{P(M \mid X)}",
    ),
    (
        "idc_two_conditions",
        lambda: idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset({"W", "Z"}),
            graph=_dag([("Z", "X"), ("W", "Y"), ("Z", "Y"), ("X", "Y")]),
        ),
        r"\frac{P(W) \cdot P(Z) \cdot P(Y \mid W, X, Z)}{P(W, Z)}",
    ),
)


@pytest.mark.parametrize(
    ("_name", "runner", "expected_formula"),
    IDC_CASES,
    ids=[case[0] for case in IDC_CASES],
)
def test_symbolic_gold_idc_cases(_name: str, runner, expected_formula: str) -> None:
    result = runner()
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert _canon(result.estimand_ast.to_latex()) == _canon(expected_formula)
    _assert_rule_subsequence(result, ("IDC_DECOMPOSE", "IDC_POSITIVITY"))


ID_STAR_CASES = (
    (
        "single_world_backdoor",
        lambda: id_star_algorithm(
            CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                conditioning=("Z",),
                kind="single_world",
            ),
            _admg(
                ["X", "Y", "Z"],
                [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")],
            ),
        ),
        IdentificationStatus.IDENTIFIED,
        "P(Y_{X=1} | Z)",
        CounterfactualNode,
    ),
    (
        "ett",
        lambda: id_star_algorithm(
            CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                evidence=(("X", 1.0),),
                kind="ett",
            ),
            _admg(
                ["X", "Y", "Z"],
                [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")],
            ),
        ),
        IdentificationStatus.IDENTIFIED,
        "P(Y_{X=1} | X=1)",
        CounterfactualNode,
    ),
    (
        "pn",
        lambda: id_star_algorithm(
            CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                evidence=(("Y", 1.0),),
                kind="pn",
            ),
            _admg(["X", "Y"], [_edge("X", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        "P(Y_{X=0} | X=1, Y=1)",
        CounterfactualNode,
    ),
    (
        "pns",
        lambda: id_star_algorithm(
            CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                reference_intervention=(("X", 0.0),),
                kind="pns",
            ),
            _admg(["X", "Y"], [_edge("X", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        "P(Y_{X=1}, Y_{X=0})",
        CrossWorldNode,
    ),
    (
        "nested",
        lambda: id_star_algorithm(
            CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                kind="nested",
            ),
            _admg(["X", "Y"], [_edge("X", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        "P(Y_{X=1})",
        NestedCounterfactualNode,
    ),
)


@pytest.mark.parametrize(
    ("_name", "runner", "expected_status", "expected_query", "expected_root"),
    ID_STAR_CASES,
    ids=[case[0] for case in ID_STAR_CASES],
)
def test_symbolic_gold_id_star_cases(
    _name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_query: str,
    expected_root,
) -> None:
    result = runner()
    assert result.status is expected_status
    assert _canon(result.query_str) == _canon(expected_query)
    assert result.estimand_ast is not None
    assert isinstance(result.estimand_ast.root, expected_root)
    _assert_rule_subsequence(
        result, ("ID_STAR_STEP1", "ID_STAR_STEP2", "ID_STAR_STEP3", "ID_STAR_STEP5")
    )


@pytest.mark.parametrize(
    ("_name", "query"),
    (
        (
            "bow_arc_single_world",
            CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world"),
        ),
        (
            "bow_arc_ett",
            CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                evidence=(("X", 1.0),),
                kind="ett",
            ),
        ),
    ),
    ids=["bow_arc_single_world", "bow_arc_ett"],
)
def test_symbolic_gold_id_star_negative_cases(_name: str, query: CtfQuery) -> None:
    result = id_star_algorithm(
        query,
        _admg(["X", "Y"], [_edge("X", "Y"), _edge("X", "Y", bidirected=True)]),
    )
    assert result.status is IdentificationStatus.HEDGE_FOUND
    assert result.hedge_certificate is not None
    assert result.hedge_certificate.hedge_root == frozenset({"Y"})


IDC_STAR_CASES = (
    (
        "idc_star_ett_with_z",
        lambda: idc_star_algorithm(
            CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                conditioning=("Z",),
                evidence=(("X", 1.0),),
                kind="ett",
            ),
            _admg(
                ["X", "Y", "Z"],
                [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")],
            ),
        ),
        IdentificationStatus.IDENTIFIED,
        "P(Y_{X=1} | X=1, Z)",
    ),
    (
        "idc_star_pn_with_x",
        lambda: idc_star_algorithm(
            CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                evidence=(("Y", 1.0),),
                conditioning=("X",),
                kind="pn",
            ),
            _admg(["X", "Y"], [_edge("X", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        "P(Y_{X=0} | Y=1, X)",
    ),
    (
        "idc_star_bow_arc_negative",
        lambda: idc_star_algorithm(
            CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                evidence=(("X", 1.0),),
                conditioning=("X",),
                kind="ett",
            ),
            _admg(["X", "Y"], [_edge("X", "Y"), _edge("X", "Y", bidirected=True)]),
        ),
        IdentificationStatus.HEDGE_FOUND,
        "P(Y_{X=1} | X=1, X)",
    ),
)


@pytest.mark.parametrize(
    ("_name", "runner", "expected_status", "expected_query"),
    IDC_STAR_CASES,
    ids=[case[0] for case in IDC_STAR_CASES],
)
def test_symbolic_gold_idc_star_cases(
    _name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_query: str,
) -> None:
    result = runner()
    assert result.status is expected_status
    assert _canon(result.query_str) == _canon(expected_query)
    if expected_status is IdentificationStatus.IDENTIFIED:
        assert result.estimand_ast is not None
        _assert_rule_subsequence(result, ("IDC_STAR_RATIO",))
    else:
        assert result.hedge_certificate is not None


Z_ID_CASES = (
    (
        "direct_z_transport",
        lambda: z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset({"Z"}),
            graph=_dag([("X", "Z"), ("Z", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        r"\sum_{Z} P(Y \mid do(X), X, Z) \cdot P^*(Z)",
        ("Z_TRANSPORT",),
    ),
    (
        "z_equals_treatment",
        lambda: z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset({"X"}),
            graph=_dag([("X", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        r"\sum_{X} P(Y \mid do(X), X, X) \cdot P^*(X)",
        ("Z_TRANSPORT",),
    ),
    (
        "no_z_falls_back_to_dag_id",
        lambda: z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset(),
            graph=_dag([("X", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        r"P(Y \mid X)",
        ("G_FORMULA",),
    ),
    (
        "bow_arc_with_irrelevant_z_is_not_false_positive",
        lambda: z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset({"Z"}),
            graph=_admg(
                ["X", "Y", "Z"],
                [_edge("X", "Y"), _edge("X", "Y", bidirected=True)],
            ),
        ),
        IdentificationStatus.ORACLE_NEEDED,
        None,
        (),
    ),
)


@pytest.mark.parametrize(
    ("_name", "runner", "expected_status", "expected_formula", "expected_trace"),
    Z_ID_CASES,
    ids=[case[0] for case in Z_ID_CASES],
)
def test_symbolic_gold_z_id_cases(
    _name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_formula: str | None,
    expected_trace: tuple[str, ...],
) -> None:
    result = runner()
    assert result.status is expected_status
    if expected_formula is not None:
        assert result.estimand_ast is not None
        assert _canon(result.estimand_ast.to_latex()) == _canon(expected_formula)
    if expected_trace:
        _assert_rule_subsequence(result, expected_trace)


MZ_ID_CASES = (
    (
        "single_z_domain",
        lambda: mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[SourceDomain(domain_id="d1", z_interventions=frozenset({"X"}))],
            graph=_dag([("X", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        r"\sum_{X} P(Y \mid do(X), X, X) \cdot P^*(X)",
        ("Z_TRANSPORT",),
    ),
    (
        "single_selection_domain",
        lambda: mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[SourceDomain(domain_id="d1", s_nodes=frozenset({"X"}))],
            graph=_dag([("X", "Y")]),
        ),
        IdentificationStatus.IDENTIFIED,
        r"P(Y \mid X)",
        ("S_AUGMENT", "G_FORMULA"),
    ),
    (
        "bow_arc_no_domains_falls_back_to_hedge",
        lambda: mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[],
            graph=_admg(["X", "Y"], [_edge("X", "Y"), _edge("X", "Y", bidirected=True)]),
        ),
        IdentificationStatus.HEDGE_FOUND,
        None,
        ("HEDGE",),
    ),
)


@pytest.mark.parametrize(
    ("_name", "runner", "expected_status", "expected_formula", "expected_trace"),
    MZ_ID_CASES,
    ids=[case[0] for case in MZ_ID_CASES],
)
def test_symbolic_gold_mz_id_cases(
    _name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_formula: str | None,
    expected_trace: tuple[str, ...],
) -> None:
    result = runner()
    assert result.status is expected_status
    if expected_formula is not None:
        assert result.estimand_ast is not None
        assert _canon(result.estimand_ast.to_latex()) == _canon(expected_formula)
    if expected_trace:
        _assert_rule_subsequence(result, expected_trace)


TRANSPORT_CASES = (
    (
        "transport_direct",
        lambda: _transport_result(
            build_selection_diagram(
                _source_context().model_copy(update={"context_id": "A"}),
                _source_context().model_copy(update={"context_id": "A"}),
                CausalGraphModel(
                    graph_type=GraphType.DAG,
                    nodes=["tax_rate", "gdp_growth"],
                    edges=[CausalEdge(src="tax_rate", dst="gdp_growth")],
                ),
            ),
            treatment="tax_rate",
            outcome="gdp_growth",
        ),
        TransportabilityStatus.IDENTIFIED,
        TransportMode.DIRECT,
        None,
    ),
    (
        "transport_frontdoor_like",
        lambda: _transport_result(
            build_selection_diagram(
                _source_context(),
                _target_context(),
                CausalGraphModel(
                    graph_type=GraphType.DAG,
                    nodes=["tax_rate", "tax_compliance", "gdp_growth"],
                    edges=[
                        CausalEdge(src="tax_rate", dst="tax_compliance"),
                        CausalEdge(src="tax_compliance", dst="gdp_growth"),
                    ],
                ),
            ),
            treatment="tax_rate",
            outcome="gdp_growth",
        ),
        TransportabilityStatus.IDENTIFIED,
        TransportMode.TRANSPORT_FORMULA,
        "P*(gdp_growth|do(tax_rate))",
    ),
    (
        "transport_unresolved_cpdag",
        lambda: _transport_result(
            build_selection_diagram(
                _source_context(),
                _target_context(),
                CausalGraphModel(
                    graph_type=GraphType.CPDAG,
                    nodes=["tax_rate", "tax_compliance", "gdp_growth"],
                    edges=[
                        CausalEdge(src="tax_compliance", dst="tax_rate"),
                        CausalEdge(src="tax_rate", dst="tax_compliance"),
                        CausalEdge(src="tax_compliance", dst="gdp_growth"),
                    ],
                ),
            ),
            treatment="tax_rate",
            outcome="gdp_growth",
        ),
        TransportabilityStatus.UNSUPPORTED,
        TransportMode.NONE,
        None,
    ),
    (
        "transport_pag_probabilistic",
        lambda: _transport_result(
            build_selection_diagram(
                _source_context(),
                _target_context(),
                CausalGraphModel(
                    graph_type=GraphType.PAG,
                    nodes=["X", "Y", "Z"],
                    edges=[
                        CausalEdge(
                            src="Z",
                            dst="Y",
                            mark_src=EdgeMark.CIRCLE,
                            mark_dst=EdgeMark.CIRCLE,
                        ),
                        CausalEdge(src="Y", dst="X"),
                    ],
                ),
            ).model_copy(
                update={
                    "s_nodes": [
                        SNode(
                            target_variable="Z",
                            context_dimension="institutional_quality",
                            source_value=0.9,
                            target_value=0.2,
                            delta=0.7,
                            severity="high",
                            origin=SNodeOrigin.CONTEXT_DELTA,
                        )
                    ],
                    "context_distance": 0.4,
                }
            ),
            treatment="X",
            outcome="Y",
            params={
                "pag_identification_policy": "probabilistic",
                "pag_max_dag_samples": 20,
                "pag_threshold": 0.5,
                "pag_seed": 17,
            },
        ),
        TransportabilityStatus.IDENTIFIED,
        TransportMode.TRANSPORT_FORMULA,
        None,
    ),
)


@pytest.mark.parametrize(
    ("_name", "runner", "expected_status", "expected_mode", "expected_formula_fragment"),
    TRANSPORT_CASES,
    ids=[case[0] for case in TRANSPORT_CASES],
)
def test_symbolic_gold_transport_cases(
    _name: str,
    runner,
    expected_status: TransportabilityStatus,
    expected_mode: TransportMode,
    expected_formula_fragment: str | None,
) -> None:
    result = runner()
    assert result.status is expected_status
    assert result.transport_mode is expected_mode
    if expected_formula_fragment is not None:
        assert result.transport_formula is not None
        assert expected_formula_fragment in result.transport_formula.formula_str
    if _name == "transport_unresolved_cpdag":
        assert result.unsupported_reason == "simplified_unresolved_s_nodes"
    if _name == "transport_pag_probabilistic":
        assert result.id_confidence_under_pag is not None
        assert 0.0 <= result.id_confidence_under_pag <= 1.0


CTF_TRANSPORT_CASES = (
    (
        "ctf_transport_pn",
        lambda: ctf_transportability(
            CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                evidence=(("Y", 1.0),),
                kind="pn",
            ),
            build_ctf_selection_diagram(
                graph=_dag([("X", "Y")]),
                s_nodes=[
                    SNode(
                        target_variable="Y",
                        context_dimension="mechanism_shift",
                        source_value=0.0,
                        target_value=1.0,
                        delta=1.0,
                        severity="medium",
                    )
                ],
            ),
        ),
        "identified",
        "P(Y_{X=0} | Y=1)",
        ("CTF_TRANSPORT_START",),
    ),
    (
        "ctf_transport_exact_reduction",
        lambda: ctf_transportability(
            CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world"),
            build_ctf_selection_diagram(
                graph=_dag([], extra_nodes=("X", "Y")),
                s_nodes=[
                    SNode(
                        target_variable="Y",
                        context_dimension="mechanism_shift",
                        source_value=0.0,
                        target_value=1.0,
                        delta=1.0,
                        severity="medium",
                    )
                ],
            ),
        ),
        "identified",
        "P(Y_{X=1})",
        ("CTF_TRANSPORT_START", "CTF_TRANSPORT_AUGMENT", "CTF_R3", "CTF_TRANSPORT_EXACT"),
    ),
    (
        "ctf_transport_bow_arc_negative",
        lambda: ctf_transportability(
            CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world"),
            build_ctf_selection_diagram(
                graph=_admg(
                    ["X", "Y"],
                    [_edge("X", "Y"), _edge("X", "Y", bidirected=True)],
                ),
                s_nodes=[
                    SNode(
                        target_variable="Y",
                        context_dimension="mechanism_shift",
                        source_value=0.0,
                        target_value=1.0,
                        delta=1.0,
                        severity="medium",
                    )
                ],
            ),
        ),
        "negative",
        None,
        (),
    ),
)


@pytest.mark.parametrize(
    ("_name", "runner", "kind", "expected_query", "expected_trace"),
    CTF_TRANSPORT_CASES,
    ids=[case[0] for case in CTF_TRANSPORT_CASES],
)
def test_symbolic_gold_ctf_transport_cases(
    _name: str,
    runner,
    kind: str,
    expected_query: str | None,
    expected_trace: tuple[str, ...],
) -> None:
    result = runner()
    if kind == "negative":
        assert isinstance(result, NegativeCertificate)
        assert result.blocking_type is BlockingType.S_NODE_UNRESOLVED
        assert result.partial_bounds is not None
        return

    assert result.status is IdentificationStatus.IDENTIFIED
    assert _canon(result.query_str) == _canon(expected_query)
    _assert_rule_subsequence(result, expected_trace)


CYCLIC_CASES = (
    (
        "cyclic_well_posed",
        lambda: cyclic_id_algorithm(
            frozenset({"A"}),
            frozenset({"B"}),
            _admg(
                ["A", "B"],
                [_edge("A", "B"), _edge("B", "A")],
                metadata={
                    "well_posedness_spec": {
                        "linear_system_matrix": np.array([[0.1, 0.1], [0.1, 0.1]])
                    }
                },
            ),
        ),
        IdentificationStatus.ORACLE_NEEDED,
        None,
        (
            "CYCLIC_START",
            "CYCLIC_SCC",
            "CYCLIC_WELL_POSED",
            "CYCLIC_SIGMA_WARN",
            "CYCLIC_FRONTIER_BOUNDARY",
        ),
    ),
    (
        "cyclic_non_well_posed",
        lambda: cyclic_id_algorithm(
            frozenset({"A"}),
            frozenset({"B"}),
            _admg(
                ["A", "B"],
                [_edge("A", "B"), _edge("B", "A")],
                metadata={
                    "well_posedness_spec": {
                        "update_fn": lambda x: float(
                            np.tanh(2.0 * float(np.asarray(x).reshape(-1)[0]))
                        )
                    }
                },
            ),
        ),
        IdentificationStatus.HEDGE_FOUND,
        None,
        (
            "CYCLIC_START",
            "CYCLIC_SCC",
            "CYCLIC_WELL_POSED",
            "CYCLIC_SIGMA_WARN",
            "CYCLIC_NON_WELL_POSED",
        ),
    ),
)


@pytest.mark.parametrize(
    ("_name", "runner", "expected_status", "expected_formula", "expected_trace"),
    CYCLIC_CASES,
    ids=[case[0] for case in CYCLIC_CASES],
)
def test_symbolic_gold_cyclic_cases(
    _name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_formula: str | None,
    expected_trace: tuple[str, ...],
) -> None:
    result = runner()
    assert result.status is expected_status
    if expected_formula is not None:
        assert result.estimand_ast is not None
        assert _canon(result.estimand_ast.to_latex()) == _canon(expected_formula)
    elif expected_status is IdentificationStatus.HEDGE_FOUND:
        assert result.hedge_certificate is not None
    else:
        assert result.estimand_ast is None
        assert result.hedge_certificate is None
    _assert_rule_subsequence(result, expected_trace)


def test_symbolic_gold_sigma_rule1() -> None:
    graph = _dag([("X", "Y"), ("Z", "X")])
    ref = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        intervention_set=("X",),
        conditioning=("Z",),
    )
    rewritten, step = apply_sigma_rule1(ref, graph, frozenset({"Z"}), frozenset({"Z"})) or (
        None,
        None,
    )

    assert rewritten is not None
    assert rewritten.conditioning == ()
    assert step is not None
    assert step.rule_name == "SIGMA_R1"


def test_symbolic_gold_sigma_rule2() -> None:
    graph = _dag([("Z", "X"), ("X", "Y")])
    ref = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        intervention_set=("X", "Z"),
        conditioning=(),
    )
    rewritten, step = apply_sigma_rule2(ref, graph, frozenset({"Z"}), frozenset({"Z"})) or (
        None,
        None,
    )

    assert rewritten is not None
    assert rewritten.intervention_set == ("X",)
    assert rewritten.conditioning == ("Z",)
    assert step is not None
    assert step.rule_name == "SIGMA_R2"


def test_symbolic_gold_sigma_rule3() -> None:
    graph = _dag([("X", "Y"), ("Z", "X")])
    ref = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=("Y",),
        intervention_set=("X", "Z"),
        conditioning=(),
    )
    rewritten, step = apply_sigma_rule3(ref, graph, frozenset({"Z"}), frozenset({"Z"})) or (
        None,
        None,
    )

    assert rewritten is not None
    assert rewritten.intervention_set == ("X",)
    assert step is not None
    assert step.rule_name == "SIGMA_R3"


def test_symbolic_gold_ctf_rule1() -> None:
    node = CounterfactualNode(
        variable="Y",
        intervention={"X": 1.0},
        conditioning=("Z",),
        world_index=0,
    )
    ast = EstimandAST(
        query_str="P(Y_{X=1}|Z)",
        root=node,
        treatment="X",
        outcome="Y",
        all_variables=("X", "Y", "Z"),
        identification_method="ctf",
    )
    amn, _ = _build_amn_for_ast(ast, _dag([("X", "Y"), ("Z", "X")]))
    rewritten, step = apply_ctf_rule1(node, amn, frozenset({"Z"})) or (None, None)

    assert rewritten is not None
    assert rewritten.conditioning == ()
    assert step is not None
    assert step.rule_name == "CTF_R1"


def test_symbolic_gold_ctf_rule2() -> None:
    node = CounterfactualNode(
        variable="Y",
        intervention={"X": 1.0, "Z": 1.0},
        conditioning=(),
        world_index=0,
    )
    ast = EstimandAST(
        query_str="P(Y_{X=1,Z=1})",
        root=node,
        treatment="X",
        outcome="Y",
        all_variables=("X", "Y", "Z"),
        identification_method="ctf",
    )
    amn, _ = _build_amn_for_ast(ast, _dag([("Z", "X"), ("X", "Y")]))
    rewritten, step = apply_ctf_rule2(node, amn, frozenset({"Z"})) or (None, None)

    assert rewritten is not None
    assert rewritten.intervention == {"X": 1.0}
    assert rewritten.conditioning == ("Z",)
    assert step is not None
    assert step.rule_name == "CTF_R2"


def test_symbolic_gold_ctf_rule3() -> None:
    node = CounterfactualNode(
        variable="Y",
        intervention={"X": 1.0, "Z": 1.0},
        conditioning=(),
        world_index=0,
    )
    ast = EstimandAST(
        query_str="P(Y_{X=1,Z=1})",
        root=node,
        treatment="X",
        outcome="Y",
        all_variables=("X", "Y", "Z"),
        identification_method="ctf",
    )
    amn, _ = _build_amn_for_ast(ast, _dag([("X", "Y"), ("Z", "X")]))
    rewritten, step = apply_ctf_rule3(node, amn, frozenset({"Z"})) or (None, None)

    assert rewritten is not None
    assert rewritten.intervention == {"X": 1.0}
    assert step is not None
    assert step.rule_name == "CTF_R3"


MGRAPH_CASES = (
    (
        "mcar",
        lambda: recoverability_test(
            query_vars=frozenset({"X", "Y"}),
            graph=build_mgraph(
                substantive_vars=["X", "Y"],
                directed_edges=[("X", "Y")],
                missingness_map={"X": MissingnessKind.MCAR},
            ),
            mgraph_meta=extract_mgraph_metadata(
                build_mgraph(
                    substantive_vars=["X", "Y"],
                    directed_edges=[("X", "Y")],
                    missingness_map={"X": MissingnessKind.MCAR},
                )
            ),
        ),
        RecoverabilityStatus.RECOVERABLE,
        r"P(X^{\text{obs}} \mid R_X=1) \cdot P(Y^{\text{obs}} \mid X)",
    ),
    (
        "mar",
        lambda: recoverability_test(
            query_vars=frozenset({"X", "Y"}),
            graph=build_mgraph(
                substantive_vars=["X", "Y"],
                directed_edges=[("Y", "R_X")],
                missingness_map={"X": MissingnessKind.MAR},
            ),
            mgraph_meta=extract_mgraph_metadata(
                build_mgraph(
                    substantive_vars=["X", "Y"],
                    directed_edges=[("Y", "R_X")],
                    missingness_map={"X": MissingnessKind.MAR},
                )
            ),
        ),
        RecoverabilityStatus.RECOVERABLE,
        r"P(X^{\text{obs}} \mid R_X=1) \cdot P(Y^{\text{obs}} \mid X)",
    ),
    (
        "mnar",
        lambda: recoverability_test(
            query_vars=frozenset({"X", "Y"}),
            graph=build_mgraph(
                substantive_vars=["X", "Y"],
                directed_edges=[("X", "Y")],
                missingness_map={"X": MissingnessKind.MNAR},
            ),
            mgraph_meta=extract_mgraph_metadata(
                build_mgraph(
                    substantive_vars=["X", "Y"],
                    directed_edges=[("X", "Y")],
                    missingness_map={"X": MissingnessKind.MNAR},
                )
            ),
        ),
        RecoverabilityStatus.NOT_RECOVERABLE,
        None,
    ),
    (
        "full_law_stage2_hedge",
        lambda: full_law_identify(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=build_mgraph(
                substantive_vars=["X", "Y"],
                directed_edges=[("X", "Y")],
                bidirected_edges=[("X", "Y")],
                missingness_map={"X": MissingnessKind.MCAR},
            ),
            mgraph_meta=extract_mgraph_metadata(
                build_mgraph(
                    substantive_vars=["X", "Y"],
                    directed_edges=[("X", "Y")],
                    bidirected_edges=[("X", "Y")],
                    missingness_map={"X": MissingnessKind.MCAR},
                )
            ),
        ),
        IdentificationStatus.HEDGE_FOUND,
        None,
    ),
)


@pytest.mark.parametrize(
    ("_name", "runner", "expected_status", "expected_formula"),
    MGRAPH_CASES,
    ids=[case[0] for case in MGRAPH_CASES],
)
def test_symbolic_gold_mgraph_cases(
    _name: str,
    runner,
    expected_status,
    expected_formula: str | None,
) -> None:
    result = runner()
    assert result.status == expected_status
    if expected_formula is not None:
        assert _canon(_latex(result)) == _canon(expected_formula)
    if _name == "mnar":
        assert result.blocking_r_nodes == frozenset({"R_X"})
        assert "MGRAPH_NOT_RECOVERABLE" in _rule_names(result)
    if _name == "full_law_stage2_hedge":
        assert result.hedge_certificate is not None
        _assert_rule_subsequence(result, ("FULL_LAW_STAGE1_PASS", "HEDGE", "FULL_LAW_STAGE2"))


PROOF_TRACE_CASES = (
    (
        "id_direct_trace",
        lambda: id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=_dag([("X", "Y")]),
        ),
        ("G_FORMULA",),
    ),
    (
        "id_frontdoor_trace",
        lambda: id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=_admg(
                ["X", "M", "Y"],
                [_edge("X", "M"), _edge("M", "Y"), _edge("X", "Y", bidirected=True)],
            ),
        ),
        ("FRONTDOOR",),
    ),
    (
        "idc_trace",
        lambda: idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset({"Z"}),
            graph=_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")]),
        ),
        ("IDC_DECOMPOSE", "IDC_POSITIVITY"),
    ),
    (
        "id_star_trace",
        lambda: id_star_algorithm(
            CtfQuery(
                outcome="Y",
                intervention=(("X", 1.0),),
                reference_intervention=(("X", 0.0),),
                kind="pns",
            ),
            _admg(["X", "Y"], [_edge("X", "Y")]),
        ),
        ("ID_STAR_STEP1", "ID_STAR_STEP2", "ID_STAR_STEP3", "ID_STAR_STEP5"),
    ),
    (
        "ctf_transport_trace",
        lambda: ctf_transportability(
            CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world"),
            build_ctf_selection_diagram(
                graph=_dag([], extra_nodes=("X", "Y")),
                s_nodes=[
                    SNode(
                        target_variable="Y",
                        context_dimension="mechanism_shift",
                        source_value=0.0,
                        target_value=1.0,
                        delta=1.0,
                        severity="medium",
                    )
                ],
            ),
        ),
        ("CTF_TRANSPORT_START", "CTF_TRANSPORT_AUGMENT", "CTF_R3", "CTF_TRANSPORT_EXACT"),
    ),
    (
        "cyclic_trace",
        lambda: cyclic_id_algorithm(
            frozenset({"A"}),
            frozenset({"B"}),
            _admg(
                ["A", "B"],
                [_edge("A", "B"), _edge("B", "A")],
                metadata={
                    "well_posedness_spec": {
                        "linear_system_matrix": np.array([[0.1, 0.1], [0.1, 0.1]])
                    }
                },
            ),
        ),
        (
            "CYCLIC_START",
            "CYCLIC_SCC",
            "CYCLIC_WELL_POSED",
            "CYCLIC_SIGMA_WARN",
            "CYCLIC_FRONTIER_BOUNDARY",
        ),
    ),
)


@pytest.mark.parametrize(
    ("_name", "runner", "expected_trace"),
    PROOF_TRACE_CASES,
    ids=[case[0] for case in PROOF_TRACE_CASES],
)
def test_symbolic_gold_proof_traces(_name: str, runner, expected_trace: tuple[str, ...]) -> None:
    _assert_rule_subsequence(runner(), expected_trace)


def test_symbolic_gold_rejects_recanting_witness_false_positive_on_clean_dag() -> None:
    has_witness, witnesses = _recanting_witness_check(
        "T",
        "Y",
        ("M",),
        {"T": ["M"], "M": ["Y"], "Y": []},
    )
    assert has_witness is False
    assert witnesses == []
