"""Layer 2 S6 fail-closed blind-spot firewall contracts and producers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from polisyos.pdc import (
    AuthorityBoundary,
    AxisFirewallStatus,
    AxisPositionDeclaration,
    Layer2ReadinessModel,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.semantic_binding import SemanticBindingLedger

LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s6_blind_spot_firewalls.v1"
)

BlindSpotAxis = Literal[
    "measurability",
    "subject_granularity",
    "state_capacity_feasibility",
    "mandate_legitimacy",
    "strategic_response",
]
AxisFailClosedDisposition = Literal["pass", "limit", "block"]
ConstructMeasurabilityStatus = Literal["observed", "proxy_only", "qualitative", "missing"]
ProxyValidityDisposition = Literal[
    "valid_proxy",
    "limited_proxy",
    "invalid_proxy",
    "not_applicable",
]
AggregationClaimLevel = Literal[
    "individual",
    "household",
    "firm",
    "group",
    "jurisdiction",
    "system",
]
AggregationValidityDisposition = Literal[
    "valid",
    "limited",
    "block_ecological_error",
    "block_simpson_risk",
]
CapacityDimension = Literal[
    "administrative",
    "fiscal",
    "enforcement",
    "delivery",
    "coordination",
    "political_feasibility",
    "institutional_credibility",
    "participation_capacity",
]
CapacityDisposition = Literal[
    "grounded",
    "capacity_building_required",
    "limited",
    "blocked",
]
MandateBasis = Literal[
    "statutory",
    "delegated",
    "participatory",
    "affected_person",
    "governance_board",
    "absent",
]
LegitimacyDisposition = Literal["grounded", "limited", "candidate_unverified", "blocked"]
StrategicResponseChannel = Literal[
    "goodhart",
    "lucas_performativity",
    "capture",
    "sabotage",
    "gaming",
    "adaptation",
    "compliance_response",
]
StrategicResponseDisposition = Literal[
    "modeled",
    "limited",
    "system_dynamics_required",
    "blocked",
]
BlindSpotOverallPosture = Literal["clear_fail_closed", "limited", "blocked"]
ConstraintRefinementRoute = Literal[
    "none",
    "acquire",
    "reframe",
    "human_decision",
    "block_candidate",
    "pending_consumer_constraint",
]
ConstraintStatus = Literal["pass", "warn", "limit", "block"]
SourceAuthority = Literal[
    "deterministic_producer",
    "governed_config",
    "human_governance",
    "llm_candidate",
    "llm_critic",
    "llm_drafter",
]

_S6_CELL_BY_AXIS: dict[BlindSpotAxis, str] = {
    "measurability": "SYSTEM.measurability",
    "subject_granularity": "SYSTEM.subject_granularity",
    "state_capacity_feasibility": "ACTOR.state_capacity_feasibility",
    "mandate_legitimacy": "ACTOR.mandate_legitimacy",
    "strategic_response": "OTHER_AGENTS.strategic_response",
}
_AXIS_BY_CELL: dict[str, BlindSpotAxis] = {cell: axis for axis, cell in _S6_CELL_BY_AXIS.items()}
_PATTERN_BY_AXIS: dict[BlindSpotAxis, str] = {
    "measurability": "P18",
    "subject_granularity": "P19",
    "state_capacity_feasibility": "P21",
    "mandate_legitimacy": "P22",
    "strategic_response": "P24",
}
_REPLAY_REF_SUFFIX_BY_AXIS: dict[BlindSpotAxis, str] = {
    "measurability": "measurability-adequacy",
    "subject_granularity": "aggregation-validity",
    "state_capacity_feasibility": "capacity-feasibility",
    "mandate_legitimacy": "mandate-legitimacy",
    "strategic_response": "strategic-response",
}
_C3_DIMENSIONS_BY_AXIS: dict[BlindSpotAxis, tuple[str, ...]] = {
    "measurability": ("measurability_adequacy",),
    "subject_granularity": ("aggregation_validity",),
    "state_capacity_feasibility": ("capacity_feasibility",),
    "mandate_legitimacy": ("mandate_legitimacy",),
    "strategic_response": ("strategic_robustness", "response_model_validity"),
}
_BRIDGE_CONSUMERS_BY_AXIS: dict[BlindSpotAxis, tuple[str, ...]] = {
    "measurability": ("KNOWLEDGE.epistemic_regime", "ACTOR.value_choice_provenance"),
    "subject_granularity": ("INTERVENTION.targeting", "KNOWLEDGE.epistemic_regime"),
    "state_capacity_feasibility": (
        "INTERVENTION.feasibility",
        "DESIGNER_ITSELF.envelope_membership",
    ),
    "mandate_legitimacy": (
        "ACTOR.value_choice_provenance",
        "PUBLIC.legitimacy_disclosure",
        "INTERVENTION.design_candidate",
    ),
    "strategic_response": (
        "SYSTEM.post_intervention_dgp",
        "SYSTEM.dynamics_feedback",
        "INTERVENTION.robustness",
    ),
}


class P18StreetlightMeasurabilityError(ValueError):
    """Proxy measurability claimed as value coverage without disclosure."""


class P19AggregationLaunderingError(ValueError):
    """Evidence scope was laundered into a different claim scope."""


class P21CapacityFeasibilityError(ValueError):
    """Capacity feasibility was claimed from unsupported or copied assumptions."""


class P22MandateLegitimacyError(ValueError):
    """Mandate or legitimacy authority was inferred from unverified prose."""


class P24StrategicResponseError(ValueError):
    """Pre-policy effects were transported across unresolved strategic response."""


class ConstructMeasurabilityRow(Layer2ReadinessModel):
    """Per-construct S6 measurability row wrapped from semantic-binding evidence."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    construct_ref: str = Field(..., min_length=1, max_length=300)
    construct_label: str = Field(default="", max_length=200)
    measurability_status: ConstructMeasurabilityStatus
    proxy_validity: ProxyValidityDisposition = "not_applicable"
    proxy_ref: str | None = Field(default=None, max_length=300)
    value_loss_disclosure_ref: str | None = Field(default=None, max_length=300)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    declared_as_value_construct_complete: bool = False
    rule_version_ref: str = Field(default="", max_length=300)


