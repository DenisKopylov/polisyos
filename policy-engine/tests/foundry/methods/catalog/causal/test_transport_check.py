from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    SNode,
    SNodeOrigin,
    TransportMode,
    TransportabilityResult,
    TransportabilityStatus,
    build_selection_diagram,
)


def test_transport_check_direct_when_no_s_nodes() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tax_rate", "gdp_growth"],
        edges=[CausalEdge(src="tax_rate", dst="gdp_growth")],
    )
    source = ContextProfile(
        context_id="DE",
        income_level=IncomeLevel.HIGH,
        institutional_quality=0.8,
    )
    target = source.model_copy(deep=True)
    diagram = build_selection_diagram(source, target, graph)

    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "tax_rate",
            "query_outcome": "gdp_growth",
        },
        {},
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])

    assert result.status is TransportabilityStatus.IDENTIFIED
    assert result.transport_mode is TransportMode.DIRECT
    assert result.final_confidence == 1.0
    assert result.identification_engine == "simplified_legacy"


def test_transport_check_transportable_uses_conditional_target_quantity_for_mediator() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tax_rate", "tax_compliance", "gdp_growth"],
        edges=[
            CausalEdge(src="tax_rate", dst="tax_compliance"),
            CausalEdge(src="tax_compliance", dst="gdp_growth"),
        ],
    )
    source = ContextProfile(
        context_id="DE",
        income_level=IncomeLevel.HIGH,
        institutional_quality=0.85,
    )
    target = ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        institutional_quality=0.35,
    )
    diagram = build_selection_diagram(source, target, graph)

    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "tax_rate",
            "query_outcome": "gdp_growth",
        },
        {},
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])

    assert result.status is TransportabilityStatus.IDENTIFIED
    assert result.transport_mode is TransportMode.TRANSPORT_FORMULA
    assert result.transport_formula is not None
    assert "P*(tax_compliance|tax_rate)" in result.transport_formula.target_quantities
    assert result.transport_formula.stratification_details
    assert result.transport_formula.stratification_details[0].requires_conditional is True


def test_transport_check_non_transportable_tracks_unsupported_cases() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["tax_rate", "tax_compliance", "gdp_growth"],
        edges=[
            CausalEdge(src="tax_compliance", dst="tax_rate"),
            CausalEdge(src="tax_rate", dst="tax_compliance"),
            CausalEdge(src="tax_compliance", dst="gdp_growth"),
        ],
    )
    source = ContextProfile(
        context_id="DE",
        income_level=IncomeLevel.HIGH,
        institutional_quality=0.8,
    )
    target = ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        institutional_quality=0.3,
    )
    diagram = build_selection_diagram(source, target, graph)

    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "tax_rate",
            "query_outcome": "gdp_growth",
        },
        {},
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_cases
    assert result.algorithm_version == "trso_v2"
    assert result.unsupported_reason == "simplified_unresolved_s_nodes"


def _pag_diagram_for_probabilistic_test() -> SelectionDiagram:
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y", "Z"],
        edges=[
            CausalEdge(src="Z", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="Y", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
    )
    source = ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH)
    target = ContextProfile(context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE)
    return SelectionDiagram(
        base_graph=graph,
        s_nodes=[
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
        source_context=source,
        target_context=target,
        context_distance=0.4,
    )


def test_transport_check_pag_probabilistic_computes_id_confidence() -> None:
    diagram = _pag_diagram_for_probabilistic_test()
    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {
            "pag_identification_policy": "probabilistic",
            "pag_max_dag_samples": 20,
            "pag_threshold": 0.5,
            "pag_seed": 17,
        },
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])

    assert result.pag_identification_policy is not None
    assert result.id_confidence_under_pag is not None
    assert result.pag_dag_sample_size is not None
    assert result.pag_transportable_count is not None
    assert result.pag_dag_sample_size > 0
    assert 0.0 <= result.id_confidence_under_pag <= 1.0
    assert result.status is TransportabilityStatus.IDENTIFIED


def test_transport_check_pag_probabilistic_threshold_blocks() -> None:
    diagram = _pag_diagram_for_probabilistic_test()
    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {
            "pag_identification_policy": "probabilistic",
            "pag_max_dag_samples": 20,
            "pag_threshold": 0.75,
            "pag_seed": 17,
        },
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])

    assert result.id_confidence_under_pag is not None
    assert result.id_confidence_under_pag < 0.75
    assert result.status is TransportabilityStatus.UNSUPPORTED
