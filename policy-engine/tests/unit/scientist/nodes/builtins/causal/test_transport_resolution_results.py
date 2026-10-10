"""Behavioral coverage for transport-resolution result and projection helpers."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.data_forge.domains.catalog.knowledge.proxy_resolver import (
    ProxyCandidate,
    ProxyChain,
    compose_confidence_harmonic,
    validate_proxy,
)
from polisyos.data_forge.domains.catalog.knowledge.types import PStarZResult
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import (
    DataGap,
    SelectionDiagram,
    SNodeOrigin,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
    load_transportability_result,
    persist_transportability_result,
)
from polisyos.ir.registry.refs import TransportabilityResultRef
from polisyos.lex.legal_evaluation.transport_constraints import (
    ConstraintSeverity,
    LegalConstraint,
    LegalConstraintSet,
    LegalToDAGMapping,
    LegalToDAGMappingType,
)
from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
    ResolutionState,
    TransportabilityResolutionLoop,
)
from polisyos.scientist.nodes.builtins.causal.transport_resolution_results import (
    _apply_partial_identification_fallback,
    _build_final_result,
    _build_proxy_quantity_or_gap,
    _legal_constraints_to_s_nodes,
)


def _graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["policy", "income_proxy", "income", "welfare"],
        edges=[
            CausalEdge(src="policy", dst="income"),
            CausalEdge(src="income_proxy", dst="income"),
            CausalEdge(src="income", dst="welfare"),
        ],
    )


def _income_pstar(confidence: float = 0.85) -> PStarZResult:
    return PStarZResult(
        canonical_variable="income",
        value=None,
        dataset_id="dataset-ua-income",
        raw_variable="income_raw",
        is_proxy=True,
        proxy_chain=["income_proxy -> income"],
        confidence=confidence,
        ci_low=0.4,
        ci_high=0.8,
        data_support_year=2020,
        data_support_country="UA",
    )


def _legal_mapping(
    *,
    source: str = "policy",
    target: str = "income",
    new_node_name: str | None = "income",
    mapping_type: LegalToDAGMappingType = LegalToDAGMappingType.MECHANISM_NODE,
) -> LegalToDAGMapping:
    constraint = LegalConstraint(
        constraint_id="synthetic-income-protection",
        description="Synthetic test constraint; not a real legal rule or issuer fact.",
        jurisdiction="synthetic-fixture",
        legal_source="test-fixture:synthetic-non-issuer",
        severity=ConstraintSeverity.HARD,
        affects_mechanism=mapping_type is LegalToDAGMappingType.MECHANISM_NODE,
    )
    return LegalToDAGMapping(
        legal_constraint=constraint,
        mapping_type=mapping_type,
        affected_edges=[(source, target)],
        new_node_name=new_node_name,
        mechanism_description="Eligibility protection changes policy access.",
        confidence_penalty=0.2,
        requires_expert_review=True,
        rationale="The binding rule changes the intervention mechanism.",
    )


def test_proxy_result_and_data_gap_follow_validation_threshold_and_conditioning() -> None:
    graph = _graph()
    adjacency = {
        "policy": {"income"},
        "income_proxy": {"income"},
        "income": {"welfare"},
        "welfare": set(),
    }
    candidate = ProxyCandidate(
        proxy_variable="income_proxy",
        proxy_dataset_id="dataset-proxy",
        proxy_raw_name="income_proxy_raw",
        base_correlation=0.8,
        context_adjustment=1.0,
        effective_confidence=0.8,
        source="seed_table",
    )
    proxy_chain = ProxyChain(
        target_variable="income",
        proxies=[candidate],
        best_single_confidence=0.8,
    )
    context = ContextProfile(context_id="target-ua", time_period="2020")
    p_star, gap, validity, penalty, requires_review, reasons = _build_proxy_quantity_or_gap(
        variable="income",
        target_context=context,
        outcome="welfare",
        adjacency=adjacency,
        proxy_chain=proxy_chain,
        condition_on={"year": 2020.0},
        proxy_threshold=0.7,
        validate_proxy_fn=validate_proxy,
        compose_confidence_harmonic_fn=compose_confidence_harmonic,
    )
    assert p_star is not None
    assert gap is None
    assert validity is not None and validity["overall_valid"] is True
    assert requires_review is False
    assert reasons == []
    assert p_star.is_conditional is True
    assert p_star.condition_on == {"year": 2020.0}
    assert p_star.proxy_chain == ["income_proxy -> income"]
    assert p_star.confidence == pytest.approx(0.7888888888888889)
    assert penalty == pytest.approx(1.0 - p_star.confidence)
    assert graph.nodes == ["policy", "income_proxy", "income", "welfare"]

    weak_chain = proxy_chain.model_copy(update={"best_single_confidence": 0.4})
    missing_p_star, data_gap, gap_validity, gap_penalty, _, _ = _build_proxy_quantity_or_gap(
        variable="income",
        target_context=context,
        outcome="welfare",
        adjacency=adjacency,
        proxy_chain=weak_chain,
        condition_on=None,
        proxy_threshold=0.7,
        validate_proxy_fn=validate_proxy,
        compose_confidence_harmonic_fn=compose_confidence_harmonic,
    )
    assert missing_p_star is None
    assert data_gap is not None
    assert data_gap.required_variable == "income"
    assert data_gap.required_context == "target-ua, 2020"
    assert data_gap.available_proxies == [candidate]
    assert gap_validity is None
    assert gap_penalty is None


def test_legal_projection_and_fresh_cas_preserve_result_alignment(
    execution_context,
) -> None:
    graph = _graph()
    source_context = ContextProfile(context_id="UA-2020", countries=["UA"], publication_year=2020)
    target_context = ContextProfile(context_id="UA-2024", countries=["UA"], publication_year=2024)
    diagram = SelectionDiagram(
        base_graph=graph,
        source_context=source_context,
        target_context=target_context,
        context_distance=0.25,
    )

    legal_nodes = _legal_constraints_to_s_nodes(
        mappings=[_legal_mapping()],
        causal_graph=graph,
    )
    assert len(legal_nodes) == 1
    assert legal_nodes[0].target_variable == "income"
    assert legal_nodes[0].legal_constraint_id == "synthetic-income-protection"
    assert legal_nodes[0].severity == "high"
    assert legal_nodes[0].origin is SNodeOrigin.LEGAL
    # Prototype only: the explicit single-edge shape is projectable here, but
    # the live bridge emits all graph edges, so this does not establish edge
    # intent or legal meaning. The review-required flag is still carried.
    modifier_nodes = _legal_constraints_to_s_nodes(
        mappings=[
            _legal_mapping(
                mapping_type=LegalToDAGMappingType.EFFECT_MODIFIER,
                new_node_name=None,
            )
        ],
        causal_graph=graph,
    )
    assert [node.target_variable for node in modifier_nodes] == ["income"]

    # A stale named mechanism target does not fall through to valid affected edges.
    stale_mechanism_reasons: list[str] = []
    assert (
        _legal_constraints_to_s_nodes(
            mappings=[_legal_mapping(new_node_name="unregistered_legal_node")],
            causal_graph=graph,
            expert_review_reasons=stale_mechanism_reasons,
        )
        == []
    )
    assert (
        "legal_mapping_unresolved:synthetic-income-protection:"
        "mechanism_target_not_present_in_current_graph"
    ) in (stale_mechanism_reasons)
    assert any(
        "legal_mapping_requires_expert_review" in reason for reason in stale_mechanism_reasons
    )

    # This field combination has no defined target projection. It is unresolved,
    # not classified as an invalid legal mapping.
    edge_with_node_name_reasons: list[str] = []
    assert (
        _legal_constraints_to_s_nodes(
            mappings=[
                _legal_mapping(
                    mapping_type=LegalToDAGMappingType.EFFECT_MODIFIER,
                    new_node_name="income",
                )
            ],
            causal_graph=graph,
            expert_review_reasons=edge_with_node_name_reasons,
        )
        == []
    )
    assert any(
        "effect_modifier_target_shape_unresolved" in reason
        for reason in edge_with_node_name_reasons
    )

    # A missing edge endpoint, ambiguous multi-edge modifier, and intervention
    # redefinition have no supported SNode target representation.
    assert (
        _legal_constraints_to_s_nodes(
            mappings=[
                _legal_mapping(
                    target="missing-variable",
                    new_node_name=None,
                    mapping_type=LegalToDAGMappingType.EFFECT_MODIFIER,
                )
            ],
            causal_graph=graph,
        )
        == []
    )
    assert (
        _legal_constraints_to_s_nodes(
            mappings=[
                _legal_mapping(
                    new_node_name=None,
                    mapping_type=LegalToDAGMappingType.EFFECT_MODIFIER,
                ).model_copy(
                    update={"affected_edges": [("policy", "income"), ("income", "welfare")]}
                )
            ],
            causal_graph=graph,
        )
        == []
    )
    assert (
        _legal_constraints_to_s_nodes(
            mappings=[
                _legal_mapping(
                    new_node_name="policy",
                    mapping_type=LegalToDAGMappingType.INTERVENTION_REDEF,
                )
            ],
            causal_graph=graph,
        )
        == []
    )

    # A completely unregistered target is also unresolved and never defaulted.
    unresolved_reasons: list[str] = []
    assert (
        _legal_constraints_to_s_nodes(
            mappings=[
                _legal_mapping(
                    source="missing-source",
                    target="missing-variable",
                    new_node_name="unregistered_legal_node",
                )
            ],
            causal_graph=graph,
            expert_review_reasons=unresolved_reasons,
        )
        == []
    )
    assert any(
        "mechanism_target_not_present_in_current_graph" in reason for reason in unresolved_reasons
    )

    gap = DataGap(
        required_variable="age",
        required_context="UA-2024",
        gap_impact="Target age distribution is missing.",
        suggested_action="Collect target age observations.",
    )
    state = ResolutionState(
        round=3,
        legal_s_nodes=legal_nodes,
        data_gaps=[gap],
        p_star_values={"income": _income_pstar()},
        proxy_penalties={"income": 0.1},
        requires_expert_review=bool(stale_mechanism_reasons),
        expert_review_reasons=stale_mechanism_reasons,
        feasible=True,
    )
    base = TransportabilityResult(
        query="P*(welfare|do(policy))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.DIRECT,
        base_confidence=0.9,
        final_confidence=0.9,
        source_context_id="stale-source-context",
        target_context_id="stale-target-context",
        warnings=["source-warning"],
        search_events=["source-search-event"],
    )

    result = _build_final_result(tr_result=base, state=state, diagram=diagram)
    assert result.status is TransportabilityStatus.IDENTIFIED
    assert result.transport_mode is TransportMode.DIRECT
    assert result.final_confidence == pytest.approx(0.567)
    assert result.data_gaps == [gap]
    assert result.p_star_values["income"].dataset_id == "dataset-ua-income"
    assert result.source_context_id == "UA-2020"
    assert result.target_context_id == "UA-2024"
    assert result.requires_expert_review is True
    assert any(
        "mechanism_target_not_present_in_current_graph" in reason
        for reason in result.expert_review_reasons
    )
    assert "source-warning" in result.warnings
    assert "Missing target quantities for 1 variable(s); added data_gaps." in result.warnings
    assert result.search_events[0] == "source-search-event"
    lineage = result.metadata["lineage_three_graph"]
    assert lineage["all_layers_present"] is True
    assert lineage["dataset"][0]["dataset_id"] == "dataset-ua-income"
    assert lineage["legal"] == [
        {
            "constraint_id": "synthetic-income-protection",
            "target_variable": "income",
            "origin": "legal",
        }
    ]
    assert base.warnings == ["source-warning"]

    ir_store = ensure_ir_artifact_store(execution_context.store)
    result_ref = persist_transportability_result(ir_store, result)
    assert isinstance(result_ref, TransportabilityResultRef)
    assert result_ref.kind == "ir.transportability_result"
    fresh_result = load_transportability_result(
        ensure_ir_artifact_store(execution_context.store),
        result_ref,
    )
    assert fresh_result == result
    assert fresh_result.status is TransportabilityStatus.IDENTIFIED
    assert fresh_result.metadata["lineage_three_graph"] == lineage


def test_resolution_loop_carries_unresolved_legal_mapping_into_review_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.scientist.nodes.builtins.causal.resolve_transport as transport_module

    mapping = _legal_mapping(new_node_name="unregistered_legal_node")
    base_result = TransportabilityResult(
        query="P*(income|do(policy))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.DIRECT,
        base_confidence=0.9,
        final_confidence=0.9,
    )

    monkeypatch.setattr(
        transport_module,
        "_evaluate_legal_constraints",
        lambda **_kwargs: LegalConstraintSet(
            jurisdiction="synthetic",
            policy_domain="fixture",
            legal_dag_mappings=[mapping],
        ),
    )
    monkeypatch.setattr(
        transport_module,
        "_run_transport_solver",
        lambda **_kwargs: {"transport_result": base_result.model_dump(mode="json")},
    )

    source = ContextProfile(context_id="source")
    target = ContextProfile(context_id="target")
    result = TransportabilityResolutionLoop(
        dataset_registry=object(),
        legal_kg_db_path=None,
        skg_query=object(),
        max_rounds=1,
    ).resolve(
        source_context=source,
        target_context=target,
        causal_graph=_graph(),
        query_treatment="policy",
        query_outcome="income",
    )

    assert result.legal_s_nodes == []
    assert result.requires_expert_review is True
    assert any(
        "mechanism_target_not_present_in_current_graph" in reason
        for reason in result.expert_review_reasons
    )


def test_partial_identification_changes_status_only_for_informative_bounds() -> None:
    unsupported = TransportabilityResult(
        query="P*(welfare|do(policy))",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        base_confidence=0.0,
        final_confidence=0.0,
        feasible=False,
        unsupported_reason="basis_not_transportable",
    )
    without_evidence, unsupported_bounds = _apply_partial_identification_fallback(
        tr_result=unsupported,
        state=ResolutionState(round=1),
        warnings=[],
    )
    assert unsupported_bounds is not None
    assert unsupported_bounds.is_informative is False
    assert without_evidence.status is TransportabilityStatus.UNSUPPORTED
    assert without_evidence.transport_mode is TransportMode.NONE
    assert without_evidence.unsupported_reason == "basis_not_transportable"

    warnings: list[str] = []
    with_evidence, informative_bounds = _apply_partial_identification_fallback(
        tr_result=unsupported,
        state=ResolutionState(round=1, p_star_values={"income": _income_pstar()}),
        warnings=warnings,
    )
    assert informative_bounds is not None
    assert informative_bounds.is_informative is True
    assert with_evidence.status is TransportabilityStatus.BOUNDED_NON_IDENTIFIED
    assert with_evidence.transport_mode is TransportMode.BOUNDS_ONLY
    assert with_evidence.unsupported_reason is None
    assert warnings == ["partial_identification_informative:manski_bounds"]
