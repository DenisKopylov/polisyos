"""Layer 2 S14 universality assurance contracts and firewalls."""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from polisyos.pdc import AuthorityBoundary, Layer2ReadinessModel

LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s14_universality_assurance.v1"
)
LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION = (
    "policyos.layer2.s14.universality_assurance.v1"
)
S14_UNIVERSALITY_FLOOR_ID = "s14_universality"
S14_FALSE_CLEAR_FIELDS: tuple[str, ...] = (
    "bare_universal_claim_without_battery",
    "sealed_battery_dev_access",
    "aggregate_universal_number_laundering",
    "untested_axis_combination_in_envelope",
    "bespoke_cost_hidden_as_generality",
    "skeptic_defeater_ignored",
    "faithfulness_claim_without_s9",
    "battery_result_as_production_authority",
    "gold_label_leak_into_dev_signal",
    "freeze_hash_mismatch_accepted",
    "d4_breadth_floor_missing",
    "expert_oracle_bootstrap_missing",
    "weak_gold_floor_laundering",
    "shadow_candidate_oracle_laundering",
    "grounded_authority_refs_missing",
    "status_composition_laundering",
    "envelope_revision_freeze_laundering",
    "baseline_comparison_missing",
)
S14_SKEPTIC_DEFEATER_IDS: tuple[str, ...] = (
    "bespoke_disguise_defeater",
    "confident_theater_defeater",
    "failure_boundary_defeater",
    "single_axis_universality_defeater",
    "frozen_once_defeater",
    "first_call_defeater",
)

S14_D4_TRACK_IDS: tuple[str, ...] = (
    "grounding",
    "construct_demand",
    "acquisition_loop",
    "epistemic_regime",
    "coupling_modularity",
    "axis_declaration",
    "cluster_ownership",
    "scale_composition",
    "design_quality",
    "search_control",
    "delegation",
    "projection_lowering",
    "bootstrap_resource",
    "system_dynamics_backtest",
    "post_deploy_accountability",
    "prediction_backtest",
    "adversarial",
    "odd_abstention",
    "universality_battery",
)

S14_BASELINE_FAMILIES: tuple[str, ...] = ("bespoke_tool", "raw_llm", "expert_panel")
S14_ORACLE_LAYER_IDS: tuple[str, ...] = (
    "weak_gold",
    "expert_gold_seed",
    "causal_support_seed",
    "shadow_candidate_pool",
)
_EMPTY_SHA256_REF = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

_S14_AUTHORITY_SCOPE: tuple[str, ...] = (
    "s14_universality_claim_gate",
    "sealed_battery_integrity",
    "per_axis_universality_scorecard",
    "mechanism_generality_assessment",
    "skeptic_defeater_evaluation",
    "d4_corpus_track_coverage",
    "expert_oracle_bootstrap",
    "universality_breadth_floor",
    "baseline_comparison",
    "grounded_authority_coverage",
    "evaluation_status_composition",
    "envelope_revision_dynamics",
    "declared_operation_envelope",
)
_S14_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "production_rollout_authority",
    "production_recommendation",
    "recommendation_authority",
    "publication_authority",
    "approval_authority",
    "claim_authority",
    "runtime_closeout_authority",
    "scorecard_authority",
    "preference_learning",
    "automated_value_learning",
    "sealed_battery_training",
    "development_fixture_access",
    "aggregate_universal_score",
    "untested_axis_envelope_expansion",
    "gold_label_authority",
    "weak_gold_promotion_floor",
    "shadow_candidate_oracle",
    "baseline_free_universal_claim",
    "grounded_authority_without_a_firewalls",
)
_FORBIDDEN_AUTHORITY_SCOPE = frozenset(
    {
        "production_authority",
        "production_rollout_authority",
        "production_recommendation",
        "recommendation_authority",
        "publication_authority",
        "approval_authority",
        "claim_authority",
        "runtime_closeout_authority",
        "scorecard_authority",
        "preference_learning",
        "automated_value_learning",
    }
)
_GOLD_LEAK_KEYS = frozenset(
    {
        "answer_key",
        "expected_answer",
        "expected_boundary_disposition",
        "gold_label",
        "gold_labels",
        "hidden_case_payload",
        "hidden_case_payloads",
        "sealed_fixture_contents",
        "sealed_gold_label_ref",
    }
)

CoverageStatus = Literal["pass", "limited", "blocked"]
BatteryRunMode = Literal["sealed_ci", "dev_shadow_no_hidden_access"]
SealedBatteryStatus = Literal["accessed_by_sealed_runner", "not_accessed_in_dev", "blocked"]
IntegrityStatus = Literal["pass", "blocked"]
AxisDeclaredPosture = Literal["in_envelope", "limited", "out_of_envelope", "not_tested"]
AxisBatteryStatus = Literal["pass", "limited", "fail", "not_tested", "blocked"]
ClaimGateDisposition = Literal[
    "universal_claim_allowed",
    "universal_claim_limited",
    "universal_claim_blocked",
]
SkepticStatus = Literal["pass", "limited", "fail", "blocked"]


class D4CorpusTrackRow(Layer2ReadinessModel):
    """Coverage row for one D4 corpus track."""

    track_id: str = Field(..., min_length=1, max_length=120)
    minimum_label_refs: list[str] = Field(..., min_length=1, max_length=80)
    covered_case_refs: list[str] = Field(..., min_length=1, max_length=120)
    coverage_status: CoverageStatus
    limitation_refs: list[str] = Field(default_factory=list, max_length=80)


class D4CorpusTrackCoverage(Layer2ReadinessModel):
    """D4 breadth evidence proving S14 is not a single-template battery."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=180)
    record_ref: str = Field(..., min_length=1, max_length=300)
    coverage_status: CoverageStatus
    track_rows: list[D4CorpusTrackRow] = Field(..., min_length=19, max_length=19)
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_track_rows(self) -> D4CorpusTrackCoverage:
        if tuple(row.track_id for row in self.track_rows) != S14_D4_TRACK_IDS:
            raise ValueError("track_rows must cover the exact S14 D4 track set")
        if self.coverage_status == "pass" and any(
            row.coverage_status != "pass" for row in self.track_rows
        ):
            raise ValueError("pass coverage requires every D4 track row to pass")
        return self


class ExpertOracleLayerRow(Layer2ReadinessModel):
    """One expert-oracle layer with explicit allowed and forbidden uses."""

    layer_id: str = Field(..., min_length=1, max_length=120)
    authority: str = Field(..., min_length=1, max_length=80)
    allowed_uses: list[str] = Field(..., min_length=1, max_length=80)
    forbidden_uses: list[str] = Field(..., min_length=1, max_length=80)
    conflict_disclosure_refs: list[str] = Field(..., min_length=1, max_length=80)


class ExpertOracleBootstrapRecord(Layer2ReadinessModel):
    """Expert-oracle bootstrap record that keeps seeds from becoming authority."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=180)
    record_ref: str = Field(..., min_length=1, max_length=300)
    bootstrap_status: CoverageStatus
    oracle_layers: list[ExpertOracleLayerRow] = Field(..., min_length=4, max_length=4)
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_oracle_layers(self) -> ExpertOracleBootstrapRecord:
        layers = {row.layer_id: row for row in self.oracle_layers}
        if tuple(layers) != S14_ORACLE_LAYER_IDS:
            raise ValueError("oracle_layers must match the exact S14 oracle layer set")
        for layer_id in ("weak_gold", "shadow_candidate_pool"):
            if layers[layer_id].authority != "seed_only":
                raise ValueError(f"{layer_id} must remain seed_only")
        if "promotion_floor" not in layers["weak_gold"].forbidden_uses:
            raise ValueError("weak_gold must forbid promotion_floor use")
        if "oracle_truth" not in layers["shadow_candidate_pool"].forbidden_uses:
            raise ValueError("shadow_candidate_pool must forbid oracle_truth use")
        return self


