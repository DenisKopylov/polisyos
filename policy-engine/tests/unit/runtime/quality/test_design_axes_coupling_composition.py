from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.pdc import AxisFirewallStatus, AxisPositionDeclaration
from polisyos.runtime.quality.design_axes.coupling_composition import (
    BoundaryCouplingClassification,
    CompositionReceipt,
    ComputationalTractabilityBudget,
    CouplingEdge,
    CouplingGraph,
    CouplingRegimeClassification,
    DecompositionResult,
    DesignInterfaceContract,
    ForecastSupportScope,
    P17BoundarySpoofError,
    P17FalseModularityError,
    P17SyntacticCompositionError,
    P17SystemDynamicsRequiredError,
    RecursiveDesignGraph,
    SystemDynamicsRequirement,
    assert_composition_laws_hold,
    build_composition_receipt,
    build_computational_tractability_budget,
    build_coupling_graph,
    build_system_dynamics_requirement,
    build_system_effect_support,
    classify_coupling,
    composition_to_axis_positions,
    coupling_accuracy,
    critical_path_regime,
    decompose_design,
    derive_recursive_design_graph,
    discover_design_modules,
)

RULE_REF = "repo://docs/adr/0174-policy-evidence-capability-graph.md"


def _modules() -> tuple[str, str, str]:
    return (
        "module://eligibility",
        "module://delivery",
        "module://finance",
    )


def _modular_graph() -> CouplingGraph:
    return build_coupling_graph(
        design_ref="pdc://layer2/s5/modular/design",
        module_refs=_modules(),
        module_discovery_ref="pdc://layer2/s5/module-discovery/modular",
        interaction_edges=(),
        rule_version_ref=RULE_REF,
    )


def _near_decomposable_graph() -> CouplingGraph:
    return build_coupling_graph(
        design_ref="pdc://layer2/s5/near/design",
        module_refs=_modules(),
        module_discovery_ref="pdc://layer2/s5/module-discovery/near",
        interaction_edges=(
            CouplingEdge(
                boundary_ref="boundary://near/eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="implementation_dependency",
                interaction_strength="weak",
                feedback_intensity="weak",
                feedback=False,
                evidence_ref="fixture://s5/near/edge-1",
            ),
        ),
        rule_version_ref=RULE_REF,
    )


def _entangled_graph() -> CouplingGraph:
    return build_coupling_graph(
        design_ref="pdc://layer2/s5/entangled/design",
        module_refs=_modules(),
        module_discovery_ref="pdc://layer2/s5/module-discovery/entangled",
        interaction_edges=(
            CouplingEdge(
                boundary_ref="boundary://entangled/eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="gaming_feedback",
                interaction_strength="strong",
                feedback_intensity="high",
                feedback=True,
                evidence_ref="fixture://s5/entangled/edge-1",
            ),
            CouplingEdge(
                boundary_ref="boundary://entangled/delivery-finance",
                source_module_ref="module://delivery",
                target_module_ref="module://finance",
                relation="budget_feedback",
                interaction_strength="strong",
                feedback_intensity="high",
                feedback=True,
                evidence_ref="fixture://s5/entangled/edge-2",
            ),
            CouplingEdge(
                boundary_ref="boundary://entangled/finance-eligibility",
                source_module_ref="module://finance",
                target_module_ref="module://eligibility",
                relation="political_feedback",
                interaction_strength="strong",
                feedback_intensity="high",
                feedback=True,
                evidence_ref="fixture://s5/entangled/edge-3",
            ),
        ),
        rule_version_ref=RULE_REF,
    )


def _hierarchical_graph() -> CouplingGraph:
    return build_coupling_graph(
        design_ref="pdc://layer2/s5/hierarchical/design",
        module_refs=_modules(),
        module_discovery_ref="pdc://layer2/s5/module-discovery/hierarchical",
        interaction_edges=(
            CouplingEdge(
                boundary_ref="boundary://hierarchical/eligibility-delivery",
                source_module_ref="module://eligibility",
                target_module_ref="module://delivery",
                relation="eligibility_drives_delivery_load",
                interaction_strength="strong",
                feedback_intensity="weak",
                feedback=False,
                evidence_ref="fixture://s5/hierarchical/edge-1",
            ),
            CouplingEdge(
                boundary_ref="boundary://hierarchical/delivery-finance",
                source_module_ref="module://delivery",
                target_module_ref="module://finance",
                relation="delivery_drives_budget_drawdown",
                interaction_strength="strong",
                feedback_intensity="weak",
                feedback=False,
                evidence_ref="fixture://s5/hierarchical/edge-2",
            ),
        ),
        rule_version_ref=RULE_REF,
    )


