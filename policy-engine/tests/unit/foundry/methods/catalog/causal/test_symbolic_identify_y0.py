from __future__ import annotations

from importlib.metadata import version

import pytest

from polisyos.foundry.methods.catalog.causal import symbolic_identify as symbolic_module
from polisyos.foundry.methods.catalog.causal import transport_engine as transport_engine_module
from polisyos.foundry.methods.catalog.causal.symbolic_identify import (
    SymbolicIdentify,
    SymbolicIdentifyV2,
    convert_graph_to_symbolic_repr,
)
from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability
from polisyos.ir.analytics.causal import ProofBundle
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    PAGIdentificationPolicy,
)
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
        graph_type=GraphType.DAG,
        nodes=["X", "M", "Y"],
        edges=[
            CausalEdge(src="X", dst="M"),
            CausalEdge(src="M", dst="Y"),
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


def _y0_surrogate_data_profile() -> dict[str, object]:
    return {
        "schema_version": "policyos.y0.surrogate-data-profile.v1",
        "populations": [{"population_id": "pi1", "outcomes": ["Y"], "interventions": ["X"]}],
    }


def _diagram_partial_frontdoor(graph_type: GraphType = GraphType.PAG) -> SelectionDiagram:
    diagram = _diagram_frontdoor_like()
    if graph_type is GraphType.PAG:
        edges = [
            CausalEdge(
                src="X",
                dst="M",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            ),
            CausalEdge(
                src="M",
                dst="Y",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            ),
        ]
    else:
        edges = [CausalEdge(src="X", dst="M"), CausalEdge(src="M", dst="Y")]
    graph = CausalGraphModel(
        graph_type=graph_type,
        nodes=["X", "M", "Y"],
        edges=edges,
    )
    return diagram.model_copy(update={"base_graph": graph})


def _assert_symbolic_partial_graph_refusal(
    payload: dict[str, object],
    *,
    reason: str = "partial_graph_completion_semantics_not_established",
) -> None:
    result = TransportabilityResult.model_validate(payload["transport_result"])
    proof_bundle = ProofBundle.model_validate(payload["proof_bundle"])

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == reason
    assert result.transport_formula is None
    assert result.pag_identification_policy is None
    assert result.id_confidence_under_pag is None
    assert result.pag_dag_sample_size is None
    assert result.pag_transportable_count is None
    assert proof_bundle.proof_status == "oracle_needed"
    assert proof_bundle.completeness_regime == "sound_incomplete"
    assert proof_bundle.metadata["reason"] == reason
    assert "negative_certificate" not in payload
    assert "recovery_plan" not in payload


def test_symbolic_graph_conversion_roundtrip_shape() -> None:
    diagram = _diagram_frontdoor_like()
    payload = convert_graph_to_symbolic_repr(diagram.base_graph)

    assert payload["nodes"] == ["X", "M", "Y"]
    assert ("X", "M") in payload["directed_edges"]
    assert ("M", "Y") in payload["directed_edges"]


@pytest.mark.parametrize(
    ("method", "params"),
    [
        (SymbolicIdentify, {"symbolic_backend": "y0"}),
        (SymbolicIdentifyV2, {"use_native_id": True, "symbolic_backend": "y0"}),
    ],
)
def test_symbolic_identify_uses_actual_y0_direct_id(method, params, monkeypatch) -> None:
    pytest.importorskip("y0")
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))

    diagram = _diagram_frontdoor_like().model_copy(update={"s_nodes": []})
    raw = method.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params=params,
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])

    assert result.status is TransportabilityStatus.IDENTIFIED
    assert result.identification_engine == "y0"
    assert result.metadata["backend_id"] == "y0"
    assert result.metadata["backend_version"] == version("y0")
    assert result.metadata["backend_operation"] == "identify_outcomes"
    assert result.metadata["backend_call_attempted"] is True
    assert result.metadata["backend_call_established"] is True
    assert result.metadata["backend_result"] == "expression_returned"
    assert result.metadata["source_data_exists"] == "not_established"
    assert result.metadata["source_data_currentness"] == "not_established"
    assert result.metadata["source_data_authority"] == "not_established"
    assert result.requires_expert_review is True
    assert result.transport_formula is not None
    assert raw["proof_bundle"]["proof_status"] == "identified"
    assert raw["proof_bundle"]["proof_stratum"] == "A2_oracle_backed"
    assert raw["proof_bundle"]["completeness_regime"] == "sound_incomplete"
    assert raw["proof_bundle"]["metadata"]["transport_review_grade"] == "review_required"
    assert raw["proof_bundle"]["metadata"]["operation_scope"]["family"] == "direct"


def test_native_id_mathematical_result_stays_identified_without_verified_origin() -> None:
    diagram = _diagram_frontdoor_like().model_copy(update={"s_nodes": []})
    raw = SymbolicIdentifyV2.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={"use_native_id": True, "oracle_backend": "none"},
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])
    proof = ProofBundle.model_validate(raw["proof_bundle"])

    assert result.status is TransportabilityStatus.IDENTIFIED
    assert result.identification_engine == "native_id"
    assert proof.proof_status == "identified"
    assert proof.estimand_ast == result.estimand_ast
    assert proof.theorem_family == result.algorithm_version
    assert proof.proof_stratum == "A1_extended"
    assert proof.completeness_regime == "sound_incomplete"
    assert proof.metadata["proof_scope"] == "conditional_graph_mathematics"
    assert proof.metadata["transport_review_grade"] == "unknown"