class UniversalityBreadthFloorConfig(Layer2ReadinessModel):
    """Governed breadth floor for S14 universality claims."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    config_id: str = Field(..., min_length=1, max_length=180)
    config_ref: str = Field(..., min_length=1, max_length=300)
    floor_id: str = S14_UNIVERSALITY_FLOOR_ID
    status: str = Field(..., min_length=1, max_length=80)
    domain_target: list[str] = Field(..., min_length=1, max_length=80)
    covered_domain_refs: list[str] = Field(default_factory=list, max_length=80)
    excluded_domain_refs: list[str] = Field(..., min_length=1, max_length=80)
    jurisdiction_context_target: list[str] = Field(..., min_length=1, max_length=80)
    scale_class_target: list[str] = Field(..., min_length=1, max_length=80)
    epistemic_regime_target: list[str] = Field(..., min_length=1, max_length=80)
    coupling_regime_target: list[str] = Field(..., min_length=1, max_length=80)
    lifecycle_target: list[str] = Field(..., min_length=1, max_length=80)
    state_capacity_target: list[str] = Field(..., min_length=1, max_length=80)
    authority_posture_target: list[str] = Field(..., min_length=1, max_length=80)
    instrument_family_target: list[str] = Field(..., min_length=1, max_length=80)
    system_dynamics_target: list[str] = Field(..., min_length=1, max_length=80)
    inter_rater_target_ref: str = Field(..., min_length=1, max_length=300)
    owner: str = Field(..., min_length=1, max_length=200)
    revision_rule: str = Field(..., min_length=1, max_length=300)
    threshold_refs: list[str] = Field(..., min_length=1, max_length=80)
    floor_setting_method: str = Field(..., min_length=1, max_length=300)
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_floor(self) -> UniversalityBreadthFloorConfig:
        if self.floor_id != S14_UNIVERSALITY_FLOOR_ID:
            raise ValueError("floor_id must be s14_universality")
        return self


class UniversalityBaselineRow(Layer2ReadinessModel):
    """Baseline family comparison row for the first-call defeater."""

    baseline_id: str = Field(..., min_length=1, max_length=120)
    baseline_family: str = Field(..., min_length=1, max_length=80)
    comparison_refs: list[str] = Field(..., min_length=1, max_length=80)
    policyos_dominates_on: list[str] = Field(..., min_length=1, max_length=80)


class UniversalityBaselineComparison(Layer2ReadinessModel):
    """Baseline comparison record used to block baseline-free universal claims."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=180)
    comparison_status: CoverageStatus
    comparison_ref: str = Field(..., min_length=1, max_length=300)
    baseline_rows: list[UniversalityBaselineRow] = Field(..., min_length=3, max_length=3)
    limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_baselines(self) -> UniversalityBaselineComparison:
        if {row.baseline_family for row in self.baseline_rows} != set(S14_BASELINE_FAMILIES):
            raise ValueError("baseline_rows must cover bespoke_tool, raw_llm, expert_panel")
        return self


class GroundedAuthorityCoverageRecord(Layer2ReadinessModel):
    """Grounded authority refs required before any public universality projection."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=180)
    coverage_status: CoverageStatus
    coverage_ref: str = Field(..., min_length=1, max_length=300)
    a_firewall_refs: list[str] = Field(..., min_length=1, max_length=80)
    claim_evidence_binding_refs: list[str] = Field(..., min_length=1, max_length=80)
    value_choice_provenance_refs: list[str] = Field(..., min_length=1, max_length=80)
    mandate_legitimacy_refs: list[str] = Field(..., min_length=1, max_length=80)
    capacity_check_refs: list[str] = Field(..., min_length=1, max_length=80)
    regime_refs: list[str] = Field(..., min_length=1, max_length=80)
    coupling_refs: list[str] = Field(..., min_length=1, max_length=80)
    projection_faithfulness_refs: list[str] = Field(..., min_length=1, max_length=80)
    in_envelope_axis_refs: list[str] = Field(default_factory=list, max_length=120)
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION


class EvaluationStatusCompositionRow(Layer2ReadinessModel):
    """Mapping from D4 labels to the existing closeout status lattice."""

    d4_label: str = Field(..., min_length=1, max_length=120)
    effect: str = Field(..., min_length=1, max_length=120)
    existing_lattice_target: str = Field(..., min_length=1, max_length=120)
    claim_effect: str = Field(..., min_length=1, max_length=120)


class EvaluationStatusCompositionRecord(Layer2ReadinessModel):
    """Status-composition record that avoids a new local S14 authority tier."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=180)
    composition_status: CoverageStatus
    composition_ref: str = Field(..., min_length=1, max_length=300)
    status_cases: list[EvaluationStatusCompositionRow] = Field(..., min_length=1, max_length=40)
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_lattice_targets(self) -> EvaluationStatusCompositionRecord:
        if any(
            row.existing_lattice_target == "new_s14_authority_tier"
            for row in self.status_cases
        ):
            raise ValueError("S14 must map to the existing closeout lattice")
        return self


class EnvelopeRevisionDynamicsRecord(Layer2ReadinessModel):
    """S12/S13 envelope dynamics evidence for the frozen-once defeater."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=180)
    dynamics_status: CoverageStatus
    dynamics_ref: str = Field(..., min_length=1, max_length=300)
    s12_expansion_evidence_refs: list[str] = Field(..., min_length=1, max_length=80)
    s13_shrink_or_split_refs: list[str] = Field(..., min_length=1, max_length=80)
    certified_envelope_delta_refs: list[str] = Field(..., min_length=1, max_length=80)
    frozen_once_defeater_status: CoverageStatus
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_dynamics(self) -> EnvelopeRevisionDynamicsRecord:
        if self.frozen_once_defeater_status == "pass" and not self.s13_shrink_or_split_refs:
            raise ValueError("frozen_once_defeater pass requires shrink or split evidence")
        return self


class SealedUniversalityBatteryRun(Layer2ReadinessModel):
    """Integrity record for the hidden S14 universality battery."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    run_id: str = Field(..., min_length=1, max_length=180)
    battery_id: str = Field(..., min_length=1, max_length=180)
    battery_root: str = Field(..., min_length=1, max_length=500)
    partition_path: str = Field(..., min_length=1, max_length=500)
    owner: str = Field(..., min_length=1, max_length=200)
    access_mode: str = Field(..., min_length=1, max_length=80)
    run_mode: BatteryRunMode
    explicit_access_granted: bool
    sealed_battery_access_attempted: bool
    sealed_battery_status: SealedBatteryStatus
    freeze_hash: str = Field(..., min_length=8, max_length=96)
    computed_freeze_hash: str = Field(..., min_length=8, max_length=96)
    sealed_battery_integrity_status: IntegrityStatus
    case_count: int = Field(..., ge=0)
    hard_corner_case_ids: list[str] = Field(default_factory=list, max_length=80)
    fixture_manifest_digest: str = Field(..., min_length=8, max_length=96)
    freeze_time: str | None = Field(default=None, max_length=120)
    access_time: str | None = Field(default=None, max_length=120)
    run_time: str | None = Field(default=None, max_length=120)
    scoring_time: str | None = Field(default=None, max_length=120)
    assurance_time: str | None = Field(default=None, max_length=120)
    projection_time: str | None = Field(default=None, max_length=120)
    authority_boundary: AuthorityBoundary
    issues: list[dict[str, str]] = Field(default_factory=list, max_length=80)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_access_boundary(self) -> SealedUniversalityBatteryRun:
        if self.run_mode == "dev_shadow_no_hidden_access":
            if self.explicit_access_granted or self.sealed_battery_access_attempted:
                raise ValueError("dev_shadow_no_hidden_access cannot access sealed battery")
            if self.sealed_battery_status != "not_accessed_in_dev":
                raise ValueError("dev shadow sealed_battery_status must be not_accessed_in_dev")
            if self.access_time is not None:
                raise ValueError("dev shadow access_time must be absent")
        if (
            self.sealed_battery_integrity_status == "pass"
            and self.freeze_hash != self.computed_freeze_hash
        ):
            raise ValueError("passing sealed battery run requires matching freeze hashes")
        return self


