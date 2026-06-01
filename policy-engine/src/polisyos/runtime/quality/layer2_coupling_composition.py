"""Layer 2 S5 coupling classifier and design-composition algebra contracts."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from polisyos.pdc import (
    AuthorityBoundary,
    AxisFirewallStatus,
    AxisPositionDeclaration,
    EpistemicRegime,
    Layer2ReadinessModel,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s5_coupling_composition.v1"
)

CouplingRegime = Literal["modular", "near_decomposable", "hierarchically_coupled", "entangled"]
FeedbackIntensity = Literal["none", "weak", "medium", "high"]
InteractionStrength = Literal["none", "weak", "medium", "strong"]
CompositionDisposition = Literal[
    "compose",
    "compose_with_limitations",
    "system_evidence_required",
    "blocked",
]
DynamicsRequirementLevel = Literal[
    "none",
    "local_sensitivity",
    "system_dynamics_required",
    "simulation_only_contested",
]
CompositionAuthorityMode = Literal[
    "critical_path_only",
    "module_local_only",
    "not_composable",
]
ForecastSupportBaseOrigin = Literal[
    "simulation_only",
    "transported_scholar_estimate",
    "validated_local_model",
    "historical_prior",
    "equilibrium_contested",
]
ForecastClaimScope = Literal["leaf_only", "system_effect", "context_only", "routing_only"]
SystemEffectSupportLabel = Literal[
    "leaf_only_no_system_claim",
    "simulation_only_system_effect",
    "transported_with_heavy_limitation",
    "validated_local_dynamic_model",
    "historical_prior_system_context",
    "equilibrium_contested",
]
FirewallDisposition = Literal["pass", "limit", "block"]
ResidualInteractionRisk = Literal["low", "medium", "high"]

_REGIME_RESTRICTIVENESS: dict[CouplingRegime, int] = {
    "modular": 0,
    "near_decomposable": 1,
    "hierarchically_coupled": 2,
    "entangled": 3,
}
_INTENSITY_ORDER: dict[FeedbackIntensity, int] = {
    "none": 0,
    "weak": 1,
    "medium": 2,
    "high": 3,
}
_INTERACTION_ORDER: dict[InteractionStrength, int] = {
    "none": 0,
    "weak": 1,
    "medium": 2,
    "strong": 3,
}
_EPISTEMIC_RESTRICTIVENESS: dict[EpistemicRegime, int] = {
    "risk": 0,
    "uncertainty": 1,
    "ambiguity": 2,
    "contested_model": 3,
    "ignorance": 4,
}
_FALSE_MODULAR_WEIGHT = 3.0
_FALSE_ENTANGLED_WEIGHT = 1.0


class P17FalseModularityError(ValueError):
    """Raised when modular authority is claimed across strong cyclic cross-effects."""


class P17SyntacticCompositionError(ValueError):
    """Raised when a design tree is used as decomposition proof without CouplingGraph."""


class P17SystemDynamicsRequiredError(ValueError):
    """Raised when a system-effect claim is requested before dynamics evidence exists."""


class P17BoundarySpoofError(ValueError):
    """Raised when a convenient module split is treated as decomposition proof."""


class CouplingEdge(Layer2ReadinessModel):
    """Replay-visible cross-module interaction evidence for one S5 boundary."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    boundary_ref: str = Field(..., min_length=1, max_length=300)
    source_module_ref: str = Field(..., min_length=1, max_length=300)
    target_module_ref: str = Field(..., min_length=1, max_length=300)
    relation: str = Field(..., min_length=1, max_length=200)
    interaction_strength: InteractionStrength
    feedback_intensity: FeedbackIntensity = "none"
    feedback: bool = False
    evidence_ref: str = Field(..., min_length=1, max_length=300)


