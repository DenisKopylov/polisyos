from __future__ import annotations

import pytest

from polisyos.foundry.methods.catalog.causal import transport_engine as transport_engine_module
from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability
from polisyos.foundry.methods.catalog.causal.transport_engine import solve_transportability
from polisyos.ir.analytics.causal import ProofBundle
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    PAGIdentificationPolicy,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.privacy_transportability import (
    DPMechanismScope,
    PrivacyAwareTransportCertificate,
    PrivacyObservedMode,
    TransportPrivacyContext,
)
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    SNode,
    SNodeOrigin,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
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


def test_transport_check_cpdag_refuses_unselected_extension_semantics() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.CPDAG,
        nodes=["X", "Y", "Z"],
        edges=[
            CausalEdge(src="X", dst="Y"),
            CausalEdge(src="Y", dst="X"),
            CausalEdge(src="Z", dst="Y"),
        ],
    )
    source = ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH)
    target = ContextProfile(context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE)
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[],
        source_context=source,
        target_context=target,
        context_distance=0.4,
    )

    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {},
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])
    proof_bundle = ProofBundle.model_validate(payload["proof_bundle"])

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.transport_mode is TransportMode.NONE
    assert result.unsupported_reason == "partial_graph_completion_semantics_not_established"
    assert result.id_confidence_under_pag is None
    assert result.pag_dag_sample_size is None
    assert result.pag_transportable_count is None
    assert proof_bundle.proof_status == "oracle_needed"
    assert proof_bundle.completeness_regime == "sound_incomplete"
    assert proof_bundle.metadata["reason"] == "partial_graph_completion_semantics_not_established"
    assert "negative_certificate" not in payload
    assert "recovery_plan" not in payload
    assert [(edge.src, edge.dst) for edge in diagram.base_graph.edges] == [
        ("X", "Y"),
        ("Y", "X"),
        ("Z", "Y"),
    ]


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


def _assert_partial_graph_refusal(payload: dict[str, object], reason: str) -> None:
    result = TransportabilityResult.model_validate(payload["transport_result"])
    proof_bundle = ProofBundle.model_validate(payload["proof_bundle"])

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.transport_mode is TransportMode.NONE
    assert result.unsupported_reason == reason
    assert result.pag_identification_policy is None
    assert result.id_confidence_under_pag is None
    assert result.pag_dag_sample_size is None
    assert result.pag_transportable_count is None
    assert result.transport_formula is None
    assert proof_bundle.proof_status == "oracle_needed"
    assert proof_bundle.completeness_regime == "sound_incomplete"
    assert proof_bundle.metadata["reason"] == reason
    assert "negative_certificate" not in payload
    assert "recovery_plan" not in payload


def test_transport_check_bidirected_pag_does_not_orient_latent_edge_as_observed_dag() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.ARROW,
                mark_dst=EdgeMark.ARROW,
            )
        ],
    )
    source = ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH)
    target = source.model_copy(deep=True)
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[],
        source_context=source,
        target_context=target,
        context_distance=0.0,
    )
    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {},
    )

    _assert_partial_graph_refusal(
        payload,
        "partial_graph_completion_semantics_not_established",
    )
    assert diagram.base_graph.edges[0].mark_src is EdgeMark.ARROW
    assert diagram.base_graph.edges[0].mark_dst is EdgeMark.ARROW


@pytest.mark.parametrize(
    "policy",
    ["conservative", "optimistic", "probabilistic", PAGIdentificationPolicy.PROBABILISTIC],
)
def test_transport_check_circle_pag_refuses_even_when_sampler_threshold_would_pass(
    policy: str | PAGIdentificationPolicy | None,
) -> None:
    diagram = _pag_diagram_for_probabilistic_test()
    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {
            "pag_identification_policy": policy,
            "pag_max_dag_samples": 20,
            "pag_threshold": 0.5,
            "pag_seed": 17,
        },
    )

    _assert_partial_graph_refusal(
        payload,
        "partial_graph_completion_semantics_not_established",
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])
    effective_policy = getattr(policy, "value", policy)
    assert (
        f"pag_policy_effective:{effective_policy};origin:not_established"
        in result.identification_trace
    )
    assert diagram.base_graph.edges[0].mark_src is EdgeMark.CIRCLE
    assert diagram.base_graph.edges[0].mark_dst is EdgeMark.CIRCLE