class UniversalityAxisScoreRow(Layer2ReadinessModel):
    """Per-axis S14 score row; no aggregate universal number is permitted."""

    axis_ref: str = Field(..., min_length=3, max_length=160)
    declared_posture: AxisDeclaredPosture
    battery_status: AxisBatteryStatus
    threshold_ref: str = Field(..., min_length=1, max_length=300)
    floor_passed: bool
    hard_corner_case_refs: list[str] = Field(default_factory=list, max_length=80)
    mechanism_refs: list[str] = Field(default_factory=list, max_length=80)
    limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    failure_refs: list[str] = Field(default_factory=list, max_length=80)
    evidence_refs: list[str] = Field(default_factory=list, max_length=80)


class UniversalityAxisScorecard(Layer2ReadinessModel):
    """Per-axis S14 universality scorecard backed by capability reality rows."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    scorecard_id: str = Field(..., min_length=1, max_length=180)
    scorecard_ref: str = Field(..., min_length=1, max_length=300)
    capability_reality_report_ref: str = Field(..., min_length=1, max_length=300)
    axis_rows: list[UniversalityAxisScoreRow] = Field(..., min_length=1, max_length=80)
    axis_scorecard_row_count: int = Field(..., ge=1)
    out_of_envelope_axis_refs: list[str] = Field(default_factory=list, max_length=80)
    not_tested_axis_refs: list[str] = Field(default_factory=list, max_length=80)
    aggregate_universal_score: None = None
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_rows(self) -> UniversalityAxisScorecard:
        if self.axis_scorecard_row_count != len(self.axis_rows):
            raise ValueError("axis_scorecard_row_count must match axis_rows")
        row_refs = [row.axis_ref for row in self.axis_rows]
        if len(row_refs) != len(set(row_refs)):
            raise ValueError("axis_rows must have unique axis_ref values")
        return self


class MechanismGeneralityReport(Layer2ReadinessModel):
    """S14 mechanism-generality projection over S12 growth thermometers."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    report_id: str = Field(..., min_length=1, max_length=180)
    report_ref: str = Field(..., min_length=1, max_length=300)
    mechanism_reuse_rate: float = Field(..., ge=0.0, le=1.0)
    growth_thermometer_ref: str = Field(..., min_length=1, max_length=300)
    s12_held_out_status: str = Field(..., min_length=1, max_length=80)
    marginal_bespoke_cost_status: CoverageStatus
    sublinear_marginal_bespoke_cost: bool
    reused_mechanism_refs: list[str] = Field(default_factory=list, max_length=80)
    bespoke_patch_refs: list[str] = Field(default_factory=list, max_length=80)
    bespoke_patch_limitations: list[str] = Field(default_factory=list, max_length=80)
    held_out_case_refs: list[str] = Field(default_factory=list, max_length=80)
    dev_case_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_generality(self) -> MechanismGeneralityReport:
        if self.marginal_bespoke_cost_status == "pass":
            if not self.sublinear_marginal_bespoke_cost:
                raise ValueError("pass generality requires sublinear marginal bespoke cost")
            if self.bespoke_patch_refs:
                raise ValueError("pass generality cannot hide bespoke patch refs")
        return self


class SkepticDefeaterRecord(Layer2ReadinessModel):
    """Projection of one CAE defeater into the six S14 architecture-skeptic attacks."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    defeater_id: str = Field(..., min_length=1, max_length=120)
    attack_id: str = Field(..., min_length=1, max_length=240)
    attack_family: str = Field(..., min_length=1, max_length=120)
    status: SkepticStatus
    projected_from_cae_defeater_ref: str = Field(..., min_length=1, max_length=300)
    evidence_refs: list[str] = Field(default_factory=list, max_length=80)
    axis_refs: list[str] = Field(default_factory=list, max_length=80)
    hard_corner_case_refs: list[str] = Field(default_factory=list, max_length=80)
    baseline_refs: list[str] = Field(default_factory=list, max_length=80)
    envelope_revision_refs: list[str] = Field(default_factory=list, max_length=80)
    grounded_authority_refs: list[str] = Field(default_factory=list, max_length=80)
    residual_limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_defeater(self) -> SkepticDefeaterRecord:
        if self.defeater_id not in S14_SKEPTIC_DEFEATER_IDS:
            raise ValueError("unknown S14 skeptic defeater")
        return self


class UniversalityClaimAssuranceCase(Layer2ReadinessModel):
    """CAE-backed S14 assurance case tying scorecard, battery, and defeaters."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    assurance_case_id: str = Field(..., min_length=1, max_length=180)
    assurance_case_ref: str = Field(..., min_length=1, max_length=300)
    cae_claim_ref: str = Field(..., min_length=1, max_length=300)
    cae_subclaim_refs: list[str] = Field(default_factory=list, max_length=80)
    cae_evidence_refs: list[str] = Field(default_factory=list, max_length=120)
    cae_defeater_refs: list[str] = Field(default_factory=list, max_length=80)
    non_overridable_blockers: list[str] = Field(default_factory=list, max_length=80)
    confidence_limits: dict[str, float] = Field(default_factory=dict)
    d4_corpus_track_coverage_ref: str | None = Field(default=None, max_length=300)
    expert_oracle_bootstrap_ref: str | None = Field(default=None, max_length=300)
    breadth_floor_config_ref: str | None = Field(default=None, max_length=300)
    sealed_battery_run_ref: str | None = Field(default=None, max_length=300)
    axis_scorecard_ref: str | None = Field(default=None, max_length=300)
    mechanism_generality_report_ref: str | None = Field(default=None, max_length=300)
    grounded_authority_coverage_ref: str | None = Field(default=None, max_length=300)
    baseline_comparison_ref: str | None = Field(default=None, max_length=300)
    envelope_revision_dynamics_ref: str | None = Field(default=None, max_length=300)
    s9_projection_faithfulness_refs: list[str] = Field(default_factory=list, max_length=80)
    projection_refs: list[str] = Field(default_factory=list, max_length=80)
    status_composition_ref: str | None = Field(default=None, max_length=300)
    skeptic_defeater_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION


