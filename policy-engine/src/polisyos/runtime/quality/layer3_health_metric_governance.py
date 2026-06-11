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