def test_symbolic_identify_handles_frontdoor_like_case(monkeypatch) -> None:
    pytest.importorskip("y0")
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))

    diagram = _diagram_frontdoor_like()
    raw = SymbolicIdentify.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={
            "symbolic_backend": "y0",
            "surrogate_data_profile": _y0_surrogate_data_profile(),
        },
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.identification_engine == "y0"
    assert result.metadata["backend_id"] == "y0"
    assert result.metadata["backend_version"] == version("y0")
    assert result.unsupported_reason == "y0_trso_population_indexed_ast_unavailable"
    assert result.transport_formula is None
    assert result.estimand_ast is None
    assert result.metadata["backend_operation"] == "identify_target_outcomes"
    assert result.metadata["backend_call_attempted"] is True
    assert result.metadata["backend_call_established"] is True
    assert result.metadata["backend_result"] == "expression_returned"
    assert result.metadata["profile_origin"] == "consumer_asserted"
    assert result.metadata["source_data_exists"] == "not_established"
    assert result.metadata["source_data_authority"] == "not_established"
    assert result.metadata["candidate_formula_latex"]
    assert result.metadata["candidate_expression_y0"]
    assert result.metadata["typed_expression_ast"] == "not_representable_population_indexed_ast"
    assert result.requires_expert_review is True
    assert raw["proof_bundle"]["proof_status"] == "oracle_needed"
    assert raw["proof_bundle"]["metadata"]["surrogate_profile_sha256"]
    assert "negative_certificate" not in raw


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

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.identification_engine == "none"
    assert result.unsupported_reason == "y0_unavailable;rpy2_unavailable"
    assert any("symbolic_backend_limited" in step for step in result.identification_trace)
    assert raw["proof_bundle"]["proof_status"] == "oracle_needed"
    assert "negative_certificate" not in raw


def test_symbolic_identify_does_not_treat_r_availability_as_execution(monkeypatch) -> None:
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

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.identification_engine == "none"
    assert result.unsupported_reason == "symbolic_backend_execution_unavailable"
    assert raw["proof_bundle"]["proof_status"] == "oracle_needed"
    assert "negative_certificate" not in raw


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
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert any("symbolic_backend_order:y0,r" in step for step in result.identification_trace)


@pytest.mark.parametrize(
    ("method", "params"),
    [
        (SymbolicIdentify, {"symbolic_backend": "y0"}),
        (SymbolicIdentifyV2, {"use_native_id": False, "symbolic_backend": "y0"}),
        (SymbolicIdentifyV2, {"use_native_id": True}),
    ],
)
@pytest.mark.parametrize("graph_type", [GraphType.PAG, GraphType.CPDAG])
def test_symbolic_methods_refuse_partial_graph_before_frontdoor_and_native_id(
    monkeypatch,
    method,
    params: dict[str, object],
    graph_type: GraphType,
) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    diagram = _diagram_partial_frontdoor(graph_type)
    request = {"pag_identification_policy": "probabilistic", **params}

    raw = method.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        request,
    )

    _assert_symbolic_partial_graph_refusal(raw)
    result = TransportabilityResult.model_validate(raw["transport_result"])
    assert (
        "pag_policy_effective:probabilistic;origin:not_established" in result.identification_trace
    )
    if method is SymbolicIdentifyV2:
        assert raw["estimand_ast"] is None
    if graph_type is GraphType.PAG:
        assert [(edge.mark_src, edge.mark_dst) for edge in diagram.base_graph.edges] == [
            (EdgeMark.CIRCLE, EdgeMark.CIRCLE),
            (EdgeMark.CIRCLE, EdgeMark.CIRCLE),
        ]
    else:
        assert [(edge.mark_src, edge.mark_dst) for edge in diagram.base_graph.edges] == [
            (EdgeMark.TAIL, EdgeMark.ARROW),
            (EdgeMark.TAIL, EdgeMark.ARROW),
        ]


@pytest.mark.parametrize("method", [SymbolicIdentify, SymbolicIdentifyV2])
def test_symbolic_present_null_policy_is_not_absence(method) -> None:
    diagram = _diagram_partial_frontdoor()
    raw = method.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {"pag_identification_policy": None, "use_native_id": True},
    )

    _assert_symbolic_partial_graph_refusal(
        raw,
        reason="pag_identification_policy_invalid",
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])
    assert "pag_policy_input:invalid_present_value" in result.identification_trace


def test_symbolic_absent_policy_is_not_reconstructed_as_a_request() -> None:
    diagram = _diagram_partial_frontdoor()
    raw = SymbolicIdentify.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {},
    )

    _assert_symbolic_partial_graph_refusal(raw)
    result = TransportabilityResult.model_validate(raw["transport_result"])
    assert "pag_policy_input:absent" in result.identification_trace
    assert not any("pag_policy_effective:" in step for step in result.identification_trace)


def test_symbolic_partial_graph_refusal_gate_removal_control(monkeypatch) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    diagram = _diagram_partial_frontdoor()
    state = {
        "selection_diagram": diagram.model_dump(mode="json"),
        "query_treatment": "X",
        "query_outcome": "Y",
    }

    actual = SymbolicIdentify.pure_step(state, {"symbolic_backend": "y0"})
    _assert_symbolic_partial_graph_refusal(actual)

    monkeypatch.setattr(symbolic_module, "scalar_graph_admission_refusal", lambda **_: None)
    without_gate = SymbolicIdentify.pure_step(
        state,
        {"symbolic_backend": "y0", "surrogate_data_profile": _y0_surrogate_data_profile()},
    )
    removed_result = TransportabilityResult.model_validate(without_gate["transport_result"])
    assert removed_result.status is TransportabilityStatus.UNSUPPORTED
    assert removed_result.transport_formula is None
    assert (
        removed_result.unsupported_reason
        == "y0_trso_api_error:PartialGraphCompletionSemanticsError"
    )
    assert without_gate["proof_bundle"]["proof_status"] == "oracle_needed"
    assert "negative_certificate" not in without_gate