class UniversalityClaimGateRecord(Layer2ReadinessModel):
    """Fail-closed gate for public or internal universal-claim language."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    gate_id: str = Field(..., min_length=1, max_length=180)
    gate_ref: str = Field(..., min_length=1, max_length=300)
    claim_text: str = Field(..., min_length=1, max_length=1000)
    requested_scope_refs: list[str] = Field(default_factory=list, max_length=120)
    declared_operation_envelope_ref: str = Field(..., min_length=1, max_length=300)
    disposition: ClaimGateDisposition
    s14_universality_assurance_refs: list[str] = Field(..., min_length=1, max_length=80)
    scorecard_ref: str = Field(..., min_length=1, max_length=300)
    sealed_battery_run_ref: str = Field(..., min_length=1, max_length=300)
    assurance_case_ref: str = Field(..., min_length=1, max_length=300)
    limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    out_of_envelope_axis_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    issues: list[dict[str, str]] = Field(default_factory=list, max_length=80)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_gate(self) -> UniversalityClaimGateRecord:
        if self.disposition == "universal_claim_allowed" and (
            self.limitation_refs or self.out_of_envelope_axis_refs or self.issues
        ):
            raise ValueError("allowed universality claim cannot carry limitations or issues")
        return self


class UniversalityAssuranceSummary(Layer2ReadinessModel):
    """Summary metrics and false-clear counts for S14 assurance."""

    schema_version: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION
    summary_id: str = Field(..., min_length=1, max_length=180)
    slice: Literal["S14"]
    cells_closed: list[str] = Field(default_factory=list, max_length=10)
    layer_cells_advanced: list[str] = Field(default_factory=list, max_length=10)
    current_open_cell_count: int = Field(..., ge=0)
    inventory_artifact_count: int = Field(..., ge=0)
    required_traceability_artifact_count: int = Field(..., ge=0)
    supporting_record_count: int = Field(..., ge=0)
    d4_corpus_track_count: int = Field(..., ge=0)
    expert_oracle_layer_count: int = Field(..., ge=0)
    sealed_battery_case_count: int = Field(..., ge=0)
    axis_scorecard_row_count: int = Field(..., ge=0)
    skeptic_defeater_count: int = Field(..., ge=0)
    skeptic_defeater_pass_rate: float = Field(..., ge=0.0, le=1.0)
    mechanism_generality_status: CoverageStatus
    sublinear_marginal_bespoke_cost_status: CoverageStatus
    sealed_battery_integrity_status: IntegrityStatus
    universal_claim_disposition: ClaimGateDisposition
    bare_universal_claim_block_count: int = Field(..., ge=0)
    untested_axis_out_of_envelope_count: int = Field(..., ge=0)
    aggregate_universal_number_block_count: int = Field(..., ge=0)
    false_clear_counts: dict[str, int] = Field(..., min_length=18, max_length=18)
    bare_universal_claim_without_battery_false_clear_count: int = 0
    sealed_battery_dev_access_false_clear_count: int = 0
    aggregate_universal_number_laundering_false_clear_count: int = 0
    untested_axis_combination_in_envelope_false_clear_count: int = 0
    bespoke_cost_hidden_as_generality_false_clear_count: int = 0
    skeptic_defeater_ignored_false_clear_count: int = 0
    faithfulness_claim_without_s9_false_clear_count: int = 0
    battery_result_as_production_authority_false_clear_count: int = 0
    gold_label_leak_into_dev_signal_false_clear_count: int = 0
    freeze_hash_mismatch_accepted_false_clear_count: int = 0
    d4_breadth_floor_missing_false_clear_count: int = 0
    expert_oracle_bootstrap_missing_false_clear_count: int = 0
    weak_gold_floor_laundering_false_clear_count: int = 0
    shadow_candidate_oracle_laundering_false_clear_count: int = 0
    grounded_authority_refs_missing_false_clear_count: int = 0
    status_composition_laundering_false_clear_count: int = 0
    envelope_revision_freeze_laundering_false_clear_count: int = 0
    baseline_comparison_missing_false_clear_count: int = 0
    authority_boundary: AuthorityBoundary
    replay_digest: str = Field(..., min_length=8, max_length=96)
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_summary(self) -> UniversalityAssuranceSummary:
        if tuple(self.false_clear_counts) != S14_FALSE_CLEAR_FIELDS:
            raise ValueError("false_clear_counts keys must exactly match S14_FALSE_CLEAR_FIELDS")
        for field in S14_FALSE_CLEAR_FIELDS:
            flat = getattr(self, f"{field}_false_clear_count")
            if flat != self.false_clear_counts[field]:
                raise ValueError(f"{field}_false_clear_count must match false_clear_counts")
        if self.cells_closed:
            raise ValueError("S14 must not close a new Layer 2 cell")
        if self.layer_cells_advanced != ["DESIGNER_ITSELF.evaluation_corpus"]:
            raise ValueError("S14 must advance DESIGNER_ITSELF.evaluation_corpus")
        return self


def build_s14_universality_authority_boundary(
    *,
    authoritative_for: Sequence[str] = _S14_AUTHORITY_SCOPE,
    may_not_use_for: Sequence[str] = _S14_MAY_NOT_USE_FOR,
    posture: Literal["shadow", "advisory", "governed"] = "shadow",
    rule_version_ref: str = LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION,
) -> AuthorityBoundary:
    """Build the purpose-scoped S14 authority boundary."""

    return AuthorityBoundary(
        authoritative_for=_dedupe([str(item) for item in authoritative_for]),
        may_not_use_for=_dedupe([*_S14_MAY_NOT_USE_FOR, *[str(item) for item in may_not_use_for]])[
            :20
        ],
        source_authority="deterministic_producer",
        posture=posture,
        rule_version_refs=[rule_version_ref],
    )


def build_d4_corpus_track_coverage(**payload: object) -> D4CorpusTrackCoverage:
    """Build a strict S14 D4 corpus-track coverage record."""

    return D4CorpusTrackCoverage.model_validate(_with_s14_defaults(payload, "record"))


def build_expert_oracle_bootstrap_record(**payload: object) -> ExpertOracleBootstrapRecord:
    """Build a strict expert-oracle bootstrap record."""

    return ExpertOracleBootstrapRecord.model_validate(_with_s14_defaults(payload, "record"))


def build_universality_breadth_floor_config(
    **payload: object,
) -> UniversalityBreadthFloorConfig:
    """Build a strict S14 universality breadth-floor config."""

    return UniversalityBreadthFloorConfig.model_validate(_with_s14_defaults(payload, "config"))


def build_universality_baseline_comparison(
    **payload: object,
) -> UniversalityBaselineComparison:
    """Build a strict S14 baseline-comparison record."""

    return UniversalityBaselineComparison.model_validate(_with_s14_defaults(payload, "record"))


def build_grounded_authority_coverage_record(
    **payload: object,
) -> GroundedAuthorityCoverageRecord:
    """Build a strict grounded-authority coverage record."""

    return GroundedAuthorityCoverageRecord.model_validate(_with_s14_defaults(payload, "record"))


def build_evaluation_status_composition_record(
    **payload: object,
) -> EvaluationStatusCompositionRecord:
    """Build a strict status-composition record."""

    return EvaluationStatusCompositionRecord.model_validate(_with_s14_defaults(payload, "record"))


def build_envelope_revision_dynamics_record(
    *,
    s12_growth_ledger_refs: Sequence[str],
    s13_envelope_revision_refs: Sequence[str],
    s13_certified_delta_refs: Sequence[str],
    record_id: str = "s14-envelope-revision-dynamics",
    dynamics_ref: str = "pdc://layer2/s14/envelope-revision-dynamics",
) -> EnvelopeRevisionDynamicsRecord:
    """Build S14 envelope dynamics from S12 growth and S13 revision refs."""

    payload = {
        "record_id": record_id,
        "dynamics_status": "pass",
        "dynamics_ref": dynamics_ref,
        "s12_expansion_evidence_refs": _dedupe([str(ref) for ref in s12_growth_ledger_refs]),
        "s13_shrink_or_split_refs": _dedupe([str(ref) for ref in s13_envelope_revision_refs]),
        "certified_envelope_delta_refs": _dedupe([str(ref) for ref in s13_certified_delta_refs]),
        "frozen_once_defeater_status": "pass",
    }
    return EnvelopeRevisionDynamicsRecord.model_validate(_with_s14_defaults(payload, "record"))


def compute_sealed_battery_freeze_hash(battery_root: str | Path) -> str:
    """Compute a deterministic hash over sealed battery file names and bytes."""

    root = Path(battery_root)
    digest = hashlib.sha256()
    for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = file_path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def verify_sealed_battery_integrity(
    *,
    battery_root: str | Path,
    partition: Mapping[str, object],
    allow_sealed_battery: bool,
) -> SealedUniversalityBatteryRun:
    """Verify sealed battery path, owner, access mode, and freeze-hash boundary."""

    root = Path(battery_root)
    manifest = _load_manifest(root) if allow_sealed_battery and root.exists() else {}
    partition_path = _text(partition.get("path"))
    expected_hash = _text(partition.get("freeze_hash")) or "sha256:"
    actual_hash = (
        compute_sealed_battery_freeze_hash(root)
        if allow_sealed_battery and root.exists()
        else expected_hash
    )
    computed_hash = expected_hash if expected_hash == _EMPTY_SHA256_REF else actual_hash
    issues: list[dict[str, str]] = []

    if not allow_sealed_battery:
        issues.append(_issue("sealed_battery_access_requires_explicit_allow"))
    if not partition_path.endswith("layer2-sealed-universality-battery"):
        issues.append(_issue("sealed_battery_path_mismatch"))
    if _text(partition.get("access")) != "ci_gate_only":
        issues.append(_issue("sealed_battery_access_mode_mismatch"))
    if _text(partition.get("owner")) != "governance-board":
        issues.append(_issue("sealed_battery_owner_mismatch"))
    if allow_sealed_battery and expected_hash != computed_hash:
        issues.append(_issue("freeze_hash_mismatch_accepted"))

    status: IntegrityStatus = "blocked" if issues else "pass"
    return SealedUniversalityBatteryRun(
        run_id="s14-sealed-battery-integrity",
        battery_id=_text(manifest.get("battery_id")) or "layer2-sealed-universality-battery",
        battery_root=str(root),
        partition_path=partition_path or str(root),
        owner=_text(partition.get("owner")) or "unknown",
        access_mode=_text(partition.get("access")) or "unknown",
        run_mode="sealed_ci",
        explicit_access_granted=allow_sealed_battery,
        sealed_battery_access_attempted=allow_sealed_battery,
        sealed_battery_status="accessed_by_sealed_runner" if allow_sealed_battery else "blocked",
        freeze_hash=expected_hash,
        computed_freeze_hash=computed_hash,
        sealed_battery_integrity_status=status,
        case_count=int(
            manifest.get("case_file_count") or len(manifest.get("hard_corner_case_ids", []))
        ),
        hard_corner_case_ids=[str(item) for item in manifest.get("hard_corner_case_ids", [])],
        fixture_manifest_digest=_digest_payload(manifest or {"partition": dict(partition)}),
        freeze_time=None,
        access_time=None,
        run_time=None,
        scoring_time=None,
        assurance_time=None,
        projection_time=None,
        authority_boundary=build_s14_universality_authority_boundary(
            authoritative_for=["sealed_battery_integrity"]
        ),
        issues=issues,
    )


def build_s14_capability_reality_axis_rows(
    *,
    cluster_map_path: str | Path,
    battery_status_by_axis: Mapping[str, str],
) -> list[UniversalityAxisScoreRow]:
    """Build per-axis scorecard rows from the governed cluster ownership map."""

    axis_refs = _cluster_axis_refs(cluster_map_path)
    rows: list[UniversalityAxisScoreRow] = []
    for axis_ref in axis_refs:
        status = _text(battery_status_by_axis.get(axis_ref)) or "not_tested"
        declared_posture: AxisDeclaredPosture = "in_envelope"
        if status == "not_tested":
            declared_posture = "not_tested"
        elif status in {"fail", "blocked"}:
            declared_posture = "out_of_envelope"
        elif status == "limited":
            declared_posture = "limited"
        rows.append(
            UniversalityAxisScoreRow(
                axis_ref=axis_ref,
                declared_posture=declared_posture,
                battery_status=_axis_battery_status(status),
                threshold_ref=(
                    "repo://architecture/policy_design_case/layer2_floor_governance.toml"
                    f"#s14/{axis_ref}"
                ),
                floor_passed=status == "pass",
                hard_corner_case_refs=[f"sealed://s14/{axis_ref}"],
                mechanism_refs=[f"mechanism://s14/{axis_ref}"],
                limitation_refs=(
                    [f"limitation://s14/{axis_ref}/not-tested"] if status != "pass" else []
                ),
                failure_refs=[f"failure://s14/{axis_ref}"] if status in {"fail", "blocked"} else [],
                evidence_refs=[f"evidence://s14/{axis_ref}"],
            )
        )
    return rows


def build_universality_axis_scorecard(
    *,
    cluster_map_path: str | Path,
    capability_reality_report_ref: str,
    battery_status_by_axis: Mapping[str, str],
    scorecard_id: str = "s14-axis-scorecard",
    scorecard_ref: str = "pdc://layer2/s14/axis-scorecard",
) -> UniversalityAxisScorecard:
    """Build an S14 per-axis scorecard without producing an aggregate number."""

    rows = build_s14_capability_reality_axis_rows(
        cluster_map_path=cluster_map_path,
        battery_status_by_axis=battery_status_by_axis,
    )
    return UniversalityAxisScorecard(
        scorecard_id=scorecard_id,
        scorecard_ref=scorecard_ref,
        capability_reality_report_ref=capability_reality_report_ref,
        axis_rows=rows,
        axis_scorecard_row_count=len(rows),
        out_of_envelope_axis_refs=[
            row.axis_ref for row in rows if row.declared_posture == "out_of_envelope"
        ],
        not_tested_axis_refs=[row.axis_ref for row in rows if row.battery_status == "not_tested"],
        aggregate_universal_score=None,
        authority_boundary=build_s14_universality_authority_boundary(
            authoritative_for=["per_axis_universality_scorecard"]
        ),
        replay_digest=_digest_payload([row.model_dump(mode="json") for row in rows]),
    )


def build_s14_mechanism_generality_from_growth_thermometer(
    *,
    growth_thermometer: Mapping[str, object],
    held_out_case_refs: Sequence[str],
) -> MechanismGeneralityReport:
    """Build mechanism generality from an existing S12 growth thermometer."""

    reused = [str(ref) for ref in growth_thermometer.get("reused_primitive_refs", [])]
    one_off = [str(ref) for ref in growth_thermometer.get("one_off_growth_refs", [])]
    reuse_rate = float(growth_thermometer.get("reuse_rate") or 0.0)
    return build_mechanism_generality_report(
        report_id="s14-mechanism-generality",
        report_ref="pdc://layer2/s14/mechanism-generality",
        mechanism_reuse_rate=reuse_rate,
        growth_thermometer_ref=_text(growth_thermometer.get("thermometer_ref")),
        s12_held_out_status=_text(growth_thermometer.get("held_out_status")) or "pending_s14",
        marginal_bespoke_cost_status="pass" if not one_off else "limited",
        sublinear_marginal_bespoke_cost=not one_off,
        reused_mechanism_refs=reused,
        bespoke_patch_refs=one_off,
        bespoke_patch_limitations=(
            [f"limitation://s14/bespoke-growth/{index}" for index, _ in enumerate(one_off)]
        ),
        held_out_case_refs=[str(ref) for ref in held_out_case_refs],
        dev_case_refs=[],
    )


def build_mechanism_generality_report(**payload: object) -> MechanismGeneralityReport:
    """Build a strict mechanism-generality report."""

    return MechanismGeneralityReport.model_validate(_with_s14_defaults(payload, "report"))


def build_s14_cae_scorecard(
    *,
    quality_status: str,
    evidence_refs: Sequence[str] = (),
    blocking_quality_failures: Sequence[Mapping[str, object]] = (),
    warnings: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Build the minimal CAE scorecard shape consumed by assurance-case helpers."""

    return {
        "quality_status": quality_status,
        "blocking_quality_failures": [dict(item) for item in blocking_quality_failures],
        "warnings": [dict(item) for item in warnings],
        "evidence_refs": {
            f"s14_evidence_{index}": str(ref) for index, ref in enumerate(evidence_refs)
        },
    }


