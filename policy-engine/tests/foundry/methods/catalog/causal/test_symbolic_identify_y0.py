from __future__ import annotations

from polisyos.foundry.methods.catalog.causal import symbolic_identify as symbolic_module
from polisyos.foundry.methods.catalog.causal.symbolic_identify import (
    SymbolicIdentify,
    convert_graph_to_symbolic_repr,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    SNode,
    SNodeOrigin,
    TransportabilityResult,
    TransportabilityStatus,
)


def _diagram_frontdoor_like() -> SelectionDiagram:
    graph = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["X", "M", "Y"],
        edges=[
            CausalEdge(src="X", dst="M"),
            CausalEdge(src="M", dst="Y"),
            CausalEdge(src="M", dst="X"),
        ],
    )
    source = ContextProfile(
        context_id="DE",
        income_level=IncomeLevel.HIGH,
        institutional_quality=0.9,
    )
    target = ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        institutional_quality=0.2,
    )
    return SelectionDiagram(
        base_graph=graph,
        s_nodes=[
            SNode(
                target_variable="M",
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
        context_distance=0.5,
    )


def test_symbolic_graph_conversion_roundtrip_shape() -> None:
    diagram = _diagram_frontdoor_like()
    payload = convert_graph_to_symbolic_repr(diagram.base_graph)

    assert payload["nodes"] == ["X", "M", "Y"]
    assert ("X", "M") in payload["directed_edges"]
    assert ("M", "Y") in payload["directed_edges"]


def test_symbolic_identify_handles_frontdoor_like_case(monkeypatch) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))

    diagram = _diagram_frontdoor_like()
    raw = SymbolicIdentify.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={},
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])

    assert result.status is TransportabilityStatus.TRANSPORTABLE
    assert result.identification_engine == "symbolic"
    assert result.transport_formula is not None
    assert result.transport_formula.adjustment_type == "frontdoor_symbolic"
    assert "P*(M|X)" in result.transport_formula.target_quantities


def test_symbolic_identify_reports_unavailable_backend(monkeypatch) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (False, "y0_unavailable"))
    monkeypatch.setattr(
        symbolic_module,
        "_r_backend_available",
        lambda: (False, "rpy2_unavailable"),
    )

    diagram = _diagram_frontdoor_like()
    raw = SymbolicIdentify.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={"require_symbolic_backend": True},
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])

    assert result.status is TransportabilityStatus.NON_TRANSPORTABLE
    assert result.identification_engine == "symbolic"
    assert result.unsupported_reason == "y0_unavailable;rpy2_unavailable"
    assert any("symbolic_backend_unavailable" in step for step in result.identification_trace)


def test_symbolic_identify_supports_r_backend_mode(monkeypatch) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (False, "y0_unavailable"))
    monkeypatch.setattr(symbolic_module, "_r_backend_available", lambda: (True, None))

    diagram = _diagram_frontdoor_like()
    raw = SymbolicIdentify.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={"symbolic_backend": "r", "require_symbolic_backend": True},
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])

    assert result.status is TransportabilityStatus.TRANSPORTABLE
    assert result.identification_engine == "symbolic"
    assert any("symbolic_backend_selected:r" in step for step in result.identification_trace)


def test_symbolic_identify_full_auto_fallback_order(monkeypatch) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (False, "y0_unavailable"))
    monkeypatch.setattr(
        symbolic_module,
        "_r_backend_available",
        lambda: (False, "rpy2_unavailable"),
    )

    diagram = _diagram_frontdoor_like()
    raw = SymbolicIdentify.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={"symbolic_backend": "full_auto", "require_symbolic_backend": True},
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])
    assert result.status is TransportabilityStatus.NON_TRANSPORTABLE
    assert any("symbolic_backend_order:y0,r" in step for step in result.identification_trace)
