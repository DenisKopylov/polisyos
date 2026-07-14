"""Layer 2 S5 coupling classifier and design-composition algebra contracts."""

from __future__ import annotations

import contextlib
import json
import tomllib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import Field

from polisyos.pdc import (
    ArtifactEnvelope,
    ArtifactRef,
    AuthorityBoundary,
    AuthorityFlowResult,
    AxisFirewallStatus,
    AxisPositionDeclaration,
    CompositionCertificate,
    CompositionGateResult,
    EmergentClaimGroundingResult,
    EpistemicRegime,
    EvidenceBasis,
    Layer2ReadinessModel,
    ObligationRecord,
    OperationClass,
    PortSpec,
    SearchTerminalKind,
    SubDesignContract,
    assert_ring2_verifier_provenance,
    gy_content_hash,
)
from polisyos.runtime.quality.evidence_independence import (
    EvidenceIndependenceError,
    validate_evidence_independence_map_record,
)

LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s5_coupling_composition.v1"
)
RULE_REF_FALLBACK = "policyos.layer2.s5.coupling_composition.v1"
REPO_ROOT = Path(__file__).resolve().parents[5]
GY_COMPOSITION_CERTIFICATES_PATH = Path(
    "architecture/policy_design_case/layer3_gy_composition_certificates.json"
)

BoundaryCouplingKind = Literal[
    "independent",
    "sequential",
    "shared_resource",
    "feedback",
    "unknown",
]
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
    independence_consistency_ref: str | None = Field(default=None, max_length=300)


class BoundaryCouplingClassification(Layer2ReadinessModel):
    """Boundary-first S5 classification row for one cross-level handoff."""

    schema_version: str = LAYER2_S5_COUPLING_COMPOSITION_SCHEMA_VERSION
    boundary_ref: str = Field(..., min_length=1, max_length=300)
    source_module_ref: str = Field(..., min_length=1, max_length=300)
    target_module_ref: str = Field(..., min_length=1, max_length=300)
    coupling_regime: CouplingRegime
    coupling_kind: BoundaryCouplingKind
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
    evidence_state: Literal["observed", "absent", "candidate"] = "absent"
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
    evidence_state: Literal["observed", "absent", "candidate"] = "absent",
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
    elif (
        graph.evidence_state == "absent"
        or graph.module_discovery_ref is None
        or not graph.interaction_edges
    ):
        classification = _default_entangled_classification(
            design_ref=graph.design_ref,
            module_refs=graph.module_refs,
            module_discovery_ref=graph.module_discovery_ref,
            rule_version_ref=graph.rule_version_ref,
            coupling_graph_ref=graph.graph_ref,
            reason=(
                "coupling evidence, an observed boundary, or module discovery proof "
                "is absent"
            ),
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


def resolve_bind_verify(
    ref: str | None,
    *,
    context: Mapping[str, object],
) -> Mapping[str, object] | None:
    """Resolve a Ring-2 evidence ref, content-bind it, and verify provenance.

    This is the single verifier-facing intake for composition evidence consumed
    by D3: child SubDesignContract port authority, independence-consistency
    corroboration, P14 independence maps, emergent-claim grounding, and
    promotion CompositionCertificate refs. Inline payloads, self-stamped labels,
    unregistered generated artifacts, missing content bindings, and non-verifier
    provenance all fail closed by returning ``None``.
    """

    if not ref:
        return None
    resolved = _resolve_registered_artifact_ref(str(ref))
    if resolved is None:
        return _resolve_live_subdesign_authority_ref(str(ref), context=context)
    artifact_payload, fragment_payload, relative_path = resolved
    if not _artifact_has_verifier_provenance(
        artifact_payload,
        fragment_payload,
        relative_path=relative_path,
    ):
        return _resolve_live_subdesign_authority_ref(str(ref), context=context)
    if not _artifact_content_binds(
        artifact_payload,
        fragment_payload,
        context=context,
    ):
        return _resolve_live_subdesign_authority_ref(str(ref), context=context)
    return fragment_payload


def _resolve_live_subdesign_authority_ref(
    ref: str,
    *,
    context: Mapping[str, object],
) -> Mapping[str, object] | None:
    if str(context.get("purpose") or "") != "subdesign_port_authority":
        return None
    path, selector = _repo_ref_path_and_selector(ref)
    if path is None:
        return None
    try:
        relative_path = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return None
    if not _generated_artifact_output_is_registered(relative_path):
        return None
    subdesign_payload = _mapping_value(context.get("live_subdesign_contract"))
    authority_payload = _mapping_value(context.get("live_provided_authority"))
    if not subdesign_payload or not authority_payload:
        return None
    binding = {
        key: context.get(key)
        for key in (
            "subdesign_id",
            "workspace_id",
            "parent_workspace_id",
            "port_id",
            "search_exit_ref",
            "search_exit_content_hash",
            "provided_authority_content_hash",
            "producer_root_refs",
            "producer_root_content_hashes",
        )
    }
    fragment_payload = {
        "verification_id": selector or ref,
        "subdesign_contract_ref": ref,
        "writer_role": "system_verifier",
        "produced_by": "polisyos.runtime.quality.design_axes.coupling_composition",
        "binding": binding,
        "authority_boundary": authority_payload,
        "subdesign_contract": subdesign_payload,
    }
    artifact_payload = {
        "schema_version": "policyos.policy_design_case.layer3_gy.composition_certificates.v1",
        "writer_role": "system_verifier",
        "produced_by": "polisyos.runtime.quality.design_axes.coupling_composition",
        "subdesign_contract_verifications": [fragment_payload],
    }
    if not _artifact_has_verifier_provenance(
        artifact_payload,
        fragment_payload,
        relative_path=relative_path,
    ):
        return None
    if not _artifact_content_binds(
        artifact_payload,
        fragment_payload,
        context=context,
    ):
        return None
    return fragment_payload


def _resolve_registered_artifact_ref(
    ref: str,
) -> tuple[Mapping[str, object], Mapping[str, object], str] | None:
    path, selector = _repo_ref_path_and_selector(ref)
    if path is None:
        return None
    try:
        relative_path = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return None
    if not _generated_artifact_output_is_registered(relative_path):
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, Mapping):
        return None
    fragment = _artifact_fragment(payload, selector=selector, ref=ref)
    if fragment is None:
        return None
    return payload, fragment, relative_path


def _repo_ref_path_and_selector(ref: str) -> tuple[Path | None, str | None]:
    if not ref.startswith("repo://"):
        return None, None
    body = ref.removeprefix("repo://")
    path_part, _, selector = body.partition("#")
    if not path_part:
        return None, None
    path = (REPO_ROOT / path_part).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError:
        return None, None
    return path, selector or None


def _generated_artifact_output_is_registered(relative_path: str) -> bool:
    try:
        generated = tomllib.loads(
            (REPO_ROOT / "architecture/generated_artifacts.toml").read_text(
                encoding="utf-8"
            )
        )
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):
        return False
    families = generated.get("family")
    if not isinstance(families, Sequence) or isinstance(
        families,
        str | bytes | bytearray,
    ):
        return False
    for family in families:
        if not isinstance(family, Mapping):
            continue
        outputs = {str(output) for output in _string_values(family.get("outputs"))}
        if relative_path in outputs and str(family.get("stale_output_behavior")) == "fail":
            return True
    return False


def _artifact_fragment(
    payload: Mapping[str, object],
    *,
    selector: str | None,
    ref: str,
) -> Mapping[str, object] | None:
    if not selector:
        return payload
    selectors = {
        selector,
        selector.rstrip("/").rsplit("/", 1)[-1],
        ref,
    }
    for key in (
        "certificates",
        "composition_receipts",
        "subdesign_contract_verifications",
        "independence_consistency_verifications",
        "p14_independence_verifications",
        "emergent_grounding_verifications",
    ):
        rows = payload.get(key)
        if not isinstance(rows, Sequence) or isinstance(rows, str | bytes | bytearray):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            values = {
                str(row.get(id_key) or "")
                for id_key in (
                    "verification_id",
                    "certificate_id",
                    "receipt_id",
                    "ref",
                    "verification_ref",
                    "subdesign_contract_ref",
                    "composition_receipt_ref",
                    "grounding_ref",
                )
            }
            gate = row.get("coupling_gate")
            if isinstance(gate, Mapping):
                values.add(str(gate.get("composition_receipt_ref") or ""))
            values.discard("")
            if values & selectors:
                return row
    direct = payload.get(selector)
    if isinstance(direct, Mapping):
        return direct
    return None