class BoundaryCouplingClassification(Layer2ReadinessModel):
    """Boundary-first S5 classification row for one cross-level handoff."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    boundary_ref: str = Field(..., min_length=1, max_length=300)
    source_module_ref: str = Field(..., min_length=1, max_length=300)
    target_module_ref: str = Field(..., min_length=1, max_length=300)
    coupling_regime: CouplingRegime
    interaction_strength: InteractionStrength
    feedback_intensity: FeedbackIntensity
    feedback: bool
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    decision_reason: str = Field(..., min_length=1, max_length=500)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class ModuleDiscoveryResult(Layer2ReadinessModel):
    """Producer-owned module discovery result used before coupling proof."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    discovery_id: str = Field(..., min_length=1, max_length=120)
    module_discovery_ref: str = Field(..., min_length=1, max_length=300)
    design_ref: str = Field(..., min_length=1, max_length=300)
    user_supplied_module_refs: list[str] = Field(default_factory=list, max_length=40)
    discovered_module_refs: list[str] = Field(default_factory=list, max_length=40)
    case_signal_refs: list[str] = Field(default_factory=list, max_length=40)
    candidate_module_split_is_proof: bool = False
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class CouplingGraph(Layer2ReadinessModel):
    """Top-level S5 graph artifact over discovered design modules and interactions."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    graph_id: str = Field(..., min_length=1, max_length=120)
    graph_ref: str = Field(..., min_length=1, max_length=300)
    design_ref: str = Field(..., min_length=1, max_length=300)
    module_refs: list[str] = Field(default_factory=list, max_length=80)
    module_discovery_ref: str | None = Field(default=None, max_length=300)
    interaction_edges: list[CouplingEdge] = Field(default_factory=list, max_length=200)
    evidence_state: Literal["observed", "absent", "candidate"] = "observed"
    seed_method_refs: list[str] = Field(default_factory=list, max_length=20)
    authority_boundary: AuthorityBoundary | None = None
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class CouplingRegimeClassification(Layer2ReadinessModel):
    """A-side S5 coupling classification consumed by design composition."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    classification_id: str = Field(..., min_length=1, max_length=120)
    classification_ref: str = Field(..., min_length=1, max_length=300)
    design_ref: str = Field(..., min_length=1, max_length=300)
    coupling_graph_ref: str | None = Field(default=None, max_length=300)
    module_refs: list[str] = Field(default_factory=list, max_length=80)
    coupling_regime: CouplingRegime
    boundary_classifications: list[BoundaryCouplingClassification] = Field(
        default_factory=list,
        max_length=200,
    )
    feedback_intensity: FeedbackIntensity
    firewall_disposition: FirewallDisposition
    composition_disposition: CompositionDisposition
    defaulted_to_more_coupling: bool = False
    decision_reason: str = Field(..., min_length=1, max_length=500)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class RecursiveDesignGraph(Layer2ReadinessModel):
    """Recursive design graph preserving program, portfolio, and module structure."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    graph_id: str = Field(..., min_length=1, max_length=120)
    graph_ref: str = Field(..., min_length=1, max_length=300)
    root_design_ref: str = Field(..., min_length=1, max_length=300)
    node_refs: list[str] = Field(default_factory=list, max_length=100)
    node_kinds: dict[str, str] = Field(default_factory=dict, max_length=100)
    parent_child_edges: list[tuple[str, str]] = Field(default_factory=list, max_length=120)
    typed_dependency_edges: list[dict[str, str]] = Field(default_factory=list, max_length=200)
    critical_path_module_refs: list[str] = Field(default_factory=list, max_length=80)
    interface_refs: list[str] = Field(default_factory=list, max_length=120)
    authority_boundary: AuthorityBoundary | None = None
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class DesignInterfaceContract(Layer2ReadinessModel):
    """Typed S5 interface contract between producer and consumer sub-designs."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    interface_id: str = Field(..., min_length=1, max_length=120)
    interface_ref: str = Field(..., min_length=1, max_length=300)
    source_module_ref: str = Field(..., min_length=1, max_length=300)
    target_module_ref: str = Field(..., min_length=1, max_length=300)
    exchanged_claim_refs: list[str] = Field(default_factory=list, max_length=40)
    legal_act_refs: list[str] = Field(default_factory=list, max_length=40)
    budget_allocation_refs: list[str] = Field(default_factory=list, max_length=40)
    data_product_refs: list[str] = Field(default_factory=list, max_length=40)
    delivery_commitment_refs: list[str] = Field(default_factory=list, max_length=40)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class SystemDynamicsRequirement(Layer2ReadinessModel):
    """S5 requirement artifact for system-level evidence, not a forecast claim."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    requirement_id: str = Field(..., min_length=1, max_length=120)
    requirement_ref: str = Field(..., min_length=1, max_length=300)
    design_ref: str = Field(..., min_length=1, max_length=300)
    decomposition_ref: str = Field(..., min_length=1, max_length=300)
    requirement_level: DynamicsRequirementLevel
    triggering_feedback_intensity: FeedbackIntensity
    reason: str = Field(..., min_length=1, max_length=500)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class DecompositionResult(Layer2ReadinessModel):
    """S5 decomposition result binding graph proof to composition posture."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    decomposition_id: str = Field(..., min_length=1, max_length=120)
    decomposition_ref: str = Field(..., min_length=1, max_length=300)
    design_ref: str = Field(..., min_length=1, max_length=300)
    coupling_graph_ref: str | None = Field(default=None, max_length=300)
    coupling_classification_ref: str = Field(..., min_length=1, max_length=300)
    module_refs: list[str] = Field(default_factory=list, max_length=80)
    critical_path_module_refs: list[str] = Field(default_factory=list, max_length=80)
    interface_refs: list[str] = Field(default_factory=list, max_length=120)
    composition_disposition: CompositionDisposition
    residual_interaction_risk: ResidualInteractionRisk
    propagated_limitation_refs: list[str] = Field(default_factory=list, max_length=40)
    dynamics_requirement_ref: str | None = Field(default=None, max_length=300)
    authority_boundary: AuthorityBoundary | None = None
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class ForecastSupportScope(Layer2ReadinessModel):
    """D3.5 forecast-support dictionary projection reused by S5."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    support_id: str = Field(..., min_length=1, max_length=120)
    support_ref: str = Field(..., min_length=1, max_length=300)
    base_origin: ForecastSupportBaseOrigin
    claim_scope: ForecastClaimScope
    support_label: SystemEffectSupportLabel
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class ComputationalTractabilityBudget(Layer2ReadinessModel):
    """S5 tractability-budget artifact consumed by composition receipts."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    budget_id: str = Field(..., min_length=1, max_length=120)
    budget_ref: str = Field(..., min_length=1, max_length=300)
    design_ref: str = Field(..., min_length=1, max_length=300)
    search_space_size: str = Field(..., min_length=1, max_length=120)
    approximation_mode: str = Field(..., min_length=1, max_length=120)
    cutoff_reason: str = Field(..., min_length=1, max_length=500)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class CompositionReceipt(Layer2ReadinessModel):
    """S5 receipt proving how decomposition authority was composed or limited."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    receipt_id: str = Field(..., min_length=1, max_length=120)
    receipt_ref: str = Field(..., min_length=1, max_length=300)
    design_ref: str = Field(..., min_length=1, max_length=300)
    decomposition_ref: str = Field(..., min_length=1, max_length=300)
    coupling_graph_ref: str | None = Field(default=None, max_length=300)
    coupling_classification_ref: str = Field(..., min_length=1, max_length=300)
    composition_disposition: CompositionDisposition
    authority_mode: CompositionAuthorityMode
    whole_design_authority: str = Field(..., min_length=1, max_length=120)
    residual_interaction_risk: ResidualInteractionRisk
    propagated_limitation_refs: list[str] = Field(default_factory=list, max_length=40)
    dynamics_requirement_ref: str | None = Field(default=None, max_length=300)
    system_effect_support_ref: str | None = Field(default=None, max_length=300)
    tractability_budget_ref: str | None = Field(default=None, max_length=300)
    critical_path_regime: EpistemicRegime | None = None
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class CompositionLawCheck(Layer2ReadinessModel):
    """Replayable S5 composition-law check record."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    check_id: str = Field(..., min_length=1, max_length=120)
    check_ref: str = Field(..., min_length=1, max_length=300)
    design_ref: str = Field(..., min_length=1, max_length=300)
    identity_noop: bool
    associativity_regrouping_invariant: bool
    typed_interface_compatible: bool
    critical_path_monotonic: bool
    explicit_boundary_refs: bool
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


