from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest

from polisyos.foundry.methods.catalog.causal import pag_member_family as pag_family_engine
from polisyos.foundry.methods.catalog.causal import transport_engine as engine
from polisyos.foundry.methods.catalog.causal.capabilities import (
    build_causal_capability_contract,
)
from polisyos.foundry.methods.catalog.causal.pag_member_family import (
    PAGAdmittedMember,
    PAGBackendIdentity,
    PAGMemberBudget,
    PAGMemberFamilyCoverage,
    PAGMemberFamilyResult,
    PAGMemberFamilyStatus,
    evaluate_pag_member_family,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    graph_content_sha256,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.estimand import DistributionDomain, EstimandAST
from polisyos.ir.analytics.transportability import (
    SelectionDiagramBuilder,
    TransportabilityCandidateInputBindingV1,
    TransportabilityCandidateMemberEvaluationV1,
    TransportabilityCandidateModelPlanRelationV1,
    TransportabilityStatus,
    TransportMode,
    build_selection_diagram,
    transportability_candidate_query_sha256,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.model_layer.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.registry.refs import CausalGraphModelRef

_PROFILE = "sha256:" + "a" * 64
_CANON = CanonSpec(forbid_floats=False, sort_keys=True, exclude_none=False)


def _sha(value: object) -> str:
    return hashlib.sha256(to_canonical_bytes(value, _CANON)).hexdigest()


def _pag() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["consumption_response", "gdp_growth"],
        edges=[
            CausalEdge(
                src="consumption_response",
                dst="gdp_growth",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
        ],
        discovery_method="FCI",
    )


def _family(graph: CausalGraphModel) -> PAGMemberFamilyResult:
    """Generate the exact two-node G06 family with a test-only equivalence oracle.

    This fixture exercises proposal generation and member consumption without
    claiming the optional pinned causal-learn backend ran. For exactly two
    adjacent observed nodes, each resolved no-selection DAG/ADMG member has the
    same circle-circle observational PAG; the broader profile/backend is tested
    separately by its owner.
    """
    identity = PAGBackendIdentity(
        backend_id="test.exact_two_node_equivalence_oracle",
        backend_version="1",
        fci_source_sha256="a" * 64,
        cit_source_sha256="b" * 64,
        adapter_source_sha256="c" * 64,
    )

    def reconstruct(
        candidate: CausalGraphModel,
        _fci: object,
        _numpy: object,
        _networkx: object,
    ) -> tuple[tuple[str, ...], dict[tuple[str, str], tuple[EdgeMark, EdgeMark]]]:
        assert candidate.graph_type in {GraphType.DAG, GraphType.ADMG}
        assert set(candidate.nodes) == set(graph.nodes)
        assert len(candidate.edges) == 1
        edge = candidate.edges[0]
        if candidate.graph_type is GraphType.DAG:
            assert (edge.mark_src, edge.mark_dst) in {
                (EdgeMark.TAIL, EdgeMark.ARROW),
                (EdgeMark.ARROW, EdgeMark.TAIL),
            }
        else:
            assert (edge.mark_src, edge.mark_dst) == (EdgeMark.ARROW, EdgeMark.ARROW)
        return tuple(sorted(candidate.nodes)), pag_family_engine._source_endpoint_map(graph)

    with (
        patch.object(
            pag_family_engine,
            "_backend_identity",
            return_value=(identity, object(), object(), object()),
        ),
        patch.object(
            pag_family_engine,
            "_oracle_pag_endpoint_map",
            side_effect=reconstruct,
        ),
    ):
        return evaluate_pag_member_family(
            graph,
            profile_id="pag.no_selection.finite_member_sensitivity",
            profile_revision="1",
            budget=PAGMemberBudget(
                max_proposals=4,
                max_members=4,
                max_oracle_operations=4,
                max_elapsed_seconds=30.0,
                max_output_bytes=262144,
            ),
        )


def _binding(
    graph: CausalGraphModel, source: ContextProfile, target: ContextProfile
) -> TransportabilityCandidateInputBindingV1:
    graph_ref = CausalGraphModelRef(
        artifact_id="sha256:" + "1" * 64, manifest_profile_sha256=_PROFILE
    )
    refs = tuple(
        InputRef(
            artifact_id=artifact_id,
            role=role,
            manifest_profile_sha256=_PROFILE,
        )
        for artifact_id, role in (
            ("sha256:" + "2" * 64, "transportability_attempt_basis"),
            ("sha256:" + "3" * 64, "transportability_workflow_spec"),
            ("sha256:" + "4" * 64, "transportability_input_state"),
            (graph_ref.artifact_id, "selected_causal_graph"),
            ("sha256:" + "5" * 64, "causal_effect_report"),
        )
    )
    treatment, outcome = "consumption_response", "gdp_growth"
    query_sha = transportability_candidate_query_sha256(treatment, outcome)
    base = {
        "graph_ref": graph_ref.model_dump(mode="json"),
        "graph_type": graph.graph_type.value,
        "graph_sha256": graph_content_sha256(graph),
        "query_treatment": treatment,
        "query_outcome": outcome,
        "query_sha256": query_sha,
        "source_context_id": source.context_id,
        "source_context_sha256": _sha(source.model_dump(mode="json")),
        "target_context_id": target.context_id,
        "target_context_sha256": _sha(target.model_dump(mode="json")),
        "profile_id": "pag.no_selection.finite_member_sensitivity",
        "profile_revision": "1",
    }
    relation = {
        "relation_id": "transportability.pag.no_selection.member_selection_diagrams",
        "revision": "1",
        **base,
    }
    return TransportabilityCandidateInputBindingV1(
        graph_ref=graph_ref,
        graph_type=graph.graph_type,
        graph_sha256=base["graph_sha256"],
        model_plan_relation=TransportabilityCandidateModelPlanRelationV1(
            relation_id=relation["relation_id"],
            revision=relation["revision"],
            content_sha256=_sha(relation),
        ),
        query_treatment=treatment,
        query_outcome=outcome,
        query_sha256=query_sha,
        source_context_id=source.context_id,
        source_context_sha256=base["source_context_sha256"],
        target_context_id=target.context_id,
        target_context_sha256=base["target_context_sha256"],
        lineage_refs=refs,
    )


def _contexts() -> tuple[ContextProfile, ContextProfile]:
    return (
        ContextProfile(context_id="source", income_level=IncomeLevel.HIGH),
        ContextProfile(context_id="target", income_level=IncomeLevel.LOW),
    )


_CandidateCase = tuple[
    CausalGraphModel,
    ContextProfile,
    ContextProfile,
    PAGMemberFamilyResult,
    TransportabilityCandidateInputBindingV1,
]


@pytest.fixture(scope="module")
def candidate_case() -> _CandidateCase:
    graph = _pag()
    source, target = _contexts()
    family = _family(graph)
    inputs = _binding(graph, source, target)
    return graph, source, target, family, inputs


def _evaluate(
    family: PAGMemberFamilyResult,
    member: PAGAdmittedMember,
    graph: CausalGraphModel,
    source: ContextProfile,
    target: ContextProfile,
    inputs: TransportabilityCandidateInputBindingV1,
    *,
    ref_profile: str | None = _PROFILE,
) -> TransportabilityCandidateMemberEvaluationV1:
    ref = CausalGraphModelRef(
        artifact_id="sha256:" + member.member_sha256,
        manifest_profile_sha256=ref_profile,
    )
    return engine.evaluate_pag_member_candidate(
        family=family,
        member=member,
        source_graph=graph,
        source_context=source,
        target_context=target,
        selection_diagram=build_selection_diagram(source, target, member.graph),
        member_graph_ref=ref,
        persisted_member_graph=member.graph,
        inputs=inputs,
        solver_mode="simplified",
        allow_degraded_transport=False,
        capability_contract=build_causal_capability_contract(),
    )


def test_admitted_g06_members_keep_exact_source_law_formulas(
    candidate_case: _CandidateCase,
) -> None:
    graph, source, target, family, inputs = candidate_case

    assert family.status is PAGMemberFamilyStatus.COMPLETED
    assert family.coverage is PAGMemberFamilyCoverage.FINITE_ENDPOINT_ASSIGNMENT_SPACE_COMPLETE
    with patch.object(
        engine,
        "solve_transportability",
        wraps=engine.solve_transportability,
    ) as solver_spy:
        rows = [
            _evaluate(family, member, graph, source, target, inputs) for member in family.members
        ]
    diagrams = [call.kwargs["selection_diagram"] for call in solver_spy.call_args_list]

    assert graph.edges[0].mark_src is EdgeMark.CIRCLE
    assert graph.edges[0].mark_dst is EdgeMark.CIRCLE
    assert len(diagrams) == len(rows) == len(family.members) == 3
    assert all(
        diagram.base_graph.graph_type in {GraphType.DAG, GraphType.ADMG} for diagram in diagrams
    )
    assert all(
        {node.target_variable for node in diagram.s_nodes} == {"consumption_response"}
        for diagram in diagrams
    )
    assert all(
        {node.context_dimension for node in diagram.s_nodes} == {"income_level"}
        for diagram in diagrams
    )
    assert all(row.disposition == "completed" and row.outcome is not None for row in rows)
    assert all(row.outcome.status is TransportabilityStatus.IDENTIFIED for row in rows)
    assert all(row.outcome.transport_mode is TransportMode.TRANSPORT_FORMULA for row in rows)
    assert all(row.outcome.transport_formula is not None for row in rows)
    assert all(
        row.outcome.transport_formula.adjustment_type == "s_admissibility_source_law"
        and not row.outcome.transport_formula.target_quantities
        and not row.outcome.result.required_target_data
        for row in rows
    )
    assert {row.outcome.result.source_context_id for row in rows} == {source.context_id}
    assert {row.outcome.result.target_context_id for row in rows} == {target.context_id}
    assert {row.outcome.result.query for row in rows} == {"P*(gdp_growth|do(consumption_response))"}

    for member, row in zip(family.members, rows, strict=True):
        assert row.outcome is not None
        ast = EstimandAST.model_validate(row.outcome.result.estimand_ast)
        refs = ast.collect_distribution_refs()
        assert refs
        assert all(ref.domain is DistributionDomain.SOURCE for ref in refs)
        assert all(not ref.intervention_set for ref in refs)
        edge = member.graph.edges[0]
        forward_query_edge = (
            edge.src == "consumption_response"
            and edge.dst == "gdp_growth"
            and edge.mark_src is EdgeMark.TAIL
            and edge.mark_dst is EdgeMark.ARROW
        )
        if forward_query_edge:
            assert all(
                ref.variables == ("gdp_growth",) and ref.conditioning == ("consumption_response",)
                for ref in refs
            )
        else:
            assert all(ref.variables == ("gdp_growth",) and not ref.conditioning for ref in refs)
        assert all(
            quantity.startswith("P_s(")
            for quantity in row.outcome.transport_formula.source_quantities
        )
        assert "P_s(" in row.outcome.transport_formula.formula_str

    bidirected_diagram = next(
        diagram for diagram in diagrams if diagram.base_graph.graph_type is GraphType.ADMG
    )
    bidirected_edge = bidirected_diagram.base_graph.edges[0]
    assert bidirected_edge.mark_src is EdgeMark.ARROW
    assert bidirected_edge.mark_dst is EdgeMark.ARROW


def test_native_fci_producer_routes_all_three_g06_members_through_solver() -> None:
    graph = _pag()
    source, target = _contexts()
    family = evaluate_pag_member_family(
        graph,
        profile_id="pag.no_selection.finite_member_sensitivity",
        profile_revision="1",
        budget=PAGMemberBudget(
            max_proposals=4,
            max_members=4,
            max_oracle_operations=3,
            max_elapsed_seconds=20.0,
            max_output_bytes=262144,
        ),
    )

    assert family.status is PAGMemberFamilyStatus.COMPLETED
    assert family.coverage is PAGMemberFamilyCoverage.FINITE_ENDPOINT_ASSIGNMENT_SPACE_COMPLETE
    assert family.counts.proposals_attempted == 4
    assert family.counts.unattempted_proposals == "0"
    assert family.counts.admitted == len(family.members) == 3
    assert family.counts.oracle_operations == 3
    assert family.counts.validation_incomplete == 0
    assert family.backend_identity is not None
    assert family.backend_identity.backend_id == "causal-learn.FCI.fci+d_separation"
    assert family.backend_identity.backend_version == "0.1.4.4"
    assert family.backend_identity.fci_source_sha256 == (
        "8f0f14f9d31847efa30fa056a162f1f9d21d07595880c1ad2b099ec11e544ead"
    )
    assert family.backend_identity.cit_source_sha256 == (
        "0d3db11083985b7cb0edbaa44662307c28f27bc135053a65751cd52f451ddc8f"
    )

    inputs = _binding(graph, source, target)
    with patch.object(
        engine,
        "solve_transportability",
        wraps=engine.solve_transportability,
    ) as solver_spy:
        rows = [
            _evaluate(family, member, graph, source, target, inputs) for member in family.members
        ]

    assert solver_spy.call_count == 3
    diagrams = [call.kwargs["selection_diagram"] for call in solver_spy.call_args_list]
    assert all(
        {node.target_variable for node in diagram.s_nodes} == {"consumption_response"}
        and {node.context_dimension for node in diagram.s_nodes} == {"income_level"}
        for diagram in diagrams
    )
    assert all(
        row.disposition == "completed"
        and row.outcome is not None
        and row.outcome.status is TransportabilityStatus.IDENTIFIED
        and row.outcome.transport_mode is TransportMode.TRANSPORT_FORMULA
        and row.outcome.transport_formula is not None
        and row.outcome.transport_formula.adjustment_type == "s_admissibility_source_law"
        and not row.outcome.transport_formula.target_quantities
        and not row.outcome.result.required_target_data
        for row in rows
    )

    for member, row in zip(family.members, rows, strict=True):
        assert row.outcome is not None
        assert row.outcome.transport_formula is not None
        ast = EstimandAST.model_validate(row.outcome.result.estimand_ast)
        refs = ast.collect_distribution_refs()
        assert refs
        assert all(
            ref.domain is DistributionDomain.SOURCE and not ref.intervention_set for ref in refs
        )
        edge = member.graph.edges[0]
        forward_query_edge = (
            edge.src == "consumption_response"
            and edge.dst == "gdp_growth"
            and edge.mark_src is EdgeMark.TAIL
            and edge.mark_dst is EdgeMark.ARROW
        )
        expected_conditioning = ("consumption_response",) if forward_query_edge else ()
        assert all(
            ref.variables == ("gdp_growth",) and ref.conditioning == expected_conditioning
            for ref in refs
        )
        assert all(
            quantity.startswith("P_s(")
            for quantity in row.outcome.transport_formula.source_quantities
        )


def test_bidirected_member_preserves_marks_through_do_surgery_and_source_id(
    candidate_case: _CandidateCase,
) -> None:
    graph, source, target, family, inputs = candidate_case
    member = next(row for row in family.members if row.graph.graph_type is GraphType.ADMG)

    from polisyos.foundry.methods.catalog.causal import admg_ops
    from polisyos.foundry.methods.catalog.causal.id_engine import core as id_core

    original_do = admg_ops.do_operator
    surgery: list[tuple[CausalGraphModel, CausalGraphModel]] = []

    def capture_surgery(
        candidate_graph: CausalGraphModel,
        intervention_set: frozenset[str],
    ) -> CausalGraphModel:
        mutilated = original_do(candidate_graph, intervention_set)
        surgery.append((candidate_graph, mutilated))
        return mutilated

    with (
        patch.object(admg_ops, "do_operator", side_effect=capture_surgery),
        patch.object(id_core, "id_algorithm", wraps=id_core.id_algorithm) as id_spy,
        patch.object(
            engine,
            "_run_simplified_legacy",
            side_effect=AssertionError(
                "ADMG selection member reached endpoint-insensitive fallback"
            ),
        ),
    ):
        row = _evaluate(family, member, graph, source, target, inputs)

    assert row.disposition == "completed"
    assert row.outcome is not None
    assert row.outcome.status is TransportabilityStatus.IDENTIFIED
    assert surgery
    input_edge = surgery[0][0].edges[0]
    assert input_edge.mark_src is EdgeMark.ARROW
    assert input_edge.mark_dst is EdgeMark.ARROW
    assert input_edge.src == "consumption_response"
    assert input_edge.dst == "gdp_growth"
    assert not any(
        edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW
        for edge in surgery[0][1].edges
    )
    id_graphs = [call.kwargs["graph"] for call in id_spy.call_args_list if "graph" in call.kwargs]
    assert any(
        graph.graph_type is GraphType.ADMG
        and any(
            edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW
            for edge in graph.edges
        )
        for graph in id_graphs
    )


def test_nontrivial_s_admissibility_sibling_uses_source_id() -> None:
    source = ContextProfile(context_id="source")
    target = ContextProfile(context_id="target")
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["policy", "mediator", "outcome"],
        edges=[
            CausalEdge(src="policy", dst="mediator"),
            CausalEdge(src="mediator", dst="outcome"),
        ],
    )
    diagram = (
        SelectionDiagramBuilder(graph)
        .add_sigma_variable("policy", context_dimension="income_level")
        .build(source, target)
    )

    result = engine.solve_transportability(
        selection_diagram=diagram,
        query_treatment="policy",
        query_outcome="outcome",
        solver_mode="simplified",
        capability_contract=build_causal_capability_contract(),
    )

    assert result.status is TransportabilityStatus.IDENTIFIED
    assert result.transport_mode is TransportMode.TRANSPORT_FORMULA
    assert result.transport_formula is not None
    assert result.transport_formula.adjustment_type == "s_admissibility_source_law"
    assert result.transport_formula.source_quantities
    assert not result.transport_formula.target_quantities
    ast = EstimandAST.model_validate(result.estimand_ast)
    refs = ast.collect_distribution_refs()
    assert all(ref.domain is DistributionDomain.SOURCE for ref in refs)
    assert {(ref.variables, ref.conditioning) for ref in refs} == {
        (("mediator",), ("policy",)),
        (("outcome",), ("mediator",)),
    }


def test_non_s_admissible_mediator_dag_retains_existing_transport_formula() -> None:
    source = ContextProfile(context_id="source", institutional_quality=0.9)
    target = ContextProfile(context_id="target", institutional_quality=0.2)
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["policy", "tax_compliance", "gdp_growth"],
        edges=[
            CausalEdge(src="policy", dst="tax_compliance"),
            CausalEdge(src="tax_compliance", dst="gdp_growth"),
        ],
    )
    diagram = engine.build_selection_diagram(source, target, graph)
    assert {node.target_variable for node in diagram.s_nodes} == {"tax_compliance"}

    result = engine.solve_transportability(
        selection_diagram=diagram,
        query_treatment="policy",
        query_outcome="gdp_growth",
        solver_mode="simplified",
        capability_contract=build_causal_capability_contract(),
    )

    assert result.status is TransportabilityStatus.IDENTIFIED
    assert result.transport_formula is not None
    assert result.transport_formula.target_quantities
    assert result.required_target_data == result.transport_formula.target_quantities
    assert result.identification_engine == "simplified_legacy"


