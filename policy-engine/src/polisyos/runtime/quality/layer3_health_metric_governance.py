"""Layer 3 G8 health-metric governance and corpus re-basing contracts.

G8 governs diagnostic metric signals and D4.4 re-basing receipts. It never
mints production, recommendation, closeout, publication, scorecard, legal, or
universal-claim authority.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

G8_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g8_health_metric_governance.v1"
G8_RULE_VERSION = "policyos.layer3.g8.health_metric_governance.v1"
G8_SURFACE_ID = "layer3_g8_health_metric_governance_surface"
G8_GENERATED_ARTIFACT_FAMILY_ID = (
    "policy-design-case-layer3-g8-health-metric-governance-artifacts"
)
G8_AUTHORITATIVE_FOR = (
    "layer3_g8_metric_governance_audit",
    "layer3_g8_d44_rebasing_integrity_reading",
    "layer3_g8_open_question_answer_reading",
)
G8_MAY_NOT_USE_FOR = (
    "production_authority",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "approval_authority",
    "scorecard_authority",
    "closeout_authority",
    "runtime_closeout_authority",
    "public_recommendation",
    "policy_recommendation",
    "legal_advice",
    "claim_authority",
    "obligation_authority",
    "causal_effect_authority",
    "proof_authority",
    "legal_authority",
    "recommendation_authority",
    "universal_claim_authority",
    "universal_claim_authority_without_s14",
    "s14_universality_claim_without_s14_gate",
    "domain_ceiling_authority_without_gate",
    "metric_optimization_authority",
    "useful_design_rate_optimization",
    "threshold_lowering",
    "s14_battery_training",
    "hidden_fixture_access",
    "g7_region_widening_authority",
)
G8_CANONICAL_METRIC_IDS = (
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness",
)
G8_METRIC_ALIASES = {
    "envelope-expansion-rate": "envelope-expansion-rate",
    "envelope-expansion-rate(region)": "envelope-expansion-rate",
    "envelope_expansion_rate_region": "envelope-expansion-rate",
    "g5_envelope_expansion_status": "envelope-expansion-rate",
    "g7_region_envelope_expansion_rate": "envelope-expansion-rate",
    "adapter-semantic-loss": "adapter-semantic-loss",
    "adapter-semantic-loss(region)": "adapter-semantic-loss",
    "semantic_loss_status": "adapter-semantic-loss",
    "g7_region_semantic_loss_status": "adapter-semantic-loss",
    "governance-throughput": "governance-throughput",
    "governance-throughput(region)": "governance-throughput",
    "g4_governance_throughput_status": "governance-throughput",
    "g4-promotion-attempts": "governance-throughput",
    "g4-governed-promoted-count": "governance-throughput",
    "g4-promotion-blocked-count": "governance-throughput",
    "g4-promotion-stalled-count": "governance-throughput",
    "g4-human-decision-routed-count": "governance-throughput",
    "g4-hard-a-incompleteness-block-count": "governance-throughput",
    "g4-search-health-stall-count": "governance-throughput",
    "g4-stale-index-stall-count": "governance-throughput",
    "g4-legal-reissue-stall-count": "governance-throughput",
    "g4-human-decision-stall-count": "governance-throughput",
    "g7_governance_throughput_status": "governance-throughput",
    "demand-pull-vs-abstention": "demand-pull-vs-abstention",
    "demand-pull-vs-abstention(region)": "demand-pull-vs-abstention",
    "abstention_or_blocker_rate": "demand-pull-vs-abstention",
    "grounded_result_rate": "demand-pull-vs-abstention",
    "out_of_envelope_abstention_rate": "demand-pull-vs-abstention",
    "g6_demand_pull_vs_abstention_status": "demand-pull-vs-abstention",
    "g7_region_value_closure_status": "demand-pull-vs-abstention",
    "g7_region_grounded_case_count": "demand-pull-vs-abstention",
    "g7_s14_grounded_breadth_feed_status": "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search-recall@known-seeds + index-staleness": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search-recall@known-seeds+index-staleness(region)": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search-recall.index_freshness_status": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search-recall.known_seed_status": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search_recall.status": "search-recall@known-seeds+index-staleness",
    "search_recall.freshness_status": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search_recall.certificate_resolution_seed_status": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search_recall.ir_catalog_seed_status": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search_recall.l2_skg_seed_status": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search_recall.known_seed_count": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search_recall.recalled_seed_count": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search_recall.missed_seed_count": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search_recall.search_ceiling_repair_required": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search_recall.domain_ceiling_allowed": (
        "search-recall@known-seeds+index-staleness"
    ),
    "search_recall_status": "search-recall@known-seeds+index-staleness",
    "index_freshness_status": "search-recall@known-seeds+index-staleness",
    "known_seed_status": "search-recall@known-seeds+index-staleness",
    "g2_search_engineering_quality_status": (
        "search-recall@known-seeds+index-staleness"
    ),
    "g3_search_recall_freshness_status": (
        "search-recall@known-seeds+index-staleness"
    ),
    "gl_search_recall_freshness_status": (
        "search-recall@known-seeds+index-staleness"
    ),
    "g1_search_recall_status": "search-recall@known-seeds+index-staleness",
    "g1_index_freshness_status": "search-recall@known-seeds+index-staleness",
    "g5_search_recall_status": "search-recall@known-seeds+index-staleness",
    "g5_index_freshness_status": "search-recall@known-seeds+index-staleness",
}
ALL_ISSUE_CODES = (
    "layer3_g8_health_metric_registry_missing",
    "layer3_g8_metric_alias_unresolved",
    "layer3_g8_metric_source_missing",
    "layer3_g8_metric_source_stale",
    "layer3_g8_metric_raw_ref_missing",
    "layer3_g8_metric_authority_boundary_missing",
    "layer3_g8_metric_used_as_closeout_authority",
    "layer3_g8_useful_design_rate_optimized",
    "layer3_g8_metric_improved_by_threshold_lowering",
    "layer3_g8_metric_improved_by_fixture_or_synthetic_breadth",
    "layer3_g8_flat_expansion_reported_as_domain_ceiling_without_search_health",
    "layer3_g8_search_recall_miss_reported_as_domain_ceiling",
    "layer3_g8_governance_stall_hidden_as_domain_ceiling",
    "layer3_g8_abstention_inertia_hidden_as_honesty",
    "layer3_g8_demand_numeric_inertia_hidden_as_pass",
    "layer3_g8_semantic_loss_hidden_by_metric_rollup",
    "layer3_g8_effective_independence_inflated",
    "layer3_g8_metric_trend_report_missing",
    "layer3_g8_warning_owner_missing",
    "layer3_g8_warning_aging_policy_missing",
    "layer3_g8_rebasing_rule_missing",
    "layer3_g8_d44_reannotation_coverage_missing",
    "layer3_g8_d44_rebasing_trigger_missing",
    "layer3_g8_rebasing_receipt_missing",
    "layer3_g8_rebasing_mutates_sealed_battery",
    "layer3_g8_rebasing_leaks_gold_or_hidden_payload",
    "layer3_g8_rebasing_lowers_s14_floor",
    "layer3_g8_rebasing_without_freeze_hash",
    "layer3_g8_open_question_answer_missing",
    "layer3_g8_closeout_signal_consumer_missing",
    "layer3_g8_public_projection_authority_leak",
    "layer3_g8_replay_manifest_missing",
    "layer3_g8_conformance_negative_missing",
    "layer3_g8_manifest_runtime_drift",
    "layer3_g8_generated_artifacts_family_missing",
    "layer3_g8_inventory_surface_missing",
    "layer3_g8_reference_docs_missing",
    "layer3_g8_route_contract_registry_missing",
    "layer3_g8_registry_ratchet_missing",
    "layer3_g8_persisted_artifact_missing",
)

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[4]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
EXPECTED_ARTIFACT_PATHS = (
    Path("architecture/policy_design_case/layer3_g8_health_metric_registry.json"),
    Path("architecture/policy_design_case/layer3_g8_metric_source_snapshot.json"),
    Path("architecture/policy_design_case/layer3_g8_normalized_metric_signals.json"),
    Path("architecture/policy_design_case/layer3_g8_metric_trend_report.json"),
    Path("architecture/policy_design_case/layer3_g8_cross_metric_diagnosis.json"),
    Path("architecture/policy_design_case/layer3_g8_domain_vs_search_ceiling_gate.json"),
    Path("architecture/policy_design_case/layer3_g8_metric_gaming_firewall.json"),
    Path("architecture/policy_design_case/layer3_g8_warning_lifecycle_ledger.json"),
    Path("architecture/policy_design_case/layer3_g8_d44_corpus_rebasing_rule.json"),
    Path("architecture/policy_design_case/layer3_g8_d44_reannotation_coverage_matrix.json"),
    Path("architecture/policy_design_case/layer3_g8_d44_rebasing_trigger_ledger.json"),
    Path("architecture/policy_design_case/layer3_g8_d44_rebasing_candidate_set.json"),
    Path("architecture/policy_design_case/layer3_g8_d44_rebasing_receipt.json"),
    Path("architecture/policy_design_case/layer3_g8_sealed_battery_integrity_join.json"),
    Path("architecture/policy_design_case/layer3_g8_open_question_answer_ledger.json"),
    Path("architecture/policy_design_case/layer3_g8_metric_governance_audit_surface.json"),
    Path("architecture/policy_design_case/layer3_g8_closeout_signal_consumer_gate.json"),
    Path("architecture/policy_design_case/layer3_g8_public_export_projection_refs.json"),
    Path("architecture/policy_design_case/layer3_g8_replay_manifest.json"),
    Path("architecture/policy_design_case/layer3_g8_conformance_report.json"),
    Path("architecture/policy_design_case/layer3_g8_health_metric_governance_delta.toml"),
    Path(
        "architecture/policy_design_case/"
        "layer3_g8_metric_governance_route_contract_registry.toml"
    ),
    Path("architecture/policy_design_case/layer3_g8_registry_ratchet_delta.json"),
    Path("architecture/policy_design_case/layer3_g8_readiness_manifest.json"),
)
EXPECTED_MANIFEST_DRIFT_KEYS = (
    "g8_metric_governance_status",
    "g8_canonical_metric_count",
    "g8_metric_alias_resolution_status",
    "g8_metric_source_snapshot_status",
    "g8_metric_source_count",
    "g8_normalized_metric_signal_status",
    "g8_metric_trend_report_status",
    "g8_effective_independence_status",
    "g8_effective_independent_evidence_count",
    "g8_domain_vs_search_ceiling_status",
    "g8_metric_gaming_firewall_status",
    "g8_warning_lifecycle_status",
    "g8_d44_rebasing_rule_status",
    "g8_d44_reannotation_coverage_status",
    "g8_d44_rebasing_trigger_status",
    "g8_d44_rebasing_receipt_status",
    "g8_sealed_battery_integrity_status",
    "g8_open_question_answer_status",
    "g8_expert_machine_surface_status",
    "g8_closeout_signal_consumer_status",
    "g8_public_projection_contract_status",
    "g8_replay_manifest_status",
    "g8_conformance_status",
    "g8_generated_artifacts_registration_status",
    "g8_inventory_surface_status",
    "g8_reference_docs_status",
    "g8_route_contract_registry_status",
    "g8_registry_ratchet_status",
)
D44_REQUIRED_REANNOTATION_FIELDS = (
    "problem_framing_independent_of_existing_policy",
    "axis_position_vector",
    "per_axis_firewall_status",
    "claim_epistemic_regime_labels",
    "regime_conditional_design_strategy",
    "scale_class",
    "recursive_sub_design_graph",
    "coupling_graph",
    "decomposition_result",
    "interaction_residual_annotations",
    "expert_candidate_designs",
    "rejected_alternatives",
    "critical_path_annotations",
    "dependency_annotations",
    "system_dynamics_feedback_equilibrium_obligations",
    "expected_evidence_tier",
    "construct_demand_denominator",
    "available_source_contracts",
    "unavailable_source_contracts",
    "expected_graded_outcome_by_authority_posture",
    "certified_operation_envelope_status",
    "expected_abstention_limitation_boundary",
    "expected_counterexample_class",
    "valid_refinement_decision",
    "search_ledger_replay_surface",
    "human_decision_points",
    "accountable_actor",
    "mandate_boundary",
    "responsibility_integrity_requirements",
    "canonical_design_record_contents",
    "projection_requests",
    "redaction_access_posture",
    "lowering_requests_with_authority_gates",
    "bootstrap_role",
    "reuse_vs_bespoke_signal",
    "resource_economics_annotation",
    "universality_battery_metadata",
    "post_deploy_monitoring_hooks",
    "historical_outcomes_prediction_backtest_usability",
    "realized_regret_observability",
    "reviewer_disagreement",
    "value_choice_provenance",
)
G8_CONFORMANCE_NEGATIVE_EXPECTED_ISSUE_CODES: dict[str, tuple[str, ...]] = {
    "metric_improved_by_threshold_lowering": (
        "layer3_g8_metric_improved_by_threshold_lowering",
    ),
    "useful_design_rate_optimization": ("layer3_g8_useful_design_rate_optimized",),
    "search_recall_miss_as_domain_ceiling": (
        "layer3_g8_search_recall_miss_reported_as_domain_ceiling",
    ),
    "flat_expansion_with_current_blocker_as_domain_ceiling": (
        "layer3_g8_flat_expansion_reported_as_domain_ceiling_without_search_health",
    ),
    "governance_stall_as_domain_ceiling": (
        "layer3_g8_governance_stall_hidden_as_domain_ceiling",
    ),
    "abstention_inertia_as_honesty": (
        "layer3_g8_abstention_inertia_hidden_as_honesty",
    ),
    "semantic_loss_hidden_by_metric_rollup": (
        "layer3_g8_semantic_loss_hidden_by_metric_rollup",
    ),
    "rebasing_mutates_sealed_battery": ("layer3_g8_rebasing_mutates_sealed_battery",),
    "rebasing_leaks_gold_or_hidden_payload": (
        "layer3_g8_rebasing_leaks_gold_or_hidden_payload",
    ),
    "rebasing_lowers_s14_floor": ("layer3_g8_rebasing_lowers_s14_floor",),
    "closeout_signal_used_as_authority": (
        "layer3_g8_metric_used_as_closeout_authority",
    ),
    "public_projection_authority_leak": (
        "layer3_g8_public_projection_authority_leak",
    ),
}


class _G8Model(BaseModel):
    """Strict immutable model base for committed G8 artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Layer3G8Issue(_G8Model):
    """Typed issue emitted by G8 validators and conformance checks."""

    issue_code: str
    ref: str
    message: str


