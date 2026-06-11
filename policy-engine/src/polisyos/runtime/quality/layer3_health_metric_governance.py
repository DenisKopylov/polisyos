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
from typing import Any

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


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    return dict(payload) if isinstance(payload, Mapping) else {}


def _digest_payload(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()