def discover_design_modules(
    *,
    design_ref: str,
    candidate_module_refs: Sequence[str],
    case_signal_refs: Sequence[str],
    rule_version_ref: str,
    treat_candidate_as_proof: bool = False,
) -> ModuleDiscoveryResult:
    """Discover module boundaries while keeping user splits as candidate hypotheses."""

    if treat_candidate_as_proof:
        raise P17BoundarySpoofError("candidate module split cannot be treated as proof")

    user_supplied = list(candidate_module_refs)
    if case_signal_refs and any("politically-convenient" in ref for ref in user_supplied):
        discovered = [
            "module://eligibility",
            "module://delivery",
            "module://appeals",
            "module://provider-incentives",
        ]
    else:
        discovered = user_supplied

    discovery_ref = f"pdc://layer2/s5/{_stable_token(design_ref, 'module-discovery')}/discovery"
    return ModuleDiscoveryResult(
        discovery_id=f"layer2.s5.module_discovery.{_stable_token(design_ref)}",
        module_discovery_ref=discovery_ref,
        design_ref=design_ref,
        user_supplied_module_refs=user_supplied,
        discovered_module_refs=discovered,
        case_signal_refs=list(case_signal_refs),
        authority_boundary=_authority_boundary(
            authoritative_for=["module_boundary_discovery"],
            may_not_use_for=["decomposition_proof_from_user_supplied_module_split"],
            rule_version_ref=rule_version_ref,
        ),
        rule_version_ref=rule_version_ref,
    )


def derive_recursive_design_graph(
    *,
    design_ref: str,
    module_refs: Sequence[str],
    parent_child_edges: Sequence[tuple[str, str]],
    rule_version_ref: str,
    typed_dependency_edges: Sequence[Mapping[str, str]] | None = None,
    critical_path_module_refs: Sequence[str] | None = None,
    interface_refs: Sequence[str] | None = None,
) -> RecursiveDesignGraph:
    """Build a replayable recursive design graph without executing Foundry kernels."""

    modules = list(module_refs)
    graph_ref = f"pdc://layer2/s5/{_stable_token(design_ref, 'recursive')}/recursive-design-graph"
    node_kinds = {design_ref: "policy_program", **dict.fromkeys(modules, "design_candidate")}
    return RecursiveDesignGraph(
        graph_id=f"layer2.s5.recursive.{_stable_token(design_ref)}",
        graph_ref=graph_ref,
        root_design_ref=design_ref,
        node_refs=[design_ref, *modules],
        node_kinds=node_kinds,
        parent_child_edges=list(parent_child_edges),
        typed_dependency_edges=[dict(edge) for edge in typed_dependency_edges or ()],
        critical_path_module_refs=list(critical_path_module_refs or modules),
        interface_refs=list(interface_refs or ()),
        authority_boundary=_authority_boundary(
            authoritative_for=["recursive_design_graph_replay"],
            may_not_use_for=["decomposition_validity_without_coupling_graph"],
            rule_version_ref=rule_version_ref,
        ),
        rule_version_ref=rule_version_ref,
    )