def test_selected_outcome_is_not_reused_as_a_covariate() -> None:
    source = ContextProfile(context_id="source")
    target = ContextProfile(context_id="target")
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    diagram = SelectionDiagramBuilder(graph).add_sigma_variable("Y").build(source, target)

    result = engine.solve_transportability(
        selection_diagram=diagram,
        query_treatment="X",
        query_outcome="Y",
        solver_mode="simplified",
        capability_contract=build_causal_capability_contract(),
    )

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "query_variable_is_selection_target"


def test_direct_scalar_pag_admission_gate_is_unchanged() -> None:
    source, target = _contexts()
    graph = _pag()
    diagram = build_selection_diagram(source, target, graph)

    result = engine.solve_transportability(
        selection_diagram=diagram,
        query_treatment="consumption_response",
        query_outcome="gdp_growth",
        solver_mode="simplified",
        capability_contract=build_causal_capability_contract(),
    )

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.transport_mode.value == "none"
    assert result.unsupported_reason == "partial_graph_completion_semantics_not_established"


def test_admg_hedge_after_s_admissibility_refuses_without_legacy_fallback() -> None:
    source = ContextProfile(context_id="source")
    target = ContextProfile(context_id="target")
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(src="X", dst="Y"),
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.ARROW,
                mark_dst=EdgeMark.ARROW,
            ),
        ],
    )
    diagram = SelectionDiagramBuilder(graph).add_sigma_variable("X").build(source, target)

    with patch.object(
        engine,
        "_run_simplified_legacy",
        side_effect=AssertionError("ADMG selection input reached endpoint-insensitive fallback"),
    ):
        result = engine.solve_transportability(
            selection_diagram=diagram,
            query_treatment="X",
            query_outcome="Y",
            solver_mode="simplified",
            capability_contract=build_causal_capability_contract(),
        )

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.unsupported_reason == "s_admissible_source_effect_not_identified:hedge_found"