MetricRegistryStatus = Literal["pass", "blocked"]


class Layer3G8HealthMetricRegistryEntry(_G8Model):
    """Canonical G8 health metric registry row normalized from the G0 ledger."""

    metric_id: str
    owner: str
    trend_vocabulary: tuple[str, ...]
    freeze_value: dict[str, Any]
    per_slice_delta_rule: str
    next_update_rule: str
    aliases: tuple[str, ...]
    source_ledger_ref: str
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8HealthMetricRegistry(_G8Model):
    """Canonical G8 health metric registry with alias and authority boundaries."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    registry_id: str = "layer3-g8://health-metric-registry"
    status: MetricRegistryStatus
    entries: tuple[Layer3G8HealthMetricRegistryEntry, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


_REGISTRY_ROWS: tuple[dict[str, Any], ...] = (
    {
        "metric_id": "envelope-expansion-rate",
        "owner": "team-runtime-quality",
        "trend_vocabulary": ("expanding", "flat", "shrinking"),
        "freeze_value": {"g0_admitted_adapter_count": 0},
        "per_slice_delta_rule": (
            "Later slices may change only after admitted adapter evidence."
        ),
        "next_update_rule": (
            "Recompute when a G1+ adapter slice writes governed artifacts."
        ),
    },
    {
        "metric_id": "adapter-semantic-loss",
        "owner": "team-runtime-quality",
        "trend_vocabulary": ("clean", "lossy"),
        "freeze_value": {"semantic_loss_events": 0},
        "per_slice_delta_rule": "Any AdapterLossBlocker event increments lossy evidence.",
        "next_update_rule": "Recompute from conformance harness outputs.",
    },
    {
        "metric_id": "governance-throughput",
        "owner": "principal-governance",
        "trend_vocabulary": ("flowing", "stalled"),
        "freeze_value": {"accepted_adr_count": 0, "open_human_gate_count": 1},
        "per_slice_delta_rule": (
            "Human acceptance gates move throughput only with acceptance refs."
        ),
        "next_update_rule": "Recompute at ADR-0175 acceptance.",
    },
    {
        "metric_id": "demand-pull-vs-abstention",
        "owner": "team-runtime-quality",
        "trend_vocabulary": ("responding", "abstention_inertia"),
        "freeze_value": {"grounded_conversion_count": 0},
        "per_slice_delta_rule": (
            "Demand pull cannot count until a grounded adapter admits evidence."
        ),
        "next_update_rule": "Recompute from universal corpus G0 route.",
    },
    {
        "metric_id": "search-recall@known-seeds+index-staleness",
        "owner": "team-runtime-quality",
        "trend_vocabulary": ("fresh_recall_ok", "search_ceiling"),
        "freeze_value": {
            "known_groundable_seed_miss_count": 0,
            "stale_required_index_count": 0,
        },
        "per_slice_delta_rule": (
            "Recall misses or stale required indexes block domain-ceiling and no-hit claims."
        ),
        "next_update_rule": (
            "Recompute from GroundingSearchDiscipline recall/freshness records."
        ),
    },
)


def canonical_metric_id(metric_id: str) -> str | None:
    """Return the canonical G8 health metric id for a known source spelling."""

    return G8_METRIC_ALIASES.get(str(metric_id))


def _aliases_for(metric_id: str) -> tuple[str, ...]:
    return tuple(
        alias for alias, canonical in G8_METRIC_ALIASES.items() if canonical == metric_id
    )


def build_g8_health_metric_registry() -> Layer3G8HealthMetricRegistry:
    """Build the canonical G8 metric registry from governed baseline rows."""

    entries = tuple(
        Layer3G8HealthMetricRegistryEntry(
            **row,
            aliases=_aliases_for(str(row["metric_id"])),
            source_ledger_ref=(
                "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml"
                f"#{row['metric_id']}"
            ),
        )
        for row in _REGISTRY_ROWS
    )
    issue_codes: list[str] = []
    if {entry.metric_id for entry in entries} != set(G8_CANONICAL_METRIC_IDS):
        issue_codes.append("layer3_g8_health_metric_registry_missing")
    return Layer3G8HealthMetricRegistry(
        status="blocked" if issue_codes else "pass",
        entries=entries,
        issue_codes=_dedupe(issue_codes),
    )


class Layer3G8MetricSourceRef(_G8Model):
    """Committed G0-G7/S14 source artifact visible to G8 metric governance."""

    slice_id: str
    path: str
    source_ref: str
    format: Literal["json", "toml"]
    status: Literal["present", "missing", "unreadable"]
    digest: str = ""
    schema_version: str = ""
    rule_version: str = ""
    generated_at: str = ""
    issue_codes: tuple[str, ...] = ()


class Layer3G8MetricSourceSnapshot(_G8Model):
    """Snapshot of committed source artifacts used by G8 normalization."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    snapshot_id: str = "layer3-g8://metric-source-snapshot"
    status: Literal["pass", "blocked"]
    sources: tuple[Layer3G8MetricSourceRef, ...]
    source_count: int
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8NormalizedMetricSignal(_G8Model):
    """Canonical G8 metric signal normalized from a raw source dialect."""

    signal_id: str
    slice_id: str
    metric_id: str
    raw_key: str
    raw_value: Any
    status: str
    raw_source_ref: str
    source_digest: str
    freshness_status: Literal["fresh_committed", "missing", "unknown_time"]
    authority_boundary_status: Literal["pass", "missing"]
    observed_at: str
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8NormalizedMetricSignals(_G8Model):
    """Canonical signal set preserving raw refs and G8 authority boundaries."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    signal_set_id: str = "layer3-g8://normalized-metric-signals"
    status: Literal["pass", "blocked"]
    signals: tuple[Layer3G8NormalizedMetricSignal, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8MetricTrendRow(_G8Model):
    """CI-visible trend row for one canonical health metric."""

    metric_id: str
    latest_status: str
    signal_count: int
    source_refs: tuple[str, ...]
    trend_vocabulary: tuple[str, ...]
    trend_status: Literal["reported", "missing"]


class Layer3G8MetricTrendReport(_G8Model):
    """First-class trend report over all five canonical G8 metrics."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    report_id: str = "layer3-g8://metric-trend-report"
    status: Literal["pass", "blocked"]
    ci_report_status: Literal["first_class_metric_trends_visible", "blocked"]
    metric_trends: tuple[Layer3G8MetricTrendRow, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


_G8_SOURCE_PATHS: tuple[tuple[str, Path, str], ...] = (
    ("G0", POLICY_DESIGN_CASE_DIR / "layer3_health_metric_ledgers.toml", "toml"),
    ("G1", POLICY_DESIGN_CASE_DIR / "layer3_g1_health_metric_delta.toml", "toml"),
    ("G1", POLICY_DESIGN_CASE_DIR / "layer3_g1_search_recall_freshness.json", "json"),
    ("G1", POLICY_DESIGN_CASE_DIR / "layer3_g1_readiness_manifest.json", "json"),
    ("G2", POLICY_DESIGN_CASE_DIR / "layer3_g2_health_metric_delta.toml", "toml"),
    ("G2", POLICY_DESIGN_CASE_DIR / "layer3_g2_search_recall_freshness.json", "json"),
    ("G2", POLICY_DESIGN_CASE_DIR / "layer3_g2_readiness_manifest.json", "json"),
    ("G3", POLICY_DESIGN_CASE_DIR / "layer3_g3_health_metric_delta.toml", "toml"),
    ("G3", POLICY_DESIGN_CASE_DIR / "layer3_g3_search_recall_freshness.json", "json"),
    ("G3", POLICY_DESIGN_CASE_DIR / "layer3_g3_readiness_manifest.json", "json"),
    ("GL", POLICY_DESIGN_CASE_DIR / "layer3_gl_health_metric_delta.toml", "toml"),
    ("GL", POLICY_DESIGN_CASE_DIR / "layer3_gl_search_recall_freshness.json", "json"),
    ("GL", POLICY_DESIGN_CASE_DIR / "layer3_gl_readiness_manifest.json", "json"),
    ("G4", POLICY_DESIGN_CASE_DIR / "layer3_g4_health_metric_delta.toml", "toml"),
    ("G4", POLICY_DESIGN_CASE_DIR / "layer3_g4_governance_throughput_delta.json", "json"),
    ("G4", POLICY_DESIGN_CASE_DIR / "layer3_g4_readiness_manifest.json", "json"),
    ("G5", POLICY_DESIGN_CASE_DIR / "layer3_g5_health_metric_delta.toml", "toml"),
    (
        "G5",
        POLICY_DESIGN_CASE_DIR / "layer3_g5_dependency_health_metric_snapshot.json",
        "json",
    ),
    (
        "G5",
        POLICY_DESIGN_CASE_DIR / "layer3_g5_grounded_result_evidence_set.json",
        "json",
    ),
    (
        "G5",
        POLICY_DESIGN_CASE_DIR / "layer3_g5_effective_evidence_independence.json",
        "json",
    ),
    (
        "G5",
        POLICY_DESIGN_CASE_DIR / "layer3_g5_grounded_abstention_quality_record.json",
        "json",
    ),
    (
        "G5",
        POLICY_DESIGN_CASE_DIR / "layer3_g5_useful_design_metric_eligibility_join.json",
        "json",
    ),
    ("G5", POLICY_DESIGN_CASE_DIR / "layer3_g5_demand_pull_attempt_record.json", "json"),
    ("G5", POLICY_DESIGN_CASE_DIR / "layer3_g5_readiness_manifest.json", "json"),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_health_metric_delta.toml", "toml"),
    (
        "G6",
        POLICY_DESIGN_CASE_DIR / "layer3_g6_demand_pull_vs_abstention_delta.json",
        "json",
    ),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_grounding_demand_record.json", "json"),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_search_ledger.json", "json"),
    (
        "G6",
        POLICY_DESIGN_CASE_DIR / "layer3_g6_orchestration_choice_audit.json",
        "json",
    ),
    (
        "G6",
        POLICY_DESIGN_CASE_DIR / "layer3_g6_candidate_authority_firewall_report.json",
        "json",
    ),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_conformance_report.json", "json"),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_readiness_manifest.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_health_metric_delta.toml", "toml"),
    (
        "G7",
        POLICY_DESIGN_CASE_DIR / "layer3_g7_dependency_readiness_snapshot.json",
        "json",
    ),
    (
        "G7",
        POLICY_DESIGN_CASE_DIR / "layer3_g7_search_recall_freshness_join.json",
        "json",
    ),
    (
        "G7",
        POLICY_DESIGN_CASE_DIR / "layer3_g7_region_conversion_status_matrix.json",
        "json",
    ),
    (
        "G7",
        POLICY_DESIGN_CASE_DIR / "layer3_g7_g5_g6_authority_boundary_report.json",
        "json",
    ),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_grounded_breadth_feed.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_region_scorecard.json", "json"),
    (
        "G7",
        POLICY_DESIGN_CASE_DIR / "layer3_g7_region_widening_audit_surface.json",
        "json",
    ),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_readiness_manifest.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_battery_input_manifest.json", "json"),
    ("S14", POLICY_DESIGN_CASE_DIR / "layer2_corpus_partition.json", "json"),
    (
        "S14",
        POLICY_DESIGN_CASE_DIR / "layer2_s14_universality_assurance_manifest.json",
        "json",
    ),
)