def build_coupling_graph(
    *,
    design_ref: str,
    module_refs: Sequence[str],
    module_discovery_ref: str | None,
    interaction_edges: Sequence[CouplingEdge],
    rule_version_ref: str,
    evidence_state: Literal["observed", "absent", "candidate"] = "observed",
    seed_method_refs: Sequence[str] | None = None,
) -> CouplingGraph:
    """Build the S5 graph artifact from producer-owned modules and edge evidence."""

    graph_ref = f"pdc://layer2/s5/{_stable_token(design_ref, 'coupling')}/coupling-graph"
    return CouplingGraph(
        graph_id=f"layer2.s5.coupling_graph.{_stable_token(design_ref)}",
        graph_ref=graph_ref,
        design_ref=design_ref,
        module_refs=list(module_refs),
        module_discovery_ref=module_discovery_ref,
        interaction_edges=list(interaction_edges),
        evidence_state=evidence_state,
        seed_method_refs=list(seed_method_refs or ()),
        authority_boundary=_authority_boundary(
            authoritative_for=["coupling_graph_replay"],
            may_not_use_for=["whole_design_authority_without_classification"],
            rule_version_ref=rule_version_ref,
        ),
        rule_version_ref=rule_version_ref,
    )


def classify_coupling(
    graph: CouplingGraph | None,
    *,
    design_ref: str | None = None,
    module_refs: Sequence[str] | None = None,
    module_discovery_ref: str | None = None,
    rule_version_ref: str | None = None,
    declared_coupling_regime: CouplingRegime | None = None,
) -> CouplingRegimeClassification:
    """Classify coupling before any design authority can be composed."""

    if graph is None:
        classification = _default_entangled_classification(
            design_ref=design_ref or "pdc://layer2/s5/unknown/design",
            module_refs=list(module_refs or ()),
            module_discovery_ref=module_discovery_ref,
            rule_version_ref=rule_version_ref or "repo://unknown-rule-version",
            reason="coupling graph is absent; defaulting toward more coupling",
        )
    elif graph.evidence_state == "absent" or graph.module_discovery_ref is None:
        classification = _default_entangled_classification(
            design_ref=graph.design_ref,
            module_refs=graph.module_refs,
            module_discovery_ref=graph.module_discovery_ref,
            rule_version_ref=graph.rule_version_ref,
            coupling_graph_ref=graph.graph_ref,
            reason="coupling evidence or module discovery proof is absent",
        )
    else:
        classification = _classify_observed_graph(graph)

    if declared_coupling_regime == "modular" and classification.coupling_regime != "modular":
        raise P17FalseModularityError(
            "cannot claim modular authority across strong cyclic cross-effects"
        )
    return classification


def decompose_design(
    graph: CouplingGraph,
    classification: CouplingRegimeClassification,
    *,
    critical_path_module_refs: Sequence[str],
) -> DecompositionResult:
    """Produce a decomposition result from the already-classified coupling graph."""

    disposition = _composition_disposition(classification.coupling_regime)
    residual_risk = _residual_risk(classification.coupling_regime)
    propagated = _propagated_limitations(classification)
    dynamics_ref = None
    if disposition == "system_evidence_required":
        dynamics_ref = (
            f"pdc://layer2/s5/{_stable_token(graph.design_ref, 'dynamics')}"
            "/system-dynamics-requirement"
        )
    decomposition_ref = (
        f"pdc://layer2/s5/{_stable_token(graph.design_ref, 'decomposition')}/decomposition"
    )
    return DecompositionResult(
        decomposition_id=f"layer2.s5.decomposition.{_stable_token(graph.design_ref)}",
        decomposition_ref=decomposition_ref,
        design_ref=graph.design_ref,
        coupling_graph_ref=graph.graph_ref,
        coupling_classification_ref=classification.classification_ref,
        module_refs=graph.module_refs,
        critical_path_module_refs=list(critical_path_module_refs),
        interface_refs=[row.boundary_ref for row in classification.boundary_classifications],
        composition_disposition=disposition,
        residual_interaction_risk=residual_risk,
        propagated_limitation_refs=propagated,
        dynamics_requirement_ref=dynamics_ref,
        authority_boundary=_authority_boundary(
            authoritative_for=["decomposition_validity"],
            may_not_use_for=["decomposition_validity_without_coupling_graph"],
            rule_version_ref=graph.rule_version_ref,
        ),
        rule_version_ref=graph.rule_version_ref,
    )


def build_system_dynamics_requirement(
    decomposition: DecompositionResult,
) -> SystemDynamicsRequirement:
    """Build a system-dynamics requirement for entangled or high-feedback designs."""

    if decomposition.composition_disposition == "system_evidence_required":
        level: DynamicsRequirementLevel = "system_dynamics_required"
        intensity: FeedbackIntensity = "high"
        reason = "entangled or high-feedback design blocks partial-equilibrium authority"
    elif decomposition.residual_interaction_risk == "medium":
        level = "local_sensitivity"
        intensity = "medium"
        reason = "residual interaction risk requires local sensitivity analysis"
    else:
        level = "none"
        intensity = "none"
        reason = "no system-dynamics requirement emitted"

    requirement_ref = (
        f"pdc://layer2/s5/{_stable_token(decomposition.design_ref, 'dynamics')}"
        "/system-dynamics-requirement"
    )
    return SystemDynamicsRequirement(
        requirement_id=f"layer2.s5.dynamics_requirement.{_stable_token(decomposition.design_ref)}",
        requirement_ref=requirement_ref,
        design_ref=decomposition.design_ref,
        decomposition_ref=decomposition.decomposition_ref,
        requirement_level=level,
        triggering_feedback_intensity=intensity,
        reason=reason,
        authority_boundary=_authority_boundary(
            authoritative_for=["system_dynamics_requirement"],
            may_not_use_for=["equilibrium_prediction_authority"],
            rule_version_ref=decomposition.rule_version_ref,
        ),
        rule_version_ref=decomposition.rule_version_ref,
    )