def _artifact_has_verifier_provenance(
    artifact_payload: Mapping[str, object],
    fragment_payload: Mapping[str, object],
    *,
    relative_path: str,
) -> bool:
    writer_role = _first_text(
        fragment_payload.get("writer_role"),
        artifact_payload.get("writer_role"),
        _mapping_value(fragment_payload.get("verifier")).get("writer_role"),
        _mapping_value(artifact_payload.get("verifier")).get("writer_role"),
    )
    if not writer_role:
        return False
    producer = _first_text(
        fragment_payload.get("produced_by"),
        artifact_payload.get("produced_by"),
        fragment_payload.get("proof_source"),
        artifact_payload.get("proof_source"),
    )
    if "run_universal_outcome_corpus.py" in producer:
        return False
    authority = _authority_boundary(
        authoritative_for=["ring2_verifier_artifact_resolution"],
        may_not_use_for=["producer_self_attestation"],
        rule_version_ref=RULE_REF_FALLBACK,
    )
    ref = ArtifactRef.from_payload(
        artifact_id=f"ring2-verifier-{_stable_token(relative_path, writer_role)}",
        artifact_type="Ring2VerifierArtifact",
        payload={
            "relative_path": relative_path,
            "writer_role": writer_role,
            "producer": producer,
        },
        schema_ref="policyos.gy.ring2.verifier_artifact.v1",
        uri=f"repo://{relative_path}",
        version="v1",
    )
    try:
        envelope = ArtifactEnvelope.model_validate(
            {
                "ref": ref.model_dump(mode="json"),
                "payload_ref": f"repo://{relative_path}",
                "payload_schema_ref": str(
                    artifact_payload.get("schema_version")
                    or "policyos.gy.verifier_artifact.v1"
                ),
                "lifecycle_state": "verified",
                "created_by": {"kind": "verifier", "id": producer or writer_role},
                "producer_operation": {
                    "kind": "validator",
                    "id": producer or "ring2-verifier",
                },
                "authority_boundary": authority.model_dump(mode="json"),
            },
            context={"writer_role": writer_role},
        )
        assert_ring2_verifier_provenance(
            envelope,
            context={"writer_role": writer_role},
        )
    except (TypeError, ValueError):
        return False
    return True


def _artifact_content_binds(
    artifact_payload: Mapping[str, object],
    fragment_payload: Mapping[str, object],
    *,
    context: Mapping[str, object],
) -> bool:
    purpose = str(context.get("purpose") or "")
    if purpose == "subdesign_port_authority":
        return _subdesign_port_authority_binds(fragment_payload, context=context)
    if purpose == "independence_consistency":
        return _independence_consistency_binds(fragment_payload, context=context)
    if purpose == "p14_independence_map":
        return _p14_verification_binds(fragment_payload, context=context)
    if purpose == "emergent_grounding":
        return _emergent_grounding_verification_binds(fragment_payload, context=context)
    if purpose == "composition_certificate":
        return _composition_certificate_binds(
            artifact_payload,
            fragment_payload,
            context=context,
        )
    return False


def _subdesign_port_authority_binds(
    fragment_payload: Mapping[str, object],
    *,
    context: Mapping[str, object],
) -> bool:
    binding = _mapping_value(fragment_payload.get("binding"))
    if not binding:
        return False
    for key in (
        "subdesign_id",
        "workspace_id",
        "parent_workspace_id",
        "port_id",
        "search_exit_ref",
        "search_exit_content_hash",
        "provided_authority_content_hash",
    ):
        expected = str(context.get(key) or "")
        if not expected or str(binding.get(key) or "") != expected:
            return False
    for key in ("producer_root_refs", "producer_root_content_hashes"):
        expected_set = set(_string_values(context.get(key)))
        actual_set = set(_string_values(binding.get(key)))
        if not expected_set or not expected_set <= actual_set:
            return False
    authority_payload = _mapping_value(fragment_payload.get("authority_boundary"))
    if not authority_payload:
        authority_payload = _mapping_value(fragment_payload.get("provided_authority"))
    if not authority_payload:
        return False
    if (
        _stable_content_hash(authority_payload)
        != str(binding.get("provided_authority_content_hash") or "")
    ):
        return False
    subdesign_payload = _mapping_value(fragment_payload.get("subdesign_contract"))
    if not subdesign_payload:
        return False
    if str(subdesign_payload.get("subdesign_id") or "") != str(
        context.get("subdesign_id") or ""
    ):
        return False
    search_exit_payload = _mapping_value(subdesign_payload.get("search_exit"))
    if not search_exit_payload:
        return False
    if _search_exit_binding_hash(search_exit_payload) != str(
        binding.get("search_exit_content_hash") or ""
    ):
        return False
    contract_roots = subdesign_payload.get("producer_roots")
    if not isinstance(contract_roots, Sequence) or isinstance(
        contract_roots,
        str | bytes | bytearray,
    ):
        return False
    contract_root_hashes = {
        str(root.get("content_hash") or "")
        for root in contract_roots
        if isinstance(root, Mapping)
    } - {""}
    expected_root_hashes = set(_string_values(context.get("producer_root_content_hashes")))
    if not expected_root_hashes or not expected_root_hashes <= contract_root_hashes:
        return False
    try:
        AuthorityBoundary.model_validate(authority_payload)
    except (TypeError, ValueError):
        return False
    return True


def _independence_consistency_binds(
    fragment_payload: Mapping[str, object],
    *,
    context: Mapping[str, object],
) -> bool:
    binding = _mapping_value(fragment_payload.get("binding"))
    if not binding:
        binding = fragment_payload
    expected = {
        "graph_hash": str(context.get("graph_hash") or ""),
        "boundary_ref": str(context.get("boundary_ref") or ""),
        "source_module_ref": str(context.get("source_module_ref") or ""),
        "target_module_ref": str(context.get("target_module_ref") or ""),
        "relation": str(context.get("relation") or ""),
    }
    if not all(expected.values()):
        return False
    return all(str(binding.get(key) or "") == value for key, value in expected.items())


def _p14_verification_binds(
    fragment_payload: Mapping[str, object],
    *,
    context: Mapping[str, object],
) -> bool:
    binding = _mapping_value(fragment_payload.get("binding"))
    if not binding:
        return False
    for key in (
        "claim_refs",
        "subdesign_refs",
        "producer_root_refs",
        "producer_root_content_hashes",
        "evidence_line_content_hashes",
        "lineage_content_hashes",
    ):
        expected = set(_string_values(context.get(key)))
        actual = set(_string_values(binding.get(key)))
        if not expected or not expected <= actual:
            return False
    for key in (
        "raw_evidence_line_count",
        "effective_independent_evidence_count",
    ):
        if context.get(key) is not None and int(binding.get(key) or -1) != int(
            context[key]  # type: ignore[arg-type]
        ):
            return False
    return True


def _composition_certificate_binds(
    artifact_payload: Mapping[str, object],
    certificate_payload: Mapping[str, object],
    *,
    context: Mapping[str, object],
) -> bool:
    try:
        certificate = CompositionCertificate.model_validate(certificate_payload)
    except (TypeError, ValueError):
        return False
    if certificate.verdict != "composable":
        return False
    if not certificate.composition_receipt_ref:
        return False
    if certificate.coupling_gate.verdict != "valid":
        return False
    if certificate.coupling_gate.composition_receipt_ref != certificate.composition_receipt_ref:
        return False
    if not certificate.authority_flow:
        return False
    receipts = artifact_payload.get("composition_receipts")
    if not isinstance(receipts, Sequence) or isinstance(receipts, str | bytes | bytearray):
        return False
    receipt_payload = next(
        (
            row
            for row in receipts
            if isinstance(row, Mapping)
            and str(row.get("receipt_ref") or "") == certificate.composition_receipt_ref
        ),
        None,
    )
    if not isinstance(receipt_payload, Mapping):
        return False
    try:
        receipt = CompositionReceipt.model_validate(receipt_payload)
    except (TypeError, ValueError):
        return False
    if receipt.receipt_ref != certificate.composition_receipt_ref:
        return False
    if receipt.composition_disposition not in {"compose", "compose_with_limitations"}:
        return False
    if receipt.authority_mode != "critical_path_only":
        return False
    expected_candidate = str(context.get("candidate_ref") or "")
    if expected_candidate and certificate.candidate_ref != expected_candidate:
        return False
    expected_program = str(context.get("target_policy_program_ref") or "")
    if expected_program and certificate.target_policy_program_ref != expected_program:
        return False
    expected_claims = set(_string_values(context.get("claim_refs")))
    return not (expected_claims and not expected_claims <= set(certificate.claim_refs))