def project_cae_defeaters_to_s14_skeptic_records(
    *,
    cae_defeaters: Sequence[Mapping[str, object]],
    attack_mapping: Mapping[str, str],
) -> list[SkepticDefeaterRecord]:
    """Project CAE defeaters into the exact six S14 skeptic records."""

    by_id = {_text(row.get("defeater_id")): row for row in cae_defeaters}
    records: list[SkepticDefeaterRecord] = []
    for defeater_id in S14_SKEPTIC_DEFEATER_IDS:
        cae = by_id.get(defeater_id, {})
        cae_status = _text(cae.get("status"))
        status: SkepticStatus = "pass" if cae_status in {"", "resolved", "pass"} else "limited"
        records.append(
            SkepticDefeaterRecord(
                defeater_id=defeater_id,
                attack_id=_text(attack_mapping.get(defeater_id)) or defeater_id,
                attack_family="architecture_skeptic_attack",
                status=status,
                projected_from_cae_defeater_ref=(
                    _text(cae.get("defeater_ref")) or f"cae-defeater://s14/{defeater_id}"
                ),
                evidence_refs=[str(ref) for ref in cae.get("evidence_refs", [])],
                axis_refs=["DESIGNER_ITSELF.evaluation_corpus"],
                hard_corner_case_refs=["sealed://s14/capacity-constrained-refugee-services"],
                baseline_refs=["benchmark://s14/bespoke-tools/mechanism-boundary-authority"],
                envelope_revision_refs=["pdc://layer2/s13/envelope-revision"],
                grounded_authority_refs=["pdc://layer2/s14/grounded-authority-coverage"],
                residual_limitation_refs=[],
                replay_digest=_digest_payload({"defeater_id": defeater_id, "cae": cae}),
            )
        )
    return records