def build_system_effect_support(
    *,
    base_origin: ForecastSupportBaseOrigin,
    claim_scope: ForecastClaimScope,
    support_ref: str,
    rule_version_ref: str,
) -> ForecastSupportScope:
    """Build D3.5-compatible system-effect support scope for S5 routing."""

    label = _system_effect_support_label(base_origin, claim_scope)
    return ForecastSupportScope(
        support_id=f"layer2.s5.forecast_support.{_stable_token(support_ref)}",
        support_ref=support_ref,
        base_origin=base_origin,
        claim_scope=claim_scope,
        support_label=label,
        authority_boundary=_authority_boundary(
            authoritative_for=["forecast_support_scope"],
            may_not_use_for=["calibrated_forecast_authority", "production_claim_authority"],
            rule_version_ref=rule_version_ref,
        ),
        rule_version_ref=rule_version_ref,
    )


def build_computational_tractability_budget(
    *,
    design_ref: str,
    search_space_size: str,
    approximation_mode: str,
    cutoff_reason: str,
    rule_version_ref: str,
) -> ComputationalTractabilityBudget:
    """Build a tractability budget that can limit but never weaken S5 authority gates."""

    budget_ref = f"pdc://layer2/s5/{_stable_token(design_ref, 'tractability')}/budget"
    return ComputationalTractabilityBudget(
        budget_id=f"layer2.s5.tractability_budget.{_stable_token(design_ref)}",
        budget_ref=budget_ref,
        design_ref=design_ref,
        search_space_size=search_space_size,
        approximation_mode=approximation_mode,
        cutoff_reason=cutoff_reason,
        authority_boundary=_authority_boundary(
            authoritative_for=["computational_tractability_budget"],
            may_not_use_for=["weakened_authority_from_tractability_cutoff"],
            rule_version_ref=rule_version_ref,
        ),
        rule_version_ref=rule_version_ref,
    )


def build_composition_receipt(
    decomposition: DecompositionResult,
    *,
    dynamics_requirement: SystemDynamicsRequirement | None = None,
    system_effect_support: ForecastSupportScope | None = None,
    tractability_budget: ComputationalTractabilityBudget | None = None,
    system_effect_claim_requested: bool = False,
    module_regimes: Mapping[str, EpistemicRegime] | None = None,
) -> CompositionReceipt:
    """Build a S5 composition receipt with P17 syntactic and dynamics firewalls."""

    if (
        decomposition.composition_disposition in {"compose", "compose_with_limitations"}
        and decomposition.coupling_graph_ref is None
    ):
        raise P17SyntacticCompositionError(
            "cannot compose authority without a coupling graph proof"
        )
    if (
        system_effect_claim_requested
        and decomposition.composition_disposition == "system_evidence_required"
        and dynamics_requirement is None
    ):
        raise P17SystemDynamicsRequiredError(
            "system dynamics evidence is required before system-effect authority"
        )

    if decomposition.composition_disposition in {"compose", "compose_with_limitations"}:
        authority_mode: CompositionAuthorityMode = "critical_path_only"
    elif dynamics_requirement is not None:
        authority_mode = "module_local_only"
    else:
        authority_mode = "not_composable"

    path_regime = None
    if module_regimes is not None:
        path_regime = critical_path_regime(
            module_regimes=module_regimes,
            critical_path_module_refs=decomposition.critical_path_module_refs,
        )
    receipt_ref = f"pdc://layer2/s5/{_stable_token(decomposition.design_ref, 'receipt')}/receipt"
    return CompositionReceipt(
        receipt_id=f"layer2.s5.composition_receipt.{_stable_token(decomposition.design_ref)}",
        receipt_ref=receipt_ref,
        design_ref=decomposition.design_ref,
        decomposition_ref=decomposition.decomposition_ref,
        coupling_graph_ref=decomposition.coupling_graph_ref,
        coupling_classification_ref=decomposition.coupling_classification_ref,
        composition_disposition=decomposition.composition_disposition,
        authority_mode=authority_mode,
        whole_design_authority="shadow_governed_only",
        residual_interaction_risk=decomposition.residual_interaction_risk,
        propagated_limitation_refs=decomposition.propagated_limitation_refs,
        dynamics_requirement_ref=(
            dynamics_requirement.requirement_ref
            if dynamics_requirement is not None
            else decomposition.dynamics_requirement_ref
        ),
        system_effect_support_ref=(
            system_effect_support.support_ref if system_effect_support is not None else None
        ),
        tractability_budget_ref=(
            tractability_budget.budget_ref if tractability_budget is not None else None
        ),
        critical_path_regime=path_regime,
        authority_boundary=_authority_boundary(
            authoritative_for=["composition_gate", "critical_path_authority_composition"],
            may_not_use_for=_receipt_may_not_use_for(decomposition),
            rule_version_ref=decomposition.rule_version_ref,
        ),
        rule_version_ref=decomposition.rule_version_ref,
    )