class ProxyValidityRecord(Layer2ReadinessModel):
    """Proxy-validity row for a construct that is not directly observed."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    proxy_record_ref: str = Field(..., min_length=1, max_length=300)
    construct_ref: str = Field(..., min_length=1, max_length=300)
    proxy_ref: str | None = Field(default=None, max_length=300)
    disposition: ProxyValidityDisposition
    value_loss_disclosure_ref: str | None = Field(default=None, max_length=300)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class ValueLossDisclosure(Layer2ReadinessModel):
    """Replayable limitation that prevents proxy/value equivalence laundering."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    disclosure_ref: str = Field(..., min_length=1, max_length=300)
    construct_ref: str = Field(..., min_length=1, max_length=300)
    proxy_ref: str | None = Field(default=None, max_length=300)
    limitation_ref: str = Field(..., min_length=1, max_length=300)
    disclosure_text: str = Field(..., min_length=1, max_length=500)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class AggregationScopeRow(Layer2ReadinessModel):
    """Per-claim aggregation validity row wrapped from concept-spine evidence."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    claim_scope: AggregationClaimLevel
    evidence_scope: AggregationClaimLevel
    population_ref: str | None = Field(default=None, max_length=300)
    subgroup_ref: str | None = Field(default=None, max_length=300)
    aggregation_validity: AggregationValidityDisposition
    simpson_risk: bool = False
    subgroup_harm_hidden: bool = False
    validity_proof_ref: str | None = Field(default=None, max_length=300)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    rule_version_ref: str = Field(default="", max_length=300)


class CapacityDimensionAssessment(Layer2ReadinessModel):
    """Capacity assessment for one required actor/jurisdiction capability dimension."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    dimension: CapacityDimension
    required: bool = True
    disposition: CapacityDisposition
    evidence_ref: str | None = Field(default=None, max_length=300)
    copied_from_actor_ref: str | None = Field(default=None, max_length=300)
    copied_from_jurisdiction_ref: str | None = Field(default=None, max_length=300)
    capacity_building_obligation_ref: str | None = Field(default=None, max_length=300)
    reason: str = Field(default="", max_length=500)
    rule_version_ref: str = Field(default="", max_length=300)


class CapacityBuildingObligation(Layer2ReadinessModel):
    """Obligation emitted when implementation depends on absent capacity."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    obligation_ref: str = Field(..., min_length=1, max_length=300)
    dimension: CapacityDimension
    actor_ref: str = Field(..., min_length=1, max_length=300)
    jurisdiction_ref: str = Field(..., min_length=1, max_length=300)
    instrument_ref: str = Field(..., min_length=1, max_length=300)
    reason: str = Field(..., min_length=1, max_length=500)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class MandateSourceRecord(Layer2ReadinessModel):
    """Mandate source row preserving provenance and candidate/authority separation."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    basis: MandateBasis
    source_authority: SourceAuthority
    source_ref: str = Field(..., min_length=1, max_length=300)
    provenance_ref: str | None = Field(default=None, max_length=300)
    disposition: LegitimacyDisposition
    authorized_objective_refs: list[str] = Field(default_factory=list, max_length=20)
    reason: str = Field(default="", max_length=500)
    rule_version_ref: str = Field(default="", max_length=300)


class ParticipationProvenanceRow(Layer2ReadinessModel):
    """Participation or consultation evidence row consumed by S6 mandate checks."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    provenance_ref: str = Field(..., min_length=1, max_length=300)
    source_ref: str | None = Field(default=None, max_length=300)
    claim_use_allowed: bool = False
    blocker_refs: list[str] = Field(default_factory=list, max_length=20)
    unresolved_high_severity_objection: bool = False
    rule_version_ref: str = Field(default="", max_length=300)


class StrategicResponseChannelAssessment(Layer2ReadinessModel):
    """Per-channel S6 response-risk row over Goodhart/Lucas/capture/gaming evidence."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    channel: StrategicResponseChannel
    disposition: StrategicResponseDisposition
    risk_level: Literal["none", "low", "medium", "high"] = "medium"
    response_model_ref: str | None = Field(default=None, max_length=300)
    post_intervention_dgp_update_ref: str | None = Field(default=None, max_length=300)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    reason: str = Field(default="", max_length=500)
    rule_version_ref: str = Field(default="", max_length=300)