def test_transport_check_absent_policy_is_not_reconstructed_as_a_request() -> None:
    diagram = _pag_diagram_for_probabilistic_test()
    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {},
    )

    _assert_partial_graph_refusal(
        payload,
        "partial_graph_completion_semantics_not_established",
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])
    assert "pag_policy_input:absent" in result.identification_trace
    assert not any("pag_policy_effective:" in step for step in result.identification_trace)


@pytest.mark.parametrize("policy", [None, "probabilistic-ish", 7])
def test_transport_check_malformed_present_pag_policy_is_typed_refusal(
    policy: str | int | None,
) -> None:
    diagram = _pag_diagram_for_probabilistic_test()
    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {"pag_identification_policy": policy},
    )

    _assert_partial_graph_refusal(payload, "pag_identification_policy_invalid")
    result = TransportabilityResult.model_validate(payload["transport_result"])
    assert "pag_policy_input:invalid_present_value" in result.identification_trace


def test_transport_check_privacy_bounds_cannot_upgrade_partial_graph_refusal() -> None:
    diagram = SelectionDiagram(
        base_graph=CausalGraphModel(
            graph_type=GraphType.PAG,
            nodes=["X", "Y"],
            edges=[
                CausalEdge(
                    src="X",
                    dst="Y",
                    mark_src=EdgeMark.ARROW,
                    mark_dst=EdgeMark.ARROW,
                )
            ],
        ),
        s_nodes=[],
        source_context=ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH),
        target_context=ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH),
        context_distance=0.0,
    )
    privacy_context = TransportPrivacyContext(
        privacy_transport_certificate=PrivacyAwareTransportCertificate(
            certificate_id="privacy-bounds-only",
            query="P*(Y|do(X))",
            selection_diagram_ref="selection_diagram:DE->DE",
            latent_transport_status=TransportabilityStatus.UNSUPPORTED,
            privacy_observed_mode=PrivacyObservedMode.BOUNDS_ONLY,
            source_domains=("DE",),
            target_domain="DE",
            dp_scope=(
                DPMechanismScope(
                    domain_id="DE",
                    mechanism_id="mechanism-1",
                    mechanism_family="laplace",
                    privacy_model="central_dp",
                    epsilon=1.0,
                ),
            ),
        )
    )

    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {"privacy_context": privacy_context},
    )
    _assert_partial_graph_refusal(
        payload,
        "partial_graph_completion_semantics_not_established",
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])
    assert result.metadata["privacy_observed_mode"] == "bounds_only"
    assert result.metadata["privacy_latent_transport_status"] == "unsupported"


@pytest.mark.parametrize("reverse_storage", [False, True])
@pytest.mark.parametrize("mark_src", list(EdgeMark))
@pytest.mark.parametrize("mark_dst", list(EdgeMark))
@pytest.mark.parametrize("graph_type", list(GraphType))
def test_transport_check_admits_only_canonical_static_graph_profiles(
    graph_type: GraphType,
    mark_src: EdgeMark,
    mark_dst: EdgeMark,
    reverse_storage: bool,
) -> None:
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
    source = ContextProfile(context_id="source")
    target = ContextProfile(context_id="target")
    diagram = SelectionDiagram(
        base_graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y"],
            edges=[CausalEdge(src="X", dst="Y")],
        ),
        s_nodes=[],
        source_context=source,
        target_context=target,
        context_distance=0.0,
    ).model_copy(update={"base_graph": graph})

    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram,
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {},
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

    if valid_dag or valid_admg:
        assert result.status is TransportabilityStatus.IDENTIFIED
        assert result.unsupported_reason is None
        return

    refusal = payload.get("proof_bundle")
    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.transport_formula is None
    assert result.identified_region is None
    assert result.unsupported_reason in {
        "partial_graph_completion_semantics_not_established",
        "unsupported_static_admg_profile",
        "causal_graph_profile_invalid",
        "causal_graph_type_not_supported",
    }
    assert refusal is not None
    proof = ProofBundle.model_validate(refusal)
    assert proof.proof_status == "oracle_needed"
    assert proof.completeness_regime == "sound_incomplete"
    assert proof.metadata["reason"] == result.unsupported_reason
    assert "negative_certificate" not in payload
    assert "recovery_plan" not in payload