def build_g8_metric_source_snapshot(
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8MetricSourceSnapshot:
    """Build a committed source snapshot for G8 normalization."""

    root = Path(repo_root).resolve()
    sources: list[Layer3G8MetricSourceRef] = []
    issues: list[str] = []
    for slice_id, relative_path, source_format in _G8_SOURCE_PATHS:
        path = root / relative_path
        source_ref = f"repo://{relative_path.as_posix()}"
        if not path.exists():
            issues.append("layer3_g8_metric_source_missing")
            sources.append(
                Layer3G8MetricSourceRef(
                    slice_id=slice_id,
                    path=relative_path.as_posix(),
                    source_ref=source_ref,
                    format=source_format,  # type: ignore[arg-type]
                    status="missing",
                    issue_codes=("layer3_g8_metric_source_missing",),
                )
            )
            continue
        try:
            payload = _read_toml(path) if source_format == "toml" else _read_json(path)
        except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError):
            issues.append("layer3_g8_metric_source_missing")
            sources.append(
                Layer3G8MetricSourceRef(
                    slice_id=slice_id,
                    path=relative_path.as_posix(),
                    source_ref=source_ref,
                    format=source_format,  # type: ignore[arg-type]
                    status="unreadable",
                    issue_codes=("layer3_g8_metric_source_missing",),
                )
            )
            continue
        sources.append(
            Layer3G8MetricSourceRef(
                slice_id=slice_id,
                path=relative_path.as_posix(),
                source_ref=source_ref,
                format=source_format,  # type: ignore[arg-type]
                status="present",
                digest=_digest_payload(payload),
                schema_version=_text(payload.get("schema_version")),
                rule_version=_text(payload.get("rule_version")),
                generated_at=_text(payload.get("generated_at")),
            )
        )
    return Layer3G8MetricSourceSnapshot(
        status="blocked" if issues else "pass",
        sources=tuple(sources),
        source_count=len(sources),
        issue_codes=_dedupe(issues),
    )


def build_g8_normalized_metric_signals(
    *,
    registry: Layer3G8HealthMetricRegistry,
    source_snapshot: Layer3G8MetricSourceSnapshot,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
    observed_at: str = "2026-06-10T00:00:00Z",
) -> Layer3G8NormalizedMetricSignals:
    """Normalize current G0-G7/S14 metric dialects into canonical G8 signals."""

    root = Path(repo_root).resolve()
    registry_ids = {entry.metric_id for entry in registry.entries}
    signals: list[Layer3G8NormalizedMetricSignal] = []
    issues: list[str] = []
    for source in source_snapshot.sources:
        if source.status != "present":
            issues.extend(source.issue_codes)
            continue
        path = root / source.path
        payload = _read_toml(path) if source.format == "toml" else _read_json(path)
        for raw_key, raw_value in _metric_items_from_payload(source.slice_id, payload):
            canonical = canonical_metric_id(raw_key)
            if canonical is None:
                continue
            if canonical not in registry_ids:
                issues.append("layer3_g8_metric_alias_unresolved")
                continue
            status = _status_from_metric_value(raw_key, raw_value)
            signal_issues = _signal_issue_codes(
                metric_id=canonical,
                raw_key=raw_key,
                status=status,
                raw_value=raw_value,
            )
            issues.extend(signal_issues)
            signals.append(
                Layer3G8NormalizedMetricSignal(
                    signal_id=(
                        "layer3-g8://normalized-metric/"
                        f"{source.slice_id.lower()}/{_slug(canonical)}/{_slug(raw_key)}"
                    ),
                    slice_id=source.slice_id,
                    metric_id=canonical,
                    raw_key=raw_key,
                    raw_value=raw_value,
                    status=status,
                    raw_source_ref=f"{source.source_ref}#{raw_key}",
                    source_digest=source.digest,
                    freshness_status="fresh_committed",
                    authority_boundary_status="pass",
                    observed_at=observed_at,
                    issue_codes=signal_issues,
                )
            )
    missing_metrics = set(G8_CANONICAL_METRIC_IDS) - {signal.metric_id for signal in signals}
    if missing_metrics:
        issues.append("layer3_g8_metric_source_missing")
    return Layer3G8NormalizedMetricSignals(
        status="blocked" if _blocking_signal_issues(issues) else "pass",
        signals=tuple(signals),
        issue_codes=_dedupe(issues),
    )


def build_g8_metric_trend_report(
    *,
    registry: Layer3G8HealthMetricRegistry,
    signals: Layer3G8NormalizedMetricSignals,
) -> Layer3G8MetricTrendReport:
    """Build a CI-visible trend report over all canonical G8 metrics."""

    rows: list[Layer3G8MetricTrendRow] = []
    issues: list[str] = []
    registry_by_metric = {entry.metric_id: entry for entry in registry.entries}
    for metric_id in G8_CANONICAL_METRIC_IDS:
        metric_signals = tuple(
            signal for signal in signals.signals if signal.metric_id == metric_id
        )
        if not metric_signals:
            issues.append("layer3_g8_metric_trend_report_missing")
            rows.append(
                Layer3G8MetricTrendRow(
                    metric_id=metric_id,
                    latest_status="missing",
                    signal_count=0,
                    source_refs=(),
                    trend_vocabulary=registry_by_metric[metric_id].trend_vocabulary,
                    trend_status="missing",
                )
            )
            continue
        rows.append(
            Layer3G8MetricTrendRow(
                metric_id=metric_id,
                latest_status=_latest_metric_status(signals, metric_id),
                signal_count=len(metric_signals),
                source_refs=_dedupe(signal.raw_source_ref for signal in metric_signals),
                trend_vocabulary=registry_by_metric[metric_id].trend_vocabulary,
                trend_status="reported",
            )
        )
    return Layer3G8MetricTrendReport(
        status="blocked" if issues else "pass",
        ci_report_status="blocked" if issues else "first_class_metric_trends_visible",
        metric_trends=tuple(rows),
        issue_codes=_dedupe(issues),
    )