class PostInterventionDGPUpdate(Layer2ReadinessModel):
    """Handoff showing that response risk changes the post-intervention DGP."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    update_ref: str = Field(..., min_length=1, max_length=300)
    design_ref: str = Field(..., min_length=1, max_length=300)
    channel_refs: list[str] = Field(default_factory=list, max_length=20)
    pre_policy_effect_refs: list[str] = Field(default_factory=list, max_length=20)
    reason: str = Field(..., min_length=1, max_length=500)
    system_dynamics_handoff_required: bool
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class MeasurabilityAdequacyRecord(Layer2ReadinessModel):
    """Top-level S6 measurability adequacy artifact for `SYSTEM.measurability`."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=120)
    record_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=120)
    design_ref: str = Field(..., min_length=1, max_length=300)
    axis: Literal["measurability"] = "measurability"
    cell_ref: Literal["SYSTEM.measurability"] = "SYSTEM.measurability"
    construct_rows: list[ConstructMeasurabilityRow] = Field(default_factory=list, max_length=80)
    proxy_validity_records: list[ProxyValidityRecord] = Field(default_factory=list, max_length=80)
    value_loss_disclosures: list[ValueLossDisclosure] = Field(default_factory=list, max_length=80)
    semantic_binding_ledger_ref: str | None = Field(default=None, max_length=300)
    firewall_pattern_id: Literal["P18"] = "P18"
    firewall_disposition: AxisFailClosedDisposition
    decision_reason: str = Field(..., min_length=1, max_length=500)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class AggregationValidityRecord(Layer2ReadinessModel):
    """Top-level S6 aggregation validity artifact for `SYSTEM.subject_granularity`."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=120)
    record_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=120)
    design_ref: str = Field(..., min_length=1, max_length=300)
    axis: Literal["subject_granularity"] = "subject_granularity"
    cell_ref: Literal["SYSTEM.subject_granularity"] = "SYSTEM.subject_granularity"
    claim_scope: AggregationClaimLevel
    evidence_scope: AggregationClaimLevel
    aggregation_rows: list[AggregationScopeRow] = Field(default_factory=list, max_length=80)
    concept_spine_carrier_ref: str | None = Field(default=None, max_length=300)
    firewall_pattern_id: Literal["P19"] = "P19"
    firewall_disposition: AxisFailClosedDisposition
    decision_reason: str = Field(..., min_length=1, max_length=500)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class CapacityFeasibilityRecord(Layer2ReadinessModel):
    """Top-level S6 capacity feasibility artifact for actor implementability."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=120)
    record_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=120)
    design_ref: str = Field(..., min_length=1, max_length=300)
    axis: Literal["state_capacity_feasibility"] = "state_capacity_feasibility"
    cell_ref: Literal["ACTOR.state_capacity_feasibility"] = "ACTOR.state_capacity_feasibility"
    actor_ref: str = Field(..., min_length=1, max_length=300)
    jurisdiction_ref: str = Field(..., min_length=1, max_length=300)
    instrument_ref: str = Field(..., min_length=1, max_length=300)
    capacity_dimensions: list[CapacityDimensionAssessment] = Field(
        default_factory=list,
        max_length=80,
    )
    capacity_building_obligations: list[CapacityBuildingObligation] = Field(
        default_factory=list,
        max_length=80,
    )
    firewall_pattern_id: Literal["P21"] = "P21"
    firewall_disposition: AxisFailClosedDisposition
    decision_reason: str = Field(..., min_length=1, max_length=500)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class MandateLegitimacyRecord(Layer2ReadinessModel):
    """Top-level S6 mandate legitimacy artifact for objective/weight closure."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=120)
    record_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=120)
    design_ref: str = Field(..., min_length=1, max_length=300)
    axis: Literal["mandate_legitimacy"] = "mandate_legitimacy"
    cell_ref: Literal["ACTOR.mandate_legitimacy"] = "ACTOR.mandate_legitimacy"
    objective_refs: list[str] = Field(default_factory=list, max_length=40)
    mandate_sources: list[MandateSourceRecord] = Field(default_factory=list, max_length=80)
    participation_provenance: list[ParticipationProvenanceRow] = Field(
        default_factory=list,
        max_length=80,
    )
    consultation_provenance: list[ParticipationProvenanceRow] = Field(
        default_factory=list,
        max_length=80,
    )
    firewall_pattern_id: Literal["P22"] = "P22"
    firewall_disposition: AxisFailClosedDisposition
    decision_reason: str = Field(..., min_length=1, max_length=500)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class StrategicResponseRecord(Layer2ReadinessModel):
    """Top-level S6 strategic-response artifact for post-intervention DGP validity."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=120)
    record_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=120)
    design_ref: str = Field(..., min_length=1, max_length=300)
    axis: Literal["strategic_response"] = "strategic_response"
    cell_ref: Literal["OTHER_AGENTS.strategic_response"] = "OTHER_AGENTS.strategic_response"
    response_channels: list[StrategicResponseChannelAssessment] = Field(
        default_factory=list,
        max_length=80,
    )
    pre_policy_effect_refs: list[str] = Field(default_factory=list, max_length=40)
    strategic_response_entry_refs: list[str] = Field(default_factory=list, max_length=40)
    post_intervention_dgp_update: PostInterventionDGPUpdate | None = None
    post_intervention_dgp_update_ref: str | None = Field(default=None, max_length=300)
    system_dynamics_handoff_required: bool = False
    firewall_pattern_id: Literal["P24"] = "P24"
    firewall_disposition: AxisFailClosedDisposition
    decision_reason: str = Field(..., min_length=1, max_length=500)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class ClusterAuthorityDimensionRecord(Layer2ReadinessModel):
    """S6 row binding a closed cell to a canonical C3 authority dimension."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    dimension_id: str = Field(..., min_length=1, max_length=160)
    dimension_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=120)
    cell_ref: str = Field(..., min_length=3, max_length=200)
    authority_dimension: Literal[
        "measurability_adequacy",
        "aggregation_validity",
        "capacity_feasibility",
        "mandate_legitimacy",
        "strategic_robustness",
        "response_model_validity",
    ]
    producer_ref: str = Field(..., min_length=1, max_length=300)
    firewall_pattern_id: Literal["P18", "P19", "P21", "P22", "P24"]
    disposition: AxisFailClosedDisposition
    maturity: Literal["fail_closed"] = "fail_closed"
    evidence_refs: list[str] = Field(default_factory=list, max_length=40)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class BlindSpotBridgeConsumerRecord(Layer2ReadinessModel):
    """Report row showing the consumer that must receive an S6 constraint or handoff."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    bridge_ref: str = Field(..., min_length=1, max_length=300)
    cell_ref: str = Field(..., min_length=3, max_length=200)
    consumer_ref: str = Field(..., min_length=1, max_length=200)
    producer_ref: str = Field(..., min_length=1, max_length=300)
    disposition: AxisFailClosedDisposition
    pending_consumer: bool = False
    constraint_ref: str = Field(..., min_length=1, max_length=300)
    handoff_reason: str = Field(..., min_length=1, max_length=500)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class BlindSpotConstraintStoreUpdate(Layer2ReadinessModel):
    """Typed S6 constraint update later mapped into the S2 constraint store."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    constraint_id: str = Field(..., min_length=1, max_length=160)
    cell_ref: str = Field(..., min_length=3, max_length=200)
    status: ConstraintStatus
    source_ref: str = Field(..., min_length=1, max_length=300)
    consumer_ref: str = Field(..., min_length=1, max_length=200)
    refinement_route: ConstraintRefinementRoute
    evidence_refs: list[str] = Field(default_factory=list, max_length=40)
    reason: str = Field(..., min_length=1, max_length=500)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class BlindSpotFirewallReport(Layer2ReadinessModel):
    """Aggregate S6 fail-closed report consumed by orchestration and S2 injection."""

    schema_version: str = LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION
    report_id: str = Field(..., min_length=1, max_length=120)
    report_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=120)
    design_ref: str = Field(..., min_length=1, max_length=300)
    maturity: Literal["fail_closed"] = "fail_closed"
    overall_posture: BlindSpotOverallPosture
    measurability: MeasurabilityAdequacyRecord
    aggregation: AggregationValidityRecord
    capacity: CapacityFeasibilityRecord
    mandate: MandateLegitimacyRecord
    strategic_response: StrategicResponseRecord
    axis_rows: list[dict[str, object]] = Field(default_factory=list, max_length=10)
    ledger_refs: list[str] = Field(default_factory=list, max_length=40)
    bridge_consumer_rows: list[BlindSpotBridgeConsumerRecord] = Field(
        default_factory=list,
        max_length=20,
    )
    constraint_store_updates: list[BlindSpotConstraintStoreUpdate] = Field(
        default_factory=list,
        max_length=40,
    )
    c3_authority_dimension_rows: list[ClusterAuthorityDimensionRecord] = Field(
        default_factory=list,
        max_length=10,
    )
    blocking_axis_refs: list[str] = Field(default_factory=list, max_length=10)
    limiting_axis_refs: list[str] = Field(default_factory=list, max_length=10)
    post_intervention_dgp_update_ref: str | None = Field(default=None, max_length=300)
    system_dynamics_handoff_required: bool = False
    regime_reissue_required: bool = False
    false_clear_penalty: float = Field(default=0.0, ge=0.0)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


def evaluate_measurability_adequacy(
    *,
    case_id: str,
    design_ref: str,
    construct_rows: Sequence[Mapping[str, object]],
    semantic_binding_ledger: SemanticBindingLedger | Mapping[str, object] | None = None,
    rule_version_ref: str,
    authority_boundary: AuthorityBoundary | None = None,
) -> MeasurabilityAdequacyRecord:
    """Evaluate construct-level measurability without treating proxies as authority."""

    rows = [
        ConstructMeasurabilityRow.model_validate(
            {**_as_mapping(row), "rule_version_ref": rule_version_ref},
        )
        for row in construct_rows
    ]
    ledger_ref = _payload_ref(semantic_binding_ledger, ("ledger_ref", "ledger_id", "record_ref"))
    declared_pass = bool(_payload_value(semantic_binding_ledger, "declared_measurability_pass"))
    problematic = [
        row
        for row in rows
        if row.measurability_status in {"proxy_only", "qualitative", "missing"}
        and (row.value_loss_disclosure_ref is None or row.proxy_validity in {"invalid_proxy"})
    ]
    if declared_pass and problematic:
        raise P18StreetlightMeasurabilityError(
            "P18 streetlight proxy/value laundering: proxy or unmeasured value construct "
            "requires value-loss disclosure before measurability can pass"
        )

    proxy_records = [
        ProxyValidityRecord(
            proxy_record_ref=f"{_record_ref(case_id, 'measurability')}/proxy/{idx}",
            construct_ref=row.construct_ref,
            proxy_ref=row.proxy_ref,
            disposition=row.proxy_validity,
            value_loss_disclosure_ref=row.value_loss_disclosure_ref,
            evidence_refs=row.evidence_refs,
            rule_version_ref=rule_version_ref,
        )
        for idx, row in enumerate(rows, start=1)
        if row.measurability_status == "proxy_only"
    ]
    disclosures = [
        ValueLossDisclosure(
            disclosure_ref=row.value_loss_disclosure_ref
            or f"{_record_ref(case_id, 'measurability')}/value-loss/{idx}",
            construct_ref=row.construct_ref,
            proxy_ref=row.proxy_ref,
            limitation_ref=f"limitation://layer2/s6/{case_id}/measurability/{idx}",
            disclosure_text=(
                f"{row.construct_ref} is {row.measurability_status}; proxy/value equivalence "
                "is limited until disclosed and validated."
            ),
            rule_version_ref=rule_version_ref,
        )
        for idx, row in enumerate(rows, start=1)
        if row.measurability_status in {"proxy_only", "qualitative", "missing"}
    ]

    if not rows:
        disposition: AxisFailClosedDisposition = "block"
        reason = "measurability evidence is absent; missing axis evidence cannot pass"
    elif problematic:
        disposition = "block"
        reason = "proxy-only, qualitative, or missing value constructs lack valid disclosure"
    elif any(row.measurability_status != "observed" for row in rows):
        disposition = "limit"
        reason = "non-observed constructs are disclosed as limitations"
    else:
        disposition = "pass"
        reason = "all declared constructs are observed or validly accounted for"

    return MeasurabilityAdequacyRecord(
        record_id=f"layer2.s6.measurability.{_stable_token(case_id)}",
        record_ref=_record_ref(case_id, "measurability"),
        case_id=case_id,
        design_ref=design_ref,
        construct_rows=rows,
        proxy_validity_records=proxy_records,
        value_loss_disclosures=disclosures,
        semantic_binding_ledger_ref=ledger_ref,
        firewall_disposition=disposition,
        decision_reason=reason,
        authority_boundary=authority_boundary
        or _authority_boundary(
            authoritative_for=["measurability_adequacy"],
            may_not_use_for=["proxy_construct_equivalence_without_disclosure"],
            rule_version_ref=rule_version_ref,
        ),
        rule_version_ref=rule_version_ref,
    )


def evaluate_aggregation_validity(
    *,
    case_id: str,
    design_ref: str,
    claim_scope: AggregationClaimLevel,
    evidence_scope: AggregationClaimLevel,
    aggregation_rows: Sequence[Mapping[str, object]],
    concept_spine_carrier: Mapping[str, object] | None = None,
    rule_version_ref: str,
    authority_boundary: AuthorityBoundary | None = None,
) -> AggregationValidityRecord:
    """Evaluate whether evidence granularity can close the claim granularity."""

    rows = [
        AggregationScopeRow.model_validate(
            {**_as_mapping(row), "rule_version_ref": rule_version_ref},
        )
        for row in aggregation_rows
    ]
    declared_pass = bool(_payload_value(concept_spine_carrier, "declared_aggregation_pass"))
    carrier_ref = _payload_ref(concept_spine_carrier, ("carrier_ref", "record_ref", "spine_ref"))
    scope_mismatch = claim_scope != evidence_scope
    blocking_rows = [
        row
        for row in rows
        if row.aggregation_validity in {"block_ecological_error", "block_simpson_risk"}
        or row.simpson_risk
        or row.subgroup_harm_hidden
    ]
    missing_proof = scope_mismatch and not any(row.validity_proof_ref for row in rows)
    if declared_pass and (blocking_rows or missing_proof):
        raise P19AggregationLaunderingError(
            "P19 aggregation scope laundering: claim scope and evidence scope diverge without "
            "aggregation validity proof"
        )

    if not rows:
        disposition: AxisFailClosedDisposition = "block"
        reason = "aggregation evidence is absent; missing axis evidence cannot pass"
    elif blocking_rows or missing_proof:
        disposition = "block"
        reason = "aggregation scope drift creates ecological-error or Simpson-risk blocker"
    elif any(row.aggregation_validity == "limited" for row in rows) or scope_mismatch:
        disposition = "limit"
        reason = "aggregation validity is scoped and must be projected as a limitation"
    else:
        disposition = "pass"
        reason = "claim scope and evidence scope are validly aligned"

    return AggregationValidityRecord(
        record_id=f"layer2.s6.aggregation.{_stable_token(case_id)}",
        record_ref=_record_ref(case_id, "subject_granularity"),
        case_id=case_id,
        design_ref=design_ref,
        claim_scope=claim_scope,
        evidence_scope=evidence_scope,
        aggregation_rows=rows,
        concept_spine_carrier_ref=carrier_ref,
        firewall_disposition=disposition,
        decision_reason=reason,
        authority_boundary=authority_boundary
        or _authority_boundary(
            authoritative_for=["aggregation_validity"],
            may_not_use_for=["aggregation_scope_transfer_without_validity"],
            rule_version_ref=rule_version_ref,
        ),
        rule_version_ref=rule_version_ref,
    )


def evaluate_capacity_feasibility(
    *,
    case_id: str,
    design_ref: str,
    actor_ref: str,
    jurisdiction_ref: str,
    instrument_ref: str,
    capacity_dimensions: Sequence[Mapping[str, object]],
    rule_version_ref: str,
    authority_boundary: AuthorityBoundary | None = None,
) -> CapacityFeasibilityRecord:
    """Evaluate actor/jurisdiction capacity and fail closed on unsupported assumptions."""

    dimensions = [
        CapacityDimensionAssessment.model_validate(
            {**_as_mapping(row), "rule_version_ref": rule_version_ref},
        )
        for row in capacity_dimensions
    ]
    unsupported_without_obligation = [
        row
        for row in dimensions
        if row.required
        and (
            row.disposition == "blocked"
            or row.evidence_ref is None
            or _copied_capacity(row, actor_ref=actor_ref, jurisdiction_ref=jurisdiction_ref)
        )
        and row.capacity_building_obligation_ref is None
    ]
    if unsupported_without_obligation:
        raise P21CapacityFeasibilityError(
            "P21 capacity feasibility laundering: required capacity is absent, unsupported, "
            "or copied across actor/jurisdiction without a capacity-building obligation"
        )

    obligations = [
        CapacityBuildingObligation(
            obligation_ref=row.capacity_building_obligation_ref
            or f"{_record_ref(case_id, 'state_capacity_feasibility')}/capacity-building/{idx}",
            dimension=row.dimension,
            actor_ref=actor_ref,
            jurisdiction_ref=jurisdiction_ref,
            instrument_ref=instrument_ref,
            reason=row.reason or f"{row.dimension} capacity requires building before rollout",
            evidence_refs=[row.evidence_ref] if row.evidence_ref else [],
            rule_version_ref=rule_version_ref,
        )
        for idx, row in enumerate(dimensions, start=1)
        if row.capacity_building_obligation_ref or row.disposition == "capacity_building_required"
    ]

    if not dimensions:
        disposition: AxisFailClosedDisposition = "block"
        reason = "capacity evidence is absent; missing axis evidence cannot pass"
    elif any(row.disposition == "blocked" for row in dimensions):
        disposition = "block"
        reason = "one or more required capacity dimensions are blocked"
    elif any(row.disposition in {"limited", "capacity_building_required"} for row in dimensions):
        disposition = "limit"
        reason = "capacity is limited or requires explicit capacity-building"
    else:
        disposition = "pass"
        reason = "required capacity dimensions are grounded for this actor and jurisdiction"

    return CapacityFeasibilityRecord(
        record_id=f"layer2.s6.capacity.{_stable_token(case_id)}",
        record_ref=_record_ref(case_id, "state_capacity_feasibility"),
        case_id=case_id,
        design_ref=design_ref,
        actor_ref=actor_ref,
        jurisdiction_ref=jurisdiction_ref,
        instrument_ref=instrument_ref,
        capacity_dimensions=dimensions,
        capacity_building_obligations=obligations,
        firewall_disposition=disposition,
        decision_reason=reason,
        authority_boundary=authority_boundary
        or _authority_boundary(
            authoritative_for=["capacity_feasibility"],
            may_not_use_for=["capacity_transfer_authority"],
            rule_version_ref=rule_version_ref,
        ),
        rule_version_ref=rule_version_ref,
    )


def evaluate_mandate_legitimacy(
    *,
    case_id: str,
    design_ref: str,
    objective_refs: Sequence[str],
    mandate_sources: Sequence[Mapping[str, object]],
    participation_evaluations: Sequence[Mapping[str, object]] = (),
    consultation_validations: Sequence[Mapping[str, object]] = (),
    rule_version_ref: str,
    authority_boundary: AuthorityBoundary | None = None,
) -> MandateLegitimacyRecord:
    """Evaluate mandate provenance without allowing LLM text to authorize objectives."""

    sources = [
        MandateSourceRecord.model_validate(
            {**_as_mapping(row), "rule_version_ref": rule_version_ref},
        )
        for row in mandate_sources
    ]
    participation_rows = [
        _participation_row(row, rule_version_ref=rule_version_ref)
        for row in participation_evaluations
    ]
    consultation_rows = [
        _consultation_row(row, rule_version_ref=rule_version_ref)
        for row in consultation_validations
    ]
    llm_objective_sources = [
        source
        for source in sources
        if source.source_authority.startswith("llm_")
        and source.authorized_objective_refs
        and source.provenance_ref is None
    ]
    if llm_objective_sources:
        raise P22MandateLegitimacyError(
            "P22 mandate legitimacy laundering: LLM participation or mandate speculation "
            "cannot authorize objectives without participation/legal/governance provenance"
        )

    if not sources:
        disposition: AxisFailClosedDisposition = "block"
        reason = "mandate evidence is absent; missing axis evidence cannot pass"
    elif any(source.disposition == "blocked" for source in sources):
        disposition = "block"
        reason = "at least one mandate source is blocked"
    elif any(not row.claim_use_allowed for row in participation_rows):
        disposition = "block"
        reason = "participation provenance blocks claim use"
    elif any(row.unresolved_high_severity_objection for row in consultation_rows):
        disposition = "block"
        reason = "consultation validation has unresolved high-severity objections"
    elif any(source.disposition in {"limited", "candidate_unverified"} for source in sources):
        disposition = "limit"
        reason = "mandate source remains limited or candidate-unverified"
    else:
        disposition = "pass"
        reason = "objective authority is grounded in mandate and participation provenance"

    return MandateLegitimacyRecord(
        record_id=f"layer2.s6.mandate.{_stable_token(case_id)}",
        record_ref=_record_ref(case_id, "mandate_legitimacy"),
        case_id=case_id,
        design_ref=design_ref,
        objective_refs=list(objective_refs),
        mandate_sources=sources,
        participation_provenance=participation_rows,
        consultation_provenance=consultation_rows,
        firewall_disposition=disposition,
        decision_reason=reason,
        authority_boundary=authority_boundary
        or _authority_boundary(
            authoritative_for=["mandate_legitimacy"],
            may_not_use_for=["mandate_authority_from_llm", "value_choice_authority"],
            rule_version_ref=rule_version_ref,
        ),
        rule_version_ref=rule_version_ref,
    )


def evaluate_strategic_response(
    *,
    case_id: str,
    design_ref: str,
    response_channels: Sequence[Mapping[str, object]],
    pre_policy_effect_refs: Sequence[str] = (),
    s5_composition_posture: Mapping[str, object] | None = None,
    strategic_response_entries: Sequence[Mapping[str, object]] = (),
    rule_version_ref: str,
    authority_boundary: AuthorityBoundary | None = None,
) -> StrategicResponseRecord:
    """Evaluate response-model validity without running a rich equilibrium model."""

    channels = [
        StrategicResponseChannelAssessment.model_validate(
            {**_as_mapping(row), "rule_version_ref": rule_version_ref},
        )
        for row in response_channels
    ]
    entries = [_as_mapping(entry) for entry in strategic_response_entries]
    unchanged_effect_claim = any(bool(entry.get("declared_unchanged_effect")) for entry in entries)
    unresolved_response = [
        channel
        for channel in channels
        if channel.disposition in {"limited", "system_dynamics_required", "blocked"}
        and (
            channel.response_model_ref is None
            or channel.post_intervention_dgp_update_ref is None
            or channel.risk_level in {"medium", "high"}
        )
    ]
    risky_channels = {channel.channel for channel in unresolved_response}
    if unchanged_effect_claim and unresolved_response:
        named_risk = "Goodhart" if "goodhart" in risky_channels else "strategic response"
        raise P24StrategicResponseError(
            f"P24 {named_risk} response-model laundering: unchanged pre-policy effect claim "
            "requires a post-intervention DGP update before projection"
        )

    handoff_required = any(
        channel.disposition == "system_dynamics_required" for channel in channels
    )
    if _payload_value(s5_composition_posture, "system_dynamics_requirement_ref"):
        handoff_required = True

    update_ref = next(
        (
            channel.post_intervention_dgp_update_ref
            for channel in channels
            if channel.post_intervention_dgp_update_ref
        ),
        None,
    )
    dgp_update = None
    if update_ref:
        dgp_update = PostInterventionDGPUpdate(
            update_ref=update_ref,
            design_ref=design_ref,
            channel_refs=[channel.channel for channel in channels],
            pre_policy_effect_refs=list(pre_policy_effect_refs),
            reason="strategic response evidence changes the post-intervention DGP",
            system_dynamics_handoff_required=handoff_required,
            authority_boundary=_authority_boundary(
                authoritative_for=["post_intervention_dgp_update"],
                may_not_use_for=["outcome_prediction_authority"],
                rule_version_ref=rule_version_ref,
            ),
            rule_version_ref=rule_version_ref,
        )

    if not channels:
        disposition: AxisFailClosedDisposition = "limit"
        reason = "strategic-response evidence is absent; missing axis evidence cannot pass"
    elif any(channel.disposition == "blocked" for channel in channels):
        disposition = "block"
        reason = "one or more strategic response channels are blocked"
    elif any(channel.disposition == "system_dynamics_required" for channel in channels):
        disposition = "block"
        reason = "response risk requires post-intervention DGP and system-dynamics handoff"
    elif any(channel.disposition == "limited" for channel in channels):
        disposition = "limit"
        reason = "strategic response is limited and must constrain robustness claims"
    else:
        disposition = "pass"
        reason = "strategic response channels are modeled for fail-closed scope"

    return StrategicResponseRecord(
        record_id=f"layer2.s6.strategic_response.{_stable_token(case_id)}",
        record_ref=_record_ref(case_id, "strategic_response"),
        case_id=case_id,
        design_ref=design_ref,
        response_channels=channels,
        pre_policy_effect_refs=list(pre_policy_effect_refs),
        strategic_response_entry_refs=[
            str(entry.get("entry_ref")) for entry in entries if entry.get("entry_ref") is not None
        ],
        post_intervention_dgp_update=dgp_update,
        post_intervention_dgp_update_ref=update_ref,
        system_dynamics_handoff_required=handoff_required,
        firewall_disposition=disposition,
        decision_reason=reason,
        authority_boundary=authority_boundary
        or _authority_boundary(
            authoritative_for=["strategic_robustness", "response_model_validity"],
            may_not_use_for=[
                "post_policy_effect_claim_without_response_model",
                "rich_response_model_authority",
                "outcome_prediction_authority",
            ],
            rule_version_ref=rule_version_ref,
        ),
        rule_version_ref=rule_version_ref,
    )


def build_s6_blind_spot_firewall_report(
    *,
    case_id: str,
    design_ref: str,
    measurability: MeasurabilityAdequacyRecord,
    aggregation: AggregationValidityRecord,
    capacity: CapacityFeasibilityRecord,
    mandate: MandateLegitimacyRecord,
    strategic_response: StrategicResponseRecord,
    rule_version_ref: str,
) -> BlindSpotFirewallReport:
    """Build the compact S6 report consumed by orchestration and S2 injection."""

    records = (measurability, aggregation, capacity, mandate, strategic_response)
    dispositions = [record.firewall_disposition for record in records]
    overall: BlindSpotOverallPosture
    if "block" in dispositions:
        overall = "blocked"
    elif "limit" in dispositions:
        overall = "limited"
    else:
        overall = "clear_fail_closed"

    axis_rows = [
        {
            "axis": record.axis,
            "cell_ref": record.cell_ref,
            "record_ref": record.record_ref,
            "firewall_pattern_id": record.firewall_pattern_id,
            "disposition": record.firewall_disposition,
            "decision_reason": record.decision_reason,
        }
        for record in records
    ]
    c3_rows = _build_c3_dimension_records(
        records,
        case_id=case_id,
        rule_version_ref=rule_version_ref,
    )
    bridge_rows = _build_bridge_rows(records, case_id=case_id, rule_version_ref=rule_version_ref)
    constraint_updates = _build_constraint_updates(
        records,
        case_id=case_id,
        rule_version_ref=rule_version_ref,
    )
    blocking_axis_refs = [
        record.cell_ref for record in records if record.firewall_disposition == "block"
    ]
    limiting_axis_refs = [
        record.cell_ref for record in records if record.firewall_disposition == "limit"
    ]
    ledger_refs = [
        measurability.record_ref,
        aggregation.record_ref,
        capacity.record_ref,
        mandate.record_ref,
        strategic_response.record_ref,
        f"pdc://layer2/s6/{case_id}/cluster-authority-dimensions",
    ]
    regime_reissue_required = measurability.firewall_disposition != "pass" or (
        aggregation.firewall_disposition != "pass"
    )

    return BlindSpotFirewallReport(
        report_id=f"layer2.s6.report.{_stable_token(case_id)}",
        report_ref=f"pdc://layer2/s6/{case_id}/blind-spot-firewall-report",
        case_id=case_id,
        design_ref=design_ref,
        overall_posture=overall,
        measurability=measurability,
        aggregation=aggregation,
        capacity=capacity,
        mandate=mandate,
        strategic_response=strategic_response,
        axis_rows=axis_rows,
        ledger_refs=ledger_refs,
        bridge_consumer_rows=bridge_rows,
        constraint_store_updates=constraint_updates,
        c3_authority_dimension_rows=c3_rows,
        blocking_axis_refs=blocking_axis_refs,
        limiting_axis_refs=limiting_axis_refs,
        post_intervention_dgp_update_ref=strategic_response.post_intervention_dgp_update_ref,
        system_dynamics_handoff_required=strategic_response.system_dynamics_handoff_required,
        regime_reissue_required=regime_reissue_required,
        false_clear_penalty=float(len(blocking_axis_refs) * 2 + len(limiting_axis_refs)),
        authority_boundary=_authority_boundary(
            authoritative_for=[
                "fail_closed_axis_firewall",
                "blind_spot_constraint_injection",
                "c3_authority_dimension_input",
            ],
            may_not_use_for=[
                "production_claim_authority",
                "rollout_authority",
                "publication_authority",
                "delegation_authority",
                "value_choice_authority",
                "outcome_prediction_authority",
                "forecast_calibration_authority",
            ],
            rule_version_ref=rule_version_ref,
        ),
        rule_version_ref=rule_version_ref,
    )


def s6_firewall_report_to_axis_positions(
    report: BlindSpotFirewallReport,
) -> tuple[list[AxisPositionDeclaration], list[AxisFirewallStatus]]:
    """Project S6 report rows into S0 axis declarations and firewall statuses."""

    positions = [
        AxisPositionDeclaration(
            cluster=record.cell_ref.split(".", maxsplit=1)[0],
            axis=record.cell_ref.split(".", maxsplit=1)[1],
            position=record.firewall_disposition,
            evidence_refs=[record.record_ref],
            authority_purpose="fail_closed_blind_spot_firewall",
            rule_version_ref=record.rule_version_ref,
        )
        for record in _report_records(report)
    ]
    firewalls = [
        AxisFirewallStatus(
            cell_ref=record.cell_ref,
            status=record.firewall_disposition,
            pattern_ids=[record.firewall_pattern_id],
            reason=record.decision_reason,
            maturity="fail_closed",
            rule_version_ref=record.rule_version_ref,
        )
        for record in _report_records(report)
    ]
    return positions, firewalls


def s6_firewall_report_to_constraint_store_updates(
    report: BlindSpotFirewallReport,
) -> list[BlindSpotConstraintStoreUpdate]:
    """Return typed S6 constraint updates for S2 mapping."""

    return list(report.constraint_store_updates)


def s6_firewall_report_to_c3_dimension_records(
    report: BlindSpotFirewallReport,
) -> list[ClusterAuthorityDimensionRecord]:
    """Return canonical C3 authority dimension rows emitted by S6."""

    return list(report.c3_authority_dimension_rows)


def s6_fail_closed_coverage(probe_results: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Compute the S6 negative-control floor metric across the five probe axes."""

    rows = [dict(row) for row in probe_results]
    axes = {str(row.get("axis", "")) for row in rows if row.get("axis")}
    false_clear_count = sum(1 for row in rows if bool(row.get("false_clear")))
    passed = [
        row
        for row in rows
        if row.get("expected_error") == row.get("observed_error")
        and row.get("observed_disposition") in {"limit", "block"}
        and not bool(row.get("false_clear"))
    ]
    rate = len(passed) / len(rows) if rows else 0.0
    per_axis = {
        axis: {
            "case_count": sum(1 for row in rows if row.get("axis") == axis),
            "passed": sum(1 for row in passed if row.get("axis") == axis),
        }
        for axis in sorted(axes)
    }
    return {
        "schema_version": LAYER2_S6_BLIND_SPOT_FIREWALLS_SCHEMA_VERSION,
        "case_count": len(rows),
        "axis_coverage_count": len(axes),
        "all_five_axes_covered": set(_S6_CELL_BY_AXIS.values()) <= axes,
        "per_axis_fail_closed_negative_control_pass_rate": rate,
        "false_clear_count": false_clear_count,
        "per_axis_negative_control_counts": per_axis,
    }