def test_s5_artifacts_are_strict() -> None:
    with pytest.raises(ValidationError):
        CouplingGraph(
            graph_id="layer2.s5.graph.strict",
            graph_ref="pdc://layer2/s5/strict/graph",
            design_ref="pdc://layer2/s5/strict/design",
            module_refs=list(_modules()),
            interaction_edges=[],
            evidence_state="observed",
            rule_version_ref=RULE_REF,
            unexpected="blocked",
        )


def test_modular_graph_can_compose_only_with_coupling_proof() -> None:
    graph = _modular_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )
    receipt = build_composition_receipt(decomposition)

    assert isinstance(classification, CouplingRegimeClassification)
    assert isinstance(receipt, CompositionReceipt)
    assert classification.coupling_regime == "modular"
    assert decomposition.composition_disposition == "compose"
    assert receipt.authority_mode == "critical_path_only"
    assert receipt.whole_design_authority == "shadow_governed_only"


def test_near_decomposable_composes_with_residual_risk_limitation() -> None:
    graph = _near_decomposable_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )
    receipt = build_composition_receipt(decomposition)

    assert classification.coupling_regime == "near_decomposable"
    assert decomposition.composition_disposition == "compose_with_limitations"
    assert receipt.residual_interaction_risk == "medium"
    assert "residual_interaction_risk" in receipt.authority_boundary.may_not_use_for


def test_false_modular_probe_fails_p17() -> None:
    with pytest.raises(P17FalseModularityError, match="strong cyclic cross-effects"):
        classify_coupling(_entangled_graph(), declared_coupling_regime="modular")


def test_absent_coupling_graph_defaults_to_more_coupling() -> None:
    classification = classify_coupling(
        None,
        design_ref="pdc://layer2/s5/absent/design",
        module_refs=list(_modules()),
        rule_version_ref=RULE_REF,
    )

    assert classification.coupling_regime == "entangled"
    assert classification.firewall_disposition == "block"
    assert classification.defaulted_to_more_coupling is True


def test_syntactic_decomposition_without_coupling_proof_cannot_compose() -> None:
    graph = _modular_graph()
    classification = classify_coupling(graph)
    decomposition = DecompositionResult(
        decomposition_id="layer2.s5.decomposition.syntax",
        decomposition_ref="pdc://layer2/s5/syntax/decomposition",
        design_ref=graph.design_ref,
        coupling_graph_ref=None,
        coupling_classification_ref=classification.classification_ref,
        module_refs=list(_modules()),
        critical_path_module_refs=list(_modules()),
        interface_refs=[],
        composition_disposition="compose",
        residual_interaction_risk="low",
        dynamics_requirement_ref=None,
        rule_version_ref=RULE_REF,
    )

    with pytest.raises(P17SyntacticCompositionError, match="coupling graph"):
        build_composition_receipt(decomposition)


def test_entangled_design_requires_system_dynamics_before_system_effect_claim() -> None:
    graph = _entangled_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )

    assert classification.coupling_regime == "entangled"
    assert classification.feedback_intensity == "high"
    assert decomposition.composition_disposition == "system_evidence_required"
    with pytest.raises(P17SystemDynamicsRequiredError, match="system dynamics"):
        build_composition_receipt(decomposition, system_effect_claim_requested=True)

    dynamics = build_system_dynamics_requirement(decomposition)
    assert isinstance(dynamics, SystemDynamicsRequirement)
    assert dynamics.requirement_level in {"system_dynamics_required", "simulation_only_contested"}


def test_hierarchically_coupled_designs_propagate_upstream_constraints() -> None:
    graph = _hierarchical_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )
    receipt = build_composition_receipt(decomposition)

    assert classification.coupling_regime == "hierarchically_coupled"
    assert decomposition.composition_disposition == "compose_with_limitations"
    assert receipt.propagated_limitation_refs
    assert receipt.authority_mode == "critical_path_only"


