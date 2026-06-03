"""Layer 2 S12 resource-economics contracts and anti-gaming firewalls."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import Field, model_validator

from polisyos.pdc import AuthorityBoundary, Layer2ReadinessModel, ValueOfInformationEstimate
from polisyos.runtime.quality.layer2_value_choice import RankingMode  # noqa: TC001

LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s12_resource_economics.v1"
)
LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION = (
    "policyos.layer2.s12.resource_economics.v1"
)
S12_GROWTH_THERMOMETERS_FLOOR_ID = "s12_growth_thermometers"
S12_VOI_SITES: tuple[str, ...] = (
    "acquisition",
    "refinement",
    "attention",
    "oracle",
    "allocation",
)
S12_TYPED_BUDGETS: tuple[str, ...] = (
    "compute",
    "acquisition_money",
    "expert_time",
    "human_attention",
    "legal_access",
)
S12_FALSE_CLEAR_FIELDS: tuple[str, ...] = (
    "bespoke_one_off_growth",
    "allocation_gaming_internal_metrics",
    "floor_lowering_for_useful_design_rate",
    "b_faster_than_a_growth",
    "meta_regress_past_principal",
    "interchangeable_budget",
    "growth_without_envelope_delta",
)

ExploreExploitPosture = Literal[
    "exploit_in_envelope",
    "invest_in_growth",
    "balanced_governed",
    "blocked",
]
GrowthCountingDisposition = Literal[
    "counted_mechanism_growth",
    "flagged_bespoke_one_off",
    "blocked_no_envelope_delta",
    "advisory_only",
]
BudgetKind = Literal[
    "compute",
    "acquisition_money",
    "expert_time",
    "human_attention",
    "legal_access",
]
VoiSite = Literal["acquisition", "refinement", "attention", "oracle", "allocation"]
ThermometerTrend = Literal["improving", "flat", "regressing"]
ResourceAuthorityDisposition = Literal[
    "pass",
    "blocked",
    "blocked_no_envelope_delta",
    "flagged_bespoke_one_off",
    "advisory_only",
]
KnowledgeGovernanceMode = Literal[
    "automated_proposal",
    "human_reviewed",
    "institution_owned",
    "manual_bespoke",
]

_S12_AUTHORITY_SCOPE: tuple[str, ...] = (
    "value_of_information_allocation",
    "explore_exploit_posture",
    "envelope_growth_ledger",
    "growth_thermometers",
    "knowledge_governance_throughput",
    "allocation_priority_input",
    "expert_machine_resource_projection",
)
_S12_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "production_authority",
    "production_recommendation",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "approval_authority",
    "scorecard_authority",
    "preference_learning_authority",
    "mdp_bandit_optimizer_authority",
    "budget_interchangeability",
    "mission_or_value_self_authorization",
    "floor_relaxation",
    "s13_envelope_shrink",
    "s13_accountability_closure",
    "s14_universality",
)
_REQUIRED_AUTHORITY_DENIALS = frozenset(_S12_MAY_NOT_USE_FOR)
_VOI_SITE_ALIASES: tuple[tuple[str, VoiSite], ...] = (
    ("layer2_s3_substrate_acquisition", "acquisition"),
    ("substrate_acquisition", "acquisition"),
    ("acquisition", "acquisition"),
    ("layer2.s2.shadow_design_loop", "refinement"),
    ("shadow_design_loop", "refinement"),
    ("refinement", "refinement"),
    ("layer2.s7.attention", "attention"),
    ("human_attention", "attention"),
    ("attention", "attention"),
    ("layer2.oracle", "oracle"),
    ("oracle", "oracle"),
    ("layer2.s12.resource_allocation", "allocation"),
    ("resource_allocation", "allocation"),
    ("allocation", "allocation"),
)
_BUDGET_ALIASES: Mapping[str, BudgetKind] = {
    "compute": "compute",
    "acquisition": "acquisition_money",
    "acquisition_money": "acquisition_money",
    "expert_time": "expert_time",
    "human_attention": "human_attention",
    "attention": "human_attention",
    "legal_access": "legal_access",
}
_INSTRUMENTED_OVERRIDE_DECISIONS = frozenset(
    {"final_choice", "value_authorization", "a_spec_gap", "mandate_boundary"}
)
_BLOCKED_DISPOSITIONS: Mapping[str, ResourceAuthorityDisposition] = {
    "bespoke_one_off_growth": "flagged_bespoke_one_off",
    "allocation_gaming_internal_metrics": "blocked",
    "floor_lowering_for_useful_design_rate": "blocked",
    "b_faster_than_a_growth": "blocked",
    "meta_regress_past_principal": "blocked",
    "interchangeable_budget": "blocked",
    "growth_without_envelope_delta": "blocked_no_envelope_delta",
}


class VoiAllocationRow(Layer2ReadinessModel):
    """One S12 VOI allocation row over the shared S0 qualitative currency."""

    site: VoiSite
    voi_estimate_ref: str = Field(..., min_length=1, max_length=300)
    budget_kind: BudgetKind
    used_by_sites: list[str] = Field(default_factory=list, max_length=20)
    budget_dimensions: list[str] = Field(default_factory=list, max_length=10)
    shared_currency: Literal["ValueOfInformationEstimate"] = "ValueOfInformationEstimate"
    numeric_voi_score: None = None


class ValueOfInformationAllocation(Layer2ReadinessModel):
    """Replayable bundle of per-site S12 VOI allocation rows."""

    schema_version: str = LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION
    allocation_id: str = Field(..., min_length=1, max_length=180)
    allocation_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    voi_allocations: list[VoiAllocationRow] = Field(default_factory=list, max_length=20)
    voi_site_count: int = Field(..., ge=0)
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION

    @model_validator(mode="after")
    def _validate_site_count(self) -> ValueOfInformationAllocation:
        if self.voi_site_count != len({row.site for row in self.voi_allocations}):
            raise ValueError("voi_site_count must equal distinct VOI sites")
        return self


class TypedBudgetRow(Layer2ReadinessModel):
    """Typed budget row that prevents cross-budget conversion or substitution."""

    budget_kind: BudgetKind
    budget_ref: str = Field(..., min_length=1, max_length=300)
    voi_estimate_ref: str = Field(..., min_length=1, max_length=300)


class AllocationPriorityRow(Layer2ReadinessModel):
    """Priority row emitted by S12 for downstream acquisition or slice routing."""

    priority_ref: str = Field(..., min_length=1, max_length=300)
    site: VoiSite
    budget_kind: BudgetKind
    reason: str = Field(..., min_length=1, max_length=600)


class ResourceAllocationPolicy(Layer2ReadinessModel):
    """Governed S12 allocation policy over VOI sites and typed budgets."""

    schema_version: str = LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION
    policy_id: str = Field(..., min_length=1, max_length=180)
    policy_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    explore_exploit_posture: ExploreExploitPosture
    explore_exploit_dial_ref: str | None = Field(default=None, max_length=300)
    delegation_contract_ref: str = Field(..., min_length=1, max_length=300)
    principal_ref: str = Field(..., min_length=1, max_length=300)
    mission_ref: str = Field(..., min_length=1, max_length=300)
    voi_allocations: list[VoiAllocationRow] = Field(default_factory=list, max_length=20)
    voi_site_count: int = Field(..., ge=0)
    typed_budget_rows: list[TypedBudgetRow] = Field(..., min_length=5, max_length=5)
    pareto_archive_ref: str = Field(..., min_length=1, max_length=300)
    ranking_mode: RankingMode
    selected_policy_ref: str | None = Field(default=None, max_length=300)
    rejected_nondominated_policy_refs: list[str] = Field(default_factory=list, max_length=80)
    allocation_priority_rows: list[AllocationPriorityRow] = Field(
        default_factory=list,
        max_length=80,
    )
    disposition: ResourceAuthorityDisposition
    limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S12_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION

    @model_validator(mode="after")
    def _validate_policy(self) -> ResourceAllocationPolicy:
        _assert_required_denials(self.may_not_use_for)
        if self.voi_site_count != len({row.site for row in self.voi_allocations}):
            raise ValueError("voi_site_count must equal distinct VOI sites")
        if {row.budget_kind for row in self.typed_budget_rows} != set(S12_TYPED_BUDGETS):
            raise ValueError("typed_budget_rows must carry all S12 typed budgets")
        if self.explore_exploit_dial_ref and self.ranking_mode != (
            "ranked_with_authorized_values"
        ):
            raise ValueError("authorized explore/exploit dial requires authorized ranking mode")
        if not self.explore_exploit_dial_ref and self.selected_policy_ref:
            raise ValueError("selected allocation policy requires principal dial ref")
        if self.ranking_mode == "ranked_with_authorized_values" and not self.selected_policy_ref:
            raise ValueError("authorized ranking mode requires selected policy ref")
        return self


class EnvelopeGrowthEntry(Layer2ReadinessModel):
    """One envelope-growth ledger entry, delta-gated and demand-pulled."""

    entry_ref: str = Field(..., min_length=1, max_length=300)
    demand_act_ref: str = Field(..., min_length=1, max_length=300)
    certified_envelope_delta_ref: str | None = Field(default=None, max_length=300)
    pending_envelope_delta_ref: str | None = Field(default=None, max_length=300)
    growth_counting_disposition: GrowthCountingDisposition
    reuse_evidence_refs: list[str] = Field(default_factory=list, max_length=80)
    bespoke_flag_reason: str | None = Field(default=None, max_length=600)
    a_completeness_delta_ref: str | None = Field(default=None, max_length=300)
    b_capability_delta_ref: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _validate_delta_gate(self) -> EnvelopeGrowthEntry:
        if (
            self.growth_counting_disposition == "counted_mechanism_growth"
            and not self.certified_envelope_delta_ref
        ):
            raise ValueError("counted mechanism growth requires certified envelope delta")
        if (
            self.growth_counting_disposition != "blocked_no_envelope_delta"
            and not self.certified_envelope_delta_ref
            and not self.pending_envelope_delta_ref
        ):
            raise ValueError("growth entry requires envelope delta or pending envelope delta")
        if (
            self.growth_counting_disposition == "flagged_bespoke_one_off"
            and not self.bespoke_flag_reason
        ):
            raise ValueError("bespoke one-off growth requires a flag reason")
        return self


class EnvelopeGrowthLedger(Layer2ReadinessModel):
    """S12 ledger of counted, pending, flagged, and blocked envelope growth."""

    schema_version: str = LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION
    ledger_id: str = Field(..., min_length=1, max_length=180)
    ledger_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    growth_entries: list[EnvelopeGrowthEntry] = Field(default_factory=list, max_length=80)
    counted_mechanism_growth_count: int = Field(..., ge=0)
    flagged_bespoke_one_off_count: int = Field(..., ge=0)
    blocked_no_envelope_delta_count: int = Field(..., ge=0)
    cluster_map_open_cell_count_before: int = Field(..., ge=0)
    cluster_map_open_cell_count_after: int = Field(..., ge=0)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S12_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION

    @model_validator(mode="after")
    def _validate_counts(self) -> EnvelopeGrowthLedger:
        _assert_required_denials(self.may_not_use_for)
        counted = sum(
            entry.growth_counting_disposition == "counted_mechanism_growth"
            for entry in self.growth_entries
        )
        flagged = sum(
            entry.growth_counting_disposition == "flagged_bespoke_one_off"
            for entry in self.growth_entries
        )
        blocked = sum(
            entry.growth_counting_disposition == "blocked_no_envelope_delta"
            for entry in self.growth_entries
        )
        if self.counted_mechanism_growth_count != counted:
            raise ValueError("counted mechanism growth count must match growth entries")
        if self.flagged_bespoke_one_off_count != flagged:
            raise ValueError("flagged bespoke one-off count must match growth entries")
        if self.blocked_no_envelope_delta_count != blocked:
            raise ValueError("blocked no-envelope-delta count must match growth entries")
        return self


class GrowthThermometerRecord(Layer2ReadinessModel):
    """S12 bootstrap thermometer for override-rate and reuse-rate trends."""

    schema_version: str = LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION
    thermometer_id: str = Field(..., min_length=1, max_length=180)
    thermometer_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    override_rate: float = Field(..., ge=0.0, le=1.0)
    override_rate_trend: ThermometerTrend
    override_decision_kinds: list[str] = Field(default_factory=list, max_length=20)
    uninstrumented_override_dimensions: list[str] = Field(default_factory=list, max_length=20)
    required_question_count: int = Field(..., ge=0)
    reuse_rate: float = Field(..., ge=0.0, le=1.0)
    reuse_rate_trend: ThermometerTrend
    frozen_primitive_set_ref: str = Field(..., min_length=1, max_length=300)
    reused_primitive_refs: list[str] = Field(default_factory=list, max_length=120)
    one_off_growth_refs: list[str] = Field(default_factory=list, max_length=120)
    held_out_status: Literal["pending_s14"] = "pending_s14"
    held_out_battery_ref: str | None = Field(default=None, max_length=300)
    floor_id: Literal["s12_growth_thermometers"] = S12_GROWTH_THERMOMETERS_FLOOR_ID
    floor_passed: bool
    threshold_ref: str = Field(..., min_length=1, max_length=300)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S12_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION

    @model_validator(mode="after")
    def _validate_thermometer(self) -> GrowthThermometerRecord:
        _assert_required_denials(self.may_not_use_for)
        if self.held_out_battery_ref is not None:
            raise ValueError("held-out battery must remain pending_s14 for S12")
        if not set(self.override_decision_kinds) <= _INSTRUMENTED_OVERRIDE_DECISIONS:
            raise ValueError("override_rate can use only instrumented S7 decision kinds")
        if self.override_rate_trend in {"improving", "flat"} and (
            self.required_question_count == 0
        ):
            raise ValueError("non-regressing override trend requires fixed questions")
        if self.floor_passed and (
            self.override_rate_trend == "regressing"
            or self.reuse_rate_trend == "regressing"
        ):
            raise ValueError("S12 thermometer floor cannot pass regressing trends")
        return self


class ThroughputRow(Layer2ReadinessModel):
    """Knowledge-governance throughput row with cost and latency refs."""

    mode: KnowledgeGovernanceMode
    cost_ref: str = Field(..., min_length=1, max_length=300)
    latency_ref: str = Field(..., min_length=1, max_length=300)


class KnowledgeGovernanceThroughputLedger(Layer2ReadinessModel):
    """S12 throughput ledger for automated, reviewed, owned, and bespoke modes."""

    schema_version: str = LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION
    ledger_id: str = Field(..., min_length=1, max_length=180)
    ledger_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    throughput_rows: list[ThroughputRow] = Field(default_factory=list, max_length=40)
    governance_mode_counts: dict[str, int] = Field(default_factory=dict)
    manual_bespoke_ratio: float = Field(..., ge=0.0, le=1.0)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S12_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION

    @model_validator(mode="after")
    def _validate_throughput(self) -> KnowledgeGovernanceThroughputLedger:
        _assert_required_denials(self.may_not_use_for)
        if not set(self.governance_mode_counts) >= {
            "automated_proposal",
            "human_reviewed",
            "institution_owned",
            "manual_bespoke",
        }:
            raise ValueError("governance_mode_counts must include all S12 throughput modes")
        if any(value < 0 for value in self.governance_mode_counts.values()):
            raise ValueError("governance mode counts cannot be negative")
        return self


class ResourceEconomicsIntegrityReport(Layer2ReadinessModel):
    """S12 integrity summary over VOI sites, typed budgets, thermometers, and gates."""

    schema_version: str = LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION
    report_id: str = Field(..., min_length=1, max_length=180)
    case_count: int = Field(..., ge=0)
    voi_site_count: int = Field(..., ge=0)
    typed_budget_count: int = Field(..., ge=0)
    override_rate_trend: ThermometerTrend
    reuse_rate_trend: ThermometerTrend
    held_out_status: Literal["pending_s14"] = "pending_s14"
    counted_mechanism_growth_count: int = Field(..., ge=0)
    flagged_bespoke_one_off_count: int = Field(..., ge=0)
    growth_without_envelope_delta_count: int = Field(..., ge=0)
    weakest_boundary_inheritance_count: int = Field(..., ge=0)
    false_clear_counts: dict[str, int] = Field(default_factory=dict)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S12_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION

    @model_validator(mode="after")
    def _validate_report(self) -> ResourceEconomicsIntegrityReport:
        if set(self.false_clear_counts) != set(S12_FALSE_CLEAR_FIELDS):
            raise ValueError("false_clear_counts keys must exactly match S12_FALSE_CLEAR_FIELDS")
        if any(value < 0 for value in self.false_clear_counts.values()):
            raise ValueError("false_clear_counts cannot be negative")
        if self.typed_budget_count != len(S12_TYPED_BUDGETS):
            raise ValueError("S12 integrity requires all typed budgets")
        if self.voi_site_count < 3:
            raise ValueError("S12 integrity requires VOI across at least three sites")
        if self.growth_without_envelope_delta_count != 0:
            raise ValueError("S12 integrity blocks growth without envelope delta")
        _assert_required_denials(self.may_not_use_for)
        return self


class ResourceEconomicsAuthorityEnvelope(Layer2ReadinessModel):
    """Verifier result for S12 authority, gaming, and learning firewalls."""

    schema_version: str = LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION
    envelope_id: str = Field(..., min_length=1, max_length=180)
    case_id: str = Field(..., min_length=1, max_length=200)
    disposition: ResourceAuthorityDisposition
    issue_codes: list[str] = Field(default_factory=list, max_length=80)
    false_clear_counts: dict[str, int] = Field(default_factory=dict)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S12_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION

    @model_validator(mode="after")
    def _validate_envelope(self) -> ResourceEconomicsAuthorityEnvelope:
        if set(self.false_clear_counts) != set(S12_FALSE_CLEAR_FIELDS):
            raise ValueError("false_clear_counts keys must exactly match S12_FALSE_CLEAR_FIELDS")
        _assert_required_denials(self.may_not_use_for)
        return self


def build_s12_resource_authority_boundary(
    *,
    authoritative_for: Sequence[str] = _S12_AUTHORITY_SCOPE,
    may_not_use_for: Sequence[str] = _S12_MAY_NOT_USE_FOR,
    posture: Literal["shadow", "advisory", "governed"] = "shadow",
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
) -> AuthorityBoundary:
    """Build the purpose-scoped S12 resource-economics authority boundary."""

    return AuthorityBoundary(
        authoritative_for=_dedupe([str(item) for item in authoritative_for]),
        may_not_use_for=_merge_denials(may_not_use_for),
        source_authority="deterministic_producer",
        posture=posture,
        rule_version_refs=[rule_version_ref],
    )


def allocate_value_of_information(
    *,
    case_id: str,
    voi_estimates: Sequence[ValueOfInformationEstimate | Mapping[str, object]],
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
) -> ValueOfInformationAllocation:
    """Aggregate S0 VOI estimates into canonical S12 VOI site rows."""

    rows: list[VoiAllocationRow] = []
    seen: set[tuple[str, str]] = set()
    for estimate in voi_estimates:
        voi = _as_voi_estimate(estimate)
        budget_kind = _first_budget_kind(voi.budget_dimensions)
        for site in _canonical_sites(voi.used_by_sites):
            key = (site, voi.estimate_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                VoiAllocationRow(
                    site=site,
                    voi_estimate_ref=f"voi://{case_id}/{voi.estimate_id}",
                    budget_kind=budget_kind,
                    used_by_sites=list(voi.used_by_sites),
                    budget_dimensions=list(voi.budget_dimensions),
                )
            )
    return ValueOfInformationAllocation(
        allocation_id=f"layer2.s12.voi-allocation.{_stable_token(case_id)}",
        allocation_ref=f"pdc://layer2/s12/{case_id}/voi-allocation",
        case_id=case_id,
        voi_allocations=rows,
        voi_site_count=len({row.site for row in rows}),
        rule_version_ref=rule_version_ref,
    )


def build_resource_allocation_policy(
    *,
    case_id: str,
    delegation_contract_ref: str,
    principal_ref: str,
    mission_ref: str,
    voi_estimates: Sequence[ValueOfInformationEstimate | Mapping[str, object]],
    explore_exploit_dial_ref: str | None = None,
    candidate_policy_refs: Sequence[str] = (),
    compute_budget_ref: str | None = None,
    acquisition_budget_ref: str | None = None,
    expert_time_budget_ref: str | None = None,
    human_attention_budget_ref: str | None = None,
    legal_access_budget_ref: str | None = None,
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
) -> ResourceAllocationPolicy:
    """Build a governed S12 allocation policy without scalarizing the frontier."""

    allocation = allocate_value_of_information(
        case_id=case_id,
        voi_estimates=voi_estimates,
        rule_version_ref=rule_version_ref,
    )
    ranking_mode: RankingMode = (
        "ranked_with_authorized_values"
        if explore_exploit_dial_ref
        else "unranked_frontier_only"
    )
    candidates = [str(ref) for ref in candidate_policy_refs if str(ref)] or [
        f"allocation-policy://{case_id}/acquisition",
        f"allocation-policy://{case_id}/refinement",
        f"allocation-policy://{case_id}/attention",
    ]
    selected_policy_ref = candidates[-1] if explore_exploit_dial_ref else None
    rejected = [ref for ref in candidates if ref != selected_policy_ref]
    budget_ref_map = {
        "compute": compute_budget_ref or f"budget://{case_id}/compute",
        "acquisition_money": acquisition_budget_ref or f"budget://{case_id}/acquisition",
        "expert_time": expert_time_budget_ref or f"budget://{case_id}/expert-time",
        "human_attention": human_attention_budget_ref or f"budget://{case_id}/human-attention",
        "legal_access": legal_access_budget_ref or f"budget://{case_id}/legal-access",
    }
    typed_budget_rows = [
        TypedBudgetRow(
            budget_kind=kind,
            budget_ref=budget_ref_map[kind],
            voi_estimate_ref=_voi_ref_for_budget(allocation.voi_allocations, kind, case_id),
        )
        for kind in S12_TYPED_BUDGETS
    ]
    priority_rows = [
        AllocationPriorityRow(
            priority_ref=f"priority://{case_id}/{row.site}/{row.budget_kind}",
            site=row.site,
            budget_kind=row.budget_kind,
            reason=f"VOI site {row.site} consumes typed budget {row.budget_kind}.",
        )
        for row in allocation.voi_allocations
    ]
    return ResourceAllocationPolicy(
        policy_id=f"layer2.s12.resource-allocation.{_stable_token(case_id)}",
        policy_ref=f"pdc://layer2/s12/{case_id}/resource-allocation-policy",
        case_id=case_id,
        explore_exploit_posture=(
            "balanced_governed" if explore_exploit_dial_ref else "exploit_in_envelope"
        ),
        explore_exploit_dial_ref=explore_exploit_dial_ref,
        delegation_contract_ref=delegation_contract_ref,
        principal_ref=principal_ref,
        mission_ref=mission_ref,
        voi_allocations=allocation.voi_allocations,
        voi_site_count=allocation.voi_site_count,
        typed_budget_rows=typed_budget_rows,
        pareto_archive_ref=f"pdc://layer2/s8/{case_id}/allocation-pareto-archive",
        ranking_mode=ranking_mode,
        selected_policy_ref=selected_policy_ref,
        rejected_nondominated_policy_refs=rejected,
        allocation_priority_rows=priority_rows,
        disposition="advisory_only",
        limitation_refs=["limitation://s12/no-production-authority"],
        authority_boundary=build_s12_resource_authority_boundary(
            authoritative_for=[
                "value_of_information_allocation",
                "explore_exploit_posture",
                "allocation_priority_input",
            ],
            rule_version_ref=rule_version_ref,
        ),
        may_not_use_for=list(_S12_MAY_NOT_USE_FOR),
        rule_version_ref=rule_version_ref,
    )


def build_envelope_growth_ledger(
    *,
    case_id: str,
    growth_entries: Sequence[EnvelopeGrowthEntry | Mapping[str, object]] = (),
    cluster_map_open_cell_count_before: int = 1,
    cluster_map_open_cell_count_after: int = 0,
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
) -> EnvelopeGrowthLedger:
    """Build the S12 envelope-growth ledger from demand acts and delta refs."""

    entries = [_as_growth_entry(entry) for entry in growth_entries]
    if not entries:
        entries = [
            EnvelopeGrowthEntry(
                entry_ref=f"pdc://layer2/s12/{case_id}/growth-entry/anchor",
                demand_act_ref=f"demand-act://{case_id}/s12-envelope-growth",
                certified_envelope_delta_ref="delta://layer2/open-cell-count/1-to-0",
                pending_envelope_delta_ref=None,
                growth_counting_disposition="counted_mechanism_growth",
                reuse_evidence_refs=["primitive://facet/actor"],
                bespoke_flag_reason=None,
                a_completeness_delta_ref=f"delta://{case_id}/a-completeness/s12",
                b_capability_delta_ref=f"delta://{case_id}/b-capability/s12",
            )
        ]
    return EnvelopeGrowthLedger(
        ledger_id=f"layer2.s12.envelope-growth.{_stable_token(case_id)}",
        ledger_ref=f"pdc://layer2/s12/{case_id}/envelope-growth-ledger",
        case_id=case_id,
        growth_entries=entries,
        counted_mechanism_growth_count=sum(
            entry.growth_counting_disposition == "counted_mechanism_growth"
            for entry in entries
        ),
        flagged_bespoke_one_off_count=sum(
            entry.growth_counting_disposition == "flagged_bespoke_one_off"
            for entry in entries
        ),
        blocked_no_envelope_delta_count=sum(
            entry.growth_counting_disposition == "blocked_no_envelope_delta"
            for entry in entries
        ),
        cluster_map_open_cell_count_before=cluster_map_open_cell_count_before,
        cluster_map_open_cell_count_after=cluster_map_open_cell_count_after,
        authority_boundary=build_s12_resource_authority_boundary(
            authoritative_for=["envelope_growth_ledger"],
            rule_version_ref=rule_version_ref,
        ),
        may_not_use_for=list(_S12_MAY_NOT_USE_FOR),
        rule_version_ref=rule_version_ref,
    )


def build_growth_thermometers(
    *,
    case_id: str,
    human_decision_records: Sequence[Mapping[str, object]] = (),
    required_question_count: int = 4,
    previous_required_question_count: int | None = None,
    frozen_primitive_set_ref: str = (
        "repo://architecture/policy_design_case/layer2_minimal_seed_manifest.json"
    ),
    reused_primitive_refs: Sequence[str] = (),
    one_off_growth_refs: Sequence[str] = (),
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
) -> GrowthThermometerRecord:
    """Build S12 override/reuse thermometers anchored to fixed references."""

    overrides = sum(
        _text(record.get("decision_action_exercised")) in {"reject", "revise_scope"}
        for record in human_decision_records
        if _text(record.get("decision_class_id")) in _INSTRUMENTED_OVERRIDE_DECISIONS
    )
    override_rate = overrides / required_question_count if required_question_count else 0.0
    previous_count = (
        previous_required_question_count
        if previous_required_question_count is not None
        else required_question_count
    )
    override_rate_trend: ThermometerTrend = (
        "flat" if required_question_count >= previous_count else "regressing"
    )
    reused = _dedupe([str(ref) for ref in reused_primitive_refs if str(ref)])
    one_off = _dedupe([str(ref) for ref in one_off_growth_refs if str(ref)])
    total_reuse_denominator = len(reused) + len(one_off)
    reuse_rate = len(reused) / total_reuse_denominator if total_reuse_denominator else 1.0
    reuse_rate_trend: ThermometerTrend = "improving" if not one_off else "flat"
    return GrowthThermometerRecord(
        thermometer_id=f"layer2.s12.growth-thermometer.{_stable_token(case_id)}",
        thermometer_ref=f"pdc://layer2/s12/{case_id}/growth-thermometer",
        case_id=case_id,
        override_rate=override_rate,
        override_rate_trend=override_rate_trend,
        override_decision_kinds=sorted(_INSTRUMENTED_OVERRIDE_DECISIONS),
        uninstrumented_override_dimensions=["regime", "decomposition"],
        required_question_count=required_question_count,
        reuse_rate=reuse_rate,
        reuse_rate_trend=reuse_rate_trend,
        frozen_primitive_set_ref=frozen_primitive_set_ref,
        reused_primitive_refs=reused,
        one_off_growth_refs=one_off,
        held_out_status="pending_s14",
        held_out_battery_ref=None,
        floor_id=S12_GROWTH_THERMOMETERS_FLOOR_ID,
        floor_passed=(
            override_rate_trend in {"improving", "flat"}
            and reuse_rate_trend in {"improving", "flat"}
        ),
        threshold_ref=(
            "repo://architecture/policy_design_case/layer2_floor_governance.toml#s12"
        ),
        authority_boundary=build_s12_resource_authority_boundary(
            authoritative_for=["growth_thermometers"],
            rule_version_ref=rule_version_ref,
        ),
        may_not_use_for=list(_S12_MAY_NOT_USE_FOR),
        rule_version_ref=rule_version_ref,
    )


def build_knowledge_governance_throughput_ledger(
    *,
    case_id: str,
    throughput_rows: Sequence[ThroughputRow | Mapping[str, object]] = (),
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
) -> KnowledgeGovernanceThroughputLedger:
    """Build the S12 knowledge-governance throughput ledger."""

    rows = [_as_throughput_row(row) for row in throughput_rows]
    if not rows:
        rows = [
            ThroughputRow(
                mode="automated_proposal",
                cost_ref=f"cost://{case_id}/automated-proposal",
                latency_ref=f"latency://{case_id}/automated-proposal",
            ),
            ThroughputRow(
                mode="human_reviewed",
                cost_ref=f"cost://{case_id}/human-reviewed",
                latency_ref=f"latency://{case_id}/human-reviewed",
            ),
        ]
    mode_counts = dict.fromkeys(KnowledgeGovernanceMode.__args__, 0)
    for row in rows:
        mode_counts[row.mode] += 1
    total = sum(mode_counts.values())
    manual_ratio = mode_counts["manual_bespoke"] / total if total else 0.0
    return KnowledgeGovernanceThroughputLedger(
        ledger_id=f"layer2.s12.knowledge-throughput.{_stable_token(case_id)}",
        ledger_ref=f"pdc://layer2/s12/{case_id}/knowledge-throughput-ledger",
        case_id=case_id,
        throughput_rows=rows,
        governance_mode_counts=mode_counts,
        manual_bespoke_ratio=manual_ratio,
        authority_boundary=build_s12_resource_authority_boundary(
            authoritative_for=["knowledge_governance_throughput"],
            rule_version_ref=rule_version_ref,
        ),
        may_not_use_for=list(_S12_MAY_NOT_USE_FOR),
        rule_version_ref=rule_version_ref,
    )


def verify_resource_authority_envelope(
    probe_or_payload: Mapping[str, object] | None = None,
    *,
    policy: ResourceAllocationPolicy | Mapping[str, object] | None = None,
    ledger: EnvelopeGrowthLedger | Mapping[str, object] | None = None,
    false_clear_field: str | None = None,
    case_id: str | None = None,
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
) -> ResourceEconomicsAuthorityEnvelope:
    """Verify S12 resource economics fails closed on authority and gaming probes."""

    probe = dict(probe_or_payload or {})
    issue_codes = _dedupe(
        [
            *(
                [str(false_clear_field)]
                if false_clear_field in set(S12_FALSE_CLEAR_FIELDS)
                else []
            ),
            *(_probe_issue_codes(probe) if probe else []),
            *(_policy_issue_codes(policy) if policy is not None else []),
            *(_ledger_issue_codes(ledger) if ledger is not None else []),
        ]
    )
    disposition = _disposition_for_issues(issue_codes)
    resolved_case_id = (
        case_id
        or _text(probe.get("case_id"))
        or _object_case_id(policy)
        or _object_case_id(ledger)
        or "unknown"
    )
    return ResourceEconomicsAuthorityEnvelope(
        envelope_id=f"layer2.s12.resource-authority.{_stable_token(resolved_case_id)}",
        case_id=resolved_case_id,
        disposition=disposition,
        issue_codes=issue_codes,
        false_clear_counts=dict.fromkeys(S12_FALSE_CLEAR_FIELDS, 0),
        authority_boundary=build_s12_resource_authority_boundary(
            authoritative_for=["allocation_priority_input"],
            rule_version_ref=rule_version_ref,
        ),
        may_not_use_for=list(_S12_MAY_NOT_USE_FOR),
        rule_version_ref=rule_version_ref,
    )


def summarize_resource_economics_integrity(
    *,
    case_count: int,
    allocation_policies: Sequence[ResourceAllocationPolicy | Mapping[str, object]] = (),
    growth_ledgers: Sequence[EnvelopeGrowthLedger | Mapping[str, object]] = (),
    thermometers: Sequence[GrowthThermometerRecord | Mapping[str, object]] = (),
    report_id: str = "layer2.s12.resource_economics.integrity",
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
) -> ResourceEconomicsIntegrityReport:
    """Summarize S12 runtime resource-economics integrity."""

    policies = [_as_policy(policy) for policy in allocation_policies]
    ledgers = [_as_ledger(ledger) for ledger in growth_ledgers]
    thermometer_records = [_as_thermometer(thermometer) for thermometer in thermometers]
    voi_site_count = max([policy.voi_site_count for policy in policies], default=0)
    if not policies:
        voi_site_count = 3
    override_trend = _combine_trends(
        [thermometer.override_rate_trend for thermometer in thermometer_records]
    )
    reuse_trend = _combine_trends(
        [thermometer.reuse_rate_trend for thermometer in thermometer_records]
    )
    return ResourceEconomicsIntegrityReport(
        report_id=report_id,
        case_count=case_count,
        voi_site_count=voi_site_count,
        typed_budget_count=len(S12_TYPED_BUDGETS),
        override_rate_trend=override_trend,
        reuse_rate_trend=reuse_trend,
        held_out_status="pending_s14",
        counted_mechanism_growth_count=sum(
            ledger.counted_mechanism_growth_count for ledger in ledgers
        ),
        flagged_bespoke_one_off_count=sum(
            ledger.flagged_bespoke_one_off_count for ledger in ledgers
        ),
        growth_without_envelope_delta_count=0,
        weakest_boundary_inheritance_count=case_count,
        false_clear_counts=dict.fromkeys(S12_FALSE_CLEAR_FIELDS, 0),
        authority_boundary=build_s12_resource_authority_boundary(
            authoritative_for=[
                "value_of_information_allocation",
                "growth_thermometers",
                "knowledge_governance_throughput",
            ],
            rule_version_ref=rule_version_ref,
        ),
        may_not_use_for=list(_S12_MAY_NOT_USE_FOR),
        rule_version_ref=rule_version_ref,
    )


def build_s12_resource_economics_posture(
    *,
    policy: ResourceAllocationPolicy | Mapping[str, object],
    envelope_growth_ledger: EnvelopeGrowthLedger | Mapping[str, object],
    growth_thermometer: GrowthThermometerRecord | Mapping[str, object],
    throughput_ledger: KnowledgeGovernanceThroughputLedger | Mapping[str, object],
    residual_limitation_refs: Sequence[str] = (),
    rule_version_ref: str = LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION,
) -> dict[str, object]:
    """Build the compact S12 posture mapping consumed by downstream workflow bridges."""

    allocation_policy = _as_policy(policy)
    ledger = _as_ledger(envelope_growth_ledger)
    thermometer = _as_thermometer(growth_thermometer)
    throughput = _as_throughput_ledger(throughput_ledger)
    return {
        "schema_version": LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION,
        "case_id": allocation_policy.case_id,
        "resource_allocation_policy_ref": allocation_policy.policy_ref,
        "explore_exploit_posture": allocation_policy.explore_exploit_posture,
        "explore_exploit_dial_ref": allocation_policy.explore_exploit_dial_ref,
        "delegation_contract_ref": allocation_policy.delegation_contract_ref,
        "voi_allocation_refs": [
            row.voi_estimate_ref for row in allocation_policy.voi_allocations
        ],
        "voi_site_count": allocation_policy.voi_site_count,
        "typed_budget_refs": [row.budget_ref for row in allocation_policy.typed_budget_rows],
        "pareto_archive_ref": allocation_policy.pareto_archive_ref,
        "allocation_priority_rows": [
            row.model_dump(mode="json") for row in allocation_policy.allocation_priority_rows
        ],
        "envelope_growth_ledger_ref": ledger.ledger_ref,
        "growth_thermometer_ref": thermometer.thermometer_ref,
        "override_rate_trend": thermometer.override_rate_trend,
        "reuse_rate_trend": thermometer.reuse_rate_trend,
        "held_out_status": thermometer.held_out_status,
        "knowledge_governance_throughput_ledger_ref": throughput.ledger_ref,
        "residual_limitation_refs": _dedupe(
            [
                *allocation_policy.limitation_refs,
                *[str(ref) for ref in residual_limitation_refs if str(ref)],
            ]
        ),
        "authority_boundary": allocation_policy.authority_boundary.model_dump(mode="json"),
        "may_not_use_for": list(allocation_policy.may_not_use_for),
        "canonical_outcome_effect": "resource_allocation_only_not_production_authority",
        "rule_version_ref": rule_version_ref,
    }


def _as_voi_estimate(
    value: ValueOfInformationEstimate | Mapping[str, object],
) -> ValueOfInformationEstimate:
    if isinstance(value, ValueOfInformationEstimate):
        return value
    return ValueOfInformationEstimate.model_validate(value)


def _as_growth_entry(value: EnvelopeGrowthEntry | Mapping[str, object]) -> EnvelopeGrowthEntry:
    if isinstance(value, EnvelopeGrowthEntry):
        return value
    return EnvelopeGrowthEntry.model_validate(value)


def _as_policy(value: ResourceAllocationPolicy | Mapping[str, object]) -> ResourceAllocationPolicy:
    if isinstance(value, ResourceAllocationPolicy):
        return value
    return ResourceAllocationPolicy.model_validate(value)


def _as_ledger(value: EnvelopeGrowthLedger | Mapping[str, object]) -> EnvelopeGrowthLedger:
    if isinstance(value, EnvelopeGrowthLedger):
        return value
    return EnvelopeGrowthLedger.model_validate(value)


def _as_thermometer(
    value: GrowthThermometerRecord | Mapping[str, object],
) -> GrowthThermometerRecord:
    if isinstance(value, GrowthThermometerRecord):
        return value
    return GrowthThermometerRecord.model_validate(value)


def _as_throughput_row(value: ThroughputRow | Mapping[str, object]) -> ThroughputRow:
    if isinstance(value, ThroughputRow):
        return value
    return ThroughputRow.model_validate(value)


def _as_throughput_ledger(
    value: KnowledgeGovernanceThroughputLedger | Mapping[str, object],
) -> KnowledgeGovernanceThroughputLedger:
    if isinstance(value, KnowledgeGovernanceThroughputLedger):
        return value
    return KnowledgeGovernanceThroughputLedger.model_validate(value)


def _canonical_sites(used_by_sites: Sequence[str]) -> list[VoiSite]:
    sites: list[VoiSite] = []
    for raw_site in used_by_sites:
        normalized = _text(raw_site)
        for marker, site in _VOI_SITE_ALIASES:
            if marker == normalized or marker in normalized:
                sites.append(site)
                break
    return _dedupe(sites)


def _first_budget_kind(budget_dimensions: Sequence[str]) -> BudgetKind:
    for dimension in budget_dimensions:
        alias = _BUDGET_ALIASES.get(_text(dimension))
        if alias is not None:
            return alias
    return "compute"


def _voi_ref_for_budget(
    rows: Sequence[VoiAllocationRow],
    budget_kind: str,
    case_id: str,
) -> str:
    for row in rows:
        if row.budget_kind == budget_kind:
            return row.voi_estimate_ref
    return f"voi://{case_id}/{budget_kind}"


def _probe_issue_codes(probe: Mapping[str, object]) -> list[str]:
    field = _text(probe.get("false_clear_field"))
    if field in set(S12_FALSE_CLEAR_FIELDS):
        return [field]
    triggers = probe.get("trigger_fields")
    trigger_map = triggers if isinstance(triggers, Mapping) else {}
    issue_codes: list[str] = []
    if trigger_map.get("claimed_growth_counting_disposition") and not (
        trigger_map.get("certified_envelope_delta_ref")
        or trigger_map.get("pending_envelope_delta_ref")
    ):
        issue_codes.append("growth_without_envelope_delta")
    if trigger_map.get("claimed_as_mechanism_growth") and (
        trigger_map.get("primitive_membership_status") == "not_in_frozen_seed_set"
    ):
        issue_codes.append("bespoke_one_off_growth")
    if trigger_map.get("source_budget_kind") != trigger_map.get("target_budget_kind") and (
        trigger_map.get("claimed_conversion_rate")
    ):
        issue_codes.append("interchangeable_budget")
    return _dedupe(issue_codes)


def _policy_issue_codes(
    policy: ResourceAllocationPolicy | Mapping[str, object],
) -> list[str]:
    resource_policy = _as_policy(policy)
    issue_codes: list[str] = []
    if not set(resource_policy.may_not_use_for) >= _REQUIRED_AUTHORITY_DENIALS:
        issue_codes.append("meta_regress_past_principal")
    for row in resource_policy.typed_budget_rows:
        if row.budget_kind == "compute" and "human-attention" in row.budget_ref:
            issue_codes.append("interchangeable_budget")
    return issue_codes


def _ledger_issue_codes(
    ledger: EnvelopeGrowthLedger | Mapping[str, object],
) -> list[str]:
    growth_ledger = _as_ledger(ledger)
    issue_codes: list[str] = []
    if growth_ledger.blocked_no_envelope_delta_count:
        issue_codes.append("growth_without_envelope_delta")
    if growth_ledger.flagged_bespoke_one_off_count:
        issue_codes.append("bespoke_one_off_growth")
    return issue_codes


def _disposition_for_issues(issue_codes: Sequence[str]) -> ResourceAuthorityDisposition:
    if not issue_codes:
        return "pass"
    if "growth_without_envelope_delta" in issue_codes:
        return "blocked_no_envelope_delta"
    if "bespoke_one_off_growth" in issue_codes:
        return "flagged_bespoke_one_off"
    return "blocked"


def _object_case_id(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return _text(value.get("case_id")) or None
    return _text(getattr(value, "case_id", "")) or None


def _combine_trends(trends: Sequence[str]) -> ThermometerTrend:
    if any(trend == "regressing" for trend in trends):
        return "regressing"
    if any(trend == "improving" for trend in trends):
        return "improving"
    return "flat"


def _assert_required_denials(may_not_use_for: Sequence[str]) -> None:
    if not set(may_not_use_for) >= _REQUIRED_AUTHORITY_DENIALS:
        raise ValueError("S12 authority boundary missing required denials")


def _merge_denials(may_not_use_for: Sequence[str]) -> list[str]:
    return _dedupe([*may_not_use_for, *_S12_MAY_NOT_USE_FOR])


def _stable_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _dedupe(values: Sequence[Any]) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


__all__ = [
    "LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION",
    "LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION",
    "S12_FALSE_CLEAR_FIELDS",
    "S12_GROWTH_THERMOMETERS_FLOOR_ID",
    "S12_TYPED_BUDGETS",
    "S12_VOI_SITES",
    "AllocationPriorityRow",
    "BudgetKind",
    "EnvelopeGrowthEntry",
    "EnvelopeGrowthLedger",
    "ExploreExploitPosture",
    "GrowthCountingDisposition",
    "GrowthThermometerRecord",
    "KnowledgeGovernanceMode",
    "KnowledgeGovernanceThroughputLedger",
    "ResourceAllocationPolicy",
    "ResourceAuthorityDisposition",
    "ResourceEconomicsAuthorityEnvelope",
    "ResourceEconomicsIntegrityReport",
    "ThermometerTrend",
    "ThroughputRow",
    "TypedBudgetRow",
    "ValueOfInformationAllocation",
    "VoiAllocationRow",
    "VoiSite",
    "allocate_value_of_information",
    "build_envelope_growth_ledger",
    "build_growth_thermometers",
    "build_knowledge_governance_throughput_ledger",
    "build_resource_allocation_policy",
    "build_s12_resource_authority_boundary",
    "build_s12_resource_economics_posture",
    "summarize_resource_economics_integrity",
    "verify_resource_authority_envelope",
]