def _report_records(
    report: BlindSpotFirewallReport,
) -> tuple[
    MeasurabilityAdequacyRecord,
    AggregationValidityRecord,
    CapacityFeasibilityRecord,
    MandateLegitimacyRecord,
    StrategicResponseRecord,
]:
    return (
        report.measurability,
        report.aggregation,
        report.capacity,
        report.mandate,
        report.strategic_response,
    )


def _build_c3_dimension_records(
    records: Sequence[
        MeasurabilityAdequacyRecord
        | AggregationValidityRecord
        | CapacityFeasibilityRecord
        | MandateLegitimacyRecord
        | StrategicResponseRecord
    ],
    *,
    case_id: str,
    rule_version_ref: str,
) -> list[ClusterAuthorityDimensionRecord]:
    c3_rows: list[ClusterAuthorityDimensionRecord] = []
    for record in records:
        axis = _AXIS_BY_CELL[record.cell_ref]
        for dimension in _C3_DIMENSIONS_BY_AXIS[axis]:
            c3_rows.append(
                ClusterAuthorityDimensionRecord(
                    dimension_id=(
                        f"layer2.s6.c3.{_stable_token(case_id, record.cell_ref, dimension)}"
                    ),
                    dimension_ref=(
                        f"pdc://layer2/s6/{case_id}/cluster-authority-dimensions/{dimension}"
                    ),
                    case_id=case_id,
                    cell_ref=record.cell_ref,
                    authority_dimension=dimension,
                    producer_ref=record.record_ref,
                    firewall_pattern_id=record.firewall_pattern_id,
                    disposition=record.firewall_disposition,
                    evidence_refs=[record.record_ref],
                    authority_boundary=_authority_boundary(
                        authoritative_for=[dimension],
                        may_not_use_for=[
                            "production_claim_authority",
                            "outcome_prediction_authority",
                        ],
                        rule_version_ref=rule_version_ref,
                    ),
                    rule_version_ref=rule_version_ref,
                ),
            )
    return c3_rows


