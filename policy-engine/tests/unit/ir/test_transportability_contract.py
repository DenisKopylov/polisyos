from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod, EstimationStatus
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
    graph_content_sha256,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.estimand import DistributionDomain, EstimandAST
from polisyos.ir.analytics.partial_identification import BoundMethod, compute_manski_bounds
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    SelectionDiagramBuilder,
    SNode,
    SNodeOrigin,
    SNodeRole,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
    load_transportability_result,
    persist_transportability_result,
)
from polisyos.ir.registry.refs import TransportabilityResultRef


def test_transportability_result_artifact_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    result = TransportabilityResult(
        sutva_assumed=True,
        sutva_violation_risk="medium",
        metadata={"source": "unit_test"},
        notes=["minimal contract"],
    )

    ref = persist_transportability_result(_ensure_ir_artifact_store(store), result)
    loaded = load_transportability_result(_ensure_ir_artifact_store(store), ref)

    assert isinstance(ref, TransportabilityResultRef)
    assert ref.kind == "ir.transportability_result"
    assert loaded == result


def test_partial_graph_refusal_retains_exact_source_identity():
    graph = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.TAIL,
            )
        ],
    )
    source = ContextProfile(context_id="source", countries=["DE"], income_level=IncomeLevel.HIGH)
    target = ContextProfile(
        context_id="target",
        countries=["UA"],
        income_level=IncomeLevel.LOWER_MIDDLE,
    )
    diagram = SelectionDiagram(
        base_graph=graph,
        source_context=source,
        target_context=target,
        context_distance=0.25,
    )
    raw = CheckTransportability.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={},
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "partial_graph_completion_semantics_not_established"
    assert result.source_graph_type is GraphType.CPDAG
    assert result.source_graph_sha256 == graph_content_sha256(graph)


def test_transportability_source_graph_type_and_digest_are_all_or_none():
    with pytest.raises(ValidationError, match="source graph type and content digest"):
        TransportabilityResult(source_graph_type=GraphType.PAG)


def test_malformed_graph_refusal_does_not_bind_the_context_placeholder_as_source():
    source = ContextProfile(context_id="source", countries=["DE"], income_level=IncomeLevel.HIGH)
    target = ContextProfile(
        context_id="target", countries=["UA"], income_level=IncomeLevel.LOWER_MIDDLE
    )
    raw_diagram = {
        "base_graph": {
            "graph_type": GraphType.DAG.value,
            "nodes": ["X", "Y"],
            "edges": [
                {
                    "src": "X",
                    "dst": "Y",
                    "mark_src": EdgeMark.CIRCLE.value,
                    "mark_dst": EdgeMark.ARROW.value,
                }
            ],
        },
        "source_context": source.model_dump(mode="json"),
        "target_context": target.model_dump(mode="json"),
        "context_distance": 0.25,
    }
    raw = CheckTransportability.pure_step(
        state={
            "selection_diagram": raw_diagram,
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={},
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "causal_graph_profile_invalid"
    assert result.source_graph_type is None
    assert result.source_graph_sha256 is None
    assert result.source_context_id == "source"
    assert result.target_context_id == "target"
    assert "graph_type:dag" in result.identification_trace
    assert "__scalar_graph_admission__" not in str(result.model_dump(mode="json"))


def test_model_copy_invalid_dag_is_refused_before_registered_scalar_claim() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    ).model_copy(
        update={
            "edges": [
                CausalEdge(
                    src="X",
                    dst="Y",
                    mark_src=EdgeMark.CIRCLE,
                    mark_dst=EdgeMark.ARROW,
                )
            ]
        }
    )
    valid_base = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    diagram = SelectionDiagram(
        base_graph=valid_base,
        source_context=ContextProfile(
            context_id="source", countries=["DE"], income_level=IncomeLevel.HIGH
        ),
        target_context=ContextProfile(
            context_id="target", countries=["UA"], income_level=IncomeLevel.LOWER_MIDDLE
        ),
        context_distance=0.25,
    ).model_copy(update={"base_graph": graph})
    raw = CheckTransportability.pure_step(
        state={
            "selection_diagram": diagram,
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={},
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "causal_graph_profile_invalid"
    assert result.transport_formula is None
    assert "graph_admission_gate:refused:causal_graph_profile_invalid" in (
        result.identification_trace
    )
    assert raw["proof_bundle"]["proof_status"] == "oracle_needed"


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
            schema_version="2.0",
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
    # C is a collider and its mechanism shifts; the queried Y mechanism does not.
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "C"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
                sources=[EdgeSource.DATA],
                data_confidence=0.9,
            ),
            CausalEdge(
                src="X",
                dst="C",
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
                sources=[EdgeSource.DATA],
                data_confidence=0.8,
            ),
            CausalEdge(
                src="Y",
                dst="C",
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
                sources=[EdgeSource.LITERATURE],
                literature_confidence=0.85,
            ),
        ],
        discovery_method="expert_elicitation",
    )
    source_ctx = ContextProfile(
        context_id="src",
        countries=["SE"],
        income_level=IncomeLevel.HIGH,
        gdp_per_capita=55_000.0,
    )
    target_ctx = ContextProfile(
        context_id="tgt",
        countries=["NG"],
        income_level=IncomeLevel.LOWER_MIDDLE,
        gdp_per_capita=2_200.0,
    )
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[
            SNode(
                target_variable="C",
                context_dimension="institutional_quality",
                source_value=0.95,
                target_value=0.3,
                delta=0.65,
                severity="high",
                origin=SNodeOrigin.CONTEXT_DELTA,
                role=SNodeRole.COLLIDER,
            ),
        ],
        source_context=source_ctx,
        target_context=target_ctx,
        context_distance=0.7,
    )
    return diagram, "X", "Y"