def test_user_supplied_module_split_is_candidate_not_boundary_proof() -> None:
    discovered = discover_design_modules(
        design_ref="pdc://layer2/s5/boundary-spoof/design",
        candidate_module_refs=[
            "module://politically-convenient-front-office",
            "module://politically-convenient-back-office",
        ],
        case_signal_refs=["fixture://s5/boundary_spoof/case-signals"],
        rule_version_ref=RULE_REF,
    )

    graph = build_coupling_graph(
        design_ref="pdc://layer2/s5/boundary-spoof/design",
        module_refs=discovered.discovered_module_refs,
        module_discovery_ref=discovered.module_discovery_ref,
        interaction_edges=_entangled_graph().interaction_edges,
        rule_version_ref=RULE_REF,
    )

    assert discovered.user_supplied_module_refs != discovered.discovered_module_refs
    assert classify_coupling(graph).coupling_regime == "entangled"

    with pytest.raises(P17BoundarySpoofError, match="candidate module split"):
        discover_design_modules(
            design_ref="pdc://layer2/s5/boundary-spoof/design",
            candidate_module_refs=[
                "module://politically-convenient-front-office",
                "module://politically-convenient-back-office",
            ],
            case_signal_refs=[],
            treat_candidate_as_proof=True,
            rule_version_ref=RULE_REF,
        )


def test_boundary_specific_classification_records_each_interface() -> None:
    graph = _hierarchical_graph()
    classification = classify_coupling(graph)

    assert classification.boundary_classifications
    assert all(
        isinstance(row, BoundaryCouplingClassification)
        for row in classification.boundary_classifications
    )
    assert {
        (row.source_module_ref, row.target_module_ref)
        for row in classification.boundary_classifications
    } == {
        ("module://eligibility", "module://delivery"),
        ("module://delivery", "module://finance"),
    }
    assert {row.coupling_regime for row in classification.boundary_classifications} == {
        "hierarchically_coupled"
    }


def test_composition_laws_identity_regrouping_interface_and_monotonicity() -> None:
    graph = _near_decomposable_graph()
    recursive = derive_recursive_design_graph(
        design_ref=graph.design_ref,
        module_refs=graph.module_refs,
        parent_child_edges=[(graph.design_ref, module_ref) for module_ref in graph.module_refs],
        rule_version_ref=RULE_REF,
    )
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=["module://eligibility", "module://delivery"],
    )
    receipt = build_composition_receipt(decomposition)

    result = assert_composition_laws_hold(
        recursive_graph=recursive,
        coupling_graph=graph,
        decomposition=decomposition,
        receipt=receipt,
    )

    assert result.identity_noop is True
    assert result.associativity_regrouping_invariant is True
    assert result.typed_interface_compatible is True
    assert result.critical_path_monotonic is True


def test_system_effect_support_reuses_forecast_support_dictionary() -> None:
    scope = build_system_effect_support(
        base_origin="simulation_only",
        claim_scope="system_effect",
        support_ref="pdc://layer2/s5/support/simulation-only-system-effect",
        rule_version_ref=RULE_REF,
    )

    assert isinstance(scope, ForecastSupportScope)
    assert scope.base_origin == "simulation_only"
    assert scope.claim_scope == "system_effect"
    assert scope.support_label == "simulation_only_system_effect"
    assert "calibrated_forecast_authority" in scope.authority_boundary.may_not_use_for


def test_computational_tractability_budget_is_consumed_by_receipt() -> None:
    graph = _entangled_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )
    budget = build_computational_tractability_budget(
        design_ref=graph.design_ref,
        search_space_size="large",
        approximation_mode="anytime_cutoff",
        cutoff_reason="feedback graph too large for exhaustive composition search",
        rule_version_ref=RULE_REF,
    )
    dynamics = build_system_dynamics_requirement(decomposition)
    receipt = build_composition_receipt(
        decomposition,
        dynamics_requirement=dynamics,
        tractability_budget=budget,
    )

    assert isinstance(budget, ComputationalTractabilityBudget)
    assert receipt.tractability_budget_ref == budget.budget_ref
    assert receipt.whole_design_authority != "production"