def _build_bridge_rows(
    records: Sequence[
        MeasurabilityAdequacyRecord
        | AggregationValidityRecord
        | CapacityFeasibilityRecord
        | MandateLegitimacyRecord
        | StrategicResponseRecord
    ],
    *,
    case_id: str,
    rule_version_ref: str,
) -> list[BlindSpotBridgeConsumerRecord]:
    rows: list[BlindSpotBridgeConsumerRecord] = []
    for record in records:
        axis = _AXIS_BY_CELL[record.cell_ref]
        for consumer in _BRIDGE_CONSUMERS_BY_AXIS[axis]:
            pending_consumer = consumer in {
                "ACTOR.value_choice_provenance",
                "SYSTEM.post_intervention_dgp",
            }
            rows.append(
                BlindSpotBridgeConsumerRecord(
                    bridge_ref=(
                        f"pdc://layer2/s6/{case_id}/bridge/"
                        f"{_stable_token(record.cell_ref, consumer)}"
                    ),
                    cell_ref=record.cell_ref,
                    consumer_ref=consumer,
                    producer_ref=record.record_ref,
                    disposition=record.firewall_disposition,
                    pending_consumer=pending_consumer,
                    constraint_ref=(
                        f"constraint://layer2/s6/{case_id}/"
                        f"{_stable_token(record.cell_ref, consumer)}"
                    ),
                    handoff_reason=record.decision_reason,
                    authority_boundary=_authority_boundary(
                        authoritative_for=["blind_spot_constraint_injection"],
                        may_not_use_for=["consumer_satisfaction_without_downstream_slice"],
                        rule_version_ref=rule_version_ref,
                    ),
                    rule_version_ref=rule_version_ref,
                ),
            )
    return rows