def _build_outcome_selection_scenario() -> tuple[SelectionDiagram, str, str]:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
                sources=[EdgeSource.DATA],
                data_confidence=0.9,
            ),
        ],
        discovery_method="scientific_test_fixture",
    )
    diagram = (
        SelectionDiagramBuilder(graph)
        .add_sigma_variable("Y")
        .build(ContextProfile(context_id="source"), ContextProfile(context_id="target"))
    )
    return diagram, "X", "Y"


def test_golden_collider_selection_preserves_identified_source_law() -> None:
    diagram, treatment, outcome = _build_golden_scenario()
    raw = CheckTransportability.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": treatment,
            "query_outcome": outcome,
        },
        params={"transport_solver_mode": "simplified"},
    )
    tr = TransportabilityResult.model_validate(raw["transport_result"])
    assert tr.status is TransportabilityStatus.IDENTIFIED
    assert tr.transport_mode is TransportMode.TRANSPORT_FORMULA
    assert tr.transport_formula is not None
    assert tr.transport_formula.adjustment_type == "s_admissibility_source_law"
    assert tr.transport_formula.source_quantities == ["P_s(Y " + chr(92) + "mid X)"]
    assert tr.transport_formula.target_quantities == []
    assert tr.blocking_s_nodes == []

    ast = EstimandAST.model_validate(tr.estimand_ast)
    refs = ast.collect_distribution_refs()
    assert all(ref.domain is DistributionDomain.SOURCE for ref in refs)
    assert {(ref.variables, ref.conditioning) for ref in refs} == {(("Y",), ("X",))}
    metadata = raw["proof_bundle"]["metadata"]
    assert metadata["s_admissibility_selection_targets"] == ["C"]
    assert metadata["source_data_exists"] == "not_established"
    assert metadata["source_data_currentness"] == "not_established"
    assert metadata["source_data_authority"] == "not_established"


def test_manski_bounds_math_uses_named_target_domain_sufficient_statistics() -> None:
    # This is an arithmetic control: these arrays are supplied as target-population moments.
    target_outcome_stratum_means = np.array([0.25, 0.55])
    target_treatment_marginals = np.array([0.6, 0.4])
    manski = compute_manski_bounds(
        outcome_conditioned=target_outcome_stratum_means,
        treatment_probs=target_treatment_marginals,
        outcome_support=(0.0, 1.0),
    )
    assert manski.method is BoundMethod.MANSKI
    assert manski.lower_bound == pytest.approx(-0.33)
    assert manski.upper_bound == pytest.approx(0.67)
    assert manski.bound_width == pytest.approx(1.0)
    assert manski.is_informative is False


def test_outcome_selection_refusal_and_target_domain_bounds_are_not_automatic() -> None:
    diagram, treatment, outcome = _build_outcome_selection_scenario()
    raw = CheckTransportability.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": treatment,
            "query_outcome": outcome,
        },
        params={"transport_solver_mode": "simplified"},
    )
    tr = TransportabilityResult.model_validate(raw["transport_result"])
    assert tr.status is TransportabilityStatus.UNSUPPORTED
    assert tr.transport_mode is TransportMode.NONE
    assert tr.unsupported_reason == "query_variable_is_selection_target"
    assert tr.transport_formula is None
    assert tr.partial_identification_result is None
    assert raw["proof_bundle"]["metadata"]["selection_targets"] == ["Y"]
    assert raw["proof_bundle"]["metadata"]["limitation_reason"] == (
        "query_variable_is_selection_target"
    )

    # The math accepts target-domain moments, but this direct consumer does not bind or attach them.
    target_outcome_stratum_means = np.array([0.25, 0.55])
    target_treatment_marginals = np.array([0.6, 0.4])
    manski = compute_manski_bounds(
        outcome_conditioned=target_outcome_stratum_means,
        treatment_probs=target_treatment_marginals,
        outcome_support=(0.0, 1.0),
    )
    assert manski.lower_bound == pytest.approx(-0.33)
    assert manski.upper_bound == pytest.approx(0.67)
    assert tr.partial_identification_result is None


def test_golden_time_stationarity_warning() -> None:
    """A typed temporal refusal preserves its stationarity diagnostics."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
                lag=2,
                sources=[EdgeSource.DATA],
                data_confidence=0.9,
            ),
        ],
        discovery_method="pcmci",
    )
    source_ctx = ContextProfile(
        context_id="src",
        countries=["DE"],
        income_level=IncomeLevel.HIGH,
        gdp_per_capita=48_000.0,
    )
    target_ctx = ContextProfile(
        context_id="tgt",
        countries=["PL"],
        income_level=IncomeLevel.HIGH,
        gdp_per_capita=17_000.0,
    )
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[],
        source_context=source_ctx,
        target_context=target_ctx,
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
    assert tr.status is TransportabilityStatus.UNSUPPORTED
    assert tr.assumes_time_stationarity is True
    assert tr.lagged_edge_count == 1
    assert tr.temporal_distance_penalty > 0.0