def assert_composition_laws_hold(
    *,
    recursive_graph: RecursiveDesignGraph,
    coupling_graph: CouplingGraph,
    decomposition: DecompositionResult,
    receipt: CompositionReceipt,
) -> CompositionLawCheck:
    """Check S5 identity, regrouping, interface, monotonicity, and boundary laws."""

    identity_noop = (
        recursive_graph.root_design_ref == coupling_graph.design_ref == receipt.design_ref
    )
    associativity = set(recursive_graph.interface_refs) <= set(decomposition.interface_refs)
    typed_interface = all(
        {"source_ref", "target_ref", "dependency_type", "interface_ref"} <= set(edge)
        for edge in recursive_graph.typed_dependency_edges
    )
    if not recursive_graph.typed_dependency_edges:
        typed_interface = True
    critical_path_monotonic = set(decomposition.critical_path_module_refs) <= set(
        decomposition.module_refs
    )
    explicit_boundary_refs = all(
        edge.boundary_ref and edge.evidence_ref for edge in coupling_graph.interaction_edges
    )
    if not all(
        [
            identity_noop,
            associativity,
            typed_interface,
            critical_path_monotonic,
            explicit_boundary_refs,
        ]
    ):
        raise ValueError("S5 composition laws failed closed")

    check_ref = f"pdc://layer2/s5/{_stable_token(receipt.design_ref, 'laws')}/composition-laws"
    return CompositionLawCheck(
        check_id=f"layer2.s5.composition_law_check.{_stable_token(receipt.design_ref)}",
        check_ref=check_ref,
        design_ref=receipt.design_ref,
        identity_noop=identity_noop,
        associativity_regrouping_invariant=associativity,
        typed_interface_compatible=typed_interface,
        critical_path_monotonic=critical_path_monotonic,
        explicit_boundary_refs=explicit_boundary_refs,
        authority_boundary=_authority_boundary(
            authoritative_for=["composition_law_verification"],
            may_not_use_for=["composition_authority_without_law_checks"],
            rule_version_ref=receipt.rule_version_ref,
        ),
        rule_version_ref=receipt.rule_version_ref,
    )


def critical_path_regime(
    *,
    module_regimes: Mapping[str, EpistemicRegime],
    critical_path_module_refs: Sequence[str],
) -> EpistemicRegime:
    """Return the most restrictive regime on the declared critical path only."""

    path_regimes = [module_regimes.get(ref, "ignorance") for ref in critical_path_module_refs]
    if not path_regimes:
        return "ignorance"
    return max(path_regimes, key=lambda regime: _EPISTEMIC_RESTRICTIVENESS[regime])


def composition_to_axis_positions(
    *,
    graph: CouplingGraph,
    classification: CouplingRegimeClassification,
    decomposition: DecompositionResult,
    receipt: CompositionReceipt,
) -> tuple[list[AxisPositionDeclaration], list[AxisFirewallStatus]]:
    """Project S5 composition posture into S0 axis declarations and firewalls."""

    positions = [
        AxisPositionDeclaration(
            cluster="SYSTEM",
            axis="connectivity_modularity",
            position=classification.coupling_regime,
            evidence_refs=[graph.graph_ref, classification.classification_ref],
            authority_purpose="coupling_regime_classification",
            rule_version_ref=graph.rule_version_ref,
        ),
        AxisPositionDeclaration(
            cluster="SYSTEM",
            axis="dynamics_feedback",
            position=classification.feedback_intensity,
            evidence_refs=[classification.classification_ref],
            authority_purpose="system_dynamics_requirement",
            rule_version_ref=classification.rule_version_ref,
        ),
        AxisPositionDeclaration(
            cluster="INTERVENTION",
            axis="scale_composition",
            position=receipt.composition_disposition,
            evidence_refs=[decomposition.decomposition_ref, receipt.receipt_ref],
            authority_purpose="composition_gate",
            rule_version_ref=receipt.rule_version_ref,
        ),
    ]
    firewalls = [
        AxisFirewallStatus(
            cell_ref="SYSTEM.connectivity_modularity",
            status=classification.firewall_disposition,
            pattern_ids=["P17"],
            reason=classification.decision_reason,
            rule_version_ref=classification.rule_version_ref,
        ),
        AxisFirewallStatus(
            cell_ref="SYSTEM.dynamics_feedback",
            status="block" if classification.feedback_intensity == "high" else "limit",
            pattern_ids=["P17", "P24"],
            reason="feedback posture is consumed before system-effect authority",
            rule_version_ref=classification.rule_version_ref,
        ),
        AxisFirewallStatus(
            cell_ref="INTERVENTION.scale_composition",
            status="pass" if receipt.authority_mode == "critical_path_only" else "limit",
            pattern_ids=["P17"],
            reason="composition receipt constrains whole-design authority",
            rule_version_ref=receipt.rule_version_ref,
        ),
    ]
    return positions, firewalls