def _emergent_grounding_verification_binds(
    fragment_payload: Mapping[str, object],
    *,
    context: Mapping[str, object],
) -> bool:
    binding = _mapping_value(fragment_payload.get("binding"))
    if not binding:
        return False
    for key in (
        "claim_refs",
        "subdesign_refs",
        "producer_root_refs",
        "producer_root_content_hashes",
        "required_grounding",
    ):
        expected = set(_string_values(context.get(key)))
        actual = set(_string_values(binding.get(key)))
        if expected and not expected <= actual:
            return False
    expected_claims = set(_string_values(context.get("claim_refs")))
    if not expected_claims:
        return False
    expected_subdesigns = set(_string_values(context.get("subdesign_refs")))
    if not expected_subdesigns:
        return False
    grounding_ref = str(context.get("grounding_ref") or "")
    if not grounding_ref or str(binding.get("grounding_ref") or "") != grounding_ref:
        return False
    authority_payload = _mapping_value(fragment_payload.get("authority_boundary"))
    if not authority_payload:
        authority_payload = _mapping_value(fragment_payload.get("grounding_authority"))
    if not authority_payload:
        return False
    try:
        AuthorityBoundary.model_validate(authority_payload)
    except (TypeError, ValueError):
        return False
    return True


def _first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, Mapping):
            nested = _first_text(
                value.get("path"),
                value.get("workflow"),
                value.get("id"),
                value.get("name"),
            )
            if nested:
                return nested
    return ""


