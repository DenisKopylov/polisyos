from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod, EstimationStatus
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.partial_identification import BoundMethod, compute_manski_bounds
from polisyos.ir.analytics.transportability import (
    SNode,
    SNodeOrigin,
    SNodeRole,
    SelectionDiagram,
    TransportMode,
    TransportabilityResult,
    TransportabilityStatus,
    load_transportability_result,
    persist_transportability_result,
)
from polisyos.ir.refs import TransportabilityResultRef

from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability


def test_transportability_result_artifact_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    result = TransportabilityResult(
        sutva_assumed=True,
        sutva_violation_risk="medium",
        metadata={"source": "unit_test"},
        notes=["minimal contract"],
    )

    ref = persist_transportability_result(store, result)
    loaded = load_transportability_result(store, ref)

    assert isinstance(ref, TransportabilityResultRef)
    assert ref.kind == "ir.transportability_result"
    assert loaded == result


def test_causal_report_accepts_transportability_fields() -> None:
    report = CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE",
        point_estimate=1.1,
        confidence_interval=(0.9, 1.3),
        inference_method="backdoor.linear_regression",
        sample_size=120,
        n_treated=60,
        n_control=60,
        pre_periods=0,
        post_periods=0,
        sutva_assumed=True,
        sutva_violation_risk="high",
        transport_result=TransportabilityResult(
            sutva_assumed=True,
            sutva_violation_risk="high",
            metadata={"phase": "8A"},
        ),
    )

    assert report.sutva_assumed is True
    assert report.sutva_violation_risk == "high"
    assert report.transport_result is not None
    assert report.transport_result.sutva_violation_risk == "high"


def test_transportability_result_upgrades_legacy_formula_alias() -> None:
    payload = {
        "status": "transportable",
        "query": "P*(Y|do(X))",
        "formula": {
            "formula_str": "P*(Y|do(X)) = Σ_z P(Y|do(X),z)P*(z)",
            "stratification_variables": ["z"],
            "stratification_details": [],
            "source_quantities": ["P(Y|do(X),z)"],
            "target_quantities": ["P*(z)"],
            "adjustment_type": "stratification",
        },
    }
    result = TransportabilityResult.model_validate(payload)

    assert result.transport_formula is not None
    dumped = result.model_dump(mode="json")
    assert "formula" not in dumped
    assert dumped["identification_engine"] == "simplified_legacy"


def test_transportability_result_normalizes_derived_fields_consistently() -> None:
    payload = {
        "status": "unsupported",
        "base_confidence": 1.4,
        "context_distance_penalty": -0.2,
        "outer_search_truncated": True,
        "lagged_edge_count": 2,
    }

    normalized = TransportabilityResult.normalize_payload(payload)
    result = TransportabilityResult.from_payload(payload)

    assert "unsupported_reason" not in payload
    assert normalized["unsupported_reason"] == "transport_unsupported"
    assert result.transport_mode is TransportMode.NONE
    assert result.unsupported_reason == "transport_unsupported"
    assert result.base_confidence == 1.0
    assert result.context_distance_penalty == 0.0
    assert result.search_budget_exhausted is True
    assert "search_budget_exhausted" in result.search_events
    assert "outer_search_truncated" in result.search_events
    assert result.lagged_edges_in_query is True
    assert result.assumes_time_stationarity is True
    assert result.time_stationarity_warning is not None

    cloned = result.model_copy(deep=True)
    assert cloned.transport_mode is TransportMode.NONE
    reparsed = TransportabilityResult.model_validate(result.model_dump(mode="json"))
    assert reparsed.transport_mode is TransportMode.NONE
    assert reparsed.search_events == result.search_events


def test_transportability_result_is_frozen_report_contract() -> None:
    result = TransportabilityResult()

    with pytest.raises(ValidationError, match="frozen"):
        result.final_confidence = 0.5


# --- DOD-145 golden tests ---