def test_registered_method_dispatch_default_keeps_request_origin_unknown(monkeypatch) -> None:
    from polisyos.foundry.methods.compiler import CompilationCache, MethodCompiler
    from polisyos.foundry.methods.selection.registry import MethodRegistry

    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    registry = MethodRegistry._create_fresh()
    registry.register(SymbolicIdentify)
    compiler = MethodCompiler(registry=registry, cache=CompilationCache(max_size=2))
    compiled = compiler.compile(SymbolicIdentify.signature.fqn, params={}, jit=False)
    diagram = _diagram_partial_frontdoor()
    state = {
        "selection_diagram": diagram.model_dump(mode="json"),
        "query_treatment": "X",
        "query_outcome": "Y",
    }

    defaulted = compiled(state, {})
    _assert_symbolic_partial_graph_refusal(defaulted)
    result = TransportabilityResult.model_validate(defaulted["transport_result"])
    assert (
        "pag_policy_effective:probabilistic;origin:not_established" in result.identification_trace
    )
    assert not any("pag_policy_input:requested:" in step for step in result.identification_trace)

    explicit_null = compiled(state, {"pag_identification_policy": None})
    _assert_symbolic_partial_graph_refusal(
        explicit_null,
        reason="pag_identification_policy_invalid",
    )


def test_symbolic_identify_v2_emits_canonical_payloads() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[],
        source_context=ContextProfile(context_id="SRC"),
        target_context=ContextProfile(context_id="TGT"),
        context_distance=0.0,
    )

    raw = SymbolicIdentifyV2.pure_step(
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params={"use_native_id": True},
    )

    result = TransportabilityResult.model_validate(raw["transport_result"])
    assert result.status is TransportabilityStatus.IDENTIFIED
    assert raw["proof_bundle"]["proof_status"] == "identified"
    assert "negative_certificate" not in raw


@pytest.mark.parametrize(
    ("method", "params"),
    [
        (SymbolicIdentify, {"symbolic_backend": "y0"}),
        (SymbolicIdentifyV2, {"use_native_id": False, "symbolic_backend": "y0"}),
        (SymbolicIdentifyV2, {"use_native_id": True}),
    ],
)
def test_symbolic_methods_refuse_admg_circle_endpoints_before_identification(
    monkeypatch,
    method,
    params: dict[str, object],
) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M", "Y"],
        edges=[
            CausalEdge(src="X", dst="M", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="M", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
        ],
    )
    diagram = _diagram_frontdoor_like().model_copy(update={"base_graph": graph})
    raw = method.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params,
    )

    _assert_symbolic_partial_graph_refusal(
        raw,
        reason="unsupported_static_admg_profile",
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])
    assert "graph_profile:unsupported_static_admg_profile" in result.identification_trace
    if method is SymbolicIdentifyV2:
        assert raw["estimand_ast"] is None


def test_symbolic_admg_profile_gate_removal_restores_frontdoor_claim(monkeypatch) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M", "Y"],
        edges=[
            CausalEdge(src="X", dst="M", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="M", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
        ],
    )
    diagram = _diagram_frontdoor_like().model_copy(update={"base_graph": graph})
    state = {
        "selection_diagram": diagram.model_dump(mode="json"),
        "query_treatment": "X",
        "query_outcome": "Y",
    }

    admitted = SymbolicIdentify.pure_step(
        state,
        {"symbolic_backend": "y0", "surrogate_data_profile": _y0_surrogate_data_profile()},
    )
    _assert_symbolic_partial_graph_refusal(admitted, reason="unsupported_static_admg_profile")

    original_gate = symbolic_module.scalar_graph_admission_refusal

    def graph_tag_only_gate(**kwargs):
        graph_type = kwargs["selection_diagram"].base_graph.graph_type
        if graph_type not in {GraphType.PAG, GraphType.CPDAG}:
            return None
        return original_gate(**kwargs)

    monkeypatch.setattr(symbolic_module, "scalar_graph_admission_refusal", graph_tag_only_gate)
    without_profile_predicate = SymbolicIdentify.pure_step(
        state,
        {"symbolic_backend": "y0", "surrogate_data_profile": _y0_surrogate_data_profile()},
    )
    result = TransportabilityResult.model_validate(without_profile_predicate["transport_result"])
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "y0_trso_api_error:UnsupportedStaticADMGProfileError"
    assert result.transport_formula is None
    assert without_profile_predicate["proof_bundle"]["proof_status"] == "oracle_needed"
    assert "negative_certificate" not in without_profile_predicate


def test_symbolic_serialized_graph_type_alias_matches_typed_profile() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M", "Y"],
        edges=[CausalEdge(src="X", dst="M"), CausalEdge(src="M", dst="Y")],
    )
    diagram = _diagram_frontdoor_like().model_copy(update={"base_graph": graph})
    json_profile = diagram.model_dump(mode="json")
    python_profile = diagram.model_dump(mode="python")
    normalized_diagram = SelectionDiagram.model_validate(json_profile)

    assert diagram.base_graph.graph_type is GraphType.ADMG
    assert [(edge.mark_src, edge.mark_dst) for edge in diagram.base_graph.edges] == [
        (EdgeMark.TAIL, EdgeMark.ARROW),
        (EdgeMark.TAIL, EdgeMark.ARROW),
    ]
    assert [node.target_variable for node in diagram.s_nodes] == ["M"]
    assert normalized_diagram.model_dump(mode="json") == json_profile

    def run(selection_diagram: SelectionDiagram | dict[str, object]) -> dict[str, object]:
        return SymbolicIdentify.pure_step(
            {
                "selection_diagram": selection_diagram,
                "query_treatment": "X",
                "query_outcome": "Y",
            },
            {"symbolic_backend": "y0", "surrogate_data_profile": _y0_surrogate_data_profile()},
        )

    typed_output = run(diagram)
    json_output = run(json_profile)
    python_output = run(python_profile)
    normalized_output = run(normalized_diagram)

    # The alias representation must not change the admitted graph, declared
    # source profile, actual Y0 expression, or proof binding.
    assert typed_output == json_output == python_output == normalized_output