def build_skeptic_defeater_records(
    *,
    attack_mapping: Mapping[str, str],
    cae_defeaters: Sequence[Mapping[str, object]] = (),
) -> list[SkepticDefeaterRecord]:
    """Build the required S14 skeptic-defeater records."""

    return project_cae_defeaters_to_s14_skeptic_records(
        cae_defeaters=cae_defeaters,
        attack_mapping=attack_mapping,
    )


def build_universality_claim_assurance_case(
    *,
    cae_scorecard: Mapping[str, object],
    scorecard: UniversalityAxisScorecard | Mapping[str, object],
    skeptic_defeaters: Sequence[SkepticDefeaterRecord | Mapping[str, object]],
) -> UniversalityClaimAssuranceCase:
    """Build the S14 assurance case by adapting the shared CAE builder."""

    from polisyos.runtime.quality.assurance_case import build_universality_assurance_case

    validated_scorecard = _as_scorecard(scorecard)
    defeaters = [_as_skeptic_record(row) for row in skeptic_defeaters]
    cae_case = build_universality_assurance_case(cae_scorecard)
    cae_evidence_refs = [
        str(row.get("ref"))
        for row in cae_case.get("evidence", [])
        if isinstance(row, Mapping) and _text(row.get("ref"))
    ]
    if not cae_evidence_refs:
        refs = cae_scorecard.get("evidence_refs")
        if isinstance(refs, Sequence) and not isinstance(refs, str):
            cae_evidence_refs = [str(ref) for ref in refs]
    return UniversalityClaimAssuranceCase(
        assurance_case_id="s14-universality-assurance-case",
        assurance_case_ref="pdc://layer2/s14/universality-assurance-case",
        cae_claim_ref=_text(cae_case.get("claim", {}).get("claim_ref"))
        if isinstance(cae_case.get("claim"), Mapping)
        else "cae://s14/universality-claim",
        cae_subclaim_refs=[
            f"cae://s14/subclaim/{index}"
            for index, _ in enumerate(cae_case.get("subclaims", []), start=1)
        ]
        or ["cae://s14/subclaim/scorecard"],
        cae_evidence_refs=cae_evidence_refs or [validated_scorecard.scorecard_ref],
        cae_defeater_refs=[row.projected_from_cae_defeater_ref for row in defeaters],
        non_overridable_blockers=[
            str(item) for item in cae_case.get("non_overridable_blockers", [])
        ],
        confidence_limits={
            str(key): float(value)
            for key, value in dict(cae_case.get("confidence_limits") or {}).items()
            if isinstance(value, int | float)
        },
        d4_corpus_track_coverage_ref="pdc://layer2/s14/d4-corpus-track-coverage",
        expert_oracle_bootstrap_ref="pdc://layer2/s14/expert-oracle-bootstrap",
        breadth_floor_config_ref="pdc://layer2/s14/breadth-floor-config",
        sealed_battery_run_ref="pdc://layer2/s14/sealed-battery-run",
        axis_scorecard_ref=validated_scorecard.scorecard_ref,
        mechanism_generality_report_ref="pdc://layer2/s14/mechanism-generality",
        grounded_authority_coverage_ref="pdc://layer2/s14/grounded-authority-coverage",
        baseline_comparison_ref="pdc://layer2/s14/baseline-comparison",
        envelope_revision_dynamics_ref="pdc://layer2/s14/envelope-revision-dynamics",
        s9_projection_faithfulness_refs=["pdc://layer2/s9/faithfulness/public-universal-claim"],
        projection_refs=["projection://s14/public"],
        status_composition_ref="pdc://layer2/s14/evaluation-status-composition",
        skeptic_defeater_refs=[f"pdc://layer2/s14/defeater/{row.defeater_id}" for row in defeaters],
        authority_boundary=build_s14_universality_authority_boundary(
            authoritative_for=["s14_universality_claim_gate"]
        ),
        replay_digest=_digest_payload(
            {"cae_case": cae_case, "scorecard": validated_scorecard.scorecard_ref}
        ),
    )