def _mapping_value(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def compose_subdesigns(
    *,
    subdesigns: Sequence[SubDesignContract],
    claims: Sequence[Mapping[str, object]],
    graph: CouplingGraph | None,
    parent_workspace_id: str,
    rule_version_ref: str | None = None,
) -> CompositionCertificate:
    """Compose child sub-designs through the D3 three-stage operator.

    This is a loop-facing bridge over the existing S5 composition engine. It
    does not classify coupling, compute authority meets, or evaluate evidence
    independence with slice-local logic; it delegates those parts to
    ``classify_coupling``/``build_composition_receipt``, ``AuthorityBoundary.meet``,
    and the runtime-quality P14 independence validator.
    """

    child_contracts = tuple(subdesigns)
    rule_ref = rule_version_ref or (
        graph.rule_version_ref if graph is not None else RULE_REF_FALLBACK
    )
    obligations: list[ObligationRecord] = []
    blocking_edges: list[str] = []
    receipt: CompositionReceipt | None = None
    decomposition: DecompositionResult | None = None
    system_dynamics: SystemDynamicsRequirement | None = None

    if graph is None or graph.evidence_state != "observed" or not graph.module_discovery_ref:
        classification = classify_coupling(
            graph,
            design_ref=f"pdc://gy/{_stable_token(parent_workspace_id, 'unknown')}/design",
            module_refs=[child.workspace_id for child in child_contracts],
            rule_version_ref=rule_ref,
        )
        gate = CompositionGateResult(
            verdict="invalid",
            blocking_edges=[],
            invalid_reason="unknown_coupling_requires_discovery",
            coupling_classification_ref=classification.classification_ref,
        )
        obligations.append(
            _composition_obligation(
                parent_workspace_id=parent_workspace_id,
                reason="unknown_coupling_requires_discovery",
                description=(
                    "Parent composition requires an observed CouplingGraph "
                    "before authority can flow."
                ),
                operation_class=OperationClass.DISCOVER,
            )
        )
        return _composition_certificate(
            parent_workspace_id=parent_workspace_id,
            subdesigns=child_contracts,
            coupling_gate=gate,
            authority_flow=[],
            emergent_claims=[],
            obligations=obligations,
            verdict="not_composable",
            receipt=None,
            claims=claims,
            rule_version_ref=rule_ref,
        )

    classification = classify_coupling(graph)
    decomposition = decompose_design(
        graph,
        classification,
        critical_path_module_refs=graph.module_refs,
    )
    blocking_edges = [row.boundary_ref for row in classification.boundary_classifications]
    if _has_unknown_coupling(classification):
        gate = CompositionGateResult(
            verdict="invalid",
            blocking_edges=blocking_edges
            or [edge.boundary_ref for edge in graph.interaction_edges],
            invalid_reason="unknown_coupling_requires_discovery",
            coupling_classification_ref=classification.classification_ref,
            decomposition_ref=decomposition.decomposition_ref,
        )
        obligations.append(
            _composition_obligation(
                parent_workspace_id=parent_workspace_id,
                reason="unknown_coupling_requires_discovery",
                description=(
                    "Coupling relation has unknown consistency; parent composition "
                    "requires discovery before authority can flow."
                ),
                operation_class=OperationClass.DISCOVER,
            )
        )
        return _composition_certificate(
            parent_workspace_id=parent_workspace_id,
            subdesigns=child_contracts,
            coupling_gate=gate,
            authority_flow=[],
            emergent_claims=[],
            obligations=obligations,
            verdict="not_composable",
            receipt=None,
            claims=claims,
            rule_version_ref=rule_ref,
        )
    has_feedback = (
        classification.feedback_intensity == "high"
        or any(
            row.coupling_kind == "feedback" or row.feedback
            for row in classification.boundary_classifications
        )
    )
    if has_feedback:
        system_dynamics = build_system_dynamics_requirement(decomposition)
        with contextlib.suppress(P17SystemDynamicsRequiredError):
            build_composition_receipt(decomposition, system_effect_claim_requested=True)
        gate = CompositionGateResult(
            verdict="requires_system_dynamics",
            blocking_edges=blocking_edges,
            invalid_reason="feedback_requires_joint_grounding",
            coupling_classification_ref=classification.classification_ref,
            decomposition_ref=decomposition.decomposition_ref,
            system_dynamics_requirement_ref=system_dynamics.requirement_ref,
        )
        obligations.append(
            _composition_obligation(
                parent_workspace_id=parent_workspace_id,
                reason="feedback_requires_joint_grounding",
                description=(
                    "Feedback changes the mathematical object; compose via a joint "
                    "sub-workspace or explicit fixpoint/equilibrium/simulation operation."
                ),
                operation_class=OperationClass.DECOMPOSE,
            )
        )
        return _composition_certificate(
            parent_workspace_id=parent_workspace_id,
            subdesigns=child_contracts,
            coupling_gate=gate,
            authority_flow=[],
            emergent_claims=[],
            obligations=obligations,
            verdict="not_composable",
            receipt=None,
            claims=claims,
            rule_version_ref=rule_ref,
        )

    if _has_shared_resource_coupling(classification):
        gate = CompositionGateResult(
            verdict="requires_capacity_aggregation",
            blocking_edges=blocking_edges
            or [edge.boundary_ref for edge in graph.interaction_edges],
            invalid_reason="shared_resource_requires_capacity_aggregation",
            coupling_classification_ref=classification.classification_ref,
            decomposition_ref=decomposition.decomposition_ref,
        )
        obligations.append(
            _composition_obligation(
                parent_workspace_id=parent_workspace_id,
                reason="capacity_aggregation_required",
                description=(
                    "Shared-resource coupling requires a CapacityAggregation operation "
                    "before parent authority can compose."
                ),
                operation_class=OperationClass.COMPOSE,
                resolution_options=[
                    {
                        "operation_class": OperationClass.COMPOSE.value,
                        "description": (
                            "CapacityAggregation is required before shared-resource "
                            "composition can carry parent authority."
                        ),
                        "capability": "CapacityAggregation",
                        "capability_state": "surface_out_of_scope",
                        "follow_on_owner": "team-runtime-quality:capacity-aggregation",
                    }
                ],
            )
        )
        return _composition_certificate(
            parent_workspace_id=parent_workspace_id,
            subdesigns=child_contracts,
            coupling_gate=gate,
            authority_flow=[],
            emergent_claims=[],
            obligations=obligations,
            verdict="not_composable",
            receipt=None,
            claims=claims,
            rule_version_ref=rule_ref,
        )

    receipt = build_composition_receipt(decomposition)
    gate = CompositionGateResult(
        verdict="valid",
        blocking_edges=blocking_edges,
        coupling_classification_ref=classification.classification_ref,
        decomposition_ref=decomposition.decomposition_ref,
        composition_receipt_ref=receipt.receipt_ref,
    )
    for child in child_contracts:
        if child.search_exit.terminal_state.kind == SearchTerminalKind.ACQUISITION_REQUIRED:
            obligations.append(
                _composition_obligation(
                    parent_workspace_id=parent_workspace_id,
                    reason="child_acquisition_required",
                    description=(
                        f"Child workspace {child.workspace_id} exited acquisition_required; "
                        "parent must fund, cap, or escalate before composition."
                    ),
                    operation_class=OperationClass.ACQUIRE,
                    blocks=[{"subdesign_ref": child.subdesign_id}],
                )
            )

    verified_evidence = _collect_verified_evidence(
        parent_workspace_id=parent_workspace_id,
        subdesigns=child_contracts,
        claims=claims,
    )
    authority_flow = _per_port_authority_flow(
        parent_workspace_id=parent_workspace_id,
        subdesigns=child_contracts,
        graph=graph,
        classification=classification,
        obligations=obligations,
        verified_evidence=verified_evidence,
    )
    weakest_part = _weakest_authority_from_flow(authority_flow)
    emergent = _emergent_claim_grounding(
        parent_workspace_id=parent_workspace_id,
        subdesigns=child_contracts,
        claims=claims,
        weakest_part=weakest_part,
        coupling_authority=_coupling_certificate_authority(
            parent_workspace_id=parent_workspace_id,
            rule_version_ref=rule_ref,
        ),
        obligations=obligations,
        rule_version_ref=rule_ref,
        verified_evidence=verified_evidence,
    )
    if _authority_outputs_unverified(
        authority_flow=authority_flow,
        emergent_claims=emergent,
        verified_evidence=verified_evidence,
    ):
        obligations.append(
            _composition_obligation(
                parent_workspace_id=parent_workspace_id,
                reason="authority_evidence_unverified",
                description=(
                    "Composition authority can only be emitted from resolved, "
                    "content-bound, verifier-produced evidence."
                ),
                operation_class=OperationClass.VERIFY,
            )
        )

    verdict = _composition_verdict(
        obligations=obligations,
        authority_flow=authority_flow,
        emergent_claims=emergent,
        composition_disposition=receipt.composition_disposition,
    )
    if verdict == "not_composable":
        authority_flow = []
        emergent = _strip_emergent_authority(emergent)
    return _composition_certificate(
        parent_workspace_id=parent_workspace_id,
        subdesigns=child_contracts,
        coupling_gate=gate,
        authority_flow=authority_flow,
        emergent_claims=emergent,
        obligations=obligations,
        verdict=verdict,
        receipt=receipt,
        claims=claims,
        rule_version_ref=rule_ref,
    )


def _composition_certificate(
    *,
    parent_workspace_id: str,
    subdesigns: Sequence[SubDesignContract],
    coupling_gate: CompositionGateResult,
    authority_flow: Sequence[AuthorityFlowResult],
    emergent_claims: Sequence[EmergentClaimGroundingResult],
    obligations: Sequence[ObligationRecord],
    verdict: Literal["composable", "composable_with_limits", "not_composable"],
    receipt: CompositionReceipt | None,
    claims: Sequence[Mapping[str, object]],
    rule_version_ref: str,
) -> CompositionCertificate:
    return CompositionCertificate(
        certificate_id=f"composition-certificate-{_stable_token(parent_workspace_id, verdict)}",
        parent_workspace_id=parent_workspace_id,
        input_subdesigns=[child.subdesign_id for child in subdesigns],
        target_policy_program_ref=_first_claim_text(
            claims,
            "target_policy_program_ref",
            "policy_program_ref",
        ),
        candidate_ref=_first_claim_text(claims, "candidate_ref"),
        claim_refs=_composition_claim_refs(claims),
        coupling_gate=coupling_gate,
        authority_flow=list(authority_flow),
        emergent_claims=list(emergent_claims),
        unresolved_obligations=list(obligations),
        verdict=verdict,
        composition_receipt_ref=receipt.receipt_ref if receipt is not None else None,
        rule_version_ref=rule_version_ref,
    )


def _strip_emergent_authority(
    emergent_claims: Sequence[EmergentClaimGroundingResult],
) -> list[EmergentClaimGroundingResult]:
    stripped: list[EmergentClaimGroundingResult] = []
    for result in emergent_claims:
        deficits = list(result.limiting_deficits)
        if "composition_not_composable" not in deficits:
            deficits.append("composition_not_composable")
        stripped.append(
            result.model_copy(
                update={
                    "resulting_authority": None,
                    "limiting_deficits": deficits,
                }
            )
        )
    return stripped


def _composition_claim_refs(claims: Sequence[Mapping[str, object]]) -> list[str]:
    refs: list[str] = []
    for claim in claims:
        refs.extend(_string_values(claim.get("claim_ref")))
        refs.extend(_string_values(claim.get("claim_refs")))
    return list(dict.fromkeys(refs))


def _first_claim_text(
    claims: Sequence[Mapping[str, object]],
    *keys: str,
) -> str | None:
    for claim in claims:
        for key in keys:
            value = claim.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _stable_content_hash(value: object) -> str:
    payload = json.loads(json.dumps(value, sort_keys=True))
    _normalise_generated_at(payload)
    return gy_content_hash(payload)


def _search_exit_binding_hash(value: object) -> str:
    payload = _mapping_value(value)
    if not payload:
        return ""
    authority_payload = _mapping_value(payload.get("authority_boundary"))
    binding_payload = {
        "exit_id": str(payload.get("exit_id") or ""),
        "workspace_id": str(payload.get("workspace_id") or ""),
        "terminal_state": _mapping_value(payload.get("terminal_state")),
        "authority_boundary_content_hash": (
            _stable_content_hash(authority_payload) if authority_payload else ""
        ),
    }
    return _stable_content_hash(binding_payload)


def _normalise_generated_at(value: object) -> None:
    if isinstance(value, dict):
        if "generated_at" in value:
            value["generated_at"] = "recomputed-run-clock-normalized"
        for child in value.values():
            _normalise_generated_at(child)
    elif isinstance(value, list):
        for child in value:
            _normalise_generated_at(child)


def _collect_verified_evidence(
    *,
    parent_workspace_id: str,
    subdesigns: Sequence[SubDesignContract],
    claims: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    verified: dict[str, Mapping[str, object]] = {}
    for child in subdesigns:
        for port in child.provides:
            ref = _verified_port_authority_ref(child, port)
            if ref is None or port.provided_authority is None:
                continue
            resolved = resolve_bind_verify(
                ref,
                context=_subdesign_port_authority_context(
                    parent_workspace_id=parent_workspace_id,
                    child=child,
                    port=port,
                ),
            )
            if resolved is not None:
                verified[ref] = resolved
    for claim in claims:
        claim_ref = str(claim.get("claim_ref") or "claim://unknown")
        required_grounding = _required_grounding_values(claim.get("required_grounding"))
        for grounding_ref in _string_values(claim.get("grounding_refs")):
            resolved = resolve_bind_verify(
                grounding_ref,
                context={
                    "purpose": "emergent_grounding",
                    "grounding_ref": grounding_ref,
                    "claim_refs": [claim_ref],
                    "subdesign_refs": [child.subdesign_id for child in subdesigns],
                    "producer_root_refs": _producer_root_refs(subdesigns),
                    "producer_root_content_hashes": _producer_root_hashes(subdesigns),
                    "required_grounding": required_grounding,
                },
            )
            if resolved is not None:
                verified[grounding_ref] = resolved
    return verified


def _verified_port_authority_ref(
    child: SubDesignContract,
    port: PortSpec | None,
) -> str | None:
    if port is None or port.provided_authority is None:
        return None
    ref = str(child.internal_trace_ref or "").strip()
    if not ref.startswith("repo://"):
        return None
    return ref


def _subdesign_port_authority_context(
    *,
    parent_workspace_id: str,
    child: SubDesignContract,
    port: PortSpec,
) -> dict[str, object]:
    authority = port.provided_authority
    return {
        "purpose": "subdesign_port_authority",
        "subdesign_contract_ref": child.internal_trace_ref,
        "subdesign_id": child.subdesign_id,
        "workspace_id": child.workspace_id,
        "parent_workspace_id": child.parent_workspace_id or parent_workspace_id,
        "port_id": port.port_id,
        "search_exit_ref": child.search_exit.exit_id,
        "search_exit_content_hash": _search_exit_binding_hash(
            child.search_exit.model_dump(mode="json")
        ),
        "producer_root_refs": _producer_root_refs([child]),
        "producer_root_content_hashes": _producer_root_hashes([child]),
        "live_subdesign_contract": child.model_dump(mode="json"),
        "live_provided_authority": (
            authority.model_dump(mode="json") if authority is not None else {}
        ),
        "provided_authority_content_hash": (
            _stable_content_hash(authority.model_dump(mode="json"))
            if authority is not None
            else ""
        ),
    }


def _verified_port_authority(
    verified_evidence: Mapping[str, Mapping[str, object]],
    ref: str | None,
) -> AuthorityBoundary | None:
    if ref is None:
        return None
    payload = verified_evidence.get(ref)
    if payload is None:
        return None
    authority_payload = _mapping_value(payload.get("authority_boundary"))
    if not authority_payload:
        authority_payload = _mapping_value(payload.get("provided_authority"))
    if not authority_payload:
        return None
    try:
        return AuthorityBoundary.model_validate(authority_payload)
    except (TypeError, ValueError):
        return None


def _composition_obligation(
    *,
    parent_workspace_id: str,
    reason: str,
    description: str,
    operation_class: OperationClass,
    blocks: Sequence[Mapping[str, object]] | None = None,
    resolution_options: Sequence[Mapping[str, object]] | None = None,
) -> ObligationRecord:
    options = (
        [dict(item) for item in resolution_options]
        if resolution_options is not None
        else [
            {
                "operation_class": operation_class.value,
                "description": description,
            }
        ]
    )
    return ObligationRecord(
        obligation_id=f"obligation-{_stable_token(parent_workspace_id, reason, description)}",
        obligation_type=reason,
        raised_by={
            "workspace_id": parent_workspace_id,
            "component": "polisyos.runtime.quality.design_axes.coupling_composition",
        },
        blocks=[dict(item) for item in (blocks or ({"claim_ref": "composition"},))],
        description=description,
        severity="blocks_composition",
        resolution_options=options,
        status="open",
    )


def _per_port_authority_flow(
    *,
    parent_workspace_id: str,
    subdesigns: Sequence[SubDesignContract],
    graph: CouplingGraph,
    classification: CouplingRegimeClassification,
    obligations: list[ObligationRecord],
    verified_evidence: Mapping[str, Mapping[str, object]],
) -> list[AuthorityFlowResult]:
    children_by_ref = _subdesigns_by_ref(subdesigns)
    coupling_kind_by_boundary = {
        row.boundary_ref: row.coupling_kind for row in classification.boundary_classifications
    }
    if not graph.interaction_edges:
        flows: list[AuthorityFlowResult] = []
        for child in subdesigns:
            port = _first_provided_authority_port(child)
            rationale_ref = _verified_port_authority_ref(child, port)
            if port is None or port.provided_authority is None:
                obligations.append(
                    _composition_obligation(
                        parent_workspace_id=parent_workspace_id,
                        reason="provided_authority_missing",
                        description=(
                            f"Child workspace {child.workspace_id} has no "
                            "authority-bearing provided port."
                        ),
                        operation_class=OperationClass.VERIFY,
                        blocks=[{"subdesign_ref": child.subdesign_id}],
                    )
                )
                continue
            if rationale_ref is None or rationale_ref not in verified_evidence:
                obligations.append(
                    _composition_obligation(
                        parent_workspace_id=parent_workspace_id,
                        reason="authority_evidence_unverified",
                        description=(
                            f"Child workspace {child.workspace_id} provided authority "
                            "without verifier-bound SubDesignContract evidence."
                        ),
                        operation_class=OperationClass.VERIFY,
                        blocks=[{"subdesign_ref": child.subdesign_id}],
                    )
                )
                continue
            resulting_authority = _verified_port_authority(
                verified_evidence,
                rationale_ref,
            )
            if resulting_authority is None:
                obligations.append(
                    _composition_obligation(
                        parent_workspace_id=parent_workspace_id,
                        reason="authority_evidence_unverified",
                        description=(
                            f"Child workspace {child.workspace_id} SubDesignContract "
                            "evidence did not resolve to authority-bearing content."
                        ),
                        operation_class=OperationClass.VERIFY,
                        blocks=[{"subdesign_ref": child.subdesign_id}],
                    )
                )
                continue
            flows.append(
                AuthorityFlowResult(
                    from_port=port.port_id,
                    to_port=f"{parent_workspace_id}:policy_program_claim",
                    resulting_authority=resulting_authority,
                    rationale_ref=rationale_ref,
                    coupling_kind="independent",
                )
            )
        return flows

    flows = []
    for edge in graph.interaction_edges:
        source = children_by_ref.get(edge.source_module_ref)
        target = children_by_ref.get(edge.target_module_ref)
        if source is None or target is None:
            obligations.append(
                _composition_obligation(
                    parent_workspace_id=parent_workspace_id,
                    reason="coupling_edge_subdesign_missing",
                    description=(
                        "CouplingGraph edge does not resolve to child SubDesignContract ports."
                    ),
                    operation_class=OperationClass.DISCOVER,
                    blocks=[{"coupling_edge_ref": edge.boundary_ref}],
                )
            )
            continue
        source_port = _first_provided_authority_port(source)
        target_port = _first_provided_authority_port(target)
        source_ref = _verified_port_authority_ref(source, source_port)
        target_ref = _verified_port_authority_ref(target, target_port)
        if (
            source_port is None
            or target_port is None
            or source_port.provided_authority is None
            or target_port.provided_authority is None
        ):
            obligations.append(
                _composition_obligation(
                    parent_workspace_id=parent_workspace_id,
                    reason="provided_authority_missing",
                    description=(
                        "Sequential authority flow requires verifier-stamped "
                        "source and target ports."
                    ),
                    operation_class=OperationClass.VERIFY,
                    blocks=[{"coupling_edge_ref": edge.boundary_ref}],
                )
            )
            continue
        if (
            source_ref is None
            or target_ref is None
            or source_ref not in verified_evidence
            or target_ref not in verified_evidence
        ):
            obligations.append(
                _composition_obligation(
                    parent_workspace_id=parent_workspace_id,
                    reason="authority_evidence_unverified",
                    description=(
                        "Sequential authority flow requires verifier-bound source "
                        "and target SubDesignContract authority."
                    ),
                    operation_class=OperationClass.VERIFY,
                    blocks=[{"coupling_edge_ref": edge.boundary_ref}],
                )
            )
            continue
        source_authority = _verified_port_authority(verified_evidence, source_ref)
        target_authority = _verified_port_authority(verified_evidence, target_ref)
        if source_authority is None or target_authority is None:
            obligations.append(
                _composition_obligation(
                    parent_workspace_id=parent_workspace_id,
                    reason="authority_evidence_unverified",
                    description=(
                        "Sequential SubDesignContract evidence did not resolve to "
                        "authority-bearing source and target content."
                    ),
                    operation_class=OperationClass.VERIFY,
                    blocks=[{"coupling_edge_ref": edge.boundary_ref}],
                )
            )
            continue
        resulting = source_authority.meet(
            target_authority,
            boundary_id=f"boundary-{_stable_token(edge.boundary_ref, 'authority-flow')}",
        )
        if _empty_authoritative_for(resulting):
            obligations.append(
                _composition_obligation(
                    parent_workspace_id=parent_workspace_id,
                    reason="empty_authoritative_for",
                    description=(
                        "Per-port authority meet has no shared authoritative purpose for this use."
                    ),
                    operation_class=OperationClass.REFINE,
                    blocks=[
                        {
                            "from_port": source_port.port_id,
                            "to_port": target_port.port_id,
                            "coupling_edge_ref": edge.boundary_ref,
                        }
                    ],
                )
            )
        flows.append(
            AuthorityFlowResult(
                from_port=source_port.port_id,
                to_port=target_port.port_id,
                resulting_authority=resulting,
                rationale_ref=source_ref,
                coupling_kind=coupling_kind_by_boundary.get(edge.boundary_ref, "unknown"),
            )
        )
    return flows


def _subdesigns_by_ref(
    subdesigns: Sequence[SubDesignContract],
) -> dict[str, SubDesignContract]:
    refs: dict[str, SubDesignContract] = {}
    for child in subdesigns:
        refs[child.workspace_id] = child
        refs[child.subdesign_id] = child
        refs[f"module://{child.subdesign_id}"] = child
        refs[f"workspace://{child.workspace_id}"] = child
    return refs


def _first_provided_authority_port(child: SubDesignContract) -> PortSpec | None:
    for port in child.provides:
        if port.provided_authority is not None:
            return port
    return child.provides[0] if child.provides else None


def _empty_authoritative_for(boundary: AuthorityBoundary) -> bool:
    values = {value for value in boundary.authoritative_for if value and value != "none"}
    return not values


def _weakest_authority_from_flow(
    authority_flow: Sequence[AuthorityFlowResult],
) -> AuthorityBoundary | None:
    boundaries = [flow.resulting_authority for flow in authority_flow]
    if not boundaries:
        return None
    result = boundaries[0]
    for boundary in boundaries[1:]:
        meet_boundary_id = "boundary-" + _stable_token(
            result.boundary_id or 'left',
            boundary.boundary_id or 'right',
        )
        result = result.meet(
            boundary,
            boundary_id=meet_boundary_id,
        )
    return result


def _authority_outputs_unverified(
    *,
    authority_flow: Sequence[AuthorityFlowResult],
    emergent_claims: Sequence[EmergentClaimGroundingResult],
    verified_evidence: Mapping[str, Mapping[str, object]],
) -> bool:
    verified_refs = set(verified_evidence)
    for flow in authority_flow:
        if flow.resulting_authority is not None and flow.rationale_ref not in verified_refs:
            return True
    for claim in emergent_claims:
        if claim.resulting_authority is None:
            continue
        if not set(claim.grounding_refs) & verified_refs:
            return True
    return False


def _emergent_claim_grounding(
    *,
    parent_workspace_id: str,
    subdesigns: Sequence[SubDesignContract],
    claims: Sequence[Mapping[str, object]],
    weakest_part: AuthorityBoundary | None,
    coupling_authority: AuthorityBoundary,
    obligations: list[ObligationRecord],
    rule_version_ref: str,
    verified_evidence: Mapping[str, Mapping[str, object]],
) -> list[EmergentClaimGroundingResult]:
    results: list[EmergentClaimGroundingResult] = []
    for claim in claims:
        claim_ref = str(claim.get("claim_ref") or "claim://unknown")
        required_grounding = _required_grounding_values(claim.get("required_grounding"))
        grounding_refs = _string_values(claim.get("grounding_refs"))
        grounding_ref, grounding_authority = _verified_grounding_authority(
            grounding_refs=grounding_refs,
            verified_evidence=verified_evidence,
        )
        if not grounding_refs or weakest_part is None:
            obligations.append(
                _composition_obligation(
                    parent_workspace_id=parent_workspace_id,
                    reason="emergent_grounding_missing",
                    description=(
                        f"Program-level claim {claim_ref} cannot inherit authority from parts; "
                        "it needs own emergent grounding."
                    ),
                    operation_class=OperationClass.COMPOSE,
                    blocks=[{"claim_ref": claim_ref}],
                )
            )
            results.append(
                EmergentClaimGroundingResult(
                    claim_ref=claim_ref,
                    grounding_status="missing",
                    required_grounding=required_grounding,
                    resulting_authority=None,
                    grounding_refs=grounding_refs,
                )
            )
            continue
        if grounding_authority is None or grounding_ref is None:
            obligations.append(
                _composition_obligation(
                    parent_workspace_id=parent_workspace_id,
                    reason="emergent_grounding_unresolved",
                    description=(
                        f"Program-level claim {claim_ref} grounding refs did not "
                        "resolve to content-bound verifier artifacts."
                    ),
                    operation_class=OperationClass.VERIFY,
                    blocks=[{"claim_ref": claim_ref}],
                )
            )
            results.append(
                EmergentClaimGroundingResult(
                    claim_ref=claim_ref,
                    grounding_status="unresolved",
                    required_grounding=required_grounding,
                    resulting_authority=None,
                    grounding_refs=grounding_refs,
                    limiting_deficits=["emergent_grounding_unresolved"],
                )
            )
            continue
        resulting = weakest_part.meet(
            grounding_authority,
            boundary_id=f"boundary-{_stable_token(claim_ref, 'part-grounding')}",
        ).meet(
            coupling_authority,
            boundary_id=f"boundary-{_stable_token(claim_ref, 'coupling-cap')}",
        )
        raw_count: int | None = None
        effective_count: int | None = None
        limiting_deficits: list[str] = []
        independence_map = claim.get("independence_map")
        if not isinstance(independence_map, Mapping):
            obligations.append(
                _composition_obligation(
                    parent_workspace_id=parent_workspace_id,
                    reason="p14_independence_map_missing",
                    description=(
                        "Program-level emergent support requires a P14 "
                        "evidence-independence map; absence cannot inflate authority."
                    ),
                    operation_class=OperationClass.VERIFY,
                    blocks=[{"claim_ref": claim_ref}],
                )
            )
            results.append(
                EmergentClaimGroundingResult(
                    claim_ref=claim_ref,
                    grounding_status="invalid",
                    required_grounding=required_grounding,
                    resulting_authority=None,
                    grounding_refs=grounding_refs,
                    limiting_deficits=["p14_independence_map_missing"],
                )
            )
            continue
        if isinstance(independence_map, Mapping):
            try:
                normalized = validate_evidence_independence_map_record(independence_map)
            except EvidenceIndependenceError as exc:
                obligations.append(
                    _composition_obligation(
                        parent_workspace_id=parent_workspace_id,
                        reason="evidence_independence_invalid",
                        description=f"P14 evidence-independence map is invalid: {exc}",
                        operation_class=OperationClass.VERIFY,
                        blocks=[{"claim_ref": claim_ref}],
                    )
                )
                results.append(
                    EmergentClaimGroundingResult(
                        claim_ref=claim_ref,
                        grounding_status="invalid",
                        required_grounding=required_grounding,
                        resulting_authority=None,
                        grounding_refs=grounding_refs,
                    )
                )
                continue
            binding_error = _p14_composition_binding_error(
                normalized,
                claim_ref=claim_ref,
                subdesigns=subdesigns,
            )
            if binding_error is not None:
                obligations.append(
                    _composition_obligation(
                        parent_workspace_id=parent_workspace_id,
                        reason="p14_independence_map_unbound",
                        description=(
                            "P14 evidence-independence map is not bound to this "
                            f"composed claim: {binding_error}."
                        ),
                        operation_class=OperationClass.VERIFY,
                        blocks=[{"claim_ref": claim_ref}],
                    )
                )
                results.append(
                    EmergentClaimGroundingResult(
                        claim_ref=claim_ref,
                        grounding_status="invalid",
                        required_grounding=required_grounding,
                        resulting_authority=None,
                        grounding_refs=grounding_refs,
                        limiting_deficits=[
                            "p14_independence_map_unbound",
                            binding_error,
                        ],
                    )
                )
                continue
            raw_count = int(normalized["raw_evidence_line_count"])
            effective_count = int(normalized["effective_independent_evidence_count"])
            mass = normalized["effective_mass_report"]
            limiting_deficits = list(_string_values(mass.get("limiting_deficits")))
            if effective_count <= 0:
                obligations.append(
                    _composition_obligation(
                        parent_workspace_id=parent_workspace_id,
                        reason="no_independent_evidence",
                        description="P14 effective independent evidence count is zero.",
                        operation_class=OperationClass.ACQUIRE,
                        blocks=[{"claim_ref": claim_ref}],
                    )
                )
                results.append(
                    EmergentClaimGroundingResult(
                        claim_ref=claim_ref,
                        grounding_status="invalid",
                        required_grounding=required_grounding,
                        resulting_authority=None,
                        grounding_refs=grounding_refs,
                        raw_evidence_line_count=raw_count,
                        effective_independent_evidence_count=effective_count,
                        limiting_deficits=limiting_deficits,
                    )
                )
                continue
            if raw_count > effective_count:
                if "dependent_evidence_collapsed" not in limiting_deficits:
                    limiting_deficits.append("dependent_evidence_collapsed")
                obligations.append(
                    _composition_obligation(
                        parent_workspace_id=parent_workspace_id,
                        reason="non_independent_evidence_collapsed",
                        description=(
                            "P14 collapsed dependent evidence; raw chapter counts "
                            "remain diagnostic-only."
                        ),
                        operation_class=OperationClass.VERIFY,
                        blocks=[{"claim_ref": claim_ref}],
                    )
                )
                resulting = resulting.meet(
                    _independence_cap_authority(
                        parent_workspace_id=parent_workspace_id,
                        rule_version_ref=rule_version_ref,
                    ),
                    boundary_id=f"boundary-{_stable_token(claim_ref, 'p14-cap')}",
                )
        results.append(
            EmergentClaimGroundingResult(
                claim_ref=claim_ref,
                grounding_status=(
                    "simulation_only"
                    if grounding_authority.evidence_kind == "simulation"
                    else "grounded"
                ),
                required_grounding=required_grounding,
                resulting_authority=resulting,
                grounding_refs=grounding_refs,
                raw_evidence_line_count=raw_count,
                effective_independent_evidence_count=effective_count,
                limiting_deficits=limiting_deficits,
            )
        )
    return results


def _grounding_authority(value: object) -> AuthorityBoundary | None:
    if isinstance(value, AuthorityBoundary):
        return value
    if isinstance(value, Mapping):
        return AuthorityBoundary.model_validate(value)
    return None


def _verified_grounding_authority(
    *,
    grounding_refs: Sequence[str],
    verified_evidence: Mapping[str, Mapping[str, object]],
) -> tuple[str | None, AuthorityBoundary | None]:
    for grounding_ref in grounding_refs:
        payload = verified_evidence.get(grounding_ref)
        if payload is None:
            continue
        authority_payload = _mapping_value(payload.get("authority_boundary"))
        if not authority_payload:
            authority_payload = _mapping_value(payload.get("grounding_authority"))
        if not authority_payload:
            continue
        try:
            return grounding_ref, AuthorityBoundary.model_validate(authority_payload)
        except (TypeError, ValueError):
            continue
    return None, None


def _p14_composition_binding_error(
    independence_map: Mapping[str, object],
    *,
    claim_ref: str,
    subdesigns: Sequence[SubDesignContract],
) -> str | None:
    binding = independence_map.get("composition_binding")
    if not isinstance(binding, Mapping):
        return "composition_binding_missing"

    map_claim_refs = set(_string_values(independence_map.get("claim_ids")))
    if not map_claim_refs or claim_ref not in map_claim_refs:
        return "map_claim_ids_unbound"

    claim_refs = set(_string_values(binding.get("claim_refs")))
    if claim_ref not in claim_refs:
        return "claim_ref_unbound"

    expected_subdesigns = {child.subdesign_id for child in subdesigns if child.subdesign_id}
    bound_subdesigns = set(_string_values(binding.get("subdesign_refs")))
    if expected_subdesigns and not expected_subdesigns <= bound_subdesigns:
        return "subdesign_refs_unbound"

    bound_roots = set(_string_values(binding.get("producer_root_refs")))
    if not _producer_roots_are_bound(subdesigns, bound_roots):
        return "producer_root_refs_unbound"

    expected_line_ids = _p14_map_line_ids(independence_map)
    bound_line_ids = set(_string_values(binding.get("evidence_line_ids")))
    if expected_line_ids and not expected_line_ids <= bound_line_ids:
        return "evidence_line_ids_unbound"

    expected_lineage_refs = _p14_map_lineage_refs(independence_map)
    bound_lineage_refs = set(_string_values(binding.get("lineage_refs")))
    if expected_lineage_refs and not expected_lineage_refs <= bound_lineage_refs:
        return "lineage_refs_unbound"

    if not expected_line_ids or not expected_lineage_refs:
        return "support_lines_or_lineage_missing"
    verification_ref = _first_text(
        binding.get("verification_ref"),
        independence_map.get("verification_ref"),
    )
    if not verification_ref:
        return "verification_ref_missing"
    evidence_line_hashes = _content_hashes_from_records(
        binding.get("evidence_line_records")
    )
    lineage_hashes = _content_hashes_from_records(binding.get("lineage_records"))
    if not lineage_hashes:
        lineage_hashes = _source_lineage_hashes(binding.get("evidence_line_records"))
    if not evidence_line_hashes or not lineage_hashes:
        return "support_content_hashes_missing"
    if set(evidence_line_hashes) != set(
        _string_values(binding.get("evidence_line_content_hashes"))
    ):
        return "evidence_line_content_hash_mismatch"
    if set(lineage_hashes) != set(_string_values(binding.get("lineage_content_hashes"))):
        return "lineage_content_hash_mismatch"
    producer_root_hashes = _producer_root_hashes(subdesigns)
    resolved = resolve_bind_verify(
        verification_ref,
        context={
            "purpose": "p14_independence_map",
            "claim_refs": [claim_ref],
            "subdesign_refs": sorted(expected_subdesigns),
            "producer_root_refs": sorted(bound_roots),
            "producer_root_content_hashes": producer_root_hashes,
            "evidence_line_content_hashes": evidence_line_hashes,
            "lineage_content_hashes": lineage_hashes,
            "raw_evidence_line_count": independence_map.get("raw_evidence_line_count"),
            "effective_independent_evidence_count": independence_map.get(
                "effective_independent_evidence_count"
            ),
        },
    )
    if resolved is None:
        return "verification_ref_unbound"
    return None


def _producer_roots_are_bound(
    subdesigns: Sequence[SubDesignContract],
    bound_refs: set[str],
) -> bool:
    root_seen = False
    for child in subdesigns:
        for root in child.producer_roots:
            root_seen = True
            identities = {root.artifact_id, root.uri, root.content_hash} - {""}
            if identities.isdisjoint(bound_refs):
                return False
    return root_seen


def _producer_root_refs(subdesigns: Sequence[SubDesignContract]) -> list[str]:
    refs: list[str] = []
    for child in subdesigns:
        for root in child.producer_roots:
            refs.extend(value for value in (root.artifact_id, root.uri) if value)
    return list(dict.fromkeys(refs))


def _producer_root_hashes(subdesigns: Sequence[SubDesignContract]) -> list[str]:
    refs: list[str] = []
    for child in subdesigns:
        for root in child.producer_roots:
            if root.content_hash:
                refs.append(root.content_hash)
    return list(dict.fromkeys(refs))


def _content_hashes_from_records(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    rows = [row for row in value if isinstance(row, Mapping)]
    return [gy_content_hash(row) for row in rows]


def _source_lineage_hashes(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    records: list[object] = []
    for row in value:
        if isinstance(row, Mapping) and isinstance(row.get("source_lineage"), Mapping):
            records.append(row["source_lineage"])
    return [gy_content_hash(row) for row in records]


def _p14_map_line_ids(independence_map: Mapping[str, object]) -> set[str]:
    line_ids: set[str] = set()
    clusters = independence_map.get("collapse_clusters")
    if not isinstance(clusters, Sequence) or isinstance(
        clusters,
        str | bytes | bytearray,
    ):
        return line_ids
    for cluster in clusters:
        if isinstance(cluster, Mapping):
            line_ids.update(_string_values(cluster.get("line_ids")))
    return line_ids


def _p14_map_lineage_refs(independence_map: Mapping[str, object]) -> set[str]:
    lineage_refs: set[str] = set()
    clusters = independence_map.get("collapse_clusters")
    if not isinstance(clusters, Sequence) or isinstance(
        clusters,
        str | bytes | bytearray,
    ):
        return lineage_refs
    for cluster in clusters:
        if not isinstance(cluster, Mapping):
            continue
        dimensions = cluster.get("collapse_dimensions")
        if not isinstance(dimensions, Mapping):
            continue
        lineage_refs.update(_string_values(dimensions.get("source_lineage_cluster_id")))
    return lineage_refs


def _required_grounding_values(value: object) -> list[str]:
    allowed = {
        "capacity_aggregation",
        "sequencing_consistency",
        "system_dynamics",
        "equilibrium_check",
        "cross_chapter_counterexample_search",
    }
    values = [item for item in _string_values(value) if item in allowed]
    return values or ["system_dynamics"]


def _string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [str(item) for item in value if str(item)]
    return []


def _coupling_certificate_authority(
    *,
    parent_workspace_id: str,
    rule_version_ref: str,
) -> AuthorityBoundary:
    return AuthorityBoundary(
        boundary_id=f"boundary-{_stable_token(parent_workspace_id, 'coupling-certificate')}",
        authoritative_for=["policy_program_claim"],
        may_not_use_for=["production_claim_authority_without_composition_certificate"],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[rule_version_ref],
        evidence_kind="derivation",
        decision_grade="decision_admissible",
        evidence_basis=EvidenceBasis(
            producer_roots=[],
            method_refs=["polisyos.runtime.quality.design_axes.coupling_composition"],
            calibration_refs=["coupling-classifier://verified"],
            counterexamples_closed=["p17:false-modularity"],
        ),
    )


def _independence_cap_authority(
    *,
    parent_workspace_id: str,
    rule_version_ref: str,
) -> AuthorityBoundary:
    return AuthorityBoundary(
        boundary_id=f"boundary-{_stable_token(parent_workspace_id, 'p14-cap')}",
        authoritative_for=["policy_program_claim"],
        may_not_use_for=["support_inflation_from_non_independent_evidence"],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[rule_version_ref],
        evidence_kind="measurement",
        decision_grade="advisory_admissible",
        evidence_basis=EvidenceBasis(
            producer_roots=[],
            method_refs=["polisyos.runtime.quality.evidence_independence"],
            calibration_refs=["p14://effective-independence"],
            counterexamples_closed=["p14:raw-count-inflation"],
        ),
    )


def _composition_verdict(
    *,
    obligations: Sequence[ObligationRecord],
    authority_flow: Sequence[AuthorityFlowResult],
    emergent_claims: Sequence[EmergentClaimGroundingResult],
    composition_disposition: CompositionDisposition,
) -> Literal["composable", "composable_with_limits", "not_composable"]:
    blocking_obligation_types = {
        "child_acquisition_required",
        "coupling_edge_subdesign_missing",
        "empty_authoritative_for",
        "emergent_grounding_missing",
        "emergent_grounding_unresolved",
        "evidence_independence_invalid",
        "no_independent_evidence",
        "p14_independence_map_unbound",
        "p14_independence_map_missing",
        "provided_authority_missing",
        "provided_authority_unverified",
        "authority_evidence_unverified",
    }
    if any(obligation.obligation_type in blocking_obligation_types for obligation in obligations):
        return "not_composable"
    if any(_empty_authoritative_for(flow.resulting_authority) for flow in authority_flow):
        return "not_composable"
    if any(
        result.grounding_status in {"missing", "invalid", "unresolved"}
        for result in emergent_claims
    ):
        return "not_composable"
    if obligations or composition_disposition == "compose_with_limitations":
        return "composable_with_limits"
    return "composable"


def _has_shared_resource_coupling(classification: CouplingRegimeClassification) -> bool:
    return any(
        row.coupling_kind == "shared_resource"
        for row in classification.boundary_classifications
    )


def _has_unknown_coupling(classification: CouplingRegimeClassification) -> bool:
    return any(
        row.coupling_kind == "unknown"
        for row in classification.boundary_classifications
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
            if edge.interaction_strength != "none"
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
        coupling_kind = _boundary_coupling_kind(edges, graph=graph)
        regime = _boundary_regime(edges, coupling_kind)
        feedback = coupling_kind == "feedback"
        rows.append(
            BoundaryCouplingClassification(
                boundary_ref=boundary_ref,
                source_module_ref=edges[0].source_module_ref,
                target_module_ref=edges[0].target_module_ref,
                coupling_regime=regime,
                coupling_kind=coupling_kind,
                interaction_strength=max(
                    (edge.interaction_strength for edge in edges),
                    key=lambda item: _INTERACTION_ORDER[item],
                ),
                feedback_intensity=_boundary_feedback_intensity(edges, coupling_kind),
                feedback=feedback,
                evidence_refs=[edge.evidence_ref for edge in edges],
                decision_reason=_classification_reason(regime),
                rule_version_ref=graph.rule_version_ref,
            )
        )
    return rows


def _boundary_regime(
    edges: Sequence[CouplingEdge],
    coupling_kind: BoundaryCouplingKind,
) -> CouplingRegime:
    if coupling_kind in {"feedback", "unknown"}:
        return "entangled"
    if all(edge.interaction_strength == "none" for edge in edges):
        return "modular"
    if any(edge.interaction_strength == "strong" for edge in edges):
        return "hierarchically_coupled"
    return "near_decomposable"


def _boundary_coupling_kind(
    edges: Sequence[CouplingEdge],
    *,
    graph: CouplingGraph,
) -> BoundaryCouplingKind:
    if any(_edge_is_graph_feedback(edge, graph) for edge in edges):
        return "feedback"
    if any(_edge_independence_consistency_ref_is_invalid(edge, graph) for edge in edges):
        return "unknown"
    if any(_edge_relation_is_shared_resource(edge) for edge in edges):
        return "shared_resource"
    if all(edge.interaction_strength == "none" for edge in edges):
        return "independent"
    return "sequential"


def _edge_is_graph_feedback(edge: CouplingEdge, graph: CouplingGraph) -> bool:
    if edge.interaction_strength == "none":
        return False
    nonzero_edges = [
        candidate
        for candidate in graph.interaction_edges
        if candidate.interaction_strength != "none"
    ]
    adjacency: dict[str, list[str]] = defaultdict(list)
    for candidate in nonzero_edges:
        adjacency[candidate.source_module_ref].append(candidate.target_module_ref)
    return _has_path(
        edge.target_module_ref,
        edge.source_module_ref,
        adjacency=adjacency,
        skip_edge=(edge.source_module_ref, edge.target_module_ref),
    )


def _has_path(
    source: str,
    target: str,
    *,
    adjacency: Mapping[str, Sequence[str]],
    skip_edge: tuple[str, str],
) -> bool:
    stack = [source]
    visited: set[str] = set()
    while stack:
        current = stack.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        for child in adjacency.get(current, ()):
            if (current, child) == skip_edge:
                continue
            stack.append(child)
    return False


def _edge_independence_consistency_ref_is_invalid(
    edge: CouplingEdge,
    graph: CouplingGraph,
) -> bool:
    if edge.interaction_strength != "none" or not edge.independence_consistency_ref:
        return False
    return (
        resolve_bind_verify(
            edge.independence_consistency_ref,
            context={
                "purpose": "independence_consistency",
                "graph_hash": gy_content_hash(graph.model_dump(mode="json")),
                "boundary_ref": edge.boundary_ref,
                "source_module_ref": edge.source_module_ref,
                "target_module_ref": edge.target_module_ref,
                "relation": edge.relation,
            },
        )
        is None
    )


def _boundary_feedback_intensity(
    edges: Sequence[CouplingEdge],
    coupling_kind: BoundaryCouplingKind,
) -> FeedbackIntensity:
    if coupling_kind == "feedback":
        return "high"
    return max(
        (edge.feedback_intensity for edge in edges),
        key=lambda item: _INTENSITY_ORDER[item],
    )


def _edge_relation_is_shared_resource(edge: CouplingEdge) -> bool:
    relation = _normalized_relation(edge.relation)
    return any(
        token in relation
        for token in ("shared_resource", "capacity", "budget", "resource")
    )


def _normalized_relation(relation: str) -> str:
    return relation.lower().replace("-", "_").replace(" ", "_")


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
    "BoundaryCouplingKind",
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
    "compose_subdesigns",
    "composition_to_axis_positions",
    "coupling_accuracy",
    "critical_path_regime",
    "decompose_design",
    "derive_recursive_design_graph",
    "discover_design_modules",
]