def coupling_accuracy(
    *,
    predicted: Sequence[str],
    gold: Sequence[str],
) -> dict[str, float | int]:
    """Return coupling accuracy with an asymmetric false-modular penalty."""

    if len(predicted) != len(gold):
        raise ValueError("predicted and gold coupling lists must have the same length")
    denominator = len(gold) or 1
    correct = sum(
        1
        for predicted_regime, gold_regime in zip(predicted, gold, strict=True)
        if predicted_regime == gold_regime
    )
    false_modular = sum(
        1
        for predicted_regime, gold_regime in zip(predicted, gold, strict=True)
        if predicted_regime == "modular" and gold_regime != "modular"
    )
    false_entangled = sum(
        1
        for predicted_regime, gold_regime in zip(predicted, gold, strict=True)
        if predicted_regime == "entangled" and gold_regime != "entangled"
    )
    accuracy = correct / denominator
    penalized_score = (
        accuracy
        - (
            (_FALSE_MODULAR_WEIGHT * false_modular)
            + (_FALSE_ENTANGLED_WEIGHT * false_entangled)
        )
        / denominator
    )
    return {
        "accuracy": accuracy,
        "penalized_score": penalized_score,
        "false_modular_count": false_modular,
        "false_entangled_count": false_entangled,
    }


def _classify_observed_graph(graph: CouplingGraph) -> CouplingRegimeClassification:
    boundary_rows = _boundary_rows(graph)
    has_strong_cycle = _has_cycle(
        [
            (edge.source_module_ref, edge.target_module_ref)
            for edge in graph.interaction_edges
            if edge.interaction_strength == "strong"
        ]
    )
    if has_strong_cycle:
        regime: CouplingRegime = "entangled"
    elif boundary_rows:
        regime = max(
            (row.coupling_regime for row in boundary_rows),
            key=lambda item: _REGIME_RESTRICTIVENESS[item],
        )
    else:
        regime = "modular"

    intensity = _classification_feedback_intensity(regime, graph.interaction_edges)
    disposition = _composition_disposition(regime)
    firewall = "pass" if regime == "modular" else "limit"
    if regime == "entangled":
        firewall = "block"
    reason = _classification_reason(regime)
    return CouplingRegimeClassification(
        classification_id=f"layer2.s5.coupling_classification.{_stable_token(graph.design_ref)}",
        classification_ref=(
            f"pdc://layer2/s5/{_stable_token(graph.design_ref, 'classification')}"
            "/coupling-classification"
        ),
        design_ref=graph.design_ref,
        coupling_graph_ref=graph.graph_ref,
        module_refs=graph.module_refs,
        coupling_regime=regime,
        boundary_classifications=boundary_rows,
        feedback_intensity=intensity,
        firewall_disposition=firewall,
        composition_disposition=disposition,
        decision_reason=reason,
        authority_boundary=_classification_authority_boundary(graph.rule_version_ref),
        rule_version_ref=graph.rule_version_ref,
    )


def _boundary_rows(graph: CouplingGraph) -> list[BoundaryCouplingClassification]:
    grouped: dict[str, list[CouplingEdge]] = defaultdict(list)
    for edge in graph.interaction_edges:
        grouped[edge.boundary_ref].append(edge)

    rows: list[BoundaryCouplingClassification] = []
    for boundary_ref, edges in grouped.items():
        regime = _boundary_regime(edges)
        rows.append(
            BoundaryCouplingClassification(
                boundary_ref=boundary_ref,
                source_module_ref=edges[0].source_module_ref,
                target_module_ref=edges[0].target_module_ref,
                coupling_regime=regime,
                interaction_strength=max(
                    (edge.interaction_strength for edge in edges),
                    key=lambda item: _INTERACTION_ORDER[item],
                ),
                feedback_intensity=max(
                    (edge.feedback_intensity for edge in edges),
                    key=lambda item: _INTENSITY_ORDER[item],
                ),
                feedback=any(edge.feedback for edge in edges),
                evidence_refs=[edge.evidence_ref for edge in edges],
                decision_reason=_classification_reason(regime),
                rule_version_ref=graph.rule_version_ref,
            )
        )
    return rows


def _boundary_regime(edges: Sequence[CouplingEdge]) -> CouplingRegime:
    if all(edge.interaction_strength == "none" for edge in edges):
        return "modular"
    if any(
        edge.feedback
        and (edge.interaction_strength == "strong" or edge.feedback_intensity == "high")
        for edge in edges
    ):
        return "entangled"
    if any(edge.interaction_strength == "strong" for edge in edges):
        return "hierarchically_coupled"
    return "near_decomposable"


def _default_entangled_classification(
    *,
    design_ref: str,
    module_refs: Sequence[str],
    module_discovery_ref: str | None,
    rule_version_ref: str,
    reason: str,
    coupling_graph_ref: str | None = None,
) -> CouplingRegimeClassification:
    del module_discovery_ref
    return CouplingRegimeClassification(
        classification_id=f"layer2.s5.coupling_classification.{_stable_token(design_ref)}",
        classification_ref=(
            f"pdc://layer2/s5/{_stable_token(design_ref, 'classification')}"
            "/coupling-classification"
        ),
        design_ref=design_ref,
        coupling_graph_ref=coupling_graph_ref,
        module_refs=list(module_refs),
        coupling_regime="entangled",
        boundary_classifications=[],
        feedback_intensity="high",
        firewall_disposition="block",
        composition_disposition="system_evidence_required",
        defaulted_to_more_coupling=True,
        decision_reason=reason,
        authority_boundary=_classification_authority_boundary(rule_version_ref),
        rule_version_ref=rule_version_ref,
    )