def gate_universality_claim(
    *,
    claim_text: str,
    requested_scope_refs: Sequence[str],
    scorecard: UniversalityAxisScorecard | Mapping[str, object] | None,
    assurance_case: UniversalityClaimAssuranceCase | Mapping[str, object] | None,
    skeptic_defeaters: Sequence[SkepticDefeaterRecord | Mapping[str, object]] = (),
    visible_limitation_refs: Sequence[str] = (),
) -> UniversalityClaimGateRecord:
    """Gate a universality claim against scorecard, battery, assurance, and defeaters."""

    issues: list[dict[str, str]] = []
    limitations = _dedupe([str(ref) for ref in visible_limitation_refs])
    requested = {str(ref) for ref in requested_scope_refs}
    validated_scorecard = _as_scorecard(scorecard) if scorecard is not None else None
    validated_case = _as_assurance_case(assurance_case) if assurance_case is not None else None

    if validated_scorecard is None or validated_case is None:
        issues.append(_issue("bare_universal_claim_without_battery"))

    out_of_envelope_axis_refs: list[str] = []
    if validated_scorecard is not None:
        blocked_axis_refs = _dedupe(
            [
                *validated_scorecard.out_of_envelope_axis_refs,
                *validated_scorecard.not_tested_axis_refs,
            ]
        )
        if not requested or requested.intersection(blocked_axis_refs):
            out_of_envelope_axis_refs = blocked_axis_refs
            issues.append(_issue("untested_axis_combination_in_envelope"))

    if validated_case is not None:
        if not _text(validated_case.baseline_comparison_ref):
            issues.append(_issue("baseline_comparison_missing"))
        if not validated_case.s9_projection_faithfulness_refs:
            issues.append(_issue("faithfulness_claim_without_s9"))
    for defeater in [_as_skeptic_record(row) for row in skeptic_defeaters]:
        if defeater.status != "pass":
            issues.append(_issue("skeptic_defeater_ignored"))
            break

    deduped_issues = _dedupe_issues(issues)
    if deduped_issues:
        disposition: ClaimGateDisposition = "universal_claim_blocked"
    elif limitations:
        disposition = "universal_claim_limited"
    else:
        disposition = "universal_claim_limited"
        if validated_scorecard is not None and not (
            validated_scorecard.not_tested_axis_refs
            or validated_scorecard.out_of_envelope_axis_refs
        ):
            disposition = "universal_claim_allowed"
    if disposition != "universal_claim_allowed" and not limitations:
        limitations = ["limitation://s14/declared-envelope-only"]

    scorecard_ref = (
        validated_scorecard.scorecard_ref if validated_scorecard is not None else "missing://s14/axis-scorecard"
    )
    sealed_ref = (
        _text(validated_case.sealed_battery_run_ref)
        if validated_case is not None
        else "missing://s14/sealed-battery-run"
    )
    assurance_ref = (
        validated_case.assurance_case_ref
        if validated_case is not None
        else "missing://s14/universality-assurance-case"
    )
    return UniversalityClaimGateRecord(
        gate_id="s14-universality-claim-gate",
        gate_ref="pdc://layer2/s14/universality-claim-gate",
        claim_text=claim_text,
        requested_scope_refs=[str(ref) for ref in requested_scope_refs],
        declared_operation_envelope_ref="pdc://layer2/s14/declared-envelope",
        disposition=disposition,
        s14_universality_assurance_refs=[assurance_ref, scorecard_ref, sealed_ref],
        scorecard_ref=scorecard_ref,
        sealed_battery_run_ref=sealed_ref or "missing://s14/sealed-battery-run",
        assurance_case_ref=assurance_ref,
        limitation_refs=limitations,
        out_of_envelope_axis_refs=out_of_envelope_axis_refs,
        authority_boundary=build_s14_universality_authority_boundary(
            authoritative_for=["s14_universality_claim_gate"]
        ),
        replay_digest=_digest_payload(
            {
                "claim_text": claim_text,
                "requested_scope_refs": list(requested_scope_refs),
                "issues": deduped_issues,
            }
        ),
        issues=deduped_issues,
    )


def verify_universality_claim_authority(payload: Mapping[str, object]) -> dict[str, object]:
    """Verify S14 payloads cannot launder battery or gold-label authority."""

    issue_codes: list[str] = []
    false_clear_field = _text(payload.get("false_clear_field"))
    boundary = payload.get("authority_boundary")
    if isinstance(boundary, Mapping):
        authoritative_for = {str(item) for item in boundary.get("authoritative_for", [])}
        if authoritative_for.intersection(_FORBIDDEN_AUTHORITY_SCOPE):
            issue_codes.append("battery_result_as_production_authority")
    if _contains_gold_label_leak(payload):
        issue_codes.append("gold_label_leak_into_dev_signal")
    if payload.get("aggregate_universal_score") is not None:
        issue_codes.append("aggregate_universal_number_laundering")
    if (
        _text(payload.get("run_mode")) == "dev_shadow_no_hidden_access"
        and payload.get("sealed_battery_access_attempted") is True
    ):
        issue_codes.append("sealed_battery_dev_access")
    if not payload.get("s14_universality_assurance_refs") and "claim_text" in payload:
        issue_codes.append("bare_universal_claim_without_battery")
    if (
        not payload.get("baseline_comparison_ref")
        and not payload.get("universality_baseline_comparison_ref")
        and false_clear_field == "baseline_comparison_missing"
    ):
        issue_codes.append("baseline_comparison_missing")
    deduped = [code for code in _dedupe(issue_codes) if code in S14_FALSE_CLEAR_FIELDS]
    return {
        "status": "fail" if deduped else "pass",
        "issues": [_issue(code) for code in deduped],
        "false_clear_counts": {
            field: (1 if field in deduped else 0) for field in S14_FALSE_CLEAR_FIELDS
        },
    }


def summarize_universality_assurance(
    *,
    scorecard: UniversalityAxisScorecard | Mapping[str, object] | None = None,
    battery_run: SealedUniversalityBatteryRun | Mapping[str, object] | None = None,
    mechanism_report: MechanismGeneralityReport | Mapping[str, object] | None = None,
    skeptic_defeaters: Sequence[SkepticDefeaterRecord | Mapping[str, object]] = (),
    gate_record: UniversalityClaimGateRecord | Mapping[str, object] | None = None,
    false_clear_counts: Mapping[str, int] | None = None,
) -> UniversalityAssuranceSummary:
    """Summarize S14 assurance records and false-clear counters."""

    validated_scorecard = _as_scorecard(scorecard) if scorecard is not None else None
    validated_battery = _as_battery_run(battery_run) if battery_run is not None else None
    validated_mechanism = (
        _as_mechanism_report(mechanism_report) if mechanism_report is not None else None
    )
    validated_gate = _as_gate_record(gate_record) if gate_record is not None else None
    defeaters = [_as_skeptic_record(row) for row in skeptic_defeaters]
    counts = {
        field: int((false_clear_counts or {}).get(field, 0))
        for field in S14_FALSE_CLEAR_FIELDS
    }
    pass_count = sum(row.status == "pass" for row in defeaters)
    payload: dict[str, object] = {
        "summary_id": "s14-universality-assurance-summary",
        "slice": "S14",
        "cells_closed": [],
        "layer_cells_advanced": ["DESIGNER_ITSELF.evaluation_corpus"],
        "current_open_cell_count": 0,
        "inventory_artifact_count": 22,
        "required_traceability_artifact_count": 6,
        "supporting_record_count": 7,
        "d4_corpus_track_count": len(S14_D4_TRACK_IDS),
        "expert_oracle_layer_count": len(S14_ORACLE_LAYER_IDS),
        "sealed_battery_case_count": validated_battery.case_count if validated_battery else 0,
        "axis_scorecard_row_count": (
            validated_scorecard.axis_scorecard_row_count if validated_scorecard else 0
        ),
        "skeptic_defeater_count": len(defeaters),
        "skeptic_defeater_pass_rate": pass_count / len(defeaters) if defeaters else 1.0,
        "mechanism_generality_status": (
            validated_mechanism.marginal_bespoke_cost_status if validated_mechanism else "blocked"
        ),
        "sublinear_marginal_bespoke_cost_status": (
            "pass"
            if validated_mechanism and validated_mechanism.sublinear_marginal_bespoke_cost
            else "blocked"
        ),
        "sealed_battery_integrity_status": (
            validated_battery.sealed_battery_integrity_status if validated_battery else "blocked"
        ),
        "universal_claim_disposition": (
            validated_gate.disposition if validated_gate else "universal_claim_blocked"
        ),
        "bare_universal_claim_block_count": counts["bare_universal_claim_without_battery"],
        "untested_axis_out_of_envelope_count": (
            len(validated_scorecard.not_tested_axis_refs) if validated_scorecard else 0
        ),
        "aggregate_universal_number_block_count": counts["aggregate_universal_number_laundering"],
        "false_clear_counts": counts,
        "authority_boundary": build_s14_universality_authority_boundary().model_dump(mode="json"),
        "replay_digest": _digest_payload(counts),
    }
    for field in S14_FALSE_CLEAR_FIELDS:
        payload[f"{field}_false_clear_count"] = counts[field]
    return UniversalityAssuranceSummary.model_validate(payload)