@pytest.mark.parametrize(
    ("supplied", "profile", "reason", "state_name"),
    [
        (False, None, "y0_surrogate_data_profile_absent", "absent"),
        (True, None, "y0_surrogate_data_profile_null", "null"),
        (
            True,
            {"schema_version": "wrong", "populations": []},
            "y0_surrogate_data_profile_invalid",
            "invalid",
        ),
    ],
)
def test_trso_profile_input_failures_are_distinct_typed_limitations(
    supplied: bool, profile: object, reason: str, state_name: str, monkeypatch
) -> None:
    pytest.importorskip("y0")
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    params: dict[str, object] = {"symbolic_backend": "y0"}
    if supplied:
        params["surrogate_data_profile"] = profile
    raw = SymbolicIdentify.pure_step(
        {
            "selection_diagram": _diagram_frontdoor_like().model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params,
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])
    proof = ProofBundle.model_validate(raw["proof_bundle"])

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == reason
    assert result.metadata["profile_input_state"] == state_name
    assert result.metadata["backend_call_established"] is False
    assert proof.proof_status == "oracle_needed"
    assert "negative_certificate" not in raw


def test_trso_call_result_is_consumed_and_api_none_does_not_become_nonidentification(
    monkeypatch,
) -> None:
    pytest.importorskip("y0")
    import y0.algorithm.transport as y0_transport

    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    call_count = 0

    def removed_operation(**kwargs):
        nonlocal call_count
        call_count += 1
        return None

    monkeypatch.setattr(y0_transport, "identify_target_outcomes", removed_operation)
    raw = SymbolicIdentify.pure_step(
        {
            "selection_diagram": _diagram_frontdoor_like().model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {
            "symbolic_backend": "y0",
            "surrogate_data_profile": _y0_surrogate_data_profile(),
        },
    )
    result = TransportabilityResult.model_validate(raw["transport_result"])

    assert call_count == 1
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "y0_trso_returned_no_expression"
    assert result.metadata["backend_call_established"] is True
    assert result.metadata["backend_result"] == "none_returned"
    assert raw["proof_bundle"]["proof_status"] == "oracle_needed"
    assert "negative_certificate" not in raw


def test_registered_v2_accepts_profile_and_keeps_unrepresentable_y0_candidate(monkeypatch) -> None:
    pytest.importorskip("y0")
    from polisyos.foundry.methods.compiler import CompilationCache, MethodCompiler
    from polisyos.foundry.methods.selection.registry import MethodRegistry

    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    registry = MethodRegistry._create_fresh()
    registry.register(SymbolicIdentifyV2)
    compiler = MethodCompiler(registry=registry, cache=CompilationCache(max_size=2))
    compiled = compiler.compile(SymbolicIdentifyV2.signature.fqn, params={}, jit=False)
    state = {
        "selection_diagram": _diagram_frontdoor_like().model_dump(mode="json"),
        "query_treatment": "X",
        "query_outcome": "Y",
    }
    absent = compiled(state, {"use_native_id": False, "oracle_backend": "y0"})
    absent_result = TransportabilityResult.model_validate(absent["transport_result"])
    assert absent_result.unsupported_reason == "y0_surrogate_data_profile_absent"
    output = compiled(
        state,
        {
            "use_native_id": False,
            "oracle_backend": "y0",
            "surrogate_data_profile": _y0_surrogate_data_profile(),
        },
    )
    result = TransportabilityResult.model_validate(output["transport_result"])
    proof = ProofBundle.model_validate(output["proof_bundle"])

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.identification_engine == "y0"
    assert result.metadata["backend_id"] == "y0"
    assert result.metadata["backend_version"] == version("y0")
    assert result.metadata["backend_operation"] == "identify_target_outcomes"
    assert result.unsupported_reason == "y0_trso_population_indexed_ast_unavailable"
    assert result.transport_formula is None
    assert result.metadata["candidate_formula_latex"]
    assert output["estimand_ast"] is None
    assert proof.proof_status == "oracle_needed"
    assert proof.metadata["surrogate_profile_sha256"] == result.metadata["surrogate_profile_sha256"]


_GRAPH_ADMISSION_ROUTES = [
    ("check", CheckTransportability, {}),
    (
        "symbolic-v1-y0",
        SymbolicIdentify,
        {"symbolic_backend": "y0", "surrogate_data_profile": _y0_surrogate_data_profile()},
    ),
    (
        "symbolic-v2-fallback-y0",
        SymbolicIdentifyV2,
        {
            "use_native_id": False,
            "symbolic_backend": "y0",
            "surrogate_data_profile": _y0_surrogate_data_profile(),
        },
    ),
    ("symbolic-v2-native", SymbolicIdentifyV2, {"use_native_id": True}),
]


@pytest.mark.parametrize(("route", "method", "params"), _GRAPH_ADMISSION_ROUTES)
@pytest.mark.parametrize("reverse_storage", [False, True])
@pytest.mark.parametrize("mark_src", list(EdgeMark))
@pytest.mark.parametrize("mark_dst", list(EdgeMark))
@pytest.mark.parametrize("graph_type", list(GraphType))
def test_all_scalar_routes_enforce_complete_graph_type_endpoint_product(
    monkeypatch,
    route: str,
    method,
    params: dict[str, object],
    graph_type: GraphType,
    mark_src: EdgeMark,
    mark_dst: EdgeMark,
    reverse_storage: bool,
) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    src, dst = ("Y", "X") if reverse_storage else ("X", "Y")
    graph = CausalGraphModel.model_construct(
        schema_version="1.0",
        graph_type=graph_type,
        nodes=["X", "Y"],
        edges=[CausalEdge(src=src, dst=dst, mark_src=mark_src, mark_dst=mark_dst)],
        discovery_method="",
        skg_version_id=None,
        pag_identification_policy=PAGIdentificationPolicy.CONSERVATIVE,
        id_confidence_under_pag=None,
        metadata={},
    )
    diagram = SelectionDiagram(
        base_graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y"],
            edges=[CausalEdge(src="X", dst="Y")],
        ),
        s_nodes=[],
        source_context=ContextProfile(context_id="source"),
        target_context=ContextProfile(context_id="target"),
        context_distance=0.0,
    ).model_copy(update={"base_graph": graph})
    payload = method.pure_step(
        {
            "selection_diagram": diagram,
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params,
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])

    valid_dag = graph_type is GraphType.DAG and (mark_src, mark_dst) == (
        EdgeMark.TAIL,
        EdgeMark.ARROW,
    )
    valid_admg = graph_type is GraphType.ADMG and (mark_src, mark_dst) in {
        (EdgeMark.TAIL, EdgeMark.ARROW),
        (EdgeMark.ARROW, EdgeMark.TAIL),
        (EdgeMark.ARROW, EdgeMark.ARROW),
    }
    graph_admission_reasons = {
        "partial_graph_completion_semantics_not_established",
        "unsupported_static_admg_profile",
        "causal_graph_profile_invalid",
        "causal_graph_type_not_supported",
    }
    assert route
    if valid_dag or valid_admg:
        assert result.unsupported_reason not in graph_admission_reasons
        assert not any(item.startswith("graph_profile:") for item in result.identification_trace)
        return

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason in graph_admission_reasons
    assert result.transport_formula is None
    assert result.identified_region is None
    proof = ProofBundle.model_validate(payload["proof_bundle"])
    assert proof.proof_status == "oracle_needed"
    assert proof.completeness_regime == "sound_incomplete"
    assert proof.metadata["reason"] == result.unsupported_reason
    assert "negative_certificate" not in payload
    assert "recovery_plan" not in payload