def test_transport_check_refuses_admg_circle_profile_before_scalar_result() -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "M", "Y"],
        edges=[
            CausalEdge(src="X", dst="M", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="M", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
        ],
    )
    source = ContextProfile(context_id="source")
    target = ContextProfile(context_id="target")
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[],
        source_context=source,
        target_context=target,
        context_distance=0.0,
    )

    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {},
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])
    proof = ProofBundle.model_validate(payload["proof_bundle"])

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "unsupported_static_admg_profile"
    assert result.transport_formula is None
    assert proof.proof_status == "oracle_needed"
    assert proof.completeness_regime == "sound_incomplete"
    assert "negative_certificate" not in payload


@pytest.mark.parametrize("entrypoint", ["registered_check", "direct_solver"])
def test_admitted_snapshot_is_consumed_after_original_graph_mutates(
    entrypoint: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    source = ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH)
    target = source.model_copy(deep=True)
    diagram = SelectionDiagram(
        base_graph=graph,
        s_nodes=[],
        source_context=source,
        target_context=target,
        context_distance=0.0,
    )
    canonical_gate = transport_engine_module._canonical_scalar_graph_refusal
    mutation_count = 0

    def mutate_original_after_gate(candidate: object) -> tuple[str | None, str]:
        nonlocal mutation_count
        decision = canonical_gate(candidate)
        if mutation_count == 0:
            mutation_count += 1
            object.__setattr__(graph, "graph_type", GraphType.ADMG)
            object.__setattr__(
                graph,
                "edges",
                [
                    CausalEdge(
                        src="X",
                        dst="Y",
                        mark_src=EdgeMark.CIRCLE,
                        mark_dst=EdgeMark.CIRCLE,
                    )
                ],
            )
        return decision

    monkeypatch.setattr(
        transport_engine_module,
        "_canonical_scalar_graph_refusal",
        mutate_original_after_gate,
    )
    state = {
        "selection_diagram": diagram,
        "query_treatment": "X",
        "query_outcome": "Y",
    }
    if entrypoint == "registered_check":
        payload = CheckTransportability.pure_step(state, {})
        result = TransportabilityResult.model_validate(payload["transport_result"])
    else:
        result = solve_transportability(
            selection_diagram=diagram,
            query_treatment="X",
            query_outcome="Y",
        )

    assert mutation_count == 1
    assert graph.graph_type is GraphType.ADMG
    assert graph.edges[0].mark_src is EdgeMark.CIRCLE
    assert result.status is TransportabilityStatus.IDENTIFIED
    assert result.transport_mode is TransportMode.DIRECT
    assert result.unsupported_reason is None


def test_hidden_s_node_container_is_typed_refused_before_transport_claim() -> None:
    class HiddenSNodes(list[SNode]):
        def __bool__(self) -> bool:
            return False

    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "M", "Y"],
        edges=[CausalEdge(src="X", dst="M"), CausalEdge(src="M", dst="Y")],
    )
    source = ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH)
    target = ContextProfile(context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE)
    canonical = SelectionDiagram(
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
    hidden = canonical.model_copy(
        update={"s_nodes": HiddenSNodes(list.__iter__(canonical.s_nodes))}
    )

    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": hidden,
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {},
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])
    proof_bundle = ProofBundle.model_validate(payload["proof_bundle"])

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "causal_graph_profile_invalid"
    assert result.transport_formula is None
    assert proof_bundle.proof_status == "oracle_needed"
    assert proof_bundle.completeness_regime == "sound_incomplete"
    assert "negative_certificate" not in payload