def test_solver_removal_yields_error_even_when_candidate_dtos_remain(
    monkeypatch: pytest.MonkeyPatch,
    candidate_case: _CandidateCase,
) -> None:
    graph, source, target, family, inputs = candidate_case
    member = next(row for row in family.members if row.graph.graph_type is GraphType.DAG)

    monkeypatch.setattr(engine, "solve_transportability", None)
    row = _evaluate(family, member, graph, source, target, inputs)

    assert row.disposition == "error"
    assert row.outcome is None
    assert row.reason is not None
    assert row.reason.code == "candidate_member_solver_error"


def test_changed_diagram_query_or_graph_kind_fails_closed(
    candidate_case: _CandidateCase,
) -> None:
    graph, source, target, family, inputs = candidate_case
    member = family.members[0]
    args = {
        "family": family,
        "member": member,
        "source_graph": graph,
        "source_context": source,
        "target_context": target,
        "member_graph_ref": CausalGraphModelRef(
            artifact_id="sha256:" + member.member_sha256,
            manifest_profile_sha256=_PROFILE,
        ),
        "persisted_member_graph": member.graph,
        "inputs": inputs,
        "solver_mode": "simplified",
        "allow_degraded_transport": False,
        "capability_contract": build_causal_capability_contract(),
    }

    altered = build_selection_diagram(source, target, member.graph).model_copy(
        update={"s_nodes": []}
    )
    with pytest.raises(engine.TransportCandidateMemberBindingError) as exc:
        engine.evaluate_pag_member_candidate(**args, selection_diagram=altered)
    assert exc.value.reason_code == "candidate_member_selection_diagram_mismatch"

    with pytest.raises(engine.TransportCandidateMemberBindingError):
        engine.evaluate_pag_member_candidate(
            **{**args, "inputs": inputs.model_copy(update={"query_outcome": "not-bound"})},
            selection_diagram=build_selection_diagram(source, target, member.graph),
        )

    with pytest.raises(engine.TransportCandidateMemberBindingError) as exc:
        engine.evaluate_pag_member_candidate(
            **{
                **args,
                "persisted_member_graph": member.graph.model_copy(
                    update={"graph_type": GraphType.PAG}
                ),
            },
            selection_diagram=build_selection_diagram(source, target, member.graph),
        )
    assert exc.value.reason_code == "candidate_member_graph_content_mismatch"


def test_incomplete_family_cannot_evaluate_a_member(
    candidate_case: _CandidateCase,
) -> None:
    graph, source, target, family, inputs = candidate_case
    member = family.members[0]
    incomplete = family.model_copy(
        update={
            "status": PAGMemberFamilyStatus.BUDGET_EXHAUSTED,
            "coverage": PAGMemberFamilyCoverage.NOT_ESTABLISHED,
        }
    )

    with pytest.raises(engine.TransportCandidateMemberBindingError) as exc:
        _evaluate(incomplete, member, graph, source, target, inputs)
    assert exc.value.reason_code == "candidate_member_family_not_complete"


def test_missing_selected_member_profile_is_typed_refusal(
    candidate_case: _CandidateCase,
) -> None:
    graph, source, target, family, inputs = candidate_case
    member = family.members[0]

    with pytest.raises(engine.TransportCandidateMemberBindingError) as exc:
        _evaluate(family, member, graph, source, target, inputs, ref_profile=None)
    assert exc.value.reason_code == "candidate_member_selected_profile_missing"