def _build_constraint_updates(
    records: Sequence[
        MeasurabilityAdequacyRecord
        | AggregationValidityRecord
        | CapacityFeasibilityRecord
        | MandateLegitimacyRecord
        | StrategicResponseRecord
    ],
    *,
    case_id: str,
    rule_version_ref: str,
) -> list[BlindSpotConstraintStoreUpdate]:
    updates: list[BlindSpotConstraintStoreUpdate] = []
    for record in records:
        status: ConstraintStatus = "pass" if record.firewall_disposition == "pass" else (
            "block" if record.firewall_disposition == "block" else "limit"
        )
        route = _refinement_route(record)
        for consumer in _BRIDGE_CONSUMERS_BY_AXIS[_AXIS_BY_CELL[record.cell_ref]]:
            updates.append(
                BlindSpotConstraintStoreUpdate(
                    constraint_id=f"layer2.s6.{_stable_token(case_id, record.cell_ref, consumer)}",
                    cell_ref=record.cell_ref,
                    status=status,
                    source_ref=record.record_ref,
                    consumer_ref=consumer,
                    refinement_route=route,
                    evidence_refs=[record.record_ref],
                    reason=record.decision_reason,
                    authority_boundary=_authority_boundary(
                        authoritative_for=["blind_spot_constraint_injection"],
                        may_not_use_for=["projection_only_constraint"],
                        rule_version_ref=rule_version_ref,
                    ),
                    rule_version_ref=rule_version_ref,
                ),
            )
    return updates