def test_critical_path_regime_is_not_average_or_min_over_all_modules() -> None:
    module_regimes = {
        "module://eligibility": "risk",
        "module://delivery": "uncertainty",
        "module://finance": "ignorance",
        "module://peripheral": "risk",
    }

    assert (
        critical_path_regime(
            module_regimes=module_regimes,
            critical_path_module_refs=["module://eligibility", "module://delivery"],
        )
        == "uncertainty"
    )
    assert (
        critical_path_regime(
            module_regimes=module_regimes,
            critical_path_module_refs=["module://eligibility", "module://finance"],
        )
        == "ignorance"
    )


def test_coupling_accuracy_penalizes_false_modular_more_than_false_entangled() -> None:
    false_modular = coupling_accuracy(predicted=["modular"], gold=["entangled"])
    false_entangled = coupling_accuracy(predicted=["entangled"], gold=["modular"])

    assert false_modular["penalized_score"] < false_entangled["penalized_score"]
    assert false_modular["false_modular_count"] == 1
    assert false_modular["false_entangled_count"] == 0
    assert false_entangled["false_modular_count"] == 0
    assert false_entangled["false_entangled_count"] == 1


def test_composition_projects_to_axis_positions_and_firewalls() -> None:
    graph = _near_decomposable_graph()
    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=list(_modules()),
    )
    receipt = build_composition_receipt(decomposition)

    positions, firewalls = composition_to_axis_positions(
        graph=graph,
        classification=classification,
        decomposition=decomposition,
        receipt=receipt,
    )

    assert all(isinstance(position, AxisPositionDeclaration) for position in positions)
    assert all(isinstance(firewall, AxisFirewallStatus) for firewall in firewalls)
    assert {position.cell_ref for position in positions} == {
        "SYSTEM.connectivity_modularity",
        "SYSTEM.dynamics_feedback",
        "INTERVENTION.scale_composition",
    }
    assert {"P17"} <= set().union(*(set(firewall.pattern_ids) for firewall in firewalls))


def test_recursive_design_graph_and_interface_contract_are_replay_visible() -> None:
    graph = _near_decomposable_graph()
    recursive = RecursiveDesignGraph(
        graph_id="layer2.s5.recursive.ua-msme",
        graph_ref="pdc://layer2/s5/ua-msme/recursive-design-graph",
        root_design_ref=graph.design_ref,
        node_refs=[graph.design_ref, *graph.module_refs],
        node_kinds={
            graph.design_ref: "policy_program",
            "module://eligibility": "design_candidate",
            "module://delivery": "design_candidate",
            "module://finance": "design_candidate",
        },
        parent_child_edges=[
            ("pdc://layer2/s5/near/design", "module://eligibility"),
            ("pdc://layer2/s5/near/design", "module://delivery"),
            ("pdc://layer2/s5/near/design", "module://finance"),
        ],
        typed_dependency_edges=[
            {
                "source_ref": "module://eligibility",
                "target_ref": "module://delivery",
                "dependency_type": "implementation_dependency",
                "interface_ref": "pdc://layer2/s5/ua-msme/interface/eligibility-delivery",
            }
        ],
        critical_path_module_refs=["module://eligibility", "module://delivery"],
        interface_refs=["pdc://layer2/s5/ua-msme/interface/eligibility-delivery"],
        rule_version_ref=RULE_REF,
    )
    interface = DesignInterfaceContract(
        interface_id="layer2.s5.interface.delivery-finance",
        interface_ref="pdc://layer2/s5/ua-msme/interface/delivery-finance",
        source_module_ref="module://delivery",
        target_module_ref="module://finance",
        exchanged_claim_refs=["claim://delivery/takeup", "claim://finance/fiscal-burden"],
        authority_boundary=classify_coupling(graph).authority_boundary,
        rule_version_ref=RULE_REF,
    )

    assert recursive.root_design_ref == graph.design_ref
    assert recursive.node_kinds[graph.design_ref] == "policy_program"
    assert recursive.critical_path_module_refs == ["module://eligibility", "module://delivery"]
    assert interface.source_module_ref in graph.module_refs
    assert interface.target_module_ref in graph.module_refs