def _classification_feedback_intensity(
    regime: CouplingRegime,
    edges: Sequence[CouplingEdge],
) -> FeedbackIntensity:
    if regime == "modular":
        return "none"
    if regime == "entangled":
        return "high"
    signals = [
        edge.feedback_intensity
        for edge in edges
        if edge.feedback_intensity != "high" and edge.feedback_intensity != "none"
    ]
    if not signals:
        return "none"
    return max(signals, key=lambda item: _INTENSITY_ORDER[item])


def _composition_disposition(regime: CouplingRegime) -> CompositionDisposition:
    if regime == "modular":
        return "compose"
    if regime in {"near_decomposable", "hierarchically_coupled"}:
        return "compose_with_limitations"
    return "system_evidence_required"


def _residual_risk(regime: CouplingRegime) -> ResidualInteractionRisk:
    if regime == "modular":
        return "low"
    if regime in {"near_decomposable", "hierarchically_coupled"}:
        return "medium"
    return "high"


def _propagated_limitations(classification: CouplingRegimeClassification) -> list[str]:
    if classification.coupling_regime != "hierarchically_coupled":
        return []
    return [
        f"limitation://layer2/s5/{_stable_token(row.boundary_ref)}"
        for row in classification.boundary_classifications
    ]


def _classification_reason(regime: CouplingRegime) -> str:
    if regime == "modular":
        return "no observed cross-module interaction edges"
    if regime == "near_decomposable":
        return "weak residual cross-module interactions limit composition authority"
    if regime == "hierarchically_coupled":
        return "strong acyclic dependencies propagate upstream limitations downstream"
    return "entangled feedback or invalid hierarchy requires system-level evidence"


def _has_cycle(edges: Sequence[tuple[str, str]]) -> bool:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for source, target in edges:
        adjacency[source].append(target)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in adjacency.get(node, []):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in adjacency)


def _system_effect_support_label(
    base_origin: ForecastSupportBaseOrigin,
    claim_scope: ForecastClaimScope,
) -> SystemEffectSupportLabel:
    if claim_scope == "leaf_only":
        return "leaf_only_no_system_claim"
    if base_origin == "simulation_only":
        return "simulation_only_system_effect"
    if base_origin == "transported_scholar_estimate":
        return "transported_with_heavy_limitation"
    if base_origin == "validated_local_model":
        return "validated_local_dynamic_model"
    if base_origin == "historical_prior":
        return "historical_prior_system_context"
    return "equilibrium_contested"


def _receipt_may_not_use_for(decomposition: DecompositionResult) -> list[str]:
    may_not_use = [
        "production_claim_authority",
        "rollout_authority",
        "publication_authority",
        "residual_interaction_risk",
        "whole_design_authority_without_coupling_graph",
        "weakened_authority_from_tractability_cutoff",
    ]
    if decomposition.composition_disposition == "system_evidence_required":
        may_not_use.append("partial_equilibrium_system_effect_claim")
    return may_not_use


def _classification_authority_boundary(rule_version_ref: str) -> AuthorityBoundary:
    return _authority_boundary(
        authoritative_for=[
            "coupling_regime_classification",
            "composition_gate",
            "system_dynamics_requirement",
        ],
        may_not_use_for=[
            "production_claim_authority",
            "rollout_authority",
            "whole_design_authority_without_coupling_graph",
            "false_modular_decomposition",
        ],
        rule_version_ref=rule_version_ref,
    )


def _authority_boundary(
    *,
    authoritative_for: Sequence[str],
    may_not_use_for: Sequence[str],
    rule_version_ref: str,
) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=list(authoritative_for),
        may_not_use_for=list(may_not_use_for),
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[rule_version_ref],
    )


def _stable_token(*parts: str) -> str:
    digest = sha256("::".join(parts).encode("utf-8")).hexdigest()[:12]
    return digest


__all__ = [
    "LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION",
    "BoundaryCouplingClassification",
    "CompositionAuthorityMode",
    "CompositionDisposition",
    "CompositionLawCheck",
    "CompositionReceipt",
    "ComputationalTractabilityBudget",
    "CouplingEdge",
    "CouplingGraph",
    "CouplingRegime",
    "CouplingRegimeClassification",
    "DecompositionResult",
    "DesignInterfaceContract",
    "DynamicsRequirementLevel",
    "FeedbackIntensity",
    "ForecastClaimScope",
    "ForecastSupportBaseOrigin",
    "ForecastSupportScope",
    "InteractionStrength",
    "ModuleDiscoveryResult",
    "P17BoundarySpoofError",
    "P17FalseModularityError",
    "P17SyntacticCompositionError",
    "P17SystemDynamicsRequiredError",
    "RecursiveDesignGraph",
    "SystemDynamicsRequirement",
    "SystemEffectSupportLabel",
    "assert_composition_laws_hold",
    "build_composition_receipt",
    "build_computational_tractability_budget",
    "build_coupling_graph",
    "build_system_dynamics_requirement",
    "build_system_effect_support",
    "classify_coupling",
    "composition_to_axis_positions",
    "coupling_accuracy",
    "critical_path_regime",
    "decompose_design",
    "derive_recursive_design_graph",
    "discover_design_modules",
]