class Layer3G8CrossMetricDiagnosis(_G8Model):
    """Cross-metric diagnosis distinguishing source ceilings from value blockers."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    diagnosis_id: str = "layer3-g8://cross-metric-diagnosis"
    status: Literal["pass", "blocked"]
    envelope_expansion_status: str
    semantic_loss_status: str
    governance_throughput_status: str
    demand_pull_status: str
    search_recall_freshness_status: str
    effective_independence_status: str
    effective_independent_evidence_count: int
    effective_independence_source_ref: str
    current_blocker_refs: tuple[str, ...]
    diagnoses: tuple[str, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8DomainVsSearchCeilingGate(_G8Model):
    """Gate preventing search/governance/abstention blockers becoming domain ceilings."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    gate_id: str = "layer3-g8://domain-vs-search-ceiling-gate"
    status: Literal[
        "domain_ceiling_candidate",
        "search_ceiling_repair_required",
        "governance_stall_repair_required",
        "abstention_inertia_repair_required",
        "semantic_loss_repair_required",
        "not_claimed_current_grounding_blocker",
        "blocked",
    ]
    domain_ceiling_claim_allowed: bool
    current_blocker_refs: tuple[str, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


def build_g8_cross_metric_diagnosis(
    *,
    signals: Layer3G8NormalizedMetricSignals,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8CrossMetricDiagnosis:
    """Build cross-metric diagnosis without minting domain-ceiling authority."""

    root = Path(repo_root).resolve()
    g5 = _read_optional_json(root / POLICY_DESIGN_CASE_DIR / "layer3_g5_readiness_manifest.json")
    g7 = _read_optional_json(root / POLICY_DESIGN_CASE_DIR / "layer3_g7_readiness_manifest.json")
    g5_independence = _read_optional_json(
        root / POLICY_DESIGN_CASE_DIR / "layer3_g5_effective_evidence_independence.json"
    )
    effective_mass = _mapping(
        _mapping(g5_independence.get("independence_map_payload")).get(
            "effective_mass_report"
        )
    )
    statuses = {
        metric_id: _latest_metric_status(signals, metric_id)
        for metric_id in G8_CANONICAL_METRIC_IDS
    }
    g5_summary = _mapping(g5.get("summary"))
    g7_summary = _mapping(g7.get("summary"))
    current_blockers: list[str] = []
    if (
        _text(g5.get("g5_conversion_outcome") or g5_summary.get("g5_conversion_outcome"))
        == "unchanged_blocker"
    ):
        current_blockers.append(
            "repo://architecture/policy_design_case/layer3_g5_readiness_manifest.json"
            "#g5_conversion_outcome"
        )
    if _text(
        g7.get("g7_region_value_closure_status")
        or g7_summary.get("g7_region_value_closure_status")
    ).startswith("blocked"):
        current_blockers.append(
            "repo://architecture/policy_design_case/layer3_g7_readiness_manifest.json"
            "#g7_region_value_closure_status"
        )
    if int(
        g7.get("g7_region_grounded_case_count")
        or g7_summary.get("g7_region_grounded_case_count")
        or 0
    ) == 0:
        current_blockers.append(
            "repo://architecture/policy_design_case/layer3_g7_readiness_manifest.json"
            "#g7_region_grounded_case_count"
        )

    diagnoses: list[str] = []
    issues: list[str] = [*signals.issue_codes]
    effective_independence_status = _text(effective_mass.get("independence_status")) or "missing"
    effective_independent_evidence_count = int(
        effective_mass.get("effective_independent_evidence_count") or 0
    )
    if effective_independence_status in {"inflated", "unknown", "missing"}:
        issues.append("layer3_g8_effective_independence_inflated")
    if _is_search_ceiling(statuses["search-recall@known-seeds+index-staleness"]):
        diagnoses.append("search_ceiling")
        issues.append("layer3_g8_search_recall_miss_reported_as_domain_ceiling")
    if _is_governance_stall(statuses["governance-throughput"]):
        diagnoses.append("governance_bottleneck")
        issues.append("layer3_g8_governance_stall_hidden_as_domain_ceiling")
    current_committed_source_set = _is_current_committed_source_set(signals)
    if (
        _is_abstention_inertia(statuses["demand-pull-vs-abstention"])
        and not (current_blockers and current_committed_source_set)
    ):
        diagnoses.append("abstention_inertia")
        issues.append("layer3_g8_abstention_inertia_hidden_as_honesty")
    if _is_semantic_loss(statuses["adapter-semantic-loss"]):
        diagnoses.append("semantic_loss")
        issues.append("layer3_g8_semantic_loss_hidden_by_metric_rollup")
    if current_blockers:
        diagnoses.append("current_grounding_blocker")
    if not diagnoses:
        diagnoses.append("healthy_metric_watch")

    blocking = {
        "layer3_g8_metric_source_missing",
        "layer3_g8_metric_alias_unresolved",
        "layer3_g8_metric_raw_ref_missing",
        "layer3_g8_metric_authority_boundary_missing",
    }
    return Layer3G8CrossMetricDiagnosis(
        status="blocked" if blocking.intersection(issues) else "pass",
        envelope_expansion_status=statuses["envelope-expansion-rate"],
        semantic_loss_status=statuses["adapter-semantic-loss"],
        governance_throughput_status=statuses["governance-throughput"],
        demand_pull_status=statuses["demand-pull-vs-abstention"],
        search_recall_freshness_status=statuses[
            "search-recall@known-seeds+index-staleness"
        ],
        effective_independence_status=effective_independence_status,
        effective_independent_evidence_count=effective_independent_evidence_count,
        effective_independence_source_ref=(
            "repo://architecture/policy_design_case/"
            "layer3_g5_effective_evidence_independence.json"
            "#independence_map_payload.effective_mass_report"
        ),
        current_blocker_refs=_dedupe(current_blockers),
        diagnoses=_dedupe(diagnoses),
        issue_codes=_dedupe(issues),
    )


def build_g8_domain_vs_search_ceiling_gate(
    *,
    diagnosis: Layer3G8CrossMetricDiagnosis,
) -> Layer3G8DomainVsSearchCeilingGate:
    """Return the strongest current blocker before any domain-ceiling claim."""

    if diagnosis.status == "blocked":
        return Layer3G8DomainVsSearchCeilingGate(
            status="blocked",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=diagnosis.issue_codes,
        )
    if "search_ceiling" in diagnosis.diagnoses:
        return Layer3G8DomainVsSearchCeilingGate(
            status="search_ceiling_repair_required",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=_dedupe(
                (
                    *diagnosis.issue_codes,
                    "layer3_g8_search_recall_miss_reported_as_domain_ceiling",
                )
            ),
        )
    if "governance_bottleneck" in diagnosis.diagnoses:
        return Layer3G8DomainVsSearchCeilingGate(
            status="governance_stall_repair_required",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=_dedupe(
                (
                    *diagnosis.issue_codes,
                    "layer3_g8_governance_stall_hidden_as_domain_ceiling",
                )
            ),
        )
    if "abstention_inertia" in diagnosis.diagnoses:
        return Layer3G8DomainVsSearchCeilingGate(
            status="abstention_inertia_repair_required",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=_dedupe(
                (
                    *diagnosis.issue_codes,
                    "layer3_g8_abstention_inertia_hidden_as_honesty",
                )
            ),
        )
    if "semantic_loss" in diagnosis.diagnoses:
        return Layer3G8DomainVsSearchCeilingGate(
            status="semantic_loss_repair_required",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=diagnosis.issue_codes,
        )
    if diagnosis.current_blocker_refs:
        return Layer3G8DomainVsSearchCeilingGate(
            status="not_claimed_current_grounding_blocker",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=diagnosis.issue_codes,
        )
    return Layer3G8DomainVsSearchCeilingGate(
        status="domain_ceiling_candidate",
        domain_ceiling_claim_allowed=True,
        current_blocker_refs=(),
        issue_codes=diagnosis.issue_codes,
    )


def domain_ceiling_claim_issue_codes(
    *,
    diagnosis: Layer3G8CrossMetricDiagnosis,
    claimed_domain_ceiling: bool,
) -> tuple[str, ...]:
    """Report issue codes if a caller tries to claim a domain ceiling."""

    if not claimed_domain_ceiling:
        return ()
    issues: list[str] = []
    if "search_ceiling" in diagnosis.diagnoses:
        issues.append("layer3_g8_search_recall_miss_reported_as_domain_ceiling")
    if "governance_bottleneck" in diagnosis.diagnoses:
        issues.append("layer3_g8_governance_stall_hidden_as_domain_ceiling")
    if "abstention_inertia" in diagnosis.diagnoses:
        issues.append("layer3_g8_abstention_inertia_hidden_as_honesty")
    if "semantic_loss" in diagnosis.diagnoses:
        issues.append("layer3_g8_semantic_loss_hidden_by_metric_rollup")
    if diagnosis.current_blocker_refs or diagnosis.envelope_expansion_status == "flat":
        issues.append("layer3_g8_flat_expansion_reported_as_domain_ceiling_without_search_health")
    return _dedupe(issues)


class Layer3G8MetricGamingFirewall(_G8Model):
    """Firewall blocking health metric gains from threshold or fixture gaming."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    firewall_id: str = "layer3-g8://metric-gaming-firewall"
    status: Literal["pass", "blocked"]
    checked_change_count: int
    blocked_change_refs: tuple[str, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8WarningLifecycleRow(_G8Model):
    """Owned warning row with aging and accepted-deficit semantics."""

    warning_id: str
    metric_id: str
    severity: Literal["info", "warn", "blocked"]
    owner: str
    deadline: str
    aging_policy: str
    accepted_deficit_policy: str
    source_ref: str
    issue_codes: tuple[str, ...] = ()


class Layer3G8WarningLifecycleLedger(_G8Model):
    """Ledger converting G8 soft gates into owned warning lifecycle rows."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    ledger_id: str = "layer3-g8://warning-lifecycle-ledger"
    status: Literal["pass", "blocked"]
    warnings: tuple[Layer3G8WarningLifecycleRow, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


def build_g8_metric_gaming_firewall(
    *,
    metric_changes: Sequence[Mapping[str, Any]],
) -> Layer3G8MetricGamingFirewall:
    """Block metric improvements produced by gaming rather than real capability."""

    issues: list[str] = []
    blocked_refs: list[str] = []
    for change in metric_changes:
        change_class = _text(change.get("change_class")).casefold()
        target_metric = _text(change.get("target_metric")).casefold()
        source_ref = _text(change.get("source_ref")) or "unknown://metric-change"
        if change.get("claimed_improvement") and change_class in {
            "threshold_lowered",
            "floor_relaxed",
            "hidden_fixture_added",
            "synthetic_breadth",
        }:
            blocked_refs.append(source_ref)
            if change_class in {"threshold_lowered", "floor_relaxed"}:
                issues.append("layer3_g8_metric_improved_by_threshold_lowering")
            else:
                issues.append("layer3_g8_metric_improved_by_fixture_or_synthetic_breadth")
        if target_metric == "useful_design_rate":
            blocked_refs.append(source_ref)
            issues.append("layer3_g8_useful_design_rate_optimized")
    return Layer3G8MetricGamingFirewall(
        status="blocked" if issues else "pass",
        checked_change_count=len(metric_changes),
        blocked_change_refs=_dedupe(blocked_refs),
        issue_codes=_dedupe(issues),
    )


def build_g8_warning_lifecycle_ledger(
    *,
    warnings: Sequence[Mapping[str, Any]],
) -> Layer3G8WarningLifecycleLedger:
    """Build an owned warning ledger and block warnings missing lifecycle fields."""

    rows: list[Layer3G8WarningLifecycleRow] = []
    issues: list[str] = []
    for raw in warnings:
        row_issues: list[str] = []
        if not _text(raw.get("owner")):
            row_issues.append("layer3_g8_warning_owner_missing")
        if not _text(raw.get("aging_policy")):
            row_issues.append("layer3_g8_warning_aging_policy_missing")
        issues.extend(row_issues)
        metric_id = _text(raw.get("metric_id"))
        severity = _text(raw.get("severity")) or "warn"
        if severity not in {"info", "warn", "blocked"}:
            severity = "warn"
        rows.append(
            Layer3G8WarningLifecycleRow(
                warning_id=_text(raw.get("warning_id")) or "layer3-g8-warning",
                metric_id=canonical_metric_id(metric_id) or metric_id,
                severity=severity,  # type: ignore[arg-type]
                owner=_text(raw.get("owner")),
                deadline=_text(raw.get("deadline")),
                aging_policy=_text(raw.get("aging_policy")),
                accepted_deficit_policy=(
                    _text(raw.get("accepted_deficit_policy"))
                    or "blocks_closeout_authority"
                ),
                source_ref=_text(raw.get("source_ref")),
                issue_codes=_dedupe(row_issues),
            )
        )
    return Layer3G8WarningLifecycleLedger(
        status="blocked" if issues else "pass",
        warnings=tuple(rows),
        issue_codes=_dedupe(issues),
    )


def build_g8_default_warning_lifecycle_ledger(
    *,
    diagnosis: Layer3G8CrossMetricDiagnosis,
) -> Layer3G8WarningLifecycleLedger:
    """Build default owned warnings from current G8 diagnosis signals."""

    warnings: list[dict[str, Any]] = []
    if "current_grounding_blocker" in diagnosis.diagnoses:
        warnings.append(
            {
                "warning_id": "layer3-g8-current-grounding-blocker",
                "metric_id": "envelope-expansion-rate",
                "severity": "warn",
                "owner": "team-runtime-quality",
                "deadline": "2026-06-17",
                "aging_policy": "escalate_if_unchanged_after_next_g_slice",
                "accepted_deficit_policy": (
                    "may_pass_engineering_readiness_but_blocks_domain_ceiling_claim"
                ),
                "source_ref": (
                    "repo://architecture/policy_design_case/"
                    "layer3_g7_readiness_manifest.json"
                ),
            }
        )
    return build_g8_warning_lifecycle_ledger(warnings=warnings)


class Layer3G8D44CorpusRebasingRule(_G8Model):
    """D4.4 re-basing rule with freeze-hash and hidden-access discipline."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    rule_id: str = "layer3-g8://d44-corpus-rebasing-rule"
    status: Literal["pass", "blocked"]
    required_reannotation_fields: tuple[str, ...]
    freeze_hash_discipline: str
    hidden_access_rule: str
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8D44ReannotationCoverageRow(_G8Model):
    """Coverage status for one required D4.4 re-annotation field."""

    field_id: str
    coverage_status: Literal[
        "required_for_next_rebase",
        "satisfied_by_existing_s14_record",
    ]
    source_ref: str
    issue_codes: tuple[str, ...] = ()


class Layer3G8D44ReannotationCoverageMatrix(_G8Model):
    """Matrix proving every D4.4 field is covered or carried to next rebase."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    matrix_id: str = "layer3-g8://d44-reannotation-coverage-matrix"
    status: Literal["pass", "blocked"]
    field_rows: tuple[Layer3G8D44ReannotationCoverageRow, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8D44RebasingTriggerRow(_G8Model):
    """One trigger considered by the D4.4 re-basing ledger."""

    trigger_id: str
    trigger_status: Literal["not_due", "due", "blocked"]
    source_ref: str
    reason: str


class Layer3G8D44RebasingTriggerLedger(_G8Model):
    """Current D4.4 re-basing trigger ledger."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    ledger_id: str = "layer3-g8://d44-rebasing-trigger-ledger"
    status: Literal["pass_no_rebase_due", "rebase_due", "blocked"]
    current_action: str
    trigger_rows: tuple[Layer3G8D44RebasingTriggerRow, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8D44RebasingCandidateSet(_G8Model):
    """Visible candidate refs considered for a future D4.4 rebase."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    candidate_set_id: str = "layer3-g8://d44-rebasing-candidate-set"
    status: Literal["pass", "blocked"]
    candidate_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8D44RebasingReceipt(_G8Model):
    """D4.4 receipt preserving freeze-hash discipline for current G8."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    receipt_id: str = "layer3-g8://d44-rebasing-receipt/current"
    status: Literal["pass_no_rebase_required", "blocked", "rebased_with_new_freeze_hash"]
    action: str
    pre_rebase_freeze_hash: str
    post_rebase_freeze_hash: str
    corpus_partition_ref: str
    s14_assurance_manifest_ref: str
    candidate_set_ref: str
    hidden_payload_access_status: Literal["not_accessed_by_g8", "blocked"]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8SealedBatteryIntegrityJoin(_G8Model):
    """Join proving G8 did not mutate or inspect sealed S14 battery payloads."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    join_id: str = "layer3-g8://sealed-battery-integrity-join"
    status: Literal["pass", "blocked"]
    partition_freeze_hash: str
    s14_manifest_freeze_hash: str
    g7_mutation_status: str
    hidden_payload_access_status: str
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


def build_g8_d44_corpus_rebasing_rule(
    *,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8D44CorpusRebasingRule:
    """Build the D4.4 corpus re-basing rule for governed G8 receipts."""

    return Layer3G8D44CorpusRebasingRule(
        status="pass",
        required_reannotation_fields=D44_REQUIRED_REANNOTATION_FIELDS,
        freeze_hash_discipline=(
            "Any re-basing that changes sealed battery membership, labels, "
            "thresholds, or expected dispositions requires a new "
            "governance-approved freeze hash and replay receipt."
        ),
        hidden_access_rule=(
            "G8 may read committed partition and S14 assurance manifests; it "
            "must not read hidden sealed case payloads or gold labels in "
            "development paths."
        ),
    )


_D44_EXISTING_S14_FIELD_REFS: dict[str, str] = {
    "expected_evidence_tier": (
        "repo://architecture/policy_design_case/"
        "layer2_s14_universality_assurance_manifest.json"
        "#supporting_records.UniversalityBreadthFloorConfig"
    ),
    "available_source_contracts": (
        "repo://architecture/policy_design_case/"
        "layer2_s14_universality_assurance_manifest.json"
        "#grounded_authority_coverage_ref"
    ),
    "expected_graded_outcome_by_authority_posture": (
        "repo://architecture/policy_design_case/"
        "layer2_s14_universality_assurance_manifest.json"
        "#supporting_records.EvaluationStatusCompositionRecord"
    ),
    "certified_operation_envelope_status": (
        "repo://architecture/policy_design_case/"
        "layer2_s14_universality_assurance_manifest.json"
        "#declared_operation_envelope_ref"
    ),
    "expected_abstention_limitation_boundary": (
        "repo://architecture/policy_design_case/"
        "layer2_s14_universality_assurance_manifest.json#universal_claim_gate_status"
    ),
    "expected_counterexample_class": (
        "repo://architecture/policy_design_case/"
        "layer2_s14_universality_assurance_manifest.json#skeptic_defeater_mapping"
    ),
    "bootstrap_role": (
        "repo://architecture/policy_design_case/"
        "layer2_s14_universality_assurance_manifest.json"
        "#supporting_records.ExpertOracleBootstrapRecord"
    ),
    "universality_battery_metadata": (
        "repo://architecture/policy_design_case/"
        "layer2_s14_universality_assurance_manifest.json"
        "#artifact_records.SealedUniversalityBatteryRun"
    ),
    "post_deploy_monitoring_hooks": (
        "repo://architecture/policy_design_case/"
        "layer2_s14_universality_assurance_manifest.json"
        "#supporting_records.EnvelopeRevisionDynamicsRecord"
    ),
    "historical_outcomes_prediction_backtest_usability": (
        "repo://architecture/policy_design_case/"
        "layer2_s14_universality_assurance_manifest.json#baseline_comparison_ref"
    ),
    "realized_regret_observability": (
        "repo://architecture/policy_design_case/"
        "layer2_s14_universality_assurance_manifest.json"
        "#supporting_records.EvaluationStatusCompositionRecord"
    ),
}


def build_g8_d44_reannotation_coverage_matrix(
    *,
    rule: Layer3G8D44CorpusRebasingRule,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8D44ReannotationCoverageMatrix:
    """Build D4.4 field coverage without silently dropping required fields."""

    rows: list[Layer3G8D44ReannotationCoverageRow] = []
    for field_id in rule.required_reannotation_fields:
        source_ref = _D44_EXISTING_S14_FIELD_REFS.get(
            field_id,
            (
                "repo://docs/system-design-decisions/"
                "universal-policy-design-target-architecture-and-gap.md#D4.4"
            ),
        )
        rows.append(
            Layer3G8D44ReannotationCoverageRow(
                field_id=field_id,
                coverage_status=(
                    "satisfied_by_existing_s14_record"
                    if field_id in _D44_EXISTING_S14_FIELD_REFS
                    else "required_for_next_rebase"
                ),
                source_ref=source_ref,
            )
        )
    missing = sorted(set(D44_REQUIRED_REANNOTATION_FIELDS) - {row.field_id for row in rows})
    stale_existing_refs = sorted(
        set(_D44_EXISTING_S14_FIELD_REFS) - set(D44_REQUIRED_REANNOTATION_FIELDS)
    )
    issues = (
        ("layer3_g8_d44_reannotation_coverage_missing",)
        if missing or stale_existing_refs
        else ()
    )
    return Layer3G8D44ReannotationCoverageMatrix(
        status="blocked" if issues else "pass",
        field_rows=tuple(rows),
        issue_codes=issues,
    )


def build_g8_d44_rebasing_trigger_ledger(
    *,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8D44RebasingTriggerLedger:
    """Build current D4.4 re-basing trigger ledger from visible G7/S14 refs."""

    root = Path(repo_root).resolve()
    g7_feed = _read_optional_json(
        root / POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_grounded_breadth_feed.json"
    )
    feed_status = _text(g7_feed.get("status")) or "blocked_no_real_grounded_breadth"
    new_breadth_due = bool(feed_status and not feed_status.startswith("blocked"))
    trigger_rows = (
        Layer3G8D44RebasingTriggerRow(
            trigger_id="new_real_grounded_breadth",
            trigger_status="due" if new_breadth_due else "not_due",
            source_ref=(
                "repo://architecture/policy_design_case/"
                "layer3_g7_s14_grounded_breadth_feed.json#status"
            ),
            reason=feed_status,
        ),
        Layer3G8D44RebasingTriggerRow(
            trigger_id="s14_floor_or_threshold_change",
            trigger_status="not_due",
            source_ref=(
                "repo://architecture/policy_design_case/"
                "layer2_s14_universality_assurance_manifest.json"
            ),
            reason="no_floor_or_threshold_change_requested_by_g8",
        ),
        Layer3G8D44RebasingTriggerRow(
            trigger_id="sealed_battery_membership_change",
            trigger_status="not_due",
            source_ref=(
                "repo://architecture/policy_design_case/layer2_corpus_partition.json"
                "#sealed_universality_battery.freeze_hash"
            ),
            reason="sealed_battery_membership_not_mutated_by_g8",
        ),
        Layer3G8D44RebasingTriggerRow(
            trigger_id="d44_reannotation_schema_change",
            trigger_status="not_due",
            source_ref="layer3-g8://d44-corpus-rebasing-rule",
            reason="initial_g8_rule_version",
        ),
        Layer3G8D44RebasingTriggerRow(
            trigger_id="post_deploy_monitoring_update",
            trigger_status="not_due",
            source_ref="layer3-g8://d44-rebasing-trigger-ledger/post-deploy-monitoring",
            reason="no_post_deploy_monitoring_signal_for_current_s14_seed",
        ),
    )
    due = [row.trigger_id for row in trigger_rows if row.trigger_status == "due"]
    return Layer3G8D44RebasingTriggerLedger(
        status="rebase_due" if due else "pass_no_rebase_due",
        current_action=(
            "prepare_rebase_receipt_for_new_grounded_breadth"
            if due
            else "no_rebase_required_current_g7_has_no_real_grounded_breadth"
        ),
        trigger_rows=trigger_rows,
        issue_codes=(),
    )


def build_g8_d44_rebasing_candidate_set(
    *,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8D44RebasingCandidateSet:
    """Build visible D4.4 candidate refs without hidden sealed payload refs."""

    return Layer3G8D44RebasingCandidateSet(
        status="pass",
        candidate_refs=(
            "repo://architecture/policy_design_case/"
            "layer2_s14_universality_assurance_manifest.json#d4_corpus_track_coverage_ref",
            "repo://architecture/policy_design_case/layer3_g7_s14_grounded_breadth_feed.json",
        ),
        source_refs=(
            "repo://architecture/policy_design_case/layer2_corpus_partition.json",
            (
                "repo://architecture/policy_design_case/"
                "layer2_s14_universality_assurance_manifest.json"
            ),
            "repo://architecture/policy_design_case/layer3_g7_s14_battery_input_manifest.json",
        ),
    )


def build_g8_d44_rebasing_receipt(
    *,
    rule: Layer3G8D44CorpusRebasingRule,
    candidate_set: Layer3G8D44RebasingCandidateSet,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8D44RebasingReceipt:
    """Build current D4.4 receipt and preserve sealed-battery freeze hashes."""

    root = Path(repo_root).resolve()
    partition = _read_json(root / POLICY_DESIGN_CASE_DIR / "layer2_corpus_partition.json")
    s14 = _read_json(
        root / POLICY_DESIGN_CASE_DIR / "layer2_s14_universality_assurance_manifest.json"
    )
    sealed = _mapping(partition.get("sealed_universality_battery"))
    partition_hash = _text(sealed.get("freeze_hash"))
    s14_hash = _text(s14.get("sealed_battery_freeze_hash"))
    issues: list[str] = []
    if not partition_hash or not s14_hash or partition_hash != s14_hash:
        issues.append("layer3_g8_rebasing_without_freeze_hash")
    return Layer3G8D44RebasingReceipt(
        status="blocked" if issues else "pass_no_rebase_required",
        action="no_rebase_required_current_g7_has_no_real_grounded_breadth",
        pre_rebase_freeze_hash=partition_hash or s14_hash,
        post_rebase_freeze_hash=s14_hash or partition_hash,
        corpus_partition_ref="repo://architecture/policy_design_case/layer2_corpus_partition.json",
        s14_assurance_manifest_ref=(
            "repo://architecture/policy_design_case/"
            "layer2_s14_universality_assurance_manifest.json"
        ),
        candidate_set_ref=candidate_set.candidate_set_id,
        hidden_payload_access_status="not_accessed_by_g8",
        issue_codes=_dedupe(issues),
    )


def build_g8_sealed_battery_integrity_join(
    *,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
    rebasing_attempt: Mapping[str, Any] | None = None,
) -> Layer3G8SealedBatteryIntegrityJoin:
    """Build sealed-battery integrity join and block mutation/leak attempts."""

    root = Path(repo_root).resolve()
    partition = _read_json(root / POLICY_DESIGN_CASE_DIR / "layer2_corpus_partition.json")
    s14 = _read_json(
        root / POLICY_DESIGN_CASE_DIR / "layer2_s14_universality_assurance_manifest.json"
    )
    g7_manifest = _read_optional_json(
        root / POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_battery_input_manifest.json"
    )
    sealed = _mapping(partition.get("sealed_universality_battery"))
    partition_hash = _text(sealed.get("freeze_hash"))
    s14_hash = _text(s14.get("sealed_battery_freeze_hash"))
    attempt = dict(rebasing_attempt or {})
    issues: list[str] = []
    hidden_status = _text(g7_manifest.get("hidden_case_access_status")) or "not_observed"
    if partition_hash != s14_hash:
        issues.append("layer3_g8_rebasing_without_freeze_hash")
    if hidden_status not in {"not_accessed_by_g7", "not_observed"}:
        issues.append("layer3_g8_rebasing_leaks_gold_or_hidden_payload")
    if attempt:
        if _text(attempt.get("pre_rebase_freeze_hash")) != _text(
            attempt.get("post_rebase_freeze_hash")
        ):
            issues.append("layer3_g8_rebasing_mutates_sealed_battery")
        if _text(attempt.get("floor_change")) == "lowered":
            issues.append("layer3_g8_rebasing_lowers_s14_floor")
        hidden_payload_ref = _text(attempt.get("hidden_payload_ref"))
        if "hidden" in hidden_payload_ref or "gold" in hidden_payload_ref:
            hidden_status = "blocked"
            issues.append("layer3_g8_rebasing_leaks_gold_or_hidden_payload")
    if _text(g7_manifest.get("sealed_battery_mutation_status")) not in {
        "",
        "not_mutated",
    }:
        issues.append("layer3_g8_rebasing_mutates_sealed_battery")
    return Layer3G8SealedBatteryIntegrityJoin(
        status="blocked" if issues else "pass",
        partition_freeze_hash=partition_hash,
        s14_manifest_freeze_hash=s14_hash,
        g7_mutation_status=(
            _text(g7_manifest.get("sealed_battery_mutation_status")) or "not_observed"
        ),
        hidden_payload_access_status=hidden_status,
        issue_codes=_dedupe(issues),
    )


class Layer3G8OpenQuestionAnswerRow(_G8Model):
    """Evidence-bound answer to one §8.4 open question."""

    question_id: str
    question: str
    answer_status: Literal[
        "answered_currently_healthy",
        "answered_currently_blocked",
        "provisional_insufficient_data",
    ]
    current_answer: str
    evidence_refs: tuple[str, ...]
    authority_boundary: str = "empirical_governance_reading_only"


class Layer3G8OpenQuestionAnswerLedger(_G8Model):
    """Ledger of current empirical answers to §8.4 open questions."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    ledger_id: str = "layer3-g8://open-question-answer-ledger"
    status: Literal["pass", "blocked"]
    answers: tuple[Layer3G8OpenQuestionAnswerRow, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


def build_g8_open_question_answer_ledger(
    *,
    diagnosis: Layer3G8CrossMetricDiagnosis,
    ceiling_gate: Layer3G8DomainVsSearchCeilingGate,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8OpenQuestionAnswerLedger:
    """Answer §8.4 open questions from current G8 evidence without authority leak."""

    rows = (
        Layer3G8OpenQuestionAnswerRow(
            question_id="8.4-waist-altitude",
            question=(
                "Is the waist vocabulary at the right altitude, or does it need "
                "a first-class dimension it currently encodes only as status?"
            ),
            answer_status=(
                "answered_currently_healthy"
                if diagnosis.semantic_loss_status in {"pass", "clean", "0"}
                else "answered_currently_blocked"
            ),
            current_answer=(
                "No forced waist change is justified by current G8 readings; "
                "semantic-loss watch remains active and any future waist change "
                "requires highest-governance rule replay."
            ),
            evidence_refs=(
                "repo://architecture/policy_design_case/"
                "layer3_health_metric_ledgers.toml#adapter-semantic-loss",
                "repo://architecture/policy_design_case/"
                "layer3_g7_health_metric_delta.toml#semantic_loss_status",
            ),
        ),
        Layer3G8OpenQuestionAnswerRow(
            question_id="8.4-real-grounding-cost",
            question=(
                "Is real grounding achievable at acceptable cost in the target "
                "domains, or is the honest equilibrium mostly abstention?"
            ),
            answer_status="provisional_insufficient_data",
            current_answer=(
                "Current G5/G7 readings prove engineering readiness and honest "
                "blockers, not a domain ceiling: G5 remains an unchanged blocker "
                "and G7 has zero grounded regional breadth."
            ),
            evidence_refs=diagnosis.current_blocker_refs,
        ),
        Layer3G8OpenQuestionAnswerRow(
            question_id="8.4-demand-pull-strength",
            question="Is demand-pull strong enough to overcome abstention inertia?",
            answer_status="provisional_insufficient_data",
            current_answer=(
                "G6 demand reaches the G5 bridge, but grounded result rate is "
                "still zero because current G5/G7 blockers remain. This is not "
                "an honesty success claim."
            ),
            evidence_refs=(
                "repo://architecture/policy_design_case/"
                "layer3_g6_demand_pull_vs_abstention_delta.json",
                "repo://architecture/policy_design_case/layer3_g6_readiness_manifest.json",
            ),
        ),
        Layer3G8OpenQuestionAnswerRow(
            question_id="8.4-search-recall-freshness",
            question=(
                "Does capability search have enough recall and freshness to "
                "distinguish honest abstention from a missed grounding path?"
            ),
            answer_status=(
                "answered_currently_healthy"
                if ceiling_gate.status != "search_ceiling_repair_required"
                else "answered_currently_blocked"
            ),
            current_answer=(
                "Current search-recall/freshness signals do not identify a "
                "search ceiling; future recall miss or stale index readings "
                "block domain-ceiling claims."
            ),
            evidence_refs=(
                "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
                "repo://architecture/policy_design_case/layer3_g2_search_recall_freshness.json",
                "repo://architecture/policy_design_case/layer3_g3_search_recall_freshness.json",
                "repo://architecture/policy_design_case/layer3_gl_search_recall_freshness.json",
                "repo://architecture/policy_design_case/layer3_g7_search_recall_freshness_join.json",
            ),
        ),
        Layer3G8OpenQuestionAnswerRow(
            question_id="8.4-agent-orchestration-authority-leak",
            question=(
                "Does the bounded agent leak authority through orchestration "
                "choices in ways the current search ledger does not capture?"
            ),
            answer_status="answered_currently_healthy",
            current_answer=(
                "Current G6 conformance and public projection checks pass; G8 "
                "preserves G6 candidate and orchestration outputs as audit "
                "signals only."
            ),
            evidence_refs=(
                "repo://architecture/policy_design_case/layer3_g6_conformance_report.json",
                "repo://architecture/policy_design_case/"
                "layer3_g6_orchestration_choice_audit.json",
                "repo://architecture/policy_design_case/layer3_g6_search_ledger.json",
            ),
        ),
    )
    missing = [row.question_id for row in rows if not row.evidence_refs]
    return Layer3G8OpenQuestionAnswerLedger(
        status="blocked" if missing else "pass",
        answers=rows,
        issue_codes=("layer3_g8_open_question_answer_missing",) if missing else (),
    )


class Layer3G8MetricGovernanceAuditSurface(_G8Model):
    """EXPERT/MACHINE audit surface for G8 metric governance readings."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    surface_id: str = G8_SURFACE_ID
    status: Literal["pass", "blocked"]
    surface_audiences: tuple[str, ...] = ("EXPERT", "MACHINE")
    metric_registry_ref: str
    normalized_metric_signals_ref: str
    metric_trend_report_status: str
    domain_vs_search_ceiling_status: str
    d44_reannotation_coverage_status: str
    d44_rebasing_trigger_status: str
    d44_rebasing_receipt_status: str
    sealed_battery_integrity_status: str
    open_question_answer_status: str
    warning_lifecycle_status: str
    metric_gaming_firewall_status: str
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8CloseoutSignalConsumerGate(_G8Model):
    """Gate allowing closeout visibility without closeout authority."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    gate_id: str = "layer3-g8://closeout-signal-consumer-gate"
    status: Literal["pass", "blocked"]
    closeout_consumption_status: Literal[
        "readiness_visible_no_authority",
        "blocked_authority_leak",
    ]
    consumed_signal_refs: tuple[str, ...]
    denied_uses: tuple[str, ...] = G8_MAY_NOT_USE_FOR
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = ("layer3_g8_metric_governance_audit",)
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8PublicExportProjectionRefs(_G8Model):
    """Reference-only public projection refs for G8 audit surfaces."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    projection_ref_id: str = "layer3-g8://public-export-projection-refs"
    public_projection_status: Literal["out_of_scope_reference_only", "blocked"]
    source_surface: str = G8_SURFACE_ID
    denied_uses: tuple[str, ...] = G8_MAY_NOT_USE_FOR
    issue_codes: tuple[str, ...] = ()


class Layer3G8ConformanceReport(_G8Model):
    """Conformance report proving required G8 negative probes fire."""

    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    report_id: str = "layer3-g8://conformance-report"
    status: Literal["pass", "blocked"]
    negative_results: tuple[dict[str, Any], ...]
    missing_negative_ids: tuple[str, ...]
    failing_negative_ids: tuple[str, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = ("layer3_g8_metric_governance_audit",)
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8Bundle(_G8Model):
    """In-memory bundle connecting G8 producers, surfaces, and conformance."""

    registry: Layer3G8HealthMetricRegistry
    source_snapshot: Layer3G8MetricSourceSnapshot
    normalized_signals: Layer3G8NormalizedMetricSignals
    metric_trend_report: Layer3G8MetricTrendReport
    cross_metric_diagnosis: Layer3G8CrossMetricDiagnosis
    ceiling_gate: Layer3G8DomainVsSearchCeilingGate
    metric_gaming_firewall: Layer3G8MetricGamingFirewall
    warning_lifecycle_ledger: Layer3G8WarningLifecycleLedger
    d44_rebasing_rule: Layer3G8D44CorpusRebasingRule
    d44_reannotation_coverage_matrix: Layer3G8D44ReannotationCoverageMatrix
    d44_rebasing_trigger_ledger: Layer3G8D44RebasingTriggerLedger
    d44_rebasing_candidate_set: Layer3G8D44RebasingCandidateSet
    d44_rebasing_receipt: Layer3G8D44RebasingReceipt
    sealed_battery_integrity_join: Layer3G8SealedBatteryIntegrityJoin
    open_question_answer_ledger: Layer3G8OpenQuestionAnswerLedger
    audit_surface: Layer3G8MetricGovernanceAuditSurface
    closeout_signal_consumer_gate: Layer3G8CloseoutSignalConsumerGate
    public_export_projection_refs: Layer3G8PublicExportProjectionRefs
    replay_manifest: dict[str, Any]
    conformance_report: Layer3G8ConformanceReport
    health_metric_governance_delta: dict[str, Any]
    route_contract_registry: dict[str, Any]
    registry_ratchet_delta: dict[str, Any]


def build_layer3_g8_bundle(repo_root: str | Path = DEFAULT_REPO_ROOT) -> Layer3G8Bundle:
    """Build the current G8 bundle from committed G0-G7/S14 artifacts."""

    registry = build_g8_health_metric_registry()
    source_snapshot = build_g8_metric_source_snapshot(repo_root)
    signals = build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=source_snapshot,
        repo_root=repo_root,
    )
    trend_report = build_g8_metric_trend_report(registry=registry, signals=signals)
    diagnosis = build_g8_cross_metric_diagnosis(signals=signals, repo_root=repo_root)
    ceiling_gate = build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)
    metric_gaming = build_g8_metric_gaming_firewall(metric_changes=[])
    warnings = build_g8_default_warning_lifecycle_ledger(diagnosis=diagnosis)
    rebasing_rule = build_g8_d44_corpus_rebasing_rule(repo_root=repo_root)
    coverage_matrix = build_g8_d44_reannotation_coverage_matrix(
        rule=rebasing_rule,
        repo_root=repo_root,
    )
    trigger_ledger = build_g8_d44_rebasing_trigger_ledger(repo_root=repo_root)
    candidate_set = build_g8_d44_rebasing_candidate_set(repo_root=repo_root)
    receipt = build_g8_d44_rebasing_receipt(
        rule=rebasing_rule,
        candidate_set=candidate_set,
        repo_root=repo_root,
    )
    sealed_join = build_g8_sealed_battery_integrity_join(repo_root=repo_root)
    open_questions = build_g8_open_question_answer_ledger(
        diagnosis=diagnosis,
        ceiling_gate=ceiling_gate,
        repo_root=repo_root,
    )
    audit_surface = build_g8_metric_governance_audit_surface(
        registry=registry,
        signals=signals,
        trend_report=trend_report,
        ceiling_gate=ceiling_gate,
        metric_gaming_firewall=metric_gaming,
        warning_lifecycle_ledger=warnings,
        d44_reannotation_coverage_matrix=coverage_matrix,
        d44_rebasing_trigger_ledger=trigger_ledger,
        rebasing_receipt=receipt,
        sealed_battery_integrity_join=sealed_join,
        open_question_ledger=open_questions,
    )
    closeout_gate = build_g8_closeout_signal_consumer_gate(
        audit_surface=audit_surface
    )
    public_refs = build_g8_public_export_projection_refs(
        audit_surface=audit_surface
    )
    replay_manifest = build_g8_replay_manifest(audit_surface=audit_surface)
    conformance = build_g8_conformance_report(repo_root=repo_root)
    return Layer3G8Bundle(
        registry=registry,
        source_snapshot=source_snapshot,
        normalized_signals=signals,
        metric_trend_report=trend_report,
        cross_metric_diagnosis=diagnosis,
        ceiling_gate=ceiling_gate,
        metric_gaming_firewall=metric_gaming,
        warning_lifecycle_ledger=warnings,
        d44_rebasing_rule=rebasing_rule,
        d44_reannotation_coverage_matrix=coverage_matrix,
        d44_rebasing_trigger_ledger=trigger_ledger,
        d44_rebasing_candidate_set=candidate_set,
        d44_rebasing_receipt=receipt,
        sealed_battery_integrity_join=sealed_join,
        open_question_answer_ledger=open_questions,
        audit_surface=audit_surface,
        closeout_signal_consumer_gate=closeout_gate,
        public_export_projection_refs=public_refs,
        replay_manifest=replay_manifest,
        conformance_report=conformance,
        health_metric_governance_delta=_g8_health_metric_governance_delta(
            registry=registry,
            trend_report=trend_report,
            ceiling_gate=ceiling_gate,
        ),
        route_contract_registry=_g8_route_contract_registry(audit_surface),
        registry_ratchet_delta=_g8_registry_ratchet_delta(conformance),
    )


def build_g8_metric_governance_audit_surface(
    *,
    registry: Layer3G8HealthMetricRegistry,
    signals: Layer3G8NormalizedMetricSignals,
    trend_report: Layer3G8MetricTrendReport,
    ceiling_gate: Layer3G8DomainVsSearchCeilingGate,
    metric_gaming_firewall: Layer3G8MetricGamingFirewall,
    warning_lifecycle_ledger: Layer3G8WarningLifecycleLedger,
    d44_reannotation_coverage_matrix: Layer3G8D44ReannotationCoverageMatrix,
    d44_rebasing_trigger_ledger: Layer3G8D44RebasingTriggerLedger,
    rebasing_receipt: Layer3G8D44RebasingReceipt,
    sealed_battery_integrity_join: Layer3G8SealedBatteryIntegrityJoin,
    open_question_ledger: Layer3G8OpenQuestionAnswerLedger,
) -> Layer3G8MetricGovernanceAuditSurface:
    """Build the reader-facing G8 audit surface."""

    issues = _dedupe(
        (
            *registry.issue_codes,
            *signals.issue_codes,
            *trend_report.issue_codes,
            *metric_gaming_firewall.issue_codes,
            *warning_lifecycle_ledger.issue_codes,
            *d44_reannotation_coverage_matrix.issue_codes,
            *d44_rebasing_trigger_ledger.issue_codes,
            *rebasing_receipt.issue_codes,
            *sealed_battery_integrity_join.issue_codes,
            *open_question_ledger.issue_codes,
        )
    )
    blocking = set(issues).intersection(
        {
            "layer3_g8_metric_source_missing",
            "layer3_g8_metric_alias_unresolved",
            "layer3_g8_metric_trend_report_missing",
            "layer3_g8_metric_improved_by_threshold_lowering",
            "layer3_g8_d44_reannotation_coverage_missing",
            "layer3_g8_d44_rebasing_trigger_missing",
            "layer3_g8_rebasing_mutates_sealed_battery",
            "layer3_g8_rebasing_leaks_gold_or_hidden_payload",
            "layer3_g8_rebasing_lowers_s14_floor",
            "layer3_g8_rebasing_without_freeze_hash",
        }
    )
    return Layer3G8MetricGovernanceAuditSurface(
        status="blocked" if blocking else "pass",
        metric_registry_ref=(
            "repo://architecture/policy_design_case/"
            "layer3_g8_health_metric_registry.json"
        ),
        normalized_metric_signals_ref=(
            "repo://architecture/policy_design_case/"
            "layer3_g8_normalized_metric_signals.json"
        ),
        metric_trend_report_status=trend_report.status,
        domain_vs_search_ceiling_status=ceiling_gate.status,
        d44_reannotation_coverage_status=d44_reannotation_coverage_matrix.status,
        d44_rebasing_trigger_status=d44_rebasing_trigger_ledger.status,
        d44_rebasing_receipt_status=rebasing_receipt.status,
        sealed_battery_integrity_status=sealed_battery_integrity_join.status,
        open_question_answer_status=open_question_ledger.status,
        warning_lifecycle_status=warning_lifecycle_ledger.status,
        metric_gaming_firewall_status=metric_gaming_firewall.status,
        issue_codes=issues,
    )


def build_g8_closeout_signal_consumer_gate(
    *,
    audit_surface: Layer3G8MetricGovernanceAuditSurface,
    authority_role: str = "readiness_visibility_only",
) -> Layer3G8CloseoutSignalConsumerGate:
    """Expose G8 signals to closeout only as readiness visibility."""

    issues: list[str] = []
    if authority_role != "readiness_visibility_only":
        issues.append("layer3_g8_metric_used_as_closeout_authority")
    if "closeout_authority" not in audit_surface.may_not_use_for:
        issues.append("layer3_g8_metric_used_as_closeout_authority")
    return Layer3G8CloseoutSignalConsumerGate(
        status="blocked" if issues else "pass",
        closeout_consumption_status=(
            "blocked_authority_leak" if issues else "readiness_visible_no_authority"
        ),
        consumed_signal_refs=(
            "repo://architecture/policy_design_case/"
            "layer3_g8_metric_governance_audit_surface.json",
            "repo://architecture/policy_design_case/"
            "layer3_g8_domain_vs_search_ceiling_gate.json",
            "repo://architecture/policy_design_case/"
            "layer3_g8_warning_lifecycle_ledger.json",
        ),
        issue_codes=_dedupe(issues),
    )


def build_g8_public_export_projection_refs(
    *,
    audit_surface: Layer3G8MetricGovernanceAuditSurface,
    authority_role: str = "projection_only",
) -> Layer3G8PublicExportProjectionRefs:
    """Declare G8 public projection refs as reference-only."""

    issues: list[str] = []
    if authority_role != "projection_only":
        issues.append("layer3_g8_public_projection_authority_leak")
    return Layer3G8PublicExportProjectionRefs(
        public_projection_status="blocked" if issues else "out_of_scope_reference_only",
        issue_codes=_dedupe(issues),
    )


def build_g8_replay_manifest(
    *,
    audit_surface: Layer3G8MetricGovernanceAuditSurface,
) -> dict[str, Any]:
    """Build a replay manifest pinning G8 source refs and rule authority."""

    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "manifest_id": "layer3-g8-health-metric-governance-replay",
        "status": "pass" if audit_surface.status in {"pass", "blocked"} else "blocked",
        "source_refs": [
            "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml",
            "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
            "repo://architecture/policy_design_case/layer3_g2_search_recall_freshness.json",
            "repo://architecture/policy_design_case/layer3_g3_search_recall_freshness.json",
            "repo://architecture/policy_design_case/layer3_gl_search_recall_freshness.json",
            "repo://architecture/policy_design_case/layer3_g4_governance_throughput_delta.json",
            "repo://architecture/policy_design_case/layer3_g5_readiness_manifest.json",
            "repo://architecture/policy_design_case/layer3_g5_dependency_health_metric_snapshot.json",
            "repo://architecture/policy_design_case/layer3_g6_demand_pull_vs_abstention_delta.json",
            "repo://architecture/policy_design_case/layer3_g6_readiness_manifest.json",
            "repo://architecture/policy_design_case/layer3_g7_search_recall_freshness_join.json",
            "repo://architecture/policy_design_case/layer3_g7_readiness_manifest.json",
            "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json",
        ],
        "audit_surface_ref": (
            "repo://architecture/policy_design_case/"
            "layer3_g8_metric_governance_audit_surface.json"
        ),
        "issue_codes": [],
        "authoritative_for": list(G8_AUTHORITATIVE_FOR),
        "may_not_use_for": list(G8_MAY_NOT_USE_FOR),
    }


def build_g8_conformance_report(
    *,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8ConformanceReport:
    """Run G8 negative probes and report missing/failing issue codes."""

    negative_results: list[dict[str, Any]] = []
    for negative_id, expected in G8_CONFORMANCE_NEGATIVE_EXPECTED_ISSUE_CODES.items():
        observed = _observed_g8_negative_issue_codes(negative_id)
        missing = sorted(set(expected) - set(observed))
        negative_results.append(
            {
                "negative_id": negative_id,
                "expected_issue_codes": list(expected),
                "observed_issue_codes": list(observed),
                "missing_issue_codes": missing,
                "status": "fail" if missing else "pass",
                "probe_ref": f"layer3-g8://conformance/negative/{negative_id}",
            }
        )
    observed_ids = {str(result["negative_id"]) for result in negative_results}
    missing_negative_ids = tuple(
        sorted(set(G8_CONFORMANCE_NEGATIVE_EXPECTED_ISSUE_CODES) - observed_ids)
    )
    failing = tuple(
        str(result["negative_id"])
        for result in negative_results
        if result["status"] != "pass"
    )
    issue_codes = tuple(
        sorted(
            {
                code
                for result in negative_results
                for code in result["missing_issue_codes"]
            }
        )
    )
    return Layer3G8ConformanceReport(
        status="blocked" if missing_negative_ids or failing else "pass",
        negative_results=tuple(negative_results),
        missing_negative_ids=missing_negative_ids,
        failing_negative_ids=failing,
        issue_codes=(
            issue_codes
            or (("layer3_g8_conformance_negative_missing",) if missing_negative_ids else ())
        ),
    )


def _observed_g8_negative_issue_codes(negative_id: str) -> tuple[str, ...]:
    if negative_id == "metric_improved_by_threshold_lowering":
        return build_g8_metric_gaming_firewall(
            metric_changes=[
                {
                    "metric_id": "demand-pull-vs-abstention",
                    "claimed_improvement": True,
                    "change_class": "threshold_lowered",
                    "source_ref": "layer3-g8://negative/threshold-lowering",
                }
            ]
        ).issue_codes
    if negative_id == "useful_design_rate_optimization":
        return build_g8_metric_gaming_firewall(
            metric_changes=[
                {
                    "metric_id": "envelope-expansion-rate",
                    "claimed_improvement": True,
                    "change_class": "metric_target_changed",
                    "target_metric": "useful_design_rate",
                    "source_ref": "layer3-g8://negative/useful-design-rate",
                }
            ]
        ).issue_codes
    if negative_id == "search_recall_miss_as_domain_ceiling":
        diagnosis = build_g8_cross_metric_diagnosis(
            signals=_negative_signal_set(
                search_status="search_ceiling",
                governance_status="pass",
                demand_status="pass",
                semantic_status="pass",
                expansion_status="flat",
            )
        )
        return domain_ceiling_claim_issue_codes(
            diagnosis=diagnosis,
            claimed_domain_ceiling=True,
        )
    if negative_id == "flat_expansion_with_current_blocker_as_domain_ceiling":
        diagnosis = Layer3G8CrossMetricDiagnosis(
            status="pass",
            envelope_expansion_status="flat",
            semantic_loss_status="pass",
            governance_throughput_status="pass",
            demand_pull_status="pass",
            search_recall_freshness_status="pass",
            effective_independence_status="sufficient",
            effective_independent_evidence_count=2,
            effective_independence_source_ref=(
                "repo://architecture/policy_design_case/"
                "layer3_g5_effective_evidence_independence.json"
                "#independence_map_payload.effective_mass_report"
            ),
            current_blocker_refs=(
                "repo://architecture/policy_design_case/"
                "layer3_g7_readiness_manifest.json#g7_region_grounded_case_count",
            ),
            diagnoses=("current_grounding_blocker",),
        )
        return domain_ceiling_claim_issue_codes(
            diagnosis=diagnosis,
            claimed_domain_ceiling=True,
        )
    if negative_id == "governance_stall_as_domain_ceiling":
        diagnosis = build_g8_cross_metric_diagnosis(
            signals=_negative_signal_set(
                search_status="pass",
                governance_status="stalled",
                demand_status="pass",
                semantic_status="pass",
                expansion_status="flat",
            )
        )
        return domain_ceiling_claim_issue_codes(
            diagnosis=diagnosis,
            claimed_domain_ceiling=True,
        )
    if negative_id == "abstention_inertia_as_honesty":
        diagnosis = build_g8_cross_metric_diagnosis(
            signals=_negative_signal_set(
                search_status="pass",
                governance_status="pass",
                demand_status="abstention_inertia",
                semantic_status="pass",
                expansion_status="flat",
            )
        )
        return domain_ceiling_claim_issue_codes(
            diagnosis=diagnosis,
            claimed_domain_ceiling=True,
        )
    if negative_id == "semantic_loss_hidden_by_metric_rollup":
        diagnosis = build_g8_cross_metric_diagnosis(
            signals=_negative_signal_set(
                search_status="pass",
                governance_status="pass",
                demand_status="pass",
                semantic_status="lossy",
                expansion_status="flat",
            )
        )
        return diagnosis.issue_codes
    if negative_id in {
        "rebasing_mutates_sealed_battery",
        "rebasing_leaks_gold_or_hidden_payload",
        "rebasing_lowers_s14_floor",
    }:
        return build_g8_sealed_battery_integrity_join(
            rebasing_attempt={
                "pre_rebase_freeze_hash": "sha256:" + "1" * 64,
                "post_rebase_freeze_hash": "sha256:" + "2" * 64,
                "floor_change": "lowered",
                "hidden_payload_ref": "sealed_gold_label_ref://leak",
            }
        ).issue_codes
    if negative_id == "closeout_signal_used_as_authority":
        return build_g8_closeout_signal_consumer_gate(
            audit_surface=_test_audit_surface(),
            authority_role="closeout_authority",
        ).issue_codes
    if negative_id == "public_projection_authority_leak":
        return build_g8_public_export_projection_refs(
            audit_surface=_test_audit_surface(),
            authority_role="claim_authority",
        ).issue_codes
    return ()


def _test_audit_surface() -> Layer3G8MetricGovernanceAuditSurface:
    return Layer3G8MetricGovernanceAuditSurface(
        status="pass",
        metric_registry_ref="repo://test/registry",
        normalized_metric_signals_ref="repo://test/signals",
        metric_trend_report_status="pass",
        domain_vs_search_ceiling_status="not_claimed_current_grounding_blocker",
        d44_reannotation_coverage_status="pass",
        d44_rebasing_trigger_status="pass_no_rebase_due",
        d44_rebasing_receipt_status="pass_no_rebase_required",
        sealed_battery_integrity_status="pass",
        open_question_answer_status="pass",
        warning_lifecycle_status="pass",
        metric_gaming_firewall_status="pass",
    )


def _negative_signal_set(
    *,
    search_status: str,
    governance_status: str,
    demand_status: str,
    semantic_status: str,
    expansion_status: str,
) -> Layer3G8NormalizedMetricSignals:
    return Layer3G8NormalizedMetricSignals(
        status="pass",
        signals=(
            Layer3G8NormalizedMetricSignal(
                signal_id="negative://envelope",
                slice_id="G8",
                metric_id="envelope-expansion-rate",
                raw_key="envelope-expansion-rate",
                raw_value=expansion_status,
                status=expansion_status,
                raw_source_ref="repo://negative#envelope",
                source_digest="sha256:" + "1" * 64,
                freshness_status="fresh_committed",
                authority_boundary_status="pass",
                observed_at="2026-06-10T00:00:00Z",
            ),
            Layer3G8NormalizedMetricSignal(
                signal_id="negative://semantic-loss",
                slice_id="G8",
                metric_id="adapter-semantic-loss",
                raw_key="adapter-semantic-loss",
                raw_value=semantic_status,
                status=semantic_status,
                raw_source_ref="repo://negative#semantic",
                source_digest="sha256:" + "1" * 64,
                freshness_status="fresh_committed",
                authority_boundary_status="pass",
                observed_at="2026-06-10T00:00:00Z",
            ),
            Layer3G8NormalizedMetricSignal(
                signal_id="negative://governance",
                slice_id="G8",
                metric_id="governance-throughput",
                raw_key="governance-throughput",
                raw_value=governance_status,
                status=governance_status,
                raw_source_ref="repo://negative#governance",
                source_digest="sha256:" + "1" * 64,
                freshness_status="fresh_committed",
                authority_boundary_status="pass",
                observed_at="2026-06-10T00:00:00Z",
            ),
            Layer3G8NormalizedMetricSignal(
                signal_id="negative://demand",
                slice_id="G8",
                metric_id="demand-pull-vs-abstention",
                raw_key="demand-pull-vs-abstention",
                raw_value=demand_status,
                status=demand_status,
                raw_source_ref="repo://negative#demand",
                source_digest="sha256:" + "1" * 64,
                freshness_status="fresh_committed",
                authority_boundary_status="pass",
                observed_at="2026-06-10T00:00:00Z",
            ),
            Layer3G8NormalizedMetricSignal(
                signal_id="negative://search",
                slice_id="G8",
                metric_id="search-recall@known-seeds+index-staleness",
                raw_key="search-recall@known-seeds+index-staleness",
                raw_value=search_status,
                status=search_status,
                raw_source_ref="repo://negative#search",
                source_digest="sha256:" + "1" * 64,
                freshness_status="fresh_committed",
                authority_boundary_status="pass",
                observed_at="2026-06-10T00:00:00Z",
            ),
        ),
    )


def _g8_health_metric_governance_delta(
    *,
    registry: Layer3G8HealthMetricRegistry,
    trend_report: Layer3G8MetricTrendReport,
    ceiling_gate: Layer3G8DomainVsSearchCeilingGate,
) -> dict[str, Any]:
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "health_metric_governance_delta": {
            "metric_ids": list(G8_CANONICAL_METRIC_IDS),
            "metric_governance_status": registry.status,
            "metric_trend_report_status": trend_report.status,
            "metric_trend_refs": [
                "repo://architecture/policy_design_case/"
                "layer3_g8_metric_trend_report.json"
            ],
            "domain_vs_search_ceiling_status": ceiling_gate.status,
            "authority_boundary": "governed_signal_never_authority",
        },
    }


def _g8_route_contract_registry(
    audit_surface: Layer3G8MetricGovernanceAuditSurface,
) -> dict[str, Any]:
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "route_contract_registry_kind": (
            "generated_metric_governance_route_contract_registry"
        ),
        "surface_id": audit_surface.surface_id,
        "producer": "src/polisyos/runtime/quality/layer3_health_metric_governance.py",
        "validator": (
            "tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py"
        ),
        "metric_trend_report": (
            "architecture/policy_design_case/layer3_g8_metric_trend_report.json"
        ),
        "closeout_consumer_gate": (
            "architecture/policy_design_case/"
            "layer3_g8_closeout_signal_consumer_gate.json"
        ),
        "may_not_use_for": list(G8_MAY_NOT_USE_FOR),
    }


def _g8_registry_ratchet_delta(
    conformance_report: Layer3G8ConformanceReport,
) -> dict[str, Any]:
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "ratchet_id": "layer3_g8_registry_ratchet_delta",
        "status": "pass" if conformance_report.status == "pass" else "blocked",
        "negative_count": len(conformance_report.negative_results),
        "missing_negative_ids": list(conformance_report.missing_negative_ids),
        "failing_negative_ids": list(conformance_report.failing_negative_ids),
    }


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _issue(issue_code: str, ref: str, message: str) -> Layer3G8Issue:
    return Layer3G8Issue(issue_code=issue_code, ref=ref, message=message)


def _text(value: object) -> str:
    return str(value) if value is not None else ""


def _text_list(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return tuple(str(item) for item in value if str(item))
    return ()


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return dict(payload) if isinstance(payload, Mapping) else {}


def _read_optional_json(path: Path) -> dict[str, Any]:
    try:
        return _read_json(path)
    except (OSError, json.JSONDecodeError):
        return {}


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    return dict(payload) if isinstance(payload, Mapping) else {}


def _digest_payload(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _metric_items_from_payload(
    slice_id: str,
    payload: Mapping[str, Any],
) -> tuple[tuple[str, Any], ...]:
    items: list[tuple[str, Any]] = []
    health_delta = _mapping(payload.get("health_metric_delta"))
    for key, value in _mapping(health_delta.get("readings")).items():
        items.append((str(key), value))
    for key, value in _mapping(health_delta.get("metric_statuses")).items():
        items.append((str(key), value))
    for key, value in _mapping(payload.get("metrics")).items():
        items.append((str(key), value))

    search_recall = _mapping(payload.get("search_recall_freshness"))
    for key in (
        "status",
        "freshness_status",
        "certificate_resolution_seed_status",
        "ir_catalog_seed_status",
        "l2_skg_seed_status",
        "known_seed_count",
        "recalled_seed_count",
        "missed_seed_count",
        "search_ceiling_repair_required",
        "domain_ceiling_allowed",
    ):
        if key in search_recall:
            items.append((f"search_recall.{key}", search_recall[key]))
    for key in (
        "search_recall_status",
        "index_freshness_status",
        "known_seed_status",
        "g1_search_recall_status",
        "g1_index_freshness_status",
    ):
        if key in search_recall:
            items.append((key, search_recall[key]))
        if key in payload:
            items.append((key, payload[key]))

    if slice_id == "G7" and "g1_search_recall_status" in payload:
        items.append(
            (
                "search-recall@known-seeds+index-staleness(region)",
                payload["g1_search_recall_status"],
            )
        )

    readings = _mapping(payload.get("readings"))
    for key in (
        "abstention_or_blocker_rate",
        "demand_reached_g5_rate",
        "g5_grounded_abstention_rate",
        "grounded_result_rate",
        "out_of_envelope_abstention_rate",
    ):
        if key in readings:
            items.append((key, readings[key]))
        if key in payload:
            items.append((key, payload[key]))

    manifest = _manifest_fields(payload)
    for key in (
        "g2_search_engineering_quality_status",
        "g3_search_recall_freshness_status",
        "gl_search_recall_freshness_status",
        "g4_governance_throughput_status",
        "g5_envelope_expansion_status",
        "g5_search_recall_status",
        "g5_index_freshness_status",
        "g5_governance_throughput_status",
        "g6_demand_pull_vs_abstention_status",
        "g7_region_envelope_expansion_rate",
        "g7_region_semantic_loss_status",
        "g7_governance_throughput_status",
        "g7_region_value_closure_status",
        "g7_region_grounded_case_count",
        "g7_s14_grounded_breadth_feed_status",
    ):
        if key in manifest:
            items.append((key, manifest[key]))

    if slice_id == "G4":
        for key in ("status", "stalled_count", "human_review_routed_count"):
            if key in payload:
                items.append(("governance-throughput", payload[key]))
        for key, value in readings.items():
            if str(key).startswith("g4-"):
                items.append(("governance-throughput", value))
    return tuple(items)


def _manifest_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = _mapping(payload.get("summary"))
    if summary:
        return {**dict(payload), **summary}
    counts = _mapping(payload.get("counts"))
    if counts:
        return {**dict(payload), **counts}
    return dict(payload)


def _status_from_metric_value(raw_key: str, value: object) -> str:
    if isinstance(value, Mapping):
        for key in ("status", "search_recall_status", "index_freshness_status"):
            if key in value:
                return _text(value.get(key))
        return "present"
    if isinstance(value, bool):
        if raw_key in {"search_recall.search_ceiling_repair_required"} and value:
            return "search_ceiling"
        if raw_key in {"search_recall.domain_ceiling_allowed"} and not value:
            return "search_ceiling_not_claimed"
        return "pass" if value else "fail"
    if isinstance(value, int | float):
        numeric = float(value)
        if raw_key in {
            "abstention_or_blocker_rate",
            "out_of_envelope_abstention_rate",
            "g5_grounded_abstention_rate",
        } and numeric >= 0.8:
            return "abstention_inertia"
        if raw_key == "grounded_result_rate" and numeric == 0.0:
            return "no_grounded_response"
        if raw_key in {"stalled_count", "g4-promotion-stalled-count"} and numeric > 0:
            return "stalled"
        if raw_key == "g7_region_grounded_case_count" and numeric == 0.0:
            return "no_grounded_response"
        if raw_key == "search_recall.missed_seed_count" and numeric > 0:
            return "search_ceiling"
        return "numeric_reading"
    return _text(value) or "present"


def _signal_issue_codes(
    *,
    metric_id: str,
    raw_key: str,
    status: str,
    raw_value: object,
) -> tuple[str, ...]:
    issues: list[str] = []
    lowered = status.casefold()
    if metric_id == "search-recall@known-seeds+index-staleness" and lowered in {
        "stale",
        "fail",
        "miss",
        "search_ceiling",
        "not_measured",
        "self_attested",
        "unmeasured",
        "missing",
    }:
        issues.append("layer3_g8_search_recall_miss_reported_as_domain_ceiling")
    if metric_id == "adapter-semantic-loss" and lowered in {"lossy", "blocked", "fail"}:
        issues.append("layer3_g8_semantic_loss_hidden_by_metric_rollup")
    if metric_id == "demand-pull-vs-abstention" and lowered in {
        "abstention_inertia",
        "no_grounded_response",
        "blocked_no_real_grounded_breadth",
        "blocked_by_current_g5_unchanged_blocker",
    }:
        issues.append("layer3_g8_demand_numeric_inertia_hidden_as_pass")
    if raw_key in {"threshold_lowered", "floor_relaxed"} or lowered == "threshold_lowered":
        issues.append("layer3_g8_metric_improved_by_threshold_lowering")
    return tuple(issues)


def _blocking_signal_issues(issue_codes: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        code
        for code in _dedupe(issue_codes)
        if code
        in {
            "layer3_g8_metric_source_missing",
            "layer3_g8_metric_alias_unresolved",
            "layer3_g8_metric_raw_ref_missing",
            "layer3_g8_metric_authority_boundary_missing",
        }
    )


def _latest_metric_status(signals: Layer3G8NormalizedMetricSignals, metric_id: str) -> str:
    matching = [signal for signal in signals.signals if signal.metric_id == metric_id]
    if not matching:
        return "missing"
    semantic_blockers = {
        "abstention_inertia",
        "no_grounded_response",
        "blocked_no_real_grounded_breadth",
        "blocked_by_current_g5_unchanged_blocker",
        "search_ceiling",
        "not_measured",
        "self_attested",
        "unmeasured",
        "missing",
        "stale",
        "miss",
        "stalled",
        "lossy",
        "blocked",
        "fail",
    }
    for signal in matching:
        if signal.status.casefold() in semantic_blockers:
            return signal.status
    rank = {
        "G8": 8.0,
        "G7": 7.0,
        "G6": 6.0,
        "G5": 5.0,
        "G4": 4.0,
        "GL": 3.5,
        "G3": 3.0,
        "G2": 2.0,
        "G1": 1.0,
        "G0": 0.0,
    }
    latest = sorted(matching, key=lambda signal: rank.get(signal.slice_id, -1))[-1]
    return latest.status


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")


def _is_current_committed_source_set(signals: Layer3G8NormalizedMetricSignals) -> bool:
    return bool(signals.signals) and all(
        signal.raw_source_ref.startswith("repo://architecture/policy_design_case/")
        for signal in signals.signals
    )


def _is_search_ceiling(status: str) -> bool:
    return status.casefold() in {
        "search_ceiling",
        "not_measured",
        "self_attested",
        "unmeasured",
        "missing",
        "stale",
        "fail",
        "miss",
        "blocked_search_control_plane_only",
    }


def _is_governance_stall(status: str) -> bool:
    return status.casefold() in {"stalled", "missing", "blocked", "fail"}


def _is_abstention_inertia(status: str) -> bool:
    return status.casefold() in {
        "abstention_inertia",
        "cheap_refusal",
        "blocked_no_demand_response",
        "no_grounded_response",
        "blocked_no_real_grounded_breadth",
        "blocked_by_current_g5_unchanged_blocker",
    }


def _is_semantic_loss(status: str) -> bool:
    return status.casefold() in {"lossy", "blocked", "fail"}