@pytest.mark.parametrize(
    ("source_type", "replacement_type", "mark_src", "mark_dst", "expected_reason"),
    [
        (
            GraphType.PAG,
            GraphType.ADMG,
            EdgeMark.CIRCLE,
            EdgeMark.CIRCLE,
            "unsupported_static_admg_profile",
        ),
        (
            GraphType.ADMG,
            GraphType.PAG,
            EdgeMark.CIRCLE,
            EdgeMark.CIRCLE,
            "partial_graph_completion_semantics_not_established",
        ),
        (GraphType.ADMG, GraphType.ADMG, EdgeMark.TAIL, EdgeMark.ARROW, None),
    ],
)
def test_relabelled_graph_profile_is_rechecked_against_retained_endpoint_marks(
    source_type: GraphType,
    replacement_type: GraphType,
    mark_src: EdgeMark,
    mark_dst: EdgeMark,
    expected_reason: str | None,
) -> None:
    graph = CausalGraphModel(
        graph_type=source_type,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=mark_src, mark_dst=mark_dst)],
    ).model_copy(update={"graph_type": replacement_type})
    result = transport_engine_module._canonical_scalar_graph_refusal(graph)
    if expected_reason is None:
        assert result[:2] == (None, "admg")
        assert result[2] is not None
    else:
        assert result[:2] == (expected_reason, replacement_type.value)


def test_noncanonical_model_copy_aliases_fail_closed_but_json_aliases_normalize() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    aliased_type = graph.model_copy(update={"graph_type": "admg"})
    aliased_mark = graph.model_copy(
        update={"edges": [graph.edges[0].model_copy(update={"mark_src": "tail"})]}
    )
    assert transport_engine_module._canonical_scalar_graph_refusal(aliased_type)[0] == (
        "causal_graph_profile_invalid"
    )
    assert transport_engine_module._canonical_scalar_graph_refusal(aliased_mark)[0] == (
        "causal_graph_profile_invalid"
    )
    assert (
        transport_engine_module._canonical_scalar_graph_refusal(
            CausalGraphModel.model_validate(graph.model_dump(mode="json"))
        )[0]
        is None
    )


@pytest.mark.parametrize(("route", "method", "params"), _GRAPH_ADMISSION_ROUTES[1:])
def test_remove_endpoint_predicate_keeps_markers_but_y0_still_refuses_unsupported_graph(
    monkeypatch,
    route: str,
    method,
    params: dict[str, object],
) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M", "Y"],
        edges=[
            CausalEdge(src="X", dst="M", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="M", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
        ],
    )
    diagram = _diagram_frontdoor_like().model_copy(update={"base_graph": graph})
    state = {
        "selection_diagram": diagram,
        "query_treatment": "X",
        "query_outcome": "Y",
    }
    admitted = method.pure_step(state, params)
    _assert_symbolic_partial_graph_refusal(
        admitted,
        reason="unsupported_static_admg_profile",
    )

    # Remove the graph endpoint predicate while retaining the typed response
    # markers. The real Y0 producer must still refuse this unsupported graph.
    monkeypatch.setattr(
        transport_engine_module,
        "_canonical_scalar_graph_refusal",
        lambda _: (None, "admg", graph),
    )
    without_predicate = method.pure_step(state, params)
    result = TransportabilityResult.model_validate(without_predicate["transport_result"])
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.transport_formula is None
    assert result.unsupported_reason in {
        "y0_trso_api_error:UnsupportedStaticADMGProfileError",
        "y0_surrogate_data_profile_absent",
    }
    assert without_predicate["proof_bundle"]["proof_status"] == "oracle_needed"
    assert "negative_certificate" not in without_predicate