def _refinement_route(
    record: MeasurabilityAdequacyRecord
    | AggregationValidityRecord
    | CapacityFeasibilityRecord
    | MandateLegitimacyRecord
    | StrategicResponseRecord,
) -> ConstraintRefinementRoute:
    if record.firewall_disposition == "pass":
        return "none"
    if record.firewall_disposition == "limit":
        return "acquire"
    if record.cell_ref in {
        "ACTOR.mandate_legitimacy",
        "OTHER_AGENTS.strategic_response",
    }:
        return "human_decision"
    if record.cell_ref == "SYSTEM.subject_granularity":
        return "reframe"
    return "block_candidate"


def _participation_row(
    row: Mapping[str, object],
    *,
    rule_version_ref: str,
) -> ParticipationProvenanceRow:
    payload = _as_mapping(row)
    return ParticipationProvenanceRow(
        provenance_ref=str(
            payload.get("provenance_ref")
            or payload.get("evaluation_ref")
            or payload.get("validation_ref")
            or "participation://unknown"
        ),
        source_ref=_optional_str(payload.get("source_ref")),
        claim_use_allowed=bool(payload.get("claim_use_allowed", False)),
        blocker_refs=[
            str(item) for item in payload.get("blockers", payload.get("blocker_refs", []))
        ],
        unresolved_high_severity_objection=bool(
            payload.get("unresolved_high_severity_objection", False),
        ),
        rule_version_ref=rule_version_ref,
    )