def _build_golden_scenario() -> tuple[SelectionDiagram, str, str]:
    """Collider S-node blocks transport → NON_TRANSPORTABLE.

    Graph: X -> Y, X -> C <- Y, S-node on C (collider).
    """
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "C"],
        edges=[
            CausalEdge(
                src="X", dst="Y",
                mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW,
                sources=[EdgeSource.DATA], data_confidence=0.9,
            ),
            CausalEdge(
                src="X", dst="C",
                mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW,
                sources=[EdgeSource.DATA], data_confidence=0.8,
            ),
            CausalEdge(
                src="Y", dst="C",
                mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW,
                sources=[EdgeSource.LITERATURE], literature_confidence=0.85,
            ),
        ],
        discovery_method="expert_elicitation",
    )
    source_ctx = ContextProfile(
        context_id="src", countries=["SE"],
        income_level=IncomeLevel.HIGH,
        gdp_per_capita=55_000.0,
    )
    target_ctx = ContextProfile(
        context_id="tgt", countries=["NG"],
        income_level=IncomeLevel.LOWER_MIDDLE,
        gdp_per_capita=2_200.0,
    )
    s_nodes = [
        SNode(
            target_variable="C",
            context_dimension="institutional_quality",
            source_value=0.95, target_value=0.3, delta=0.65,
            severity="high",
            origin=SNodeOrigin.CONTEXT_DELTA,
            role=SNodeRole.COLLIDER,
        ),
    ]
    diagram = SelectionDiagram(
        base_graph=graph, s_nodes=s_nodes,
        source_context=source_ctx, target_context=target_ctx,
        context_distance=0.7,
    )
    return diagram, "X", "Y"


def test_golden_non_transportable_verdict() -> None:
    """Collider S-node blocks transport → UNSUPPORTED in legacy simplified mode."""
    diagram, treatment, outcome = _build_golden_scenario()
    raw = CheckTransportability.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": treatment,
            "query_outcome": outcome,
        },
        params={},
    )
    tr = TransportabilityResult.model_validate(raw["transport_result"])
    assert tr.status == TransportabilityStatus.UNSUPPORTED
    assert tr.final_confidence == 0.0
    assert len(tr.blocking_s_nodes) >= 1


def test_golden_manski_bounds_fallback() -> None:
    """When transport fails, Manski bounds provide partial identification."""
    manski = compute_manski_bounds(
        outcome_conditioned=np.array([0.3, 0.6]),
        treatment_probs=np.array([0.45, 0.55]),
        outcome_support=(0.0, 1.0),
    )
    assert manski.method == BoundMethod.MANSKI
    assert manski.lower_bound < manski.upper_bound
    assert manski.lower_bound <= 0.3
    assert manski.upper_bound >= 0.3
    assert manski.bound_width > 0


def test_golden_non_transportable_then_manski_e2e() -> None:
    """Full pipeline: transport fails → Manski bounds provide fallback."""
    diagram, treatment, outcome = _build_golden_scenario()

    raw = CheckTransportability.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": treatment,
            "query_outcome": outcome,
        },
        params={},
    )
    tr = TransportabilityResult.model_validate(raw["transport_result"])
    assert tr.status == TransportabilityStatus.UNSUPPORTED

    manski = compute_manski_bounds(
        outcome_conditioned=np.array([0.25, 0.55]),
        treatment_probs=np.array([0.6, 0.4]),
        outcome_support=(0.0, 1.0),
    )
    assert manski.lower_bound < manski.upper_bound
    assert manski.bound_width > 0


def test_golden_time_stationarity_warning() -> None:
    """Lagged edges set assumes_time_stationarity=True."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X", dst="Y",
                mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW,
                lag=2,
                sources=[EdgeSource.DATA], data_confidence=0.9,
            ),
        ],
        discovery_method="pcmci",
    )
    source_ctx = ContextProfile(
        context_id="src", countries=["DE"],
        income_level=IncomeLevel.HIGH,
        gdp_per_capita=48_000.0,
    )
    target_ctx = ContextProfile(
        context_id="tgt", countries=["PL"],
        income_level=IncomeLevel.HIGH,
        gdp_per_capita=17_000.0,
    )
    diagram = SelectionDiagram(
        base_graph=graph, s_nodes=[],
        source_context=source_ctx, target_context=target_ctx,
        context_distance=0.3,
    )
    raw = CheckTransportability.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={},
    )
    tr = TransportabilityResult.model_validate(raw["transport_result"])
    assert tr.assumes_time_stationarity is True
    assert tr.lagged_edge_count == 1
    assert tr.temporal_distance_penalty > 0.0