@pytest.mark.parametrize(("route", "method", "params"), _GRAPH_ADMISSION_ROUTES)
def test_public_method_dispatcher_numpy_runner_returns_typed_profile_refusal(
    monkeypatch,
    route: str,
    method,
    params: dict[str, object],
) -> None:
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M", "Y"],
        edges=[
            CausalEdge(src="X", dst="M", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="M", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
        ],
    )
    diagram = _diagram_frontdoor_like().model_copy(update={"base_graph": graph})
    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    dispatched = dispatcher.dispatch(
        method_class=method,
        signature=method.signature,
        state={
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params=params,
        seed=0,
    )
    output = dispatched.output
    result = TransportabilityResult.model_validate(output["transport_result"])

    assert route
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "unsupported_static_admg_profile"
    assert result.transport_formula is None
    proof = ProofBundle.model_validate(output["proof_bundle"])
    assert proof.proof_status == "oracle_needed"
    assert proof.completeness_regime == "sound_incomplete"
    assert output.get("estimand_ast") is None
    assert "negative_certificate" not in output


@pytest.mark.parametrize(("route", "method", "params"), _GRAPH_ADMISSION_ROUTES)
def test_invalid_graph_mapping_is_typed_refusal_before_any_scalar_route(
    monkeypatch,
    route: str,
    method,
    params: dict[str, object],
) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    diagram = _diagram_frontdoor_like().model_dump(mode="json")
    diagram["base_graph"] = {
        "graph_type": "dag",
        "nodes": ["X", "M", "Y"],
        "edges": [
            {"src": "X", "dst": "M", "mark_src": "circle", "mark_dst": "circle"},
            {"src": "M", "dst": "Y", "mark_src": "tail", "mark_dst": "arrow"},
        ],
    }
    payload = method.pure_step(
        {
            "selection_diagram": diagram,
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params,
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])

    assert route
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "causal_graph_profile_invalid"
    assert "graph_profile:causal_graph_profile_invalid" in result.identification_trace
    assert result.transport_formula is None
    proof = ProofBundle.model_validate(payload["proof_bundle"])
    assert proof.proof_status == "oracle_needed"
    assert proof.completeness_regime == "sound_incomplete"
    assert "negative_certificate" not in payload
    assert "recovery_plan" not in payload


@pytest.mark.parametrize(("route", "method", "params"), _GRAPH_ADMISSION_ROUTES)
@pytest.mark.parametrize(
    ("graph_type", "edges", "expected_reason"),
    [
        (
            GraphType.ADMG,
            [CausalEdge(src="X", dst="Y", lag=1)],
            "unsupported_static_admg_profile",
        ),
        (
            GraphType.DAG,
            [CausalEdge(src="X", dst="Y", lag=1)],
            "unsupported_static_admg_profile",
        ),
        (
            GraphType.ADMG,
            [CausalEdge(src="X", dst="Y"), CausalEdge(src="Y", dst="X")],
            "causal_graph_profile_invalid",
        ),
    ],
)
def test_scalar_graph_admission_enforces_static_lag_and_acyclic_profile(
    monkeypatch,
    route: str,
    method,
    params: dict[str, object],
    graph_type: GraphType,
    edges: list[CausalEdge],
    expected_reason: str,
) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    graph = CausalGraphModel.model_construct(
        schema_version="1.0",
        graph_type=graph_type,
        nodes=["X", "Y"],
        edges=edges,
        discovery_method="",
        skg_version_id=None,
        pag_identification_policy=PAGIdentificationPolicy.CONSERVATIVE,
        id_confidence_under_pag=None,
        metadata={},
    )
    diagram = _diagram_frontdoor_like().model_copy(update={"base_graph": graph})
    payload = method.pure_step(
        {
            "selection_diagram": diagram,
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params,
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])

    assert route
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == expected_reason
    assert result.transport_formula is None
    proof = ProofBundle.model_validate(payload["proof_bundle"])
    assert proof.proof_status == "oracle_needed"
    assert proof.completeness_regime == "sound_incomplete"
    assert "negative_certificate" not in payload


def _live_subclass_diagram(kind: str) -> SelectionDiagram:
    source = ContextProfile(context_id="subclass-source")
    target = ContextProfile(context_id="subclass-target")
    benign = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "M", "Y"],
        edges=[CausalEdge(src="X", dst="M"), CausalEdge(src="M", dst="Y")],
    )
    static_admg = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M", "Y"],
        edges=[CausalEdge(src="X", dst="M"), CausalEdge(src="M", dst="Y")],
    )
    if kind == "graph":

        class LyingGraph(CausalGraphModel):
            def model_dump(self, *args: object, **kwargs: object) -> dict[str, object]:
                return benign.model_dump(*args, **kwargs)

        graph = LyingGraph(
            graph_type=GraphType.ADMG,
            nodes=["X", "M", "Y"],
            edges=[
                CausalEdge(src="X", dst="M", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
                CausalEdge(src="M", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            ],
        )
        return SelectionDiagram(
            base_graph=graph, s_nodes=[], source_context=source, target_context=target
        )
    if kind == "edge":

        class LyingEdge(CausalEdge):
            def model_dump(self, *args: object, **kwargs: object) -> dict[str, object]:
                return CausalEdge(src="X", dst="M").model_dump(*args, **kwargs)

        graph = CausalGraphModel(
            graph_type=GraphType.ADMG,
            nodes=["X", "M", "Y"],
            edges=[
                LyingEdge(src="X", dst="M"),
                CausalEdge(src="M", dst="Y"),
            ],
        )
        return SelectionDiagram(
            base_graph=graph, s_nodes=[], source_context=source, target_context=target
        )
    if kind == "diagram":

        class LyingDiagram(SelectionDiagram):
            def model_dump(self, *args: object, **kwargs: object) -> dict[str, object]:
                return _diagram_frontdoor_like().model_dump(*args, **kwargs)

        return LyingDiagram(
            base_graph=static_admg, s_nodes=[], source_context=source, target_context=target
        )
    raise AssertionError(f"unknown live object subclass kind: {kind}")


@pytest.mark.parametrize(("route", "method", "params"), _GRAPH_ADMISSION_ROUTES)
@pytest.mark.parametrize("kind", ["graph", "edge", "diagram"])
def test_public_dispatcher_refuses_noncanonical_live_object_subclasses(
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    method: type[CheckTransportability] | type[SymbolicIdentify] | type[SymbolicIdentifyV2],
    params: dict[str, object],
    kind: str,
) -> None:
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    diagram = _live_subclass_diagram(kind)
    dispatched = MethodDispatcher(enable_runtime_selection=False).dispatch(
        method_class=method,
        signature=method.signature,
        state={
            "selection_diagram": diagram,
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params=params,
        seed=0,
    )
    output = dispatched.output
    result = TransportabilityResult.model_validate(output["transport_result"])

    assert route
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "causal_graph_profile_invalid"
    assert result.transport_formula is None
    proof = ProofBundle.model_validate(output["proof_bundle"])
    assert proof.proof_status == "oracle_needed"
    assert proof.completeness_regime == "sound_incomplete"
    assert proof.metadata["reason"] == "causal_graph_profile_invalid"
    assert output.get("estimand_ast") is None
    assert "negative_certificate" not in output
    assert "recovery_plan" not in output


@pytest.mark.parametrize(("route", "method", "params"), _GRAPH_ADMISSION_ROUTES)
def test_public_dispatcher_refuses_model_copy_hidden_s_nodes(
    route: str,
    method: type[CheckTransportability] | type[SymbolicIdentify] | type[SymbolicIdentifyV2],
    params: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    class HiddenSNodes(list[SNode]):
        def __bool__(self) -> bool:
            return False

    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    canonical = _diagram_frontdoor_like()
    diagram = canonical.model_copy(
        update={"s_nodes": HiddenSNodes(list.__iter__(canonical.s_nodes))}
    )
    dispatched = MethodDispatcher(enable_runtime_selection=False).dispatch(
        method_class=method,
        signature=method.signature,
        state={
            "selection_diagram": diagram,
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params=params,
        seed=0,
    )
    output = dispatched.output
    result = TransportabilityResult.model_validate(output["transport_result"])
    proof = ProofBundle.model_validate(output["proof_bundle"])

    assert route
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "causal_graph_profile_invalid"
    assert result.transport_formula is None
    assert proof.proof_status == "oracle_needed"
    assert proof.completeness_regime == "sound_incomplete"
    assert proof.metadata["reason"] == "causal_graph_profile_invalid"
    assert output.get("estimand_ast") is None
    assert "negative_certificate" not in output
    assert "recovery_plan" not in output


@pytest.mark.parametrize(("route", "method", "params"), _GRAPH_ADMISSION_ROUTES)
def test_public_dispatcher_refuses_model_copy_partial_admg_before_claim(
    route: str,
    method: (type[CheckTransportability] | type[SymbolicIdentify] | type[SymbolicIdentifyV2]),
    params: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    if method in {SymbolicIdentify, SymbolicIdentifyV2}:
        monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    directed_admg = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M", "Y"],
        edges=[CausalEdge(src="X", dst="M"), CausalEdge(src="M", dst="Y")],
    )
    partial_graph = directed_admg.model_copy(
        update={
            "edges": [
                CausalEdge(
                    src="X",
                    dst="M",
                    mark_src=EdgeMark.CIRCLE,
                    mark_dst=EdgeMark.CIRCLE,
                ),
                CausalEdge(
                    src="M",
                    dst="Y",
                    mark_src=EdgeMark.CIRCLE,
                    mark_dst=EdgeMark.CIRCLE,
                ),
            ]
        }
    )
    diagram = _diagram_frontdoor_like().model_copy(update={"base_graph": partial_graph})
    dispatched = MethodDispatcher(enable_runtime_selection=False).dispatch(
        method_class=method,
        signature=method.signature,
        state={
            "selection_diagram": diagram,
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params=params,
        seed=0,
    )
    output = dispatched.output
    result = TransportabilityResult.model_validate(output["transport_result"])
    proof = ProofBundle.model_validate(output["proof_bundle"])

    assert route
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "unsupported_static_admg_profile"
    assert result.transport_formula is None
    assert proof.proof_status == "oracle_needed"
    assert proof.completeness_regime == "sound_incomplete"
    assert proof.metadata["reason"] == "unsupported_static_admg_profile"
    assert output.get("estimand_ast") is None
    assert "negative_certificate" not in output
    assert "recovery_plan" not in output


def test_direct_solver_refuses_noncanonical_live_diagram_subclass() -> None:
    diagram = _live_subclass_diagram("diagram")

    result = transport_engine_module.solve_transportability(
        selection_diagram=diagram,
        query_treatment="X",
        query_outcome="Y",
    )

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "causal_graph_profile_invalid"
    assert result.transport_formula is None


def test_direct_solver_refuses_model_copy_hidden_s_nodes() -> None:
    class HiddenSNodes(list[SNode]):
        def __bool__(self) -> bool:
            return False

    canonical = _diagram_frontdoor_like()
    diagram = canonical.model_copy(
        update={"s_nodes": HiddenSNodes(list.__iter__(canonical.s_nodes))}
    )

    result = transport_engine_module.solve_transportability(
        selection_diagram=diagram,
        query_treatment="X",
        query_outcome="Y",
    )

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "causal_graph_profile_invalid"
    assert result.transport_formula is None


@pytest.mark.parametrize(
    ("method", "params"),
    [
        (CheckTransportability, {}),
        (SymbolicIdentify, {}),
        (SymbolicIdentifyV2, {"use_native_id": False, "symbolic_backend": "y0"}),
        (SymbolicIdentifyV2, {"use_native_id": True}),
    ],
)
@pytest.mark.parametrize("container_kind", ["edge_iteration", "s_node_truthiness"])
def test_noncanonical_live_containers_cannot_change_admitted_diagram(
    method, params: dict[str, object], container_kind: str, monkeypatch
) -> None:
    if method in {SymbolicIdentify, SymbolicIdentifyV2}:
        monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))

    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "M", "Y"],
        edges=[CausalEdge(src="X", dst="M"), CausalEdge(src="M", dst="Y")],
    )
    source = ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH)
    target = ContextProfile(context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE)
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[
            SNode(
                target_variable="M",
                context_dimension="institutional_quality",
                source_value=0.9,
                target_value=0.2,
                delta=0.7,
                severity="high",
            )
        ],
        source_context=source,
        target_context=target,
        context_distance=0.4,
    )

    if container_kind == "edge_iteration":

        class HiddenEdges(list[CausalEdge]):
            def __iter__(self):
                for edge in list.__iter__(self):
                    yield edge.model_copy(
                        update={"mark_src": EdgeMark.CIRCLE, "mark_dst": EdgeMark.CIRCLE}
                    )

        object.__setattr__(graph, "edges", HiddenEdges(list.__iter__(graph.edges)))
    else:

        class HiddenSNodes(list[SNode]):
            def __bool__(self) -> bool:
                return False

        object.__setattr__(diagram, "s_nodes", HiddenSNodes(list.__iter__(diagram.s_nodes)))

    payload = method.pure_step(
        {
            "selection_diagram": diagram,
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        params,
    )
    _assert_symbolic_partial_graph_refusal(payload, reason="causal_graph_profile_invalid")
    assert payload["transport_result"]["transport_formula"] is None
    assert payload["proof_bundle"]["proof_status"] == "oracle_needed"


@pytest.mark.parametrize(
    ("route", "params"),
    [
        ("check", {}),
        (
            "symbolic-v1",
            {"symbolic_backend": "y0", "surrogate_data_profile": _y0_surrogate_data_profile()},
        ),
        (
            "symbolic-v2-fallback",
            {
                "use_native_id": False,
                "symbolic_backend": "y0",
                "surrogate_data_profile": _y0_surrogate_data_profile(),
            },
        ),
        ("symbolic-v2-native", {"use_native_id": True}),
    ],
)
def test_registered_routes_consume_the_same_snapshot_that_passed_admission(
    route: str, params: dict[str, object], monkeypatch
) -> None:
    monkeypatch.setattr(symbolic_module, "_y0_available", lambda: (True, None))
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "M", "Y"],
        edges=[CausalEdge(src="X", dst="M"), CausalEdge(src="M", dst="Y")],
    )
    source = ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH)
    target = ContextProfile(context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE)
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[
            SNode(
                target_variable="M",
                context_dimension="institutional_quality",
                source_value=0.9,
                target_value=0.2,
                delta=0.7,
                severity="high",
            )
        ],
        source_context=source,
        target_context=target,
        context_distance=0.4,
    )
    state = {
        "selection_diagram": diagram,
        "query_treatment": "X",
        "query_outcome": "Y",
    }

    def run_route() -> dict[str, object]:
        if route == "check":
            return CheckTransportability.pure_step(state, params)
        if route == "symbolic-v1":
            return SymbolicIdentify.pure_step(state, params)
        return SymbolicIdentifyV2.pure_step(state, params)

    baseline = run_route()
    canonical_gate = transport_engine_module._canonical_scalar_graph_refusal
    mutation_count = 0

    def mutate_original_after_gate(
        candidate: object,
    ) -> tuple[str | None, str, CausalGraphModel | None]:
        nonlocal mutation_count
        decision = canonical_gate(candidate)
        if mutation_count == 0:
            mutation_count += 1
            object.__setattr__(graph, "graph_type", GraphType.ADMG)
            object.__setattr__(
                graph,
                "edges",
                [
                    edge.model_copy(
                        update={"mark_src": EdgeMark.CIRCLE, "mark_dst": EdgeMark.CIRCLE}
                    )
                    for edge in list.__iter__(graph.edges)
                ],
            )
        return decision

    monkeypatch.setattr(
        transport_engine_module,
        "_canonical_scalar_graph_refusal",
        mutate_original_after_gate,
    )
    payload = run_route()

    result = TransportabilityResult.model_validate(payload["transport_result"])
    assert mutation_count == 1
    assert graph.graph_type is GraphType.ADMG
    assert graph.edges[0].mark_src is EdgeMark.CIRCLE
    # The route may legitimately return a bounded or unavailable backend result;
    # the property is that mutating the caller's source after admission cannot
    # change any result/proof field relative to the same canonical input.
    assert payload == baseline