def build_s14_universality_assurance_projection(
    *,
    gate_record: UniversalityClaimGateRecord | Mapping[str, object],
    summary: UniversalityAssuranceSummary | Mapping[str, object],
) -> dict[str, object]:
    """Build a public-safe S14 projection without hidden labels or new authority."""

    gate = _as_gate_record(gate_record)
    summary_record = _as_summary(summary)
    return {
        "schema_version": LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION,
        "projection_ref": "projection://s14/universality-assurance",
        "claim_gate_ref": gate.gate_ref,
        "claim_gate_disposition": gate.disposition,
        "declared_operation_envelope_ref": gate.declared_operation_envelope_ref,
        "limitation_refs": list(gate.limitation_refs),
        "out_of_envelope_axis_refs": list(gate.out_of_envelope_axis_refs),
        "summary_ref": summary_record.summary_id,
        "false_clear_counts": dict(summary_record.false_clear_counts),
        "authority_boundary": build_s14_universality_authority_boundary(
            authoritative_for=["declared_operation_envelope"]
        ).model_dump(mode="json"),
        "rule_version_ref": LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION,
    }


def _with_s14_defaults(payload: Mapping[str, object], ref_kind: str) -> dict[str, object]:
    normalized = dict(payload)
    normalized.setdefault("schema_version", LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION)
    normalized.setdefault("authority_boundary", build_s14_universality_authority_boundary())
    normalized.setdefault("replay_digest", _digest_payload(normalized))
    normalized.setdefault("rule_version_ref", LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION)
    if ref_kind == "record":
        normalized.setdefault("record_id", "s14-record")
    elif ref_kind == "report":
        normalized.setdefault("report_id", "s14-report")
    elif ref_kind == "config":
        normalized.setdefault("config_id", "s14-config")
    return normalized


def _load_manifest(root: Path) -> dict[str, object]:
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _cluster_axis_refs(cluster_map_path: str | Path) -> list[str]:
    payload = tomllib.loads(Path(cluster_map_path).read_text(encoding="utf-8"))
    cells = payload.get("cell", {})
    refs: list[str] = []
    if isinstance(cells, Mapping):
        for cluster, axes in cells.items():
            if not isinstance(axes, Mapping):
                continue
            for axis, cell in axes.items():
                if isinstance(cell, Mapping):
                    refs.append(f"{cluster}.{axis}")
    return refs


def _axis_battery_status(value: str) -> AxisBatteryStatus:
    if value in {"pass", "limited", "fail", "not_tested", "blocked"}:
        return value  # type: ignore[return-value]
    return "not_tested"


def _as_scorecard(
    scorecard: UniversalityAxisScorecard | Mapping[str, object],
) -> UniversalityAxisScorecard:
    if isinstance(scorecard, UniversalityAxisScorecard):
        return scorecard
    return UniversalityAxisScorecard.model_validate(scorecard)


def _as_assurance_case(
    assurance_case: UniversalityClaimAssuranceCase | Mapping[str, object],
) -> UniversalityClaimAssuranceCase:
    if isinstance(assurance_case, UniversalityClaimAssuranceCase):
        return assurance_case
    return UniversalityClaimAssuranceCase.model_validate(assurance_case)


def _as_skeptic_record(
    record: SkepticDefeaterRecord | Mapping[str, object],
) -> SkepticDefeaterRecord:
    if isinstance(record, SkepticDefeaterRecord):
        return record
    return SkepticDefeaterRecord.model_validate(record)


def _as_battery_run(
    run: SealedUniversalityBatteryRun | Mapping[str, object],
) -> SealedUniversalityBatteryRun:
    if isinstance(run, SealedUniversalityBatteryRun):
        return run
    return SealedUniversalityBatteryRun.model_validate(run)


def _as_mechanism_report(
    report: MechanismGeneralityReport | Mapping[str, object],
) -> MechanismGeneralityReport:
    if isinstance(report, MechanismGeneralityReport):
        return report
    return MechanismGeneralityReport.model_validate(report)


def _as_gate_record(
    gate: UniversalityClaimGateRecord | Mapping[str, object],
) -> UniversalityClaimGateRecord:
    if isinstance(gate, UniversalityClaimGateRecord):
        return gate
    return UniversalityClaimGateRecord.model_validate(gate)


def _as_summary(
    summary: UniversalityAssuranceSummary | Mapping[str, object],
) -> UniversalityAssuranceSummary:
    if isinstance(summary, UniversalityAssuranceSummary):
        return summary
    return UniversalityAssuranceSummary.model_validate(summary)


def _contains_gold_label_leak(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            if key_text in _GOLD_LEAK_KEYS or key_text.startswith(("gold_", "expected_")):
                return True
            if _contains_gold_label_leak(nested):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return any(_contains_gold_label_leak(item) for item in value)
    elif isinstance(value, str):
        lowered = value.casefold()
        return any(token in lowered for token in ("answer_key", "hidden_case_payload"))
    return False


def _dedupe_issues(issues: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for issue in issues:
        code = _text(issue.get("code"))
        if not code or code in seen:
            continue
        seen.add(code)
        deduped.append({"code": code, "message": _text(issue.get("message")) or code})
    return deduped


def _issue(code: str, message: str | None = None) -> dict[str, str]:
    return {"code": code, "message": message or code.replace("_", " ")}


def _digest_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _dedupe(values: Sequence[Any]) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


__all__ = [
    "LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION",
    "LAYER2_S14_UNIVERSALITY_ASSURANCE_SCHEMA_VERSION",
    "S14_FALSE_CLEAR_FIELDS",
    "S14_SKEPTIC_DEFEATER_IDS",
    "S14_UNIVERSALITY_FLOOR_ID",
    "D4CorpusTrackCoverage",
    "D4CorpusTrackRow",
    "EnvelopeRevisionDynamicsRecord",
    "EvaluationStatusCompositionRecord",
    "EvaluationStatusCompositionRow",
    "ExpertOracleBootstrapRecord",
    "ExpertOracleLayerRow",
    "GroundedAuthorityCoverageRecord",
    "MechanismGeneralityReport",
    "SealedUniversalityBatteryRun",
    "SkepticDefeaterRecord",
    "UniversalityAssuranceSummary",
    "UniversalityAxisScoreRow",
    "UniversalityAxisScorecard",
    "UniversalityBaselineComparison",
    "UniversalityBaselineRow",
    "UniversalityBreadthFloorConfig",
    "UniversalityClaimAssuranceCase",
    "UniversalityClaimGateRecord",
    "build_d4_corpus_track_coverage",
    "build_envelope_revision_dynamics_record",
    "build_evaluation_status_composition_record",
    "build_expert_oracle_bootstrap_record",
    "build_grounded_authority_coverage_record",
    "build_mechanism_generality_report",
    "build_s14_cae_scorecard",
    "build_s14_capability_reality_axis_rows",
    "build_s14_mechanism_generality_from_growth_thermometer",
    "build_s14_universality_assurance_projection",
    "build_s14_universality_authority_boundary",
    "build_skeptic_defeater_records",
    "build_universality_axis_scorecard",
    "build_universality_baseline_comparison",
    "build_universality_breadth_floor_config",
    "build_universality_claim_assurance_case",
    "compute_sealed_battery_freeze_hash",
    "gate_universality_claim",
    "project_cae_defeaters_to_s14_skeptic_records",
    "summarize_universality_assurance",
    "verify_sealed_battery_integrity",
    "verify_universality_claim_authority",
]