def _consultation_row(
    row: Mapping[str, object],
    *,
    rule_version_ref: str,
) -> ParticipationProvenanceRow:
    payload = _as_mapping(row)
    return ParticipationProvenanceRow(
        provenance_ref=str(
            payload.get("provenance_ref")
            or payload.get("validation_ref")
            or payload.get("evaluation_ref")
            or "consultation://unknown"
        ),
        source_ref=_optional_str(payload.get("source_ref")),
        claim_use_allowed=not bool(payload.get("unresolved_high_severity_objection", False)),
        blocker_refs=[
            str(item) for item in payload.get("blockers", payload.get("blocker_refs", []))
        ],
        unresolved_high_severity_objection=bool(
            payload.get("unresolved_high_severity_objection", False),
        ),
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


def _record_ref(case_id: str, axis: BlindSpotAxis) -> str:
    return f"pdc://layer2/s6/{case_id}/{_REPLAY_REF_SUFFIX_BY_AXIS[axis]}"


def _stable_token(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return sha256(payload.encode("utf-8")).hexdigest()[:12]


def _as_mapping(row: Mapping[str, object] | object) -> dict[str, object]:
    if isinstance(row, Mapping):
        return dict(row)
    if hasattr(row, "model_dump"):
        dumped = row.model_dump()
        if isinstance(dumped, Mapping):
            return dict(dumped)
    raise TypeError(f"expected mapping-like S6 row, got {type(row)!r}")


def _payload_value(payload: Mapping[str, object] | object | None, key: str) -> object | None:
    if payload is None:
        return None
    if isinstance(payload, Mapping):
        return payload.get(key)
    return getattr(payload, key, None)


def _payload_ref(
    payload: Mapping[str, object] | object | None,
    keys: Sequence[str],
) -> str | None:
    for key in keys:
        value = _payload_value(payload, key)
        if value is not None:
            return str(value)
    return None


def _copied_capacity(
    row: CapacityDimensionAssessment,
    *,
    actor_ref: str,
    jurisdiction_ref: str,
) -> bool:
    return bool(
        (row.copied_from_actor_ref and row.copied_from_actor_ref != actor_ref)
        or (
            row.copied_from_jurisdiction_ref
            and row.copied_from_jurisdiction_ref != jurisdiction_ref
        ),
    )


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)
