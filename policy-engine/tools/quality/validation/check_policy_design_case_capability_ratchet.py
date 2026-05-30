#!/usr/bin/env python3
"""Build and validate the Policy Design Case capability ratchet report."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.capability_ratchet import (  # noqa: E402
    CAPABILITY_RATCHET_SCHEMA_VERSION,
    REALITY_STATES,
    build_capability_reality_report,
)

SCHEMA_VERSION = CAPABILITY_RATCHET_SCHEMA_VERSION
TOOL_NAME = "quality.validation.check-policy-design-case-capability-ratchet"
GENERATED_AT = "2026-05-23T00:00:00Z"
DEFAULT_REPORT_PATH = Path("architecture/policy_design_case/capability_reality_report.json")
WAVE3_CORPUS_COVERAGE_PATH = Path(
    "architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json"
)
WAVE4_I4_MANIFEST_PATH = Path(
    "architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json"
)
REFERENCE_DOC_PATH = Path("docs/reference/policy-design-case-capability-ratchet.md")
REUSE_CLASSIFICATIONS = frozenset(
    {"wire_existing", "extend_existing", "consolidate_existing", "build_new"}
)
TRACEABILITY_ROLLOUT_FIELDS = frozenset(
    {"feature_flag_or_scope", "canary_or_revalidation", "rollback_or_reversal"}
)
WAVE3_COVERAGE_REF_FIELDS = frozenset(
    {
        "authority_bearing_fixture_ref",
        "blocked_or_laundering_fixture_ref",
        "typed_blocker_fixture_ref",
        "producer_report_ref",
        "runtime_consumer_ref",
        "authority_envelope_ref",
    }
)


DEFAULT_WAVE1_CAPABILITY_CLAIMS: tuple[dict[str, Any], ...] = (
    {
        "capability_id": "w1a_capability_ratchet",
        "capability_name": "W1.A Capability Ratchet",
        "reality_state": "implemented",
        "purpose": "diagnostic_only",
        "authority_scope": "release_readiness_signal",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-07-01",
        "hold_reason": "implemented in W1.A",
        "next_wave_target": "Wave 6 revalidation",
        "chain_id": "wave1-quality-foundation",
        "research_refs": ["E0", "C36", "P01", "P02", "P03", "P10", "P13"],
        "no_adr_required": (
            "W1.A implements diagnostic capability maturity reporting from the "
            "Wave 0 source/ADR foundation without adding new policy-domain "
            "decision semantics."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "diagnostic release/readiness report only",
            "canary_or_revalidation": (
                "uv run python tools/quality/validation/"
                "check_policy_design_case_capability_ratchet.py --repo-root ."
            ),
            "rollback_or_reversal": (
                "revert the generated report and ratchet checker changes; downstream "
                "runtime authority does not depend on the diagnostic report"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/capability_ratchet.py",
        "producer_ref": (
            "repo://tools/quality/validation/"
            "check_policy_design_case_capability_ratchet.py"
            "#build_capability_reality_report_payload"
        ),
        "artifact_ref": ("repo://architecture/policy_design_case/capability_reality_report.json"),
        "bridge_ref": (
            "repo://tools/quality/validation/"
            "check_policy_design_case_capability_ratchet.py"
            "#validate_capability_reality_report"
        ),
        "consumer_ref": "repo://docs/reference/policy-design-case-capability-ratchet.md",
        "verification_ref": (
            "repo://tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py"
        ),
        "surface_ref": "repo://docs/reference/policy-design-case-capability-ratchet.md",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_capability_ratchet.py"
            "#test_implemented_claim_with_missing_producer_downgrades_to_contract_only"
        ),
        "mitigation_refs": [
            "repo://docs/reference/policy-design-case-failure-patterns.md",
        ],
        "mitigation_enforced": True,
    },
    {
        "capability_id": "w1b_semantic_fixtures",
        "capability_name": "W1.B Semantic Fixtures",
        "reality_state": "implemented",
        "purpose": "diagnostic_only",
        "authority_scope": "semantic_adequacy_validation",
        "validation_profile": "planning",
        "owner": "team-evaluation",
        "expiry": "2026-07-01",
        "hold_reason": "implemented in W1.B",
        "next_wave_target": "Wave 2 semantic producer integration",
        "chain_id": "wave1-quality-foundation",
        "research_refs": ["E1", "C30", "P10", "P15"],
        "no_adr_required": (
            "W1.B creates semantic false-pass fixtures and does not choose new "
            "structural policy thresholds beyond Wave 0 accepted ADR boundaries."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "repo-quality fixture pack only",
            "canary_or_revalidation": (
                "uv run pytest tests/repo_quality/tools/"
                "test_policy_design_case_semantic_fixtures.py -q"
            ),
            "rollback_or_reversal": (
                "remove the fixture pack and detector registration; no public "
                "authority surface consumes these fixtures directly in Wave 1"
            ),
        },
        "typed_contract_ref": ("repo://src/polisyos/runtime/quality/semantic_fixtures.py"),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/semantic_fixtures.py"
            "#evaluate_semantic_gold_card_fixture"
        ),
        "artifact_ref": ("repo://tests/fixtures/policy_design_case/semantic_false_passes"),
        "bridge_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_design_case_semantic_fixtures.py"
            "#test_w1b_semantic_false_pass_gold_cards_are_frozen"
        ),
        "consumer_ref": (
            "repo://tests/repo_quality/tools/test_policy_design_case_semantic_fixtures.py"
        ),
        "verification_ref": ("repo://tests/unit/runtime/quality/test_semantic_gold_cards.py"),
        "surface_ref": ("repo://tests/fixtures/policy_design_case/semantic_false_passes/README.md"),
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_design_case_semantic_fixtures.py"
            "#test_w1b_semantic_false_pass_gold_cards_are_frozen"
        ),
    },
    {
        "capability_id": "w1c_status_and_deficits",
        "capability_name": "W1.C Status And Deficits",
        "reality_state": "implemented",
        "purpose": "closeout_input",
        "authority_scope": "status_deficit_closeout_composition",
        "validation_profile": "production",
        "owner": "team-quality-closeout",
        "expiry": "2026-07-01",
        "hold_reason": "implemented in W1.C",
        "next_wave_target": "Wave 2 runtime reader integration",
        "chain_id": "wave1-quality-foundation",
        "research_refs": ["E2", "C1", "C31", "P04", "P09"],
        "no_adr_required": (
            "W1.C composes local statuses into shared effects while preserving "
            "local meanings; it does not ratify new domain status semantics."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime-quality status envelope and scorecard bridge",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_status_deficits.py -q"
            ),
            "rollback_or_reversal": (
                "remove the status-envelope bridge from scorecard/approval and "
                "fall back to local producer status behavior"
            ),
        },
        "typed_contract_ref": ("repo://src/polisyos/runtime/quality/status_deficits.py"),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/status_deficits.py#build_status_envelope"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave1_baseline_smoke_corpus.json#status_deficit_crosswalk"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/scorecard.py"
            "#_status_envelope_from_quality_evidence"
        ),
        "consumer_ref": (
            "repo://src/polisyos/runtime/quality/approval.py#_deficit_closeout_reasons"
        ),
        "verification_ref": ("repo://tests/unit/runtime/quality/test_status_deficits.py"),
        "surface_ref": "repo://docs/reference/runtime/quality-scorecard.md",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_status_deficits.py"
            "#test_deficit_crosswalk_keeps_accepted_limitation_review_reissue_and_block_distinct"
        ),
    },
    {
        "capability_id": "w1d_closeout_reader_skeleton",
        "capability_name": "W1.D Closeout Reader Skeleton",
        "reality_state": "implemented",
        "purpose": "closeout_input",
        "authority_scope": "can_i_closeout_reader",
        "validation_profile": "production",
        "owner": "team-quality-closeout",
        "expiry": "2026-07-01",
        "hold_reason": "implemented in W1.D as a fail-closed reader skeleton",
        "next_wave_target": "Wave 2 closeout substrate integration",
        "chain_id": "wave1-closeout-skeleton",
        "research_refs": ["E3", "C3", "P01", "P05", "P10"],
        "no_adr_required": (
            "W1.D adds a fail-closed closeout reader skeleton over existing "
            "compatibility evidence without minting new closeout domain rules."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "check_can_i_closeout --reader-skeleton",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_closeout_reader.py "
                "tests/repo_quality/tools/test_can_i_closeout.py -q"
            ),
            "rollback_or_reversal": (
                "disable --reader-skeleton and keep compatibility-only "
                "check_can_i_closeout behavior"
            ),
        },
        "typed_contract_ref": ("repo://src/polisyos/runtime/quality/closeout_reader.py"),
        "producer_ref": (
            "repo://tools/quality/validation/check_can_i_closeout.py#--reader-skeleton"
        ),
        "artifact_ref": ("repo://architecture/policy_design_case/wave1_closeout_reader_smoke.json"),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/closeout_reader.py"
            "#build_closeout_reader_skeleton_from_bundle_dir"
        ),
        "consumer_ref": "repo://tools/quality/validation/check_can_i_closeout.py",
        "verification_ref": ("repo://tests/unit/runtime/quality/test_closeout_reader.py"),
        "surface_ref": "repo://docs/runbooks/policy-design-case-operator-triage.md",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_closeout_reader.py"
            "#test_projection_readiness_packaging_and_public_export_cannot_satisfy_closeout"
        ),
    },
    {
        "capability_id": "w1e_documentation_paths",
        "capability_name": "W1.E Documentation Paths",
        "reality_state": "implemented",
        "purpose": "public_surface",
        "authority_scope": "operator_audit_evidence_paths",
        "validation_profile": "production",
        "owner": "team-docs-platform",
        "expiry": "2026-07-01",
        "hold_reason": "implemented in W1.E",
        "next_wave_target": "Wave 5 documentation revalidation",
        "chain_id": "wave1-docs-evidence-paths",
        "research_refs": ["E23", "C0", "C27", "P03", "P06", "P13"],
        "no_adr_required": (
            "W1.E locks repository-owned evidence paths and command-evidence "
            "conventions without adding a new architecture decision."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "published docs/reference and MkDocs nav only",
            "canary_or_revalidation": (
                "uv run pytest tests/repo_quality/tools/"
                "test_policy_design_case_documentation_paths.py -q"
            ),
            "rollback_or_reversal": (
                "revert documentation path ledger/nav changes and keep W0 source "
                "ownership as the fallback evidence index"
            ),
        },
        "typed_contract_ref": ("repo://docs/reference/policy-design-case-evidence-paths.md"),
        "producer_ref": (
            "repo://docs/reference/policy-design-case-evidence-paths.md#canonical-path-matrix"
        ),
        "artifact_ref": "repo://docs/reference/policy-design-case-evidence-paths.md",
        "bridge_ref": "repo://docs/runbooks/policy-design-case-operator-triage.md",
        "consumer_ref": "repo://docs/reference/documentation-inventory.md",
        "verification_ref": (
            "repo://tests/repo_quality/tools/test_policy_design_case_documentation_paths.py"
        ),
        "surface_ref": "repo://architecture/tooling/mkdocs/nav/30-reference.yml",
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_design_case_documentation_paths.py"
            "#test_w1e_rejects_local_or_ephemeral_source_paths"
        ),
        "promised_audiences": ["operator", "reviewer"],
    },
)

DEFAULT_WAVE2_CAPABILITY_CLAIMS: tuple[dict[str, Any], ...] = (
    {
        "capability_id": "w2a_concept_spine_handshake",
        "capability_name": "W2.A Concept Spine And Handshake Kernel",
        "reality_state": "implemented",
        "purpose": "closeout_input",
        "authority_scope": "shared_semantic_spine_and_producer_handshake",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-07-01",
        "hold_reason": "implemented in W2.A",
        "next_wave_target": "Wave 3 producer adapter integration",
        "chain_id": "wave2-shared-carriers",
        "research_refs": ["E6", "C28", "C37", "C40", "P02", "P08", "P12"],
        "no_adr_required": (
            "W2.A wires shared semantic runtime carriers and producer handshakes "
            "without minting new policy-domain decision semantics."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime-quality concept spine and handoff records",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_concept_spine.py "
                "tests/unit/runtime/quality/test_wave2_walking_skeleton.py -q"
            ),
            "rollback_or_reversal": (
                "remove Wave 2 producer-spine handoff consumption and keep adapters "
                "on pre-W2 local semantic labels"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/concept_spine.py",
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/concept_spine.py"
            "#build_hybrid_concept_spine_carrier"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/wave2_i2_walking_skeleton/concept_spine.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/evidence_spine_handoff.py"
            "#build_evidence_spine_handoff_ledger"
        ),
        "consumer_ref": "repo://src/polisyos/runtime/quality/claim_registry.py",
        "verification_ref": "repo://tests/unit/runtime/quality/test_concept_spine.py",
        "surface_ref": (
            "repo://architecture/policy_design_case/"
            "wave2_i2_walking_skeleton/producer_handshake_ledger.json"
        ),
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_concept_spine.py"
            "#test_bridge_authority_is_closeout_scoped_not_producer_evidence"
        ),
    },
    {
        "capability_id": "w2b_rule_evolution_registry",
        "capability_name": "W2.B Rule Evolution Registry",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "rule_alias_replay_and_semantic_change_detection",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-07-01",
        "hold_reason": "implemented in W2.B",
        "next_wave_target": "Wave 3 PDC producer replay integration",
        "chain_id": "wave2-rule-evolution",
        "research_refs": ["E14", "C21", "C33", "P06", "P07", "P08"],
        "no_adr_required": (
            "W2.B records rule evolution and replay behavior for existing "
            "requirement semantics; compatibility still depends on matching logic "
            "hashes rather than a new policy threshold."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime-quality rule evolution registry",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_rule_evolution.py -q"
            ),
            "rollback_or_reversal": (
                "disable rule-alias compatibility annotations and require explicit "
                "new requirement ids when replay cannot prove old logic"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/rule_evolution.py",
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/rule_evolution.py#build_rule_evolution_registry"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave2_i2_walking_skeleton/rule_evolution_registry.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/rule_evolution.py"
            "#build_rule_evolution_replay_context"
        ),
        "consumer_ref": (
            "repo://src/polisyos/runtime/quality/rule_evolution.py#public_rule_evolution_annotation"
        ),
        "verification_ref": "repo://tests/unit/runtime/quality/test_rule_evolution.py",
        "surface_ref": (
            "repo://architecture/policy_design_case/"
            "wave2_i2_walking_skeleton/rule_evolution_registry.json"
        ),
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_rule_evolution.py"
            "#test_requirement_id_alias_with_changed_logic_hash_requires_revalidation"
        ),
    },
    {
        "capability_id": "w2c_cost_degradation_telemetry",
        "capability_name": "W2.C Cost And Degradation Primitives",
        "reality_state": "implemented",
        "purpose": "diagnostic_only",
        "authority_scope": "cost_degradation_observability_without_silent_blocking",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-07-01",
        "hold_reason": "implemented in W2.C",
        "next_wave_target": "Wave 4 budget policy calibration",
        "chain_id": "wave2-telemetry",
        "research_refs": ["E18", "C23", "P09", "P13"],
        "no_adr_required": (
            "W2.C is telemetry-first and only permits blocking when an existing "
            "authority-level policy ref is present."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime-quality cost/degradation telemetry",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_cost_degradation.py -q"
            ),
            "rollback_or_reversal": (
                "drop cost/degradation scorecard observations while preserving "
                "evidence-quality status semantics"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/cost_degradation.py",
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/cost_degradation.py"
            "#build_cost_degradation_telemetry_from_quality_context"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave2_i2_walking_skeleton/cost_degradation_telemetry.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/cost_degradation.py"
            "#cost_degradation_scorecard_gates"
        ),
        "consumer_ref": "repo://src/polisyos/runtime/quality/closeout_reader.py",
        "verification_ref": "repo://tests/unit/runtime/quality/test_cost_degradation.py",
        "surface_ref": "repo://docs/reference/runtime/cost-degradation-telemetry.md",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_cost_degradation.py"
            "#test_cost_telemetry_cannot_silently_downgrade_evidence_quality"
        ),
    },
    {
        "capability_id": "w2d_soft_gate_telemetry",
        "capability_name": "W2.D Self-FMEA And Soft-Gate Telemetry",
        "reality_state": "implemented",
        "purpose": "diagnostic_only",
        "authority_scope": "warning_lifecycle_fmea_and_advisory_review_telemetry",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-07-01",
        "hold_reason": "implemented in W2.D",
        "next_wave_target": "Wave 4 soft-gate maturity policy",
        "chain_id": "wave2-telemetry",
        "research_refs": ["E19", "C24", "C32", "P04", "P09", "P13"],
        "decision_refs": ["ADR-0169", "ADR-0171"],
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime-quality soft gate telemetry",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_soft_gate_telemetry.py -q"
            ),
            "rollback_or_reversal": (
                "remove advisory soft-gate telemetry reads while keeping existing "
                "human review and bounded-liveness records"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/soft_gate_telemetry.py",
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/soft_gate_telemetry.py"
            "#build_soft_gate_telemetry_report"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave2_i2_walking_skeleton/soft_gate_telemetry.json"
        ),
        "bridge_ref": "repo://src/polisyos/runtime/quality/prompt_tool_ledger.py",
        "consumer_ref": "repo://src/polisyos/runtime/quality/closeout_reader.py",
        "verification_ref": "repo://tests/unit/runtime/quality/test_soft_gate_telemetry.py",
        "surface_ref": "repo://docs/reference/runtime/human-review-calibration.md",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_soft_gate_telemetry.py"
            "#test_soft_gate_telemetry_exposes_liveness_hooks_and_advisory_review_boundary"
        ),
    },
    {
        "capability_id": "w2e_calibration_ledger",
        "capability_name": "W2.E Calibration Ledger Schema",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "historical_prior_influence_without_current_evidence_closure",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-07-01",
        "hold_reason": "implemented in W2.E",
        "next_wave_target": "Wave 4 longitudinal threshold governance",
        "chain_id": "wave2-influence-records",
        "research_refs": ["E20", "C25", "C35", "C41", "P07", "P10", "P15"],
        "no_adr_required": (
            "W2.E makes sparse history transparent and non-blocking; mature "
            "blocking thresholds remain governed config until longitudinal data "
            "exists."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime-quality calibration ledger and influence refs",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_calibration_ledger.py -q"
            ),
            "rollback_or_reversal": (
                "remove historical-prior influence from routing/review hints and "
                "fall back to current-run evidence only"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/calibration_ledger.py",
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/calibration_ledger.py#build_calibration_ledger"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave2_i2_walking_skeleton/historical_prior_firewall.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/calibration_ledger.py"
            "#calibration_influence_for_scope"
        ),
        "consumer_ref": "repo://src/polisyos/runtime/quality/claim_registry.py",
        "verification_ref": "repo://tests/unit/runtime/quality/test_calibration_ledger.py",
        "surface_ref": "repo://docs/reference/runtime/calibration-ledger.md",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_calibration_ledger.py"
            "#test_historical_prior_refs_fail_claim_registry_evidence_slots"
        ),
    },
    {
        "capability_id": "w2f_balanced_memory_schema",
        "capability_name": "W2.F Balanced Memory Schema",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "balanced_memory_influence_without_current_evidence_closure",
        "validation_profile": "production",
        "owner": "team-scientist-orchestration",
        "expiry": "2026-07-01",
        "hold_reason": "implemented in W2.F",
        "next_wave_target": "Wave 5 memory dashboard/API surface",
        "chain_id": "wave2-influence-records",
        "research_refs": ["E21", "C25", "C41", "P11", "P15"],
        "decision_refs": ["ADR-0172"],
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "Scientist balanced memory and runtime influence records",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/scientist/orchestration/memory/"
                "test_balanced_memory.py tests/unit/runtime/quality/"
                "test_memory_influence_records.py -q"
            ),
            "rollback_or_reversal": (
                "disable balanced-memory influence records and keep prior failure "
                "lesson storage without current-run evidence influence"
            ),
        },
        "typed_contract_ref": ("repo://src/polisyos/scientist/orchestration/memory/balanced.py"),
        "producer_ref": (
            "repo://src/polisyos/scientist/orchestration/memory/balanced.py"
            "#build_balanced_memory_record"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave2_i2_walking_skeleton/memory_influence_firewall.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/memory_influence.py#build_memory_influence_record"
        ),
        "consumer_ref": (
            "repo://src/polisyos/runtime/quality/memory_influence.py"
            "#memory_influence_claim_evidence_issues"
        ),
        "verification_ref": (
            "repo://tests/unit/scientist/orchestration/memory/test_balanced_memory.py"
        ),
        "surface_out_of_scope": {
            "rationale": (
                "Wave 5 owns public/dashboard/API memory surfaces; Wave 2 exposes "
                "runtime influence records and an audit firewall only."
            ),
            "owner": "team-scientist-orchestration",
            "review_date": "2026-06-30",
            "inspection_path": "docs/adr/0172-balanced-memory-influence-ledger.md",
        },
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_memory_influence_records.py"
            "#test_memory_influence_ref_cannot_satisfy_claim_registry_evidence_slot"
        ),
    },
    {
        "capability_id": "w2i2_walking_skeleton",
        "capability_name": "W2.I2 Walking Skeleton",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "wave2_exit_runtime_seam_proof",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-07-01",
        "hold_reason": "implemented as the Wave 2 exit seam",
        "next_wave_target": "Wave 3 broad adapter work",
        "chain_id": "wave2-i2-walking-skeleton",
        "research_refs": ["E6", "C36", "C41", "P01", "P02", "P10", "P15"],
        "no_adr_required": (
            "The I2 skeleton wires accepted Wave 2 carriers into a deterministic "
            "runtime proof and does not add a new governance decision."
        ),
        "reuse_classification": "wire_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "architecture/policy_design_case/wave2_i2_walking_skeleton",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_wave2_walking_skeleton.py -q"
            ),
            "rollback_or_reversal": (
                "delete the Wave 2 I2 bundle and keep Wave 3 blocked until a typed "
                "architecture blocker or replacement seam proof is recorded"
            ),
        },
        "typed_contract_ref": ("repo://src/polisyos/runtime/quality/wave2_walking_skeleton.py"),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/wave2_walking_skeleton.py"
            "#build_wave2_policy_design_case_walking_skeleton"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/wave2_i2_walking_skeleton/manifest.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/wave2_walking_skeleton.py"
            "#persist_wave2_policy_design_case_walking_skeleton"
        ),
        "consumer_ref": "repo://src/polisyos/runtime/quality/closeout_reader.py",
        "verification_ref": ("repo://tests/unit/runtime/quality/test_wave2_walking_skeleton.py"),
        "surface_ref": (
            "repo://docs/archive/reports/2026-05-22-policy-design-case-wave2-closeout.md"
        ),
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_wave2_walking_skeleton.py"
            "#test_wave2_i2_negative_rejects_projection_as_closeout_substitute"
        ),
    },
)

DEFAULT_WAVE3_CAPABILITY_CLAIMS: tuple[dict[str, Any], ...] = (
    {
        "capability_id": "w3a_ir_analytics_bridge",
        "capability_name": "W3.A IR Analytics Bridge",
        "reality_state": "implemented",
        "purpose": "evidence_producer",
        "authority_scope": "claim_bound_ir_proof_status",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-08-01",
        "hold_reason": "implemented in W3.A",
        "next_wave_target": "Wave 4 conflict composition",
        "chain_id": "wave3-producer-adapters",
        "research_refs": ["E8", "C9", "C10", "C13", "C14", "P02", "P10", "P14"],
        "no_adr_required": (
            "W3.A wires existing proof-carrying IR analytics into claim registry "
            "surfaces without choosing new policy-domain authority semantics."
        ),
        "reuse_classification": "wire_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime quality IR analytics claim bridge",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_claim_registry.py "
                "tests/unit/scientist/validation/test_policy_grounding_matrix.py -q"
            ),
            "rollback_or_reversal": "remove ir_analytics_bridge from runtime claim registry inputs",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/ir_analytics_bridge.py",
        "producer_ref": "repo://src/polisyos/runtime/quality/ir_analytics_bridge.py#build_ir_analytics_claim_bridge",
        "artifact_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json#ir_analytics",
        "bridge_ref": "repo://src/polisyos/runtime/quality/claim_registry.py#build_runtime_claim_registry",
        "consumer_ref": "repo://src/polisyos/scientist/validation/policy_grounding.py",
        "verification_ref": "repo://tests/unit/runtime/quality/test_claim_registry.py",
        "surface_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json",
        "semantic_test_ref": "repo://tests/unit/runtime/quality/test_claim_registry.py#test_ir_analytics_required_claim_fails_without_bridge_binding",
    },
    {
        "capability_id": "w3b_lex_legal_adapter",
        "capability_name": "W3.B Lex Legal Adapter",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "claim_level_legal_admissibility",
        "validation_profile": "production",
        "owner": "team-lex",
        "expiry": "2026-08-01",
        "hold_reason": "implemented in W3.B",
        "next_wave_target": "Wave 4 admissibility composition",
        "chain_id": "wave3-producer-adapters",
        "research_refs": ["E9", "C7", "C11", "P01", "P05", "P08", "P12"],
        "decision_refs": ["ADR-0168"],
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "Lex NormPack legal authority report",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/lex "
                "tests/unit/runtime/quality/test_lex_legal_authority_surface.py -q"
            ),
            "rollback_or_reversal": (
                "disable claim_legal_anchors merge in normpack applicability report"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/lex/normpack/legal_authority.py",
        "producer_ref": "repo://src/polisyos/lex/normpack/legal_authority.py#build_legal_authority_report",
        "artifact_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json#lex",
        "bridge_ref": "repo://src/polisyos/lex/normpack/applicability_report.py#build_normative_applicability_report",
        "consumer_ref": "repo://src/polisyos/runtime/quality/semantic_binding.py",
        "verification_ref": "repo://tests/unit/lex/test_legal_authority_adapter.py",
        "surface_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json",
        "semantic_test_ref": "repo://tests/unit/lex/test_legal_authority_adapter.py#test_generic_ukrainian_topic_match_stays_context_not_authority",
    },
    {
        "capability_id": "w3c_fabric_data_adapter",
        "capability_name": "W3.C Fabric Data Adapter",
        "reality_state": "implemented",
        "purpose": "evidence_producer",
        "authority_scope": "source_contract_bound_scenario_family",
        "validation_profile": "production",
        "owner": "team-fabric",
        "expiry": "2026-08-01",
        "hold_reason": "implemented in W3.C",
        "next_wave_target": "Wave 4 data authority composition",
        "chain_id": "wave3-producer-adapters",
        "research_refs": [
            "E10",
            "C2",
            "C6",
            "C11",
            "C22",
            "P01",
            "P02",
            "P08",
            "P14",
        ],
        "no_adr_required": (
            "W3.C binds existing Fabric contracts and Data Forge facets "
            "without adding new decision thresholds."
        ),
        "reuse_classification": "wire_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "production data contract index source-family binding",
            "canary_or_revalidation": (
                "uv run pytest "
                "tests/unit/runtime/quality/test_production_data_contract_index.py "
                "tests/unit/runtime/quality/test_semantic_binding.py -q"
            ),
            "rollback_or_reversal": (
                "remove production_data_contract_index report from scenario evidence inputs"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/production_data_contract_index.py",
        "producer_ref": "repo://src/polisyos/runtime/quality/production_data_contract_index.py#ProductionDataContractIndex.build_scenario_binding_report",
        "artifact_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json#fabric",
        "bridge_ref": "repo://src/polisyos/runtime/quality/semantic_binding.py#_fabric_selection_issues",
        "consumer_ref": "repo://src/polisyos/runtime/quality/semantic_binding.py",
        "verification_ref": "repo://tests/unit/runtime/quality/test_production_data_contract_index.py",
        "surface_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json",
        "semantic_test_ref": "repo://tests/unit/runtime/quality/test_production_data_contract_index.py#test_contract_index_blocks_cloud_curated_macro_contracts_for_public_golden",
    },
    {
        "capability_id": "w3d_scholar_adapter",
        "capability_name": "W3.D Scholar Adapter",
        "reality_state": "implemented",
        "purpose": "evidence_producer",
        "authority_scope": "academic_support_not_participation_legitimacy",
        "validation_profile": "production",
        "owner": "team-scholar",
        "expiry": "2026-08-01",
        "hold_reason": "implemented in W3.D",
        "next_wave_target": "Wave 4 evidence portfolio composition",
        "chain_id": "wave3-producer-adapters",
        "research_refs": ["E11", "C13", "C14", "C26", "P05", "P10", "P14"],
        "decision_refs": ["ADR-0167"],
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "Scholar search job academic evidence artifact",
            "canary_or_revalidation": (
                "uv run pytest "
                "tests/unit/runtime/quality/test_scholar_academic_evidence.py "
                "tests/unit/scholar/search/test_service_jobs_tools.py -q"
            ),
            "rollback_or_reversal": (
                "stop persisting scholar.academic_evidence from deep search jobs"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/scholar/_impl/evidence.py",
        "producer_ref": "repo://src/polisyos/scholar/search/jobs.py#DeepResearchJobManager._persist_scholar_academic_evidence_async",
        "artifact_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json#scholar",
        "bridge_ref": "repo://src/polisyos/runtime/quality/scholar_academic_evidence.py#build_scholar_academic_evidence_boundary_record",
        "consumer_ref": "repo://src/polisyos/runtime/quality/scorecard.py",
        "verification_ref": "repo://tests/unit/runtime/quality/test_scholar_academic_evidence.py",
        "surface_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json",
        "semantic_test_ref": "repo://tests/unit/runtime/quality/test_scholar_academic_evidence.py#test_scholar_evidence_blocks_participation_like_support_without_downgrade",
    },
    {
        "capability_id": "w3e_foundry_method_adapter",
        "capability_name": "W3.E Foundry Method Adapter",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "method_obligation_validity",
        "validation_profile": "production",
        "owner": "team-foundry",
        "expiry": "2026-08-01",
        "hold_reason": "implemented in W3.E",
        "next_wave_target": "Wave 4 method-output claim composition",
        "chain_id": "wave3-producer-adapters",
        "research_refs": ["E12", "C9", "C10", "C11", "C13", "P01", "P10", "P14"],
        "no_adr_required": (
            "W3.E records method obligations and uncertainty surfaces under "
            "existing Foundry validation ownership."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "Foundry method-quality report and Scientist workflow bridge",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/foundry/validation/test_method_quality.py "
                "tests/unit/scientist/orchestration -q"
            ),
            "rollback_or_reversal": (
                "remove method-quality persistence hooks from Scientist workflow builder"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/foundry/validation/method_quality.py",
        "producer_ref": "repo://src/polisyos/foundry/validation/method_quality.py#build_foundry_method_report_from_execution_outputs",
        "artifact_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json#foundry",
        "bridge_ref": "repo://src/polisyos/scientist/orchestration/workflows/builder.py#_attach_foundry_method_report",
        "consumer_ref": "repo://src/polisyos/runtime/quality/claim_registry.py",
        "verification_ref": "repo://tests/unit/foundry/validation/test_method_quality.py",
        "surface_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json",
        "semantic_test_ref": "repo://tests/unit/foundry/validation/test_method_quality.py#test_generic_foundry_execute_cannot_satisfy_policy_method_obligations",
    },
    {
        "capability_id": "w3f_data_forge_closeout_binding",
        "capability_name": "W3.F Data Forge Closeout Binding",
        "reality_state": "implemented",
        "purpose": "closeout_input",
        "authority_scope": "official_snapshot_release_read_api_identity",
        "validation_profile": "production",
        "owner": "team-data-forge",
        "expiry": "2026-08-01",
        "hold_reason": "implemented in W3.F",
        "next_wave_target": "Wave 4 closeout substrate composition",
        "chain_id": "wave3-producer-adapters",
        "research_refs": ["E16", "C9", "C11", "C20", "C22", "P01", "P08", "P10"],
        "no_adr_required": (
            "W3.F extends Data Forge snapshot finalize/read API identity "
            "without new domain thresholds."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "Data Forge snapshot binding runtime quality evidence",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_data_forge_binding.py -q"
            ),
            "rollback_or_reversal": "disable data_forge_snapshot_binding scorecard gate",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/data_forge_binding.py",
        "producer_ref": "repo://src/polisyos/data_forge/kernel/snapshot/finalize.py#finalize_snapshot",
        "artifact_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json#data_forge",
        "bridge_ref": "repo://src/polisyos/runtime/quality/scorecard.py",
        "consumer_ref": "repo://src/polisyos/runtime/quality/semantic_binding.py",
        "verification_ref": "repo://tests/unit/runtime/quality/test_data_forge_binding.py",
        "surface_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json",
        "semantic_test_ref": "repo://tests/unit/runtime/quality/test_data_forge_binding.py#test_data_forge_snapshot_binding_requires_closeout_grade_identity_lineage_and_claims",
    },
    {
        "capability_id": "w3g_acquisition_planner",
        "capability_name": "W3.G Acquisition Planner",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "eligible_acquisition_next_actions",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-08-01",
        "hold_reason": "implemented in W3.G",
        "next_wave_target": "Wave 4 runtime blocker composition",
        "chain_id": "wave3-producer-adapters",
        "research_refs": ["E17", "C22", "P01", "P09", "P10"],
        "decision_refs": ["ADR-0166"],
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime evidence acquisition planner",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_acquisition_planner.py -q"
            ),
            "rollback_or_reversal": "remove acquisition_planner report from scorecard projection",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/acquisition_planner.py",
        "producer_ref": "repo://src/polisyos/runtime/quality/acquisition_planner.py#plan_evidence_acquisition",
        "artifact_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json#acquisition",
        "bridge_ref": "repo://src/polisyos/runtime/quality/acquisition_planner.py#acquisition_planner_scorecard_gates",
        "consumer_ref": "repo://src/polisyos/runtime/quality/scorecard.py",
        "verification_ref": "repo://tests/unit/runtime/quality/test_acquisition_planner.py",
        "surface_ref": "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json",
        "semantic_test_ref": "repo://tests/unit/runtime/quality/test_acquisition_planner.py#test_non_overridable_gate_blocks_even_when_voi_prefers_proxy",
    },
    {
        "capability_id": "w3i3_producer_adapter_checkpoint",
        "capability_name": "I3 Producer Adapter Mid-wave Checkpoint",
        "reality_state": "implemented",
        "purpose": "diagnostic_only",
        "authority_scope": "wave3_exit_acceptance_evidence",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-08-01",
        "hold_reason": "implemented as Wave 3 exit evidence",
        "next_wave_target": "Wave 4 orchestration",
        "chain_id": "wave3-i3-checkpoint",
        "research_refs": [
            "E8",
            "E9",
            "E10",
            "E11",
            "E12",
            "E16",
            "E17",
            "C22",
            "P01",
            "P02",
            "P10",
        ],
        "no_adr_required": (
            "I3 records integration evidence for W3 adapters and does not add "
            "new policy authority semantics."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": (
                "architecture/policy_design_case/wave3_i3_producer_adapter_checkpoint"
            ),
            "canary_or_revalidation": (
                "uv run pytest "
                "tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q"
            ),
            "rollback_or_reversal": (
                "remove W3 capability claims and checkpoint artifact before Wave 4 starts"
            ),
        },
        "typed_contract_ref": "repo://docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md#Wave-3---Producer-Adapters-And-Claim-Bound-Evidence",
        "producer_ref": "repo://tools/quality/validation/check_policy_design_case_capability_ratchet.py#DEFAULT_WAVE3_CAPABILITY_CLAIMS",
        "artifact_ref": "repo://architecture/policy_design_case/wave3_i3_producer_adapter_checkpoint/manifest.json",
        "bridge_ref": "repo://tools/quality/validation/check_policy_design_case_capability_ratchet.py#validate_capability_reality_report",
        "consumer_ref": "repo://docs/reference/policy-design-case-capability-ratchet.md",
        "verification_ref": "repo://tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py",
        "surface_ref": "repo://architecture/policy_design_case/wave3_i3_producer_adapter_checkpoint/manifest.json",
        "semantic_test_ref": "repo://tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py#test_wave3_exit_records_i3_checkpoint_and_adapter_corpus_coverage",
    },
)

DEFAULT_POLICY_EVIDENCE_CAPABILITY_GRAPH_PHASE0_CLAIMS: tuple[dict[str, Any], ...] = (
    {
        "capability_id": "policy_evidence_capability_graph",
        "capability_name": "Policy Evidence Capability Graph",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "phase7_policy_evidence_capability_graph_runtime_authority",
        "validation_profile": "planning",
        "owner": "team-runtime-quality",
        "expiry": "2027-12-31",
        "hold_reason": (
            "Phase 7 wires typed capability index artifacts through resolver "
            "execution, W12 validation, replay refs, DCAT/PROV exports, audit "
            "inspection, and generated capability cards."
        ),
        "next_wave_target": "Policy Evidence Capability Graph operational hardening",
        "chain_id": "policy-evidence-capability-graph-phase7",
        "decision_refs": ["ADR-0174"],
        "research_refs": [
            "E8",
            "C1",
            "C2",
            "C3",
            "P01",
            "P02",
            "P03",
            "P05",
            "P06",
            "P10",
            "P14",
            "P15",
        ],
        "reuse_classification": "build_new",
        "rejected_reuse_evidence": [
            (
                "L1-L6 production-data layers exist, but no cross-modal "
                "release-time capability graph artifact exists."
            ),
            (
                "L7 curated contracts are compatibility fixtures and cannot be "
                "promoted into graph authority."
            ),
        ],
        "rollout_refs": {
            "feature_flag_or_scope": (
                "Phase 7 capability graph authority path; scenario-family "
                "strings remain compatibility/audit projections only"
            ),
            "canary_or_revalidation": (
                "uv run pytest tests/repo_quality/tools/"
                "test_policy_evidence_capability_exports.py "
                "tests/unit/runtime/quality/test_replay.py "
                "tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q"
            ),
            "rollback_or_reversal": (
                "disable capability-index promotion, keep compatibility "
                "projection read-only, and require replay warnings for legacy PDCs"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/runtime/quality/capability_authority.py"
            "#CapabilityBindingResult"
        ),
        "producer_ref": (
            "repo://tools/quality/validation/"
            "build_policy_evidence_capability_index.py"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "capability_index_phase1_artifact_profile.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/capability_resolver.py"
            "#RequirementToCapabilityResolver.from_duckdb"
        ),
        "consumer_ref": (
            "repo://tools/quality/validation/run_universal_outcome_corpus.py"
            "#_capability_graph_context"
        ),
        "verification_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_evidence_capability_exports.py"
        ),
        "surface_ref": (
            "repo://tools/quality/validation/"
            "inspect_policy_evidence_capability_index.py"
        ),
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/"
            "test_w12d_universal_outcome_corpus_run.py"
            "#test_w12d_corpus_stub_consumes_capability_index_and_emits_claim_binding_refs"
        ),
        "mitigation_credit": 2.0,
        "mitigation_refs": [
            "repo://docs/reference/policy-design-case-failure-patterns.md",
        ],
        "mitigation_enforced": True,
    },
    {
        "capability_id": "construct_registry",
        "capability_name": "Construct Registry",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "phase7_construct_registry_loaded_for_capability_resolution",
        "validation_profile": "planning",
        "owner": "team-runtime-quality",
        "expiry": "2027-12-31",
        "hold_reason": (
            "Governed construct registry artifact, loader, rule cross-reference, "
            "resolver execution, W12.D binding trace, and I7-bis load check are wired."
        ),
        "next_wave_target": "Policy Evidence Capability Graph operational hardening",
        "chain_id": "policy-evidence-capability-graph-phase7",
        "decision_refs": ["ADR-0174"],
        "research_refs": ["E8", "C1", "P01", "P02", "P04", "P05", "P06", "P10", "P12"],
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "Phase 2 construct registry artifact and validation only",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_construct_registry.py "
                "tests/unit/runtime/quality/test_concept_spine.py "
                "tests/unit/obligation_rules -q"
            ),
            "rollback_or_reversal": (
                "revert construct_registry.py, construct_registry_v1.yaml, and "
                "W6.B required_evidence_constructs; keep ADR-0174 Phase 0 baseline"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/runtime/quality/construct_registry.py#ConstructRegistry"
        ),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/construct_registry.py#load_construct_registry"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/construct_registry_v1.yaml"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/construct_registry.py"
            "#validate_obligation_rule_construct_refs"
        ),
        "consumer_ref": (
            "repo://src/polisyos/obligation_rules/catalog.py#_vertical_seed_rule_specs"
        ),
        "verification_ref": "repo://tests/unit/runtime/quality/test_construct_registry.py",
        "surface_ref": (
            "repo://docs/reference/policy-design-case-evidence-paths.md"
            "#policy-evidence-capability-graph-phase-2"
        ),
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_construct_registry.py"
            "#test_scenario_family_name_alone_does_not_grant_authority"
        ),
        "mitigation_refs": [
            "repo://docs/reference/policy-design-case-failure-patterns.md",
        ],
        "mitigation_enforced": True,
    },
    {
        "capability_id": "requirement_to_capability_resolver",
        "capability_name": "Requirement To Capability Resolver",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "phase7_requirement_to_capability_resolver_with_replay_refs",
        "validation_profile": "planning",
        "owner": "team-runtime-quality",
        "expiry": "2027-12-31",
        "hold_reason": (
            "Construct-aware RequirementSpec resolution consumes the DuckDB "
            "capability index, records selected and rejected bindings, exposes "
            "W8.E/W8.F signals, and supplies frozen refs for replay."
        ),
        "next_wave_target": "Policy Evidence Capability Graph operational hardening",
        "chain_id": "policy-evidence-capability-graph-phase7",
        "decision_refs": ["ADR-0174"],
        "research_refs": [
            "E8",
            "C1",
            "C2",
            "C3",
            "P02",
            "P04",
            "P05",
            "P10",
            "P14",
            "P15",
        ],
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": (
                "RequirementToCapabilityResolver is the authority path; "
                "legacy family fallback remains frozen replay compatibility only"
            ),
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/"
                "test_capability_resolver.py tests/repo_quality/tools/"
                "test_w12d_universal_outcome_corpus_run.py -q"
            ),
            "rollback_or_reversal": (
                "temporarily enable the legacy family fallback flag and keep "
                "construct-resolved blockers visible until Phase 7 replay closes"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/runtime/quality/capability_resolver.py"
            "#RequirementToCapabilityQuery"
        ),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/capability_resolver.py"
            "#RequirementToCapabilityResolver"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "capability_index_phase1_artifact_profile.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/data_requirement/compiler.py"
            "#_capability_bindings_for_requirements"
        ),
        "consumer_ref": (
            "repo://tools/quality/validation/"
            "run_universal_outcome_corpus.py#_claim_bindings_from_pipeline"
        ),
        "verification_ref": (
            "repo://tests/unit/runtime/quality/test_capability_resolver.py"
        ),
        "surface_ref": (
            "repo://tools/quality/validation/"
            "inspect_policy_evidence_capability_index.py"
        ),
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/"
            "test_i7bis_universal_compilation_integration_realism_check.py"
            "#test_i7bis_runs_full_universal_path_and_inspects_w8b_warrants"
        ),
        "mitigation_refs": [
            "repo://docs/reference/policy-design-case-failure-patterns.md",
        ],
        "mitigation_enforced": True,
    },
    {
        "capability_id": "capability_index_compiler",
        "capability_name": "Capability Index Compiler",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "phase7_capability_index_compiler_audit_export_replay_surface",
        "validation_profile": "planning",
        "owner": "team-runtime-quality",
        "expiry": "2027-12-31",
        "hold_reason": (
            "Capability index compilation now has runtime resolver consumption, "
            "DCAT/PROV/audit-card exports, generated-artifact registration, "
            "and frozen replay policy."
        ),
        "mitigation_credit": 6.0,
        "next_wave_target": "Policy Evidence Capability Graph operational hardening",
        "chain_id": "policy-evidence-capability-graph-phase7",
        "decision_refs": ["ADR-0174"],
        "research_refs": [
            "E8",
            "C1",
            "C2",
            "C3",
            "P01",
            "P02",
            "P03",
            "P05",
            "P07",
            "P10",
            "P12",
            "P15",
        ],
        "reuse_classification": "build_new",
        "rejected_reuse_evidence": [
            (
                "Existing production-data summaries and scenario-family "
                "contract fixtures do not provide a typed, queryable capability "
                "index with construct coverage, authority envelopes, and replay refs."
            ),
            (
                "Existing generated-artifact docs are inventory surfaces, not a "
                "compiler for capability, conflict, failure-mode, and acquisition tables."
            ),
        ],
        "rollout_refs": {
            "feature_flag_or_scope": (
                "release-time capability index artifact producer plus export, "
                "card, resolver, and replay consumers"
            ),
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/"
                "test_capability_index_compiler.py tests/repo_quality/tools/"
                "test_policy_evidence_capability_index.py tests/repo_quality/tools/"
                "test_policy_evidence_capability_exports.py -q"
            ),
            "rollback_or_reversal": (
                "remove exported capability index projections and keep frozen "
                "legacy replay warnings for closed PDCs without refs"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/capability_index.py",
        "producer_ref": (
            "repo://tools/quality/validation/"
            "build_policy_evidence_capability_index.py"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "capability_index_phase1_artifact_profile.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/capability_index_compiler.py"
            "#compile_capability_index"
        ),
        "consumer_ref": "repo://docs/reference/generated-artifacts.md",
        "verification_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_evidence_capability_index.py"
        ),
        "surface_ref": (
            "repo://tools/quality/validation/"
            "generate_policy_evidence_capability_cards.py"
        ),
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_evidence_capability_exports.py"
            "#test_capability_index_exports_dcat_prov_inspection_and_cards"
        ),
        "mitigation_refs": [
            "repo://docs/reference/policy-design-case-failure-patterns.md",
        ],
        "mitigation_enforced": True,
    },
    {
        "capability_id": "legacy_scenario_family_authority",
        "capability_name": "Legacy Scenario-Family Authority Lookup",
        "reality_state": "surface_out_of_scope",
        "purpose": "diagnostic_only",
        "authority_scope": "legacy_replay_and_audit_projection_only",
        "validation_profile": "planning",
        "owner": "team-runtime-quality",
        "expiry": "2027-12-31",
        "hold_reason": (
            "Scenario-family strings are intentionally sunset as authority "
            "selectors; Phase 7 permits them only in compatibility/audit "
            "projection and frozen legacy replay warnings."
        ),
        "next_wave_target": "consumer migration completion",
        "chain_id": "policy-evidence-capability-graph-phase7",
        "decision_refs": ["ADR-0174"],
        "research_refs": ["P03", "P05", "P06", "P07", "P10", "P15"],
        "reuse_classification": "sunset_existing",
        "rollout_refs": {
            "feature_flag_or_scope": (
                "No authority lookup path; legacy reader exists only for "
                "closed PDC replay without capability_index_ref until 2027-12-31"
            ),
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_replay.py -q"
            ),
            "rollback_or_reversal": (
                "restore only typed legacy replay warnings; do not restore "
                "scenario-family authority lookup"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/runtime/quality/replay.py"
            "#build_policy_evidence_capability_replay_policy"
        ),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/replay.py"
            "#POLICY_EVIDENCE_LEGACY_READER_REF"
        ),
        "artifact_ref": (
            "repo://architecture/shims.toml#scenario_family_authority_lookup"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/replay.py"
            "#validate_policy_evidence_capability_replay_refs"
        ),
        "consumer_ref": (
            "repo://tests/unit/runtime/quality/test_replay.py"
            "#test_legacy_pdc_replay_does_not_silently_use_current_filesystem"
        ),
        "verification_ref": "repo://tests/unit/runtime/quality/test_replay.py",
        "surface_ref": (
            "repo://architecture/shims.toml#scenario_family_authority_lookup"
        ),
        "surface_out_of_scope": {
            "rationale": (
                "Scenario-family authority is removed by design; only "
                "compatibility/audit projection and frozen legacy replay are "
                "allowed surfaces until consumer migration completes."
            ),
            "owner": "team-runtime-quality",
            "review_date": "2027-12-31",
            "inspection_path": "architecture/shims.toml#scenario_family_authority_lookup",
        },
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_replay.py"
            "#test_legacy_pdc_replay_does_not_silently_use_current_filesystem"
        ),
        "mitigation_refs": [
            "repo://docs/reference/policy-design-case-failure-patterns.md",
        ],
        "mitigation_enforced": True,
    },
    {
        "capability_id": "production_data_acquisition_planner",
        "capability_name": "Production Data Acquisition Planner",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "phase6_construct_aware_acquisition_and_white_space",
        "validation_profile": "planning",
        "owner": "team-runtime-quality",
        "expiry": "2026-07-31",
        "hold_reason": (
            "Phase 6 wires construct-aware failure-mode nodes, owned acquisition "
            "strategies, resolver-reachable strategy refs, DuckDB queryability, "
            "and grouped white-space reporting."
        ),
        "next_wave_target": "Policy Evidence Capability Graph Phase 7",
        "chain_id": "policy-evidence-capability-graph-phase6",
        "decision_refs": ["ADR-0174", "ADR-0166"],
        "research_refs": [
            "E17",
            "C1",
            "C2",
            "C3",
            "C22",
            "P01",
            "P02",
            "P03",
            "P04",
            "P05",
            "P09",
            "P10",
        ],
        "reuse_classification": "consolidate_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "capability-index failure modes and acquisition planner bridge",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/"
                "test_capability_white_space.py tests/unit/runtime/quality/"
                "test_acquisition_planner.py -q"
            ),
            "rollback_or_reversal": (
                "disable capability white-space report generation and keep "
                "resolver blocked statuses visible without acquisition strategy promotion"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/runtime/quality/capability_index.py"
            "#AcquisitionStrategy"
        ),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/capability_index_compiler.py"
            "#build_acquisition_strategies"
        ),
        "artifact_ref": (
            "repo://tools/quality/validation/production_quality_evidence_inventory.py"
            "#--capability-index"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/acquisition_planner.py"
            "#acquisition_gaps_from_capability_failure_modes"
        ),
        "consumer_ref": (
            "repo://src/polisyos/runtime/quality/capability_resolver.py"
            "#RequirementToCapabilityResolver.from_duckdb"
        ),
        "verification_ref": (
            "repo://tests/unit/runtime/quality/test_capability_white_space.py"
        ),
        "surface_ref": (
            "repo://docs/runbooks/policy-design-case-operator-triage.md"
            "#acquisition-strategy-ownership"
        ),
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_capability_white_space.py"
            "#test_failure_mode_strategy_refs_are_reachable_from_resolver_output"
        ),
        "mitigation_refs": [
            "repo://docs/reference/policy-design-case-failure-patterns.md",
        ],
        "mitigation_enforced": True,
    },
    {
        "capability_id": "authority_composition",
        "capability_name": "Authority Composition And Binding Status Lattice",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "phase3_capability_authority_composition",
        "validation_profile": "planning",
        "owner": "team-runtime-quality",
        "expiry": "2026-07-31",
        "hold_reason": (
            "Phase 3 implements the binding-status lattice, nine-factor minimum "
            "authority composition, C41 historical-prior firewall, W8.F "
            "independence factor, W8.E conflict marker preservation, and "
            "projection-side laundering guards."
        ),
        "next_wave_target": "Policy Evidence Capability Graph Phase 4",
        "chain_id": "policy-evidence-capability-graph-phase3",
        "decision_refs": ["ADR-0174"],
        "research_refs": ["E0", "C3", "C41", "P04", "P05", "P10", "P14", "P15"],
        "reuse_classification": "build_new",
        "rejected_reuse_evidence": [
            (
                "Existing authority.py guards projection/runtime envelopes, but "
                "no capability-specific nine-factor composition lattice existed."
            ),
            (
                "Existing W8.E/W8.F records exposed conflicts and independence, "
                "but no capability binding result consumed them before selection."
            ),
        ],
        "rollout_refs": {
            "feature_flag_or_scope": "Phase 3 authority composition library and tests",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/"
                "test_capability_authority.py -q"
            ),
            "rollback_or_reversal": (
                "remove capability_authority.py and keep downstream resolver "
                "adoption blocked until authority semantics are restored"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/runtime/quality/capability_authority.py"
            "#CapabilityBindingResult"
        ),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/capability_authority.py"
            "#compose_capability_authority"
        ),
        "artifact_ref": (
            "repo://tests/fixtures/capability_authority/mixed_outcomes_v1.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/authority.py"
            "#capability_binding_purpose_blockers"
        ),
        "consumer_ref": (
            "repo://src/polisyos/runtime/quality/projection_semantics.py"
            "#_assert_capability_binding_results_projection_safe"
        ),
        "verification_ref": (
            "repo://tests/unit/runtime/quality/test_capability_authority.py"
        ),
        "surface_ref": (
            "repo://tests/fixtures/capability_authority/mixed_outcomes_v1.json"
        ),
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_capability_authority.py"
            "#test_capability_with_below_floor_factor_degrades"
        ),
        "mitigation_refs": [
            "repo://docs/reference/policy-design-case-failure-patterns.md",
        ],
        "mitigation_enforced": True,
    },
    {
        "capability_id": "cross_modal_capability_graph",
        "capability_name": "Cross-Modal Capability Graph",
        "reality_state": "implemented",
        "purpose": "diagnostic_only",
        "authority_scope": "phase5_cross_modal_capability_graph_consumers",
        "validation_profile": "planning",
        "owner": "team-runtime-quality",
        "expiry": "2026-07-31",
        "hold_reason": (
            "Phase 5 wires capability binding results through Fabric, Lex, "
            "Foundry, Scholar, Participation, HypothesisLedger advisory "
            "firewalls, and W12.D/I7-bis producer-pipeline consumers."
        ),
        "next_wave_target": "Policy Evidence Capability Graph Phase 7",
        "chain_id": "policy-evidence-capability-graph-phase3",
        "decision_refs": ["ADR-0174"],
        "research_refs": [
            "E8",
            "C1",
            "C2",
            "C3",
            "P01",
            "P02",
            "P03",
            "P04",
            "P05",
            "P10",
            "P12",
            "P14",
            "P15",
        ],
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": (
                "Phase 5 multi-modal producer consumers read shared capability "
                "and construct refs while preserving producer authority bounds"
            ),
            "canary_or_revalidation": (
                "uv run pytest tests/unit/fabric/catalog tests/unit/lex "
                "tests/unit/foundry/methods/selection "
                "tests/unit/scholar_requirement "
                "tests/unit/participation_requirement "
                "tests/unit/runtime/quality/test_producer_pipeline.py "
                "tests/unit/runtime/quality/test_hypothesis_ledger.py -q"
            ),
            "rollback_or_reversal": (
                "disable capability_bindings inputs to the producer pipeline and "
                "fall back to explicit typed limitations from each modality"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/runtime/quality/capability_authority.py"
            "#CapabilityBindingResult"
        ),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/producer_pipeline.py"
            "#run_requirement_spec_producer_pipeline"
        ),
        "artifact_ref": (
            "repo://tools/quality/validation/run_universal_outcome_corpus.py"
            "#capability_graph_trace"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/producer_pipeline.py"
            "#_producer_binding_decisions"
        ),
        "consumer_ref": (
            "repo://tools/quality/validation/"
            "run_universal_outcome_corpus.py#_claim_bindings_from_pipeline"
        ),
        "verification_ref": (
            "repo://tests/unit/runtime/quality/test_producer_pipeline.py"
        ),
        "surface_ref": (
            "repo://tools/quality/validation/run_universal_outcome_corpus.py"
        ),
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_producer_pipeline.py"
            "#test_pipeline_persists_per_producer_capability_refs_and_cross_modal_traceability"
        ),
        "mitigation_refs": [
            "repo://docs/reference/policy-design-case-failure-patterns.md",
        ],
        "mitigation_enforced": True,
    },
)

DEFAULT_CAPABILITY_CLAIMS: tuple[dict[str, Any], ...] = (
    *DEFAULT_WAVE1_CAPABILITY_CLAIMS,
    *DEFAULT_WAVE2_CAPABILITY_CLAIMS,
    *DEFAULT_WAVE3_CAPABILITY_CLAIMS,
    *DEFAULT_POLICY_EVIDENCE_CAPABILITY_GRAPH_PHASE0_CLAIMS,
    {
        "capability_id": "w4a_nl_replay_orchestration",
        "capability_name": "W4.A NL/Replay Orchestration",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "runtime_orchestration_spine_continuity",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-09-01",
        "hold_reason": "implemented in W4.A and closed in I4 manifest",
        "next_wave_target": "Wave 5 external replay/export consumers",
        "chain_id": "wave4-runtime-closeout",
        "research_refs": ["E7", "C8", "C40", "P02", "P12"],
        "no_adr_required": (
            "W4.A wires existing producer-spine and handoff records through runtime "
            "orchestration surfaces without adding new policy authority semantics."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime control, replay, bundle inspection, readiness, and export handoff paths",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_nl_replay_orchestration.py "
                "tests/repo_quality/tools/test_evidence_bundle_inspection.py -q"
            ),
            "rollback_or_reversal": "remove runtime_orchestration_continuity from canary bundle assembly",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/nl_replay_orchestration.py#NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION",
        "producer_ref": "repo://src/polisyos/runtime/quality/nl_replay_orchestration.py#build_nl_replay_orchestration_continuity",
        "artifact_ref": "repo://architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json#runtime_orchestration_continuity",
        "bridge_ref": "repo://tools/ops_runners/runtime/canary_evidence.py#runtime_orchestration_continuity",
        "consumer_ref": "repo://tools/quality/validation/inspect_evidence_bundles.py#runtime_orchestration_continuity",
        "verification_ref": "repo://tests/unit/runtime/quality/test_nl_replay_orchestration.py",
        "surface_ref": "repo://architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json#runtime_orchestration_continuity",
        "semantic_test_ref": "repo://tests/unit/runtime/quality/test_nl_replay_orchestration.py#test_nl_replay_continuity_binds_carrier_spine_claims_and_producers",
    },
    {
        "capability_id": "w4b_portfolio_aggregation",
        "capability_name": "W4.B Portfolio Aggregation",
        "reality_state": "implemented",
        "purpose": "evidence_producer",
        "authority_scope": "effective_evidence_support_accounting",
        "validation_profile": "production",
        "owner": "team-science-quality",
        "expiry": "2026-09-01",
        "hold_reason": "implemented in W4.B and closed in I4 manifest",
        "next_wave_target": "Wave 5 external portfolio/audit consumers",
        "chain_id": "wave4-runtime-closeout",
        "research_refs": ["E13", "C29", "P14"],
        "no_adr_required": (
            "W4.B reports evidence-strength truthfulness from existing evidence "
            "lineage and method-equivalence records without choosing new domain thresholds."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "strict hard-collapse with graded independence behind governed feature flags",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_evidence_independence_map.py "
                "tests/unit/runtime/quality/test_evidence_synthesis_report.py -q"
            ),
            "rollback_or_reversal": "remove policy_design_portfolio_effective_support from I4 closeout readers",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/evidence_independence.py#INDEPENDENCE_MAP_SCHEMA_VERSION",
        "producer_ref": "repo://src/polisyos/runtime/quality/evidence_independence.py#build_evidence_independence_map",
        "artifact_ref": "repo://architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json#portfolio_effective_support",
        "bridge_ref": "repo://tools/ops_runners/runtime/canary_evidence.py#_wave4_i4_portfolio_effective_support",
        "consumer_ref": "repo://src/polisyos/runtime/quality/closeout_reader.py#portfolio_effective_support",
        "verification_ref": "repo://tests/unit/runtime/quality/test_evidence_independence_map.py",
        "surface_ref": "repo://architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json#portfolio_effective_support",
        "semantic_test_ref": "repo://tests/unit/runtime/quality/test_evidence_independence_map.py#test_independence_map_collapses_400_raw_lines_to_small_effective_count",
    },
    {
        "capability_id": "w4c_lifecycle_partial_reissue",
        "capability_name": "W4.C Lifecycle And Partial Reissue",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "claim_scoped_public_revalidation_state",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-09-01",
        "hold_reason": "implemented in W4.C and closed in I4 manifest",
        "next_wave_target": "Wave 5 public revision export consumers",
        "chain_id": "wave4-runtime-closeout",
        "research_refs": ["E15", "C20", "C21", "C33", "P07", "P08", "P09"],
        "no_adr_required": (
            "W4.C maps existing DDM, legal, source, participation, policy-context, "
            "and rule-evolution events to scoped claims without adding new lifecycle law."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "claim lifecycle runtime reader and public revision projection",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_policy_design_case_lifecycle.py "
                "tests/unit/tools/test_canary_evidence.py::test_assemble_canary_evidence_preserves_scoped_lifecycle_reissue_as_i4_blocker -q"
            ),
            "rollback_or_reversal": "remove lifecycle_reissue from I4 closeout reader inputs",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/case_lifecycle.py#LIFECYCLE_REISSUE_REPORT_SCHEMA_VERSION",
        "producer_ref": "repo://src/polisyos/runtime/quality/case_lifecycle.py#build_lifecycle_reissue_report",
        "artifact_ref": "repo://architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json#lifecycle_partial_reissue",
        "bridge_ref": "repo://tools/ops_runners/runtime/canary_evidence.py#_wave4_i4_lifecycle_reissue_report",
        "consumer_ref": "repo://src/polisyos/runtime/quality/closeout_reader.py#lifecycle_reissue",
        "verification_ref": "repo://tests/unit/runtime/quality/test_policy_design_case_lifecycle.py",
        "surface_ref": "repo://architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json#lifecycle_partial_reissue",
        "semantic_test_ref": "repo://tests/unit/runtime/quality/test_policy_design_case_lifecycle.py#test_lifecycle_reissue_report_rejects_unscoped_events_without_whole_case_rewrite",
    },
    {
        "capability_id": "w4d_closeout_integration",
        "capability_name": "W4.D Closeout Integration",
        "reality_state": "implemented",
        "purpose": "closeout_input",
        "authority_scope": "can_i_closeout_i4_runtime_reader",
        "validation_profile": "production",
        "owner": "team-quality-closeout",
        "expiry": "2026-09-01",
        "hold_reason": "implemented in W4.D and closed in I4 manifest",
        "next_wave_target": "Wave 5 external closeout surfaces",
        "chain_id": "wave4-runtime-closeout",
        "research_refs": ["E3", "C3", "C24", "C31", "P01", "P04", "P05", "P10"],
        "no_adr_required": (
            "W4.D de-stubs the existing closeout reader over real upstream readers "
            "without allowing readiness, scorecard, or projection surfaces to mint closeout."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "check_can_i_closeout --reader-integration and production canary closeout",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_closeout_reader.py "
                "tests/repo_quality/tools/test_can_i_closeout.py -q"
            ),
            "rollback_or_reversal": "disable --reader-integration and fail closed to reader skeleton",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/closeout_reader.py#CLOSEOUT_INTEGRATION_SCHEMA_VERSION",
        "producer_ref": "repo://src/polisyos/runtime/quality/closeout_reader.py#build_can_i_closeout_verdict",
        "artifact_ref": "repo://architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json#can_i_closeout",
        "bridge_ref": "repo://src/polisyos/runtime/quality/closeout_reader.py#build_can_i_closeout_verdict_from_bundle_dir",
        "consumer_ref": "repo://tools/quality/validation/check_can_i_closeout.py",
        "verification_ref": "repo://tests/unit/runtime/quality/test_closeout_reader.py",
        "surface_ref": "repo://architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json#can_i_closeout",
        "semantic_test_ref": "repo://tests/unit/runtime/quality/test_closeout_reader.py#test_w4_closeout_preserves_upstream_blocker_when_readiness_and_scorecard_pass",
    },
    {
        "capability_id": "w4e_typed_pdc_projection_backend",
        "capability_name": "W4.E Typed PDC Projection Backend",
        "reality_state": "implemented",
        "purpose": "public_surface",
        "authority_scope": "typed_non_authority_projection_contract",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-09-01",
        "hold_reason": "implemented in W4.E and closed in I4 manifest",
        "next_wave_target": "Wave 5 public/reviewer/expert/machine consumer hardening",
        "chain_id": "wave4-runtime-closeout",
        "research_refs": ["E4", "C16", "C17", "C19", "C39a", "C39b", "P03", "P05", "P15"],
        "no_adr_required": (
            "W4.E exposes typed projection truth under projection_only authority; "
            "it does not create claim, closeout, or publication authority."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime API response shapes, OpenAPI, generated client, and projection contract fixtures",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py "
                "tests/unit/runtime/http/test_runtime_api_contract_hardening.py -q"
            ),
            "rollback_or_reversal": "remove policy_design_case_projection fields from runtime response DTOs",
        },
        "typed_contract_ref": "repo://src/polisyos/core/contracts/policy_design_case_projection.py#PolicyDesignCaseProjection",
        "producer_ref": "repo://src/polisyos/runtime/quality/projection_semantics.py#build_policy_design_case_projection_semantics",
        "artifact_ref": "repo://architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json#typed_policy_design_case_projection",
        "bridge_ref": "repo://src/polisyos/runtime/quality/projection_semantics.py#build_policy_design_case_projection_contract_fixture",
        "consumer_ref": "repo://src/polisyos/core/contracts/control.py#policy_design_case_projection",
        "verification_ref": "repo://tests/unit/runtime/http/test_runtime_api_contract_hardening.py",
        "surface_ref": "repo://schemas/runtime_api_v1.openapi.json#PolicyDesignCaseProjection",
        "semantic_test_ref": "repo://tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py#test_projection_contract_rejects_public_audience_hiding_blockers_or_contested_state",
    },
    {
        "capability_id": "w4i4_runtime_pdc_graph_closeout",
        "capability_name": "I4 Runtime PDC Graph And Closeout",
        "reality_state": "implemented",
        "purpose": "closeout_input",
        "authority_scope": "wave4_i4_real_multi_producer_runtime_graph",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-09-01",
        "hold_reason": "implemented as Wave 4 exit evidence",
        "next_wave_target": "Wave 5 external surface rollout",
        "chain_id": "wave4-i4-closeout",
        "research_refs": [
            "E3",
            "E4",
            "E7",
            "E13",
            "E15",
            "C3",
            "C8",
            "C16",
            "C20",
            "C29",
            "C31",
            "C40",
            "P01",
            "P02",
            "P05",
            "P10",
            "P12",
            "P14",
            "P15",
        ],
        "no_adr_required": (
            "I4 records integration evidence over W4 runtime outputs and does not "
            "change the accepted ADR authority boundaries."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "production canary I4 PDC graph and can_i_closeout evidence",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/tools/test_canary_evidence.py::test_assemble_canary_evidence_writes_wave4_i4_pdc_graph_and_closeout "
                "tests/unit/tools/test_canary_evidence.py::test_assemble_canary_evidence_preserves_scoped_lifecycle_reissue_as_i4_blocker -q"
            ),
            "rollback_or_reversal": "remove Wave 4 I4 graph and closeout readers from production canary evidence assembly",
        },
        "typed_contract_ref": "repo://tools/ops_runners/runtime/canary_evidence.py#_wave4_i4_graph",
        "producer_ref": "repo://tools/ops_runners/runtime/canary_evidence.py#_with_wave4_i4_policy_design_case_outputs",
        "artifact_ref": "repo://architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json#i4_policy_design_case_graph",
        "bridge_ref": "repo://tools/ops_runners/runtime/canary_evidence.py#_with_wave4_i4_closeout_verdict",
        "consumer_ref": "repo://src/polisyos/runtime/quality/closeout_reader.py#build_can_i_closeout_verdict",
        "verification_ref": "repo://tests/unit/tools/test_canary_evidence.py",
        "surface_ref": "repo://architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json#i4_policy_design_case_graph",
        "semantic_test_ref": "repo://tests/unit/tools/test_canary_evidence.py#test_assemble_canary_evidence_preserves_scoped_lifecycle_reissue_as_i4_blocker",
    },
    {
        "capability_id": "w5a_external_surfaces_truth",
        "capability_name": "W5.A Client, Dashboard, Export, And Audit",
        "reality_state": "implemented",
        "purpose": "public_surface",
        "authority_scope": "public_reviewer_expert_machine_truth_preserving_surfaces",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-10-01",
        "hold_reason": "implemented in W5.A and closed by I5 consumer truth evidence",
        "next_wave_target": "Wave 6 local/cloud validation",
        "chain_id": "wave5-external-surfaces",
        "research_refs": ["E5", "C39a", "P03", "P05", "P10"],
        "no_adr_required": (
            "W5.A consumes the accepted W4 typed projection and hardens external "
            "consumers without minting claim, scorecard, or closeout authority."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": (
                "public, reviewer, expert, machine, dashboard, public export, "
                "and external audit projection consumers"
            ),
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py "
                "tests/unit/runtime/quality/test_public_export.py "
                "tests/unit/runtime/quality/test_external_audit.py -q && "
                "corepack pnpm --dir apps/runtime-dashboard exec vitest run "
                "src/api/validators.test.ts"
            ),
            "rollback_or_reversal": (
                "disable Universal PDC projection and quarantine public/dashboard/"
                "API/export surfaces while preserving closeout and audit refs"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/core/contracts/policy_design_case_projection.py"
            "#PolicyDesignCaseProjection"
        ),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/projection_semantics.py"
            "#build_policy_design_case_projection_contract_fixture"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave5_i5_external_consumer_truth_manifest.json#w5a_external_surfaces_truth"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/projection_semantics.py"
            "#verify_policy_design_case_projection_consumer_contract"
        ),
        "consumer_ref": (
            "repo://apps/runtime-dashboard/src/api/validators.ts"
            "#policyDesignCaseProjectionSchema"
        ),
        "verification_ref": (
            "repo://tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py"
        ),
        "surface_ref": (
            "repo://architecture/policy_design_case/"
            "wave5_i5_external_consumer_truth_manifest.json#external_contract_fixtures"
        ),
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py"
            "#test_projection_contract_rejects_missing_omission_manifest_even_when_shape_passes"
        ),
    },
    {
        "capability_id": "w5b_semantic_evaluation_packs",
        "capability_name": "W5.B Semantic Evaluation Packs",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "split_aware_false_pass_semantic_benchmark",
        "validation_profile": "production",
        "owner": "team-evaluation",
        "expiry": "2026-10-01",
        "hold_reason": "implemented in W5.B as public, hidden, and rotating false-pass packs",
        "next_wave_target": "Wave 6 local/cloud validation",
        "chain_id": "wave5-semantic-evaluation",
        "research_refs": ["E22", "C30", "P10", "P14", "P15"],
        "no_adr_required": (
            "W5.B implements semantic false-pass benchmark governance over "
            "accepted Wave 0/W1 boundaries; tuned thresholds remain governed "
            "config and are not hardened here."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "repo-quality semantic fixture pack and benchmark metadata",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_semantic_gold_cards.py "
                "tests/repo_quality/tools/"
                "test_policy_design_case_w5b_semantic_evaluation_packs.py -q"
            ),
            "rollback_or_reversal": (
                "remove W5.B manifest registration and keep W1.B semantic fixtures "
                "as the baseline semantic false-pass guard"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/runtime/quality/semantic_fixtures.py"
            "#PolicyDesignCaseSemanticEvaluationPack"
        ),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/semantic_fixtures.py"
            "#evaluate_semantic_evaluation_pack"
        ),
        "artifact_ref": (
            "repo://tests/fixtures/policy_design_case/semantic_evaluation_packs/"
            "w5b_false_pass_pack_manifest.json"
        ),
        "bridge_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_design_case_w5b_semantic_evaluation_packs.py"
            "#test_w5b_semantic_evaluation_pack_manifest_is_reproducible_and_split_aware"
        ),
        "consumer_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_design_case_w5b_semantic_evaluation_packs.py"
        ),
        "verification_ref": "repo://tests/unit/runtime/quality/test_semantic_gold_cards.py",
        "surface_ref": (
            "repo://tests/fixtures/policy_design_case/semantic_evaluation_packs/README.md"
        ),
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_design_case_w5b_semantic_evaluation_packs.py"
            "#test_w5b_hidden_and_rotating_fixtures_are_not_public_detail_surfaces"
        ),
    },
    {
        "capability_id": "w5c_calibration_behavior",
        "capability_name": "W5.C Calibration Behavior",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "future_calibration_posture_without_current_evidence_closure",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-10-01",
        "hold_reason": "implemented in W5.C as warning/review first behavior",
        "next_wave_target": "Wave 6 rollout posture validation",
        "chain_id": "wave5-influence-boundaries",
        "research_refs": ["E20", "C35", "C41", "P07", "P09", "P10"],
        "no_adr_required": (
            "W5.C applies the existing calibration ledger as future posture only; "
            "mature blocking remains feature-flagged and governed."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": (
                "policy_design_case.calibration_mature_history_gates disabled "
                "unless mature governed evidence is present"
            ),
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_calibration_ledger.py -q"
            ),
            "rollback_or_reversal": (
                "disable policy_design_case.calibration_mature_history_gates and "
                "retain calibration as warning/review-only influence"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/runtime/quality/calibration_ledger.py"
            "#CalibrationBehaviorPolicy"
        ),
        "producer_ref": (
            "repo://src/polisyos/runtime/quality/calibration_ledger.py"
            "#calibration_behavior_scorecard_gates"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave5_i5_external_consumer_truth_manifest.json#w5c_calibration_behavior"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/scorecard.py"
            "#calibration_behavior_scorecard_gates"
        ),
        "consumer_ref": "repo://src/polisyos/runtime/quality/scorecard.py",
        "verification_ref": "repo://tests/unit/runtime/quality/test_calibration_ledger.py",
        "surface_ref": "repo://docs/reference/runtime/calibration-ledger.md",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_calibration_ledger.py"
            "#test_historical_prior_refs_fail_claim_registry_evidence_slots"
        ),
    },
    {
        "capability_id": "w5d_balanced_memory_behavior",
        "capability_name": "W5.D Balanced Memory Behavior",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "balanced_memory_future_influence_without_evidence_admission",
        "validation_profile": "production",
        "owner": "team-scientist-orchestration",
        "expiry": "2026-10-01",
        "hold_reason": "implemented in W5.D with scope, TTL, revocation, and contamination controls",
        "next_wave_target": "Wave 6 local/cloud validation",
        "chain_id": "wave5-influence-boundaries",
        "research_refs": ["E21", "C25", "C41", "P11", "P15"],
        "decision_refs": ["ADR-0172"],
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": (
                "Scientist balanced memory retrieval and Research DAG influence "
                "projection; no current evidence-slot admission"
            ),
            "canary_or_revalidation": (
                "uv run pytest tests/unit/scientist/orchestration/memory/test_balanced_memory.py "
                "tests/unit/runtime/quality/test_memory_influence_records.py "
                "tests/unit/scientist/orchestration/memory/test_research_dag_projection.py -q"
            ),
            "rollback_or_reversal": (
                "disable balanced-memory retrieval and keep failure-lesson storage "
                "without current-run influence"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/runtime/quality/memory_influence.py"
            "#MemoryInfluenceRecord"
        ),
        "producer_ref": (
            "repo://src/polisyos/scientist/orchestration/memory/retrieval.py"
            "#retrieve_balanced_memories"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave5_i5_external_consumer_truth_manifest.json#w5d_balanced_memory_behavior"
        ),
        "bridge_ref": (
            "repo://src/polisyos/scientist/methods/research_dag/projections.py"
            "#project_memory_influence_records_to_research_dag"
        ),
        "consumer_ref": (
            "repo://src/polisyos/runtime/quality/claim_registry.py"
            "#memory_influence_claim_evidence_issues"
        ),
        "verification_ref": (
            "repo://tests/unit/scientist/orchestration/memory/test_balanced_memory.py"
        ),
        "surface_ref": (
            "repo://architecture/policy_design_case/"
            "wave5_i5_external_consumer_truth_manifest.json#memory_boundary"
        ),
        "semantic_test_ref": (
            "repo://tests/unit/scientist/orchestration/memory/test_balanced_memory.py"
            "#test_balanced_memory_retrieval_rejects_scope_expiry_revocation_and_contamination"
        ),
    },
    {
        "capability_id": "w5e_operator_docs_runbooks",
        "capability_name": "W5.E Docs, Runbooks, And ADR Index",
        "reality_state": "implemented",
        "purpose": "public_surface",
        "authority_scope": "operator_lookup_and_rollout_rollback_bridge",
        "validation_profile": "production",
        "owner": "team-docs-platform",
        "expiry": "2026-10-01",
        "hold_reason": "implemented in W5.E as operator guide and rollout runbook",
        "next_wave_target": "Wave 6 rollout decision evidence",
        "chain_id": "wave5-operator-surfaces",
        "research_refs": ["E23", "C27", "P03", "P06", "P13"],
        "no_adr_required": (
            "W5.E creates operator bridge documentation over existing ADRs, "
            "evidence paths, feature flags, tuned configs, and runbooks."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": (
                "docs/reference operator guide, docs/runbooks rollout/rollback, "
                "MkDocs nav, and documentation inventory"
            ),
            "canary_or_revalidation": (
                "uv run pytest tests/repo_quality/tools/"
                "test_policy_design_case_w5e_docs_runbooks.py "
                "tests/repo_quality/tools/test_docs_lifecycle.py "
                "tests/repo_quality/tools/test_docs_gate.py -q"
            ),
            "rollback_or_reversal": (
                "revert W5.E operator guide/runbook/nav changes and keep W1.E "
                "evidence paths as fallback"
            ),
        },
        "typed_contract_ref": (
            "repo://docs/reference/policy-design-case-operator-guide.md"
            "#Capability-Evidence"
        ),
        "producer_ref": (
            "repo://docs/reference/policy-design-case-operator-guide.md"
            "#Tuned-Parameter-Owner-Ledger"
        ),
        "artifact_ref": "repo://docs/reference/policy-design-case-operator-guide.md",
        "bridge_ref": "repo://docs/reference/policy-design-case-evidence-paths.md",
        "consumer_ref": "repo://docs/reference/documentation-inventory.md",
        "verification_ref": (
            "repo://tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py"
        ),
        "surface_ref": "repo://architecture/tooling/mkdocs/nav/30-reference.yml",
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py"
            "#test_w5e_rejects_local_or_ephemeral_operator_paths"
        ),
    },
    {
        "capability_id": "w5i5_external_consumer_truth_check",
        "capability_name": "I5 External Consumer Truth Check",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "wave5_external_consumer_truth_preservation",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-10-01",
        "hold_reason": "implemented as Wave 5 exit evidence",
        "next_wave_target": "Wave 6 local/cloud validation",
        "chain_id": "wave5-i5-consumer-truth",
        "research_refs": [
            "E5",
            "E20",
            "E21",
            "E22",
            "E23",
            "C30",
            "C35",
            "C39a",
            "C41",
            "P03",
            "P05",
            "P10",
            "P11",
            "P14",
            "P15",
        ],
        "no_adr_required": (
            "I5 records integration evidence over W5 external, evaluation, "
            "calibration, memory, and operator surfaces without changing accepted "
            "ADR authority boundaries."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": (
                "Wave 5 external consumer truth manifest and capability ratchet report"
            ),
            "canary_or_revalidation": (
                "uv run pytest tests/repo_quality/tools/"
                "test_policy_design_case_capability_ratchet.py::"
                "test_wave5_exit_records_i5_manifest_and_influence_boundaries -q"
            ),
            "rollback_or_reversal": (
                "remove Wave 5 capability claims and I5 manifest before Wave 6 starts"
            ),
        },
        "typed_contract_ref": (
            "repo://docs/plans/active/"
            "POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
            "#I5 External consumer truth check"
        ),
        "producer_ref": (
            "repo://tools/quality/validation/check_policy_design_case_capability_ratchet.py"
            "#DEFAULT_CAPABILITY_CLAIMS"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave5_i5_external_consumer_truth_manifest.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/runtime/quality/projection_semantics.py"
            "#verify_policy_design_case_projection_consumer_contract"
        ),
        "consumer_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_design_case_capability_ratchet.py"
            "#test_wave5_exit_records_i5_manifest_and_influence_boundaries"
        ),
        "verification_ref": (
            "repo://tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py"
        ),
        "surface_ref": (
            "repo://architecture/policy_design_case/"
            "wave5_i5_external_consumer_truth_manifest.json"
        ),
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py"
            "#test_projection_contract_rejects_public_audience_hiding_blockers_or_contested_state"
        ),
    },
    {
        "capability_id": "w6a_local_validation_ladder",
        "capability_name": "W6.A Local Validation Ladder",
        "reality_state": "implemented",
        "purpose": "diagnostic_only",
        "authority_scope": "local_validation_command_evidence_and_outcome_metrics",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-11-01",
        "hold_reason": (
            "implemented as an executable local validation ladder; a green run "
            "or typed blocker output is runtime evidence, while useful-design "
            "capability still depends on corpus outcomes"
        ),
        "next_wave_target": "W6.B bundle/replay/inspection and W6.C cloud validation",
        "chain_id": "wave6-local-validation",
        "research_refs": ["E24", "C27", "P01", "P02", "P03", "P10", "P13", "P15"],
        "no_adr_required": (
            "W6.A implements the accepted validation ladder and metric split; it "
            "does not ratify new policy-domain thresholds or rollout posture."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": (
                "local command-evidence producer for unit, repo-quality, semantic, "
                "and local production-debug validation before cloud lanes"
            ),
            "canary_or_revalidation": (
                "uv run python tools/quality/validation/"
                "run_policy_design_case_local_validation_ladder.py --repo-root . "
                "--profile quick --output _build/.tmp/production-quality/"
                "universal_pdc_local_validation_ladder.json"
            ),
            "rollback_or_reversal": (
                "fall back to the raw W6 validation commands in the implementation "
                "plan and mark W6.A as verification_missing until the runner is repaired"
            ),
        },
        "typed_contract_ref": (
            "repo://tools/quality/validation/"
            "run_policy_design_case_local_validation_ladder.py#build_ladder_manifest"
        ),
        "producer_ref": (
            "repo://tools/quality/validation/"
            "run_policy_design_case_local_validation_ladder.py"
            "#run_local_validation_ladder"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave6_local_validation_ladder_manifest.json"
        ),
        "bridge_ref": (
            "repo://tools/quality/validation/"
            "run_policy_design_case_local_validation_ladder.py"
            "#build_local_outcome_metrics"
        ),
        "consumer_ref": (
            "repo://docs/runbooks/policy-design-case-rollout-rollback.md"
            "#4-local-validation"
        ),
        "verification_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_design_case_local_validation_ladder.py"
        ),
        "surface_ref": (
            "repo://docs/reference/policy-design-case-operator-guide.md"
            "#Validation-Ladder"
        ),
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/"
            "test_policy_design_case_local_validation_ladder.py"
            "#test_w6a_metrics_keep_closeout_honesty_and_useful_design_separate"
        ),
    },
    {
        "capability_id": "w6e_llm_formulator_critic_ensemble",
        "capability_name": "W6.E LLM Formulator + Multi-Critic Ensemble Producer",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "candidate_only_formulation_and_critic_laundering_guard",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-11-01",
        "hold_reason": (
            "implemented as a structured candidate-only producer and eight-basis "
            "critic ensemble; all outputs remain candidate_unverified until W6.F "
            "firewall admission"
        ),
        "next_wave_target": "W6.F hypothesis ledger + candidate-to-authority firewall",
        "chain_id": "wave6-universal-compilation-kernel",
        "research_refs": [
            "E22",
            "C4",
            "C5",
            "C9",
            "C12",
            "C19",
            "C26",
            "P05",
            "P10",
            "P12",
            "P15",
        ],
        "no_adr_required": (
            "W6.E implements the C12 candidate-side boundary over existing W0-W5 "
            "authority decisions and does not admit LLM content to any authority slot."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": (
                "candidate-only W6.E formulator and critic ensemble; downstream "
                "authority reads remain blocked until W6.F"
            ),
            "canary_or_revalidation": (
                "uv run pytest tests/unit/scientist/policy_design/test_formulator.py "
                "tests/unit/scientist/policy_design/test_critic_ensemble.py -q"
            ),
            "rollback_or_reversal": (
                "remove W6.E lazy exports and capability claim; old policy_design "
                "critic/adversary modules remain unchanged"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/scientist/policy_design/formulator.py"
            "#FormulatorCandidate"
        ),
        "producer_ref": (
            "repo://src/polisyos/scientist/policy_design/formulator.py"
            "#LLMFormulator"
        ),
        "artifact_ref": (
            "repo://architecture/policy_design_case/"
            "wave6e_llm_formulator_critic_ensemble_manifest.json"
        ),
        "bridge_ref": (
            "repo://src/polisyos/scientist/policy_design/formulator.py"
            "#InMemoryHypothesisLedger"
        ),
        "consumer_ref": (
            "repo://tests/unit/scientist/policy_design/test_critic_ensemble.py"
        ),
        "verification_ref": (
            "repo://tests/unit/scientist/policy_design/test_formulator.py"
        ),
        "surface_ref": (
            "repo://architecture/policy_design_case/"
            "wave6e_llm_formulator_critic_ensemble_manifest.json"
        ),
        "semantic_test_ref": (
            "repo://tests/unit/scientist/policy_design/test_critic_ensemble.py"
            "#test_affected_person_critic_flags_preference_speculation_without_provenance"
        ),
    },
    {
        "capability_id": "w6a_universal_policy_grammar_compiler",
        "capability_name": "W6.A Universal Policy Grammar Compiler",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "intent_to_universal_policy_design_case_facets",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-11-01",
        "hold_reason": (
            "implemented as deterministic facet compiler plus W6.C consumer bridge; "
            "producer adapters are explicitly out of scope until Wave 7"
        ),
        "next_wave_target": "Wave 7 requirement compilers",
        "chain_id": "wave6-universal-compilation-kernel",
        "research_refs": ["E24", "C4", "C6", "C11", "C28", "P02", "P05", "P15"],
        "no_adr_required": (
            "W6.A reuses existing IR governance enums and W2.A concept-spine refs "
            "without changing accepted authority semantics."
        ),
        "reuse_classification": "build_new",
        "rejected_reuse_evidence": [
            "ProblemFrame and PolicySpec describe policy intent but do not emit the "
            "universal facet algebra required by downstream compilers.",
            "ConstraintCritic and challenge_factory expose signal vocabularies but "
            "are not typed facet producers.",
        ],
        "rollout_refs": {
            "feature_flag_or_scope": "Wave 6 compilation-only producer, no adapter invocation",
            "canary_or_revalidation": "uv run pytest tests/unit/policy_grammar -q",
            "rollback_or_reversal": (
                "mark w6a_universal_policy_grammar_compiler producer_missing and "
                "block Wave 7 requirement compilation"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/core/contracts/runtime.py#UniversalPolicyDesignCase",
        "producer_ref": "repo://src/polisyos/policy_grammar/__init__.py#PolicyGrammarCompiler",
        "artifact_ref": "repo://src/polisyos/policy_grammar/__init__.py#persist_universal_policy_design_case",
        "bridge_ref": "repo://src/polisyos/policy_grammar/__init__.py#facet_snapshots_for_obligation_graph",
        "consumer_ref": "repo://src/polisyos/obligation_graph/__init__.py#compile_obligation_graph",
        "verification_ref": "repo://tests/unit/policy_grammar/test_universal_policy_grammar_compiler.py",
        "surface_ref": "repo://src/polisyos/policy_grammar/__init__.py#facet_snapshots_for_obligation_graph",
        "semantic_test_ref": (
            "repo://tests/unit/policy_grammar/test_universal_policy_grammar_compiler.py"
            "#test_compiler_emits_typed_facets_for_three_diverse_policy_intents"
        ),
    },
    {
        "capability_id": "w6b_governed_obligation_rule_catalog",
        "capability_name": "W6.B Governed Obligation Rule Catalog",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "governed_obligation_rulebook_with_replay_metadata",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-11-01",
        "hold_reason": "implemented with 50+ governed seed rules and W2.B rule-evolution bridge",
        "next_wave_target": "Wave 7 requirement compilers",
        "chain_id": "wave6-universal-compilation-kernel",
        "research_refs": ["E24", "C5", "C21", "C33", "P06", "P07", "P15"],
        "no_adr_required": (
            "W6.B seeds governed compilation rules and routes evolution through W2.B; "
            "it does not admit LLM candidates without governance decisions."
        ),
        "reuse_classification": "build_new",
        "rejected_reuse_evidence": [
            "W2.B owns replay/evolution refs but not the governed obligation taxonomy.",
            "policy_design objectives/critic/adversary modules emit signals, not a "
            "versioned rulebook."
        ],
        "rollout_refs": {
            "feature_flag_or_scope": "governed obligation catalog for Wave 6 compilation only",
            "canary_or_revalidation": "uv run pytest tests/unit/obligation_rules -q",
            "rollback_or_reversal": (
                "withdraw catalog capability claim and prevent W6.C governed-rule "
                "promotion until rules are readmitted"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/obligation_rules/catalog.py#ObligationRule",
        "producer_ref": "repo://src/polisyos/obligation_rules/catalog.py#build_seed_obligation_rule_catalog",
        "artifact_ref": "repo://src/polisyos/obligation_rules/catalog.py#persist_obligation_rule_catalog",
        "bridge_ref": "repo://src/polisyos/obligation_rules/catalog.py#build_rule_evolution_registry_for_catalog",
        "consumer_ref": "repo://src/polisyos/obligation_graph/_impl/compiler.py#_adapt_obligation_rule_catalog_row",
        "verification_ref": "repo://tests/unit/obligation_rules/test_catalog.py",
        "surface_ref": "repo://src/polisyos/obligation_rules/catalog.py#governed_rule_catalog_public_surface",
        "semantic_test_ref": (
            "repo://tests/unit/obligation_rules/test_catalog.py"
            "#test_seed_catalog_has_required_governed_rules_and_family_coverage"
        ),
    },
    {
        "capability_id": "w6c_obligation_graph_compiler",
        "capability_name": "W6.C Obligation Graph Compiler",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "candidate_bundle_frontier_obligation_ledgers",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-11-01",
        "hold_reason": "implemented with candidate ledger, bundle dedupe, blocking frontier, and LLM ceiling guard",
        "next_wave_target": "Wave 7 requirement compilers",
        "chain_id": "wave6-universal-compilation-kernel",
        "research_refs": ["E24", "C4", "C5", "C12", "C22", "C38", "P02", "P13", "P14", "P15"],
        "no_adr_required": (
            "W6.C compiles governed obligations under existing authority/status "
            "boundaries and keeps producer adapter execution out of scope."
        ),
        "reuse_classification": "build_new",
        "rejected_reuse_evidence": [
            "Temporal logic and deterministic critics expose obligation-like signals "
            "but no three-tier candidate/bundle/frontier ledger.",
            "Existing closeout readers consume blockers but do not compile governed "
            "obligation candidates."
        ],
        "rollout_refs": {
            "feature_flag_or_scope": "Wave 6 obligation compilation artifact only",
            "canary_or_revalidation": "uv run pytest tests/unit/obligation_graph -q",
            "rollback_or_reversal": (
                "mark w6c_obligation_graph_compiler producer_missing and block "
                "Wave 7 obligation-driven requirement compilation"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/obligation_graph/__init__.py#ObligationGraph",
        "producer_ref": "repo://src/polisyos/obligation_graph/__init__.py#compile_obligation_graph",
        "artifact_ref": "repo://src/polisyos/obligation_graph/__init__.py#write_obligation_graph_artifact",
        "bridge_ref": "repo://src/polisyos/obligation_graph/_impl/compiler.py#_adapt_obligation_rule_catalog_row",
        "consumer_ref": "repo://src/polisyos/scientist/policy_design/claim_decomposition.py#ClaimDecompositionObligation",
        "verification_ref": "repo://tests/unit/obligation_graph/test_compiler.py",
        "surface_ref": "repo://src/polisyos/obligation_graph/__init__.py#obligation_graph_audit_surface",
        "semantic_test_ref": (
            "repo://tests/unit/obligation_graph/test_compiler.py"
            "#test_compiler_consumes_policy_grammar_case_and_governed_rule_catalog"
        ),
    },
    {
        "capability_id": "w6d_claim_decomposition_compiler",
        "capability_name": "W6.D Claim Decomposition Compiler",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "typed_claim_family_baseline_alternative_seed_records",
        "validation_profile": "production",
        "owner": "team-policyos-runtime",
        "expiry": "2026-11-01",
        "hold_reason": "implemented with typed claim-family assignments, baselines, alternatives, and registry guard",
        "next_wave_target": "Wave 7 method validity requirement compilation",
        "chain_id": "wave6-universal-compilation-kernel",
        "research_refs": ["E24", "C2", "C7", "C9", "C10", "C18", "C34", "P02", "P15"],
        "no_adr_required": (
            "W6.D emits pre-evidence claim seeds and method preconditions; final "
            "method choices remain owned by Wave 7+ producer validation."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "claim decomposition seed records before producer evidence",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/scientist/policy_design/test_claim_decomposition.py "
                "tests/unit/runtime/quality/test_claim_registry.py -q"
            ),
            "rollback_or_reversal": (
                "disable claim-decomposition consumer bridge and keep superiority "
                "claims out of runtime claim registry"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/scientist/evidence/claims/models.py#ClaimFamilyAssignment",
        "producer_ref": "repo://src/polisyos/scientist/policy_design/claim_decomposition.py#ClaimDecompositionCompiler",
        "artifact_ref": "repo://src/polisyos/scientist/evidence/claims/models.py#ClaimLedger",
        "bridge_ref": "repo://src/polisyos/runtime/quality/claim_registry.py#runtime_claim_registry_superiority_comparator_refs_missing",
        "consumer_ref": "repo://src/polisyos/runtime/quality/claim_registry.py#build_runtime_claim_registry",
        "verification_ref": "repo://tests/unit/scientist/policy_design/test_claim_decomposition.py",
        "surface_ref": "repo://docs/reference/scientist/claim-ledger.md",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_claim_registry.py"
            "#test_superiority_claim_requires_baseline_and_named_alternative_refs"
        ),
    },
    {
        "capability_id": "w6f_hypothesis_ledger_candidate_firewall",
        "capability_name": "W6.F Hypothesis Ledger + Candidate-To-Authority Firewall",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "candidate_hypothesis_persistence_and_consumer_firewall",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-11-01",
        "hold_reason": "implemented with runtime hypothesis ledger, candidate refs, and claim-registry consumer enforcement",
        "next_wave_target": "Wave 7 requirement compiler read surfaces",
        "chain_id": "wave6-universal-compilation-kernel",
        "research_refs": ["E22", "E24", "C2", "C5", "C9", "C12", "C17", "C19", "C41", "P05", "P10", "P15"],
        "no_adr_required": (
            "W6.F enforces the existing W0-W5 authority boundary: candidate output "
            "may be visible but cannot satisfy protected slots without validation."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime-quality candidate firewall on claim-registry and projection read paths",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/runtime/quality/test_hypothesis_ledger.py "
                "tests/unit/runtime/quality/test_candidate_firewall.py -q"
            ),
            "rollback_or_reversal": (
                "remove candidate refs from authority-slot readers and mark W6.F "
                "bridge_missing until firewall validation is restored"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/hypothesis_ledger.py#HypothesisLedger",
        "producer_ref": "repo://src/polisyos/scientist/policy_design/formulator.py#FormulatorCandidate",
        "artifact_ref": "repo://src/polisyos/runtime/quality/hypothesis_ledger.py#persist_hypothesis_ledger",
        "bridge_ref": "repo://src/polisyos/runtime/quality/candidate_firewall.py#assert_no_candidate_authority_laundering",
        "consumer_ref": "repo://src/polisyos/runtime/quality/claim_registry.py#_candidate_firewall_issues",
        "verification_ref": "repo://tests/unit/runtime/quality/test_hypothesis_ledger.py",
        "surface_ref": "repo://src/polisyos/runtime/quality/candidate_firewall.py#candidate_firewall_issues_for_payload",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_candidate_firewall.py"
            "#test_unverified_candidate_ref_is_blocked_at_consumer_read_surface"
        ),
    },
    {
        "capability_id": "w9a_drift_detector_implementations",
        "capability_name": "W9.A Drift Detector Implementations",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "continuous_governance_drift_event_production",
        "validation_profile": "production",
        "owner": "team-scientist-governance",
        "expiry": "2026-12-01",
        "hold_reason": "implemented with calibration, fairness, policy-context, and source-invalidation detector producers",
        "next_wave_target": "Wave 10 lifecycle/public-surface hardening",
        "chain_id": "wave9-advanced-lifecycle-drift-replay",
        "research_refs": ["E15", "E20", "E21", "C20", "C25", "C33", "P01", "P02", "P07", "P09", "P11"],
        "no_adr_required": (
            "W9.A wires detector producers into existing continuous-governance event "
            "contracts and sparse-history policy without introducing new authority thresholds."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "continuous governance drift detectors over calibration, fairness, policy context, and source invalidation",
            "canary_or_revalidation": "uv run pytest tests/unit/scientist/governance/continuous/detectors -q",
            "rollback_or_reversal": "mark W9.A producer_missing and route closed PDC drift handling through lifecycle blocker only",
        },
        "typed_contract_ref": "repo://src/polisyos/scientist/governance/continuous/monitors.py#GovernanceMonitorEvent",
        "producer_ref": "repo://src/polisyos/scientist/governance/continuous/detectors",
        "artifact_ref": "repo://src/polisyos/scientist/governance/continuous/detectors/common.py#DriftDetectionResult",
        "bridge_ref": "repo://src/polisyos/scientist/governance/continuous/lifecycle_bridge.py#bridge_governance_events_to_claim_lifecycle",
        "consumer_ref": "repo://src/polisyos/scientist/governance/continuous/reports.py#export_public_validity_report",
        "verification_ref": "repo://tests/unit/scientist/governance/continuous/detectors/test_drift_detectors.py",
        "surface_ref": "repo://src/polisyos/scientist/governance/continuous/reports.py#export_public_validity_report",
        "semantic_test_ref": (
            "repo://tests/unit/scientist/governance/continuous/detectors/test_drift_detectors.py"
            "#test_calibration_detector_blocks_only_mature_governed_adverse_history"
        ),
    },
    {
        "capability_id": "w9b_partial_scope_reissue_mechanics",
        "capability_name": "W9.B Partial-Scope Reissue Mechanics",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "claim_scoped_reissue_with_historical_meaning_preserved",
        "validation_profile": "production",
        "owner": "team-scientist-governance",
        "expiry": "2026-12-01",
        "hold_reason": "implemented with scope_to_revise, unchanged_records, superseded_refs, public_diff_refs, and partial_publication_state",
        "next_wave_target": "Wave 10 public revision dashboard/API projection",
        "chain_id": "wave9-advanced-lifecycle-drift-replay",
        "research_refs": ["E15", "E20", "C20", "C33", "P02", "P04", "P07", "P08", "P09"],
        "no_adr_required": (
            "W9.B extends the existing reissue packet and W4.C lifecycle semantics "
            "to claim-scoped publication state without changing closed-case meaning rules."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "partial-scope reissue packets for detector-affected claim ids",
            "canary_or_revalidation": "uv run pytest tests/unit/scientist/governance/continuous/test_reissue_partial_scope.py -q",
            "rollback_or_reversal": "reject partial-scope packets and mark W9.B producer_missing while keeping whole-case reissue semantics",
        },
        "typed_contract_ref": "repo://src/polisyos/scientist/governance/continuous/reissue.py#ReissuePacket",
        "producer_ref": "repo://src/polisyos/scientist/governance/continuous/reissue.py#build_partial_scope_reissue_packet",
        "artifact_ref": "repo://src/polisyos/scientist/governance/continuous/reissue.py#persist_reissue_packet",
        "bridge_ref": "repo://src/polisyos/scientist/governance/continuous/lifecycle_bridge.py#build_partial_scope_reissue_packet",
        "consumer_ref": "repo://src/polisyos/scientist/governance/continuous/lifecycle_bridge.py#public_revision_state",
        "verification_ref": "repo://tests/unit/scientist/governance/continuous/test_reissue_partial_scope.py",
        "surface_ref": "repo://src/polisyos/scientist/governance/continuous/reissue.py#PartialPublicationState",
        "semantic_test_ref": (
            "repo://tests/unit/scientist/governance/continuous/test_reissue_partial_scope.py"
            "#test_partial_scope_builder_rejects_unscoped_detector_event"
        ),
    },
    {
        "capability_id": "w9c_data_forge_snapshot_provenance_manifest",
        "capability_name": "W9.C Data Forge Snapshot Provenance Manifest",
        "reality_state": "implemented",
        "purpose": "closeout_input",
        "authority_scope": "official_snapshot_claim_authority_with_manifest_provenance",
        "validation_profile": "production",
        "owner": "team-data-forge",
        "expiry": "2026-12-01",
        "hold_reason": "implemented with durable snapshot provenance manifest and closeout-grade official snapshot answer",
        "next_wave_target": "Wave 10 universal-corpus fixture expansion",
        "chain_id": "wave9-advanced-lifecycle-drift-replay",
        "research_refs": ["E11", "E15", "C3", "C20", "C33", "P03", "P07", "P08", "P09", "P12"],
        "no_adr_required": (
            "W9.C persists provenance for existing Data Forge snapshot transactions "
            "and binds closeout answers to official manifests without adding new data authority roles."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "Data Forge snapshot finalize and closeout snapshot-binding reader",
            "canary_or_revalidation": "uv run pytest tests/unit/data_forge/test_provenance_manifest.py -q",
            "rollback_or_reversal": "block closeout-grade Data Forge snapshot authority on missing provenance_manifest_ref",
        },
        "typed_contract_ref": "repo://src/polisyos/data_forge/__init__.py#SnapshotProvenanceManifest",
        "producer_ref": "repo://src/polisyos/data_forge/__init__.py#write_snapshot_provenance_manifest",
        "artifact_ref": "repo://src/polisyos/data_forge/__init__.py#DATA_FORGE_PROVENANCE_MANIFEST_FILE",
        "bridge_ref": "repo://src/polisyos/data_forge/kernel/snapshot/finalize.py#provenance_manifest_ref",
        "consumer_ref": "repo://src/polisyos/runtime/quality/data_forge_binding.py#official_data_forge_snapshot_for_claim",
        "verification_ref": "repo://tests/unit/data_forge/test_provenance_manifest.py",
        "surface_ref": "repo://src/polisyos/runtime/quality/data_forge_binding.py#official_data_forge_snapshot_for_claim",
        "semantic_test_ref": (
            "repo://tests/unit/data_forge/test_provenance_manifest.py"
            "#test_snapshot_without_provenance_manifest_ref_cannot_satisfy_closeout_authority"
        ),
    },
    {
        "capability_id": "w9d_memory_decay_ttl_contamination_controls",
        "capability_name": "W9.D Memory Decay, TTL, And Contamination Controls",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "balanced_memory_future_influence_with_decay_and_revocation",
        "validation_profile": "production",
        "owner": "team-scientist-orchestration",
        "expiry": "2026-12-01",
        "hold_reason": "implemented with TTL, influence decay, contamination policy, scope revocation, and conservative-bias metrics",
        "next_wave_target": "Wave 10 memory audit/export surfaces",
        "chain_id": "wave9-advanced-lifecycle-drift-replay",
        "research_refs": ["E14", "E21", "C20", "C33", "P07", "P09", "P11", "P15"],
        "no_adr_required": (
            "W9.D strengthens existing W2.F/W5.D balanced memory boundaries so memory "
            "remains future influence rather than evidence or authority."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "balanced/reflexive memory retrieval, decay, contamination rejection, and scope revocation",
            "canary_or_revalidation": "uv run pytest tests/unit/scientist/orchestration/memory/test_decay_and_contamination.py -q",
            "rollback_or_reversal": "disable decayed memory retrieval influence and mark W9.D producer_missing until TTL/revocation semantics are restored",
        },
        "typed_contract_ref": "repo://src/polisyos/scientist/orchestration/memory/balanced.py#BalancedMemoryDecayPolicy",
        "producer_ref": "repo://src/polisyos/scientist/orchestration/memory/retrieval.py#retrieve_balanced_memories",
        "artifact_ref": "repo://src/polisyos/scientist/orchestration/memory/balanced.py#BalancedMemoryApplicability",
        "bridge_ref": "repo://src/polisyos/scientist/orchestration/memory/failure_lessons.py#revoke_balanced_scope",
        "consumer_ref": "repo://src/polisyos/scientist/governance/continuous/detectors/common.py#balanced_memory_context",
        "verification_ref": "repo://tests/unit/scientist/orchestration/memory/test_decay_and_contamination.py",
        "surface_ref": "repo://src/polisyos/scientist/orchestration/memory/retrieval.py#conservative_bias_metrics",
        "semantic_test_ref": (
            "repo://tests/unit/scientist/orchestration/memory/test_decay_and_contamination.py"
            "#test_warning_only_failure_lesson_older_than_default_ttl_cannot_influence"
        ),
    },
    {
        "capability_id": "w9e_continuous_governance_lifecycle_bridge",
        "capability_name": "W9.E Continuous Governance Event To Claim Lifecycle Bridge",
        "reality_state": "implemented",
        "purpose": "lifecycle_trigger",
        "authority_scope": "detector_event_to_claim_lifecycle_transition",
        "validation_profile": "production",
        "owner": "team-scientist-governance",
        "expiry": "2026-12-01",
        "hold_reason": "implemented with typed event-to-lifecycle transition records, public revision state, and missing-bridge blocker",
        "next_wave_target": "Wave 10 lifecycle dashboard/API bridge",
        "chain_id": "wave9-advanced-lifecycle-drift-replay",
        "research_refs": ["E15", "E20", "C20", "C33", "P02", "P04", "P07", "P09"],
        "no_adr_required": (
            "W9.E implements the C20 lifecycle dependency over existing continuous "
            "governance events and W9.B partial reissue semantics."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "continuous-governance detector event bridge into claim lifecycle and public revision projection",
            "canary_or_revalidation": "uv run pytest tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py -q",
            "rollback_or_reversal": "emit event_missing_lifecycle_bridge blockers and prevent silent closed-PDC stale state",
        },
        "typed_contract_ref": "repo://src/polisyos/scientist/governance/continuous/lifecycle_bridge.py#LifecycleBridgeResult",
        "producer_ref": "repo://src/polisyos/scientist/governance/continuous/lifecycle_bridge.py#bridge_governance_events_to_claim_lifecycle",
        "artifact_ref": "repo://src/polisyos/scientist/governance/continuous/lifecycle_bridge.py#persist_lifecycle_bridge_result",
        "bridge_ref": "repo://src/polisyos/scientist/governance/continuous/lifecycle_bridge.py#GovernanceMonitorEvent -> ClaimLifecycleEvent -> public revision state",
        "consumer_ref": "repo://src/polisyos/scientist/governance/continuous/reports.py#export_public_validity_report",
        "verification_ref": "repo://tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py",
        "surface_ref": "repo://src/polisyos/scientist/governance/continuous/lifecycle_bridge.py#public_revision_state",
        "semantic_test_ref": (
            "repo://tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py"
            "#test_unscoped_detector_event_produces_missing_lifecycle_bridge_blocker"
        ),
    },
    {
        "capability_id": "w9f_rule_evolution_replay_engine",
        "capability_name": "W9.F Rule Evolution Replay Engine",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "closed_pdc_original_vs_new_rule_replay_and_revalidation",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-12-01",
        "hold_reason": "implemented with original/new rule replay, comparison reports, research-DAG replay, and C33 mandatory revalidation triggers",
        "next_wave_target": "Wave 10 replay export and case-portfolio revalidation scheduling",
        "chain_id": "wave9-advanced-lifecycle-drift-replay",
        "research_refs": ["E7", "E15", "C20", "C33", "P04", "P07", "P08", "P09"],
        "no_adr_required": (
            "W9.F executes replay using the W2.B rule-evolution registry and the "
            "accepted C33 change-class table rather than creating new replay policy."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime-quality closed-PDC rule replay and comparison reports",
            "canary_or_revalidation": "uv run pytest tests/unit/runtime/quality/test_rule_replay_engine.py -q",
            "rollback_or_reversal": "mark rule replay producer_missing and require manual revalidation blockers for C33 mandatory classes",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/rule_replay_engine.py#RULE_REPLAY_CONTRACT_ID",
        "producer_ref": "repo://src/polisyos/runtime/quality/rule_replay_engine.py#build_rule_replay_comparison_report",
        "artifact_ref": "repo://src/polisyos/runtime/quality/rule_replay_engine.py#persist_rule_replay_comparison_report",
        "bridge_ref": "repo://src/polisyos/runtime/quality/rule_replay_engine.py#W2.B rule registry -> research-DAG replay -> claim lifecycle",
        "consumer_ref": "repo://src/polisyos/runtime/quality/case_lifecycle.py#build_lifecycle_reissue_report",
        "verification_ref": "repo://tests/unit/runtime/quality/test_rule_replay_engine.py",
        "surface_ref": "repo://src/polisyos/runtime/quality/rule_replay_engine.py#public_comparison_report",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_rule_replay_engine.py"
            "#test_comparison_report_triggers_mandatory_revalidation_and_claim_lifecycle"
        ),
    },
    {
        "capability_id": "w9i9_lifecycle_drift_smoke",
        "capability_name": "I9 Lifecycle Drift Smoke",
        "reality_state": "implemented",
        "purpose": "diagnostic_only",
        "authority_scope": "wave9_exit_acceptance_evidence",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2026-12-01",
        "hold_reason": "implemented as an integration smoke over detector, partial reissue, lifecycle bridge, provenance, memory decay, and rule replay",
        "next_wave_target": "Wave 10 advanced lifecycle acceptance baseline",
        "chain_id": "wave9-advanced-lifecycle-drift-replay",
        "research_refs": ["E15", "E20", "E21", "C20", "C33", "P01", "P02", "P07", "P09"],
        "no_adr_required": (
            "I9 records Wave 9 integration evidence and does not introduce new "
            "policy authority semantics beyond the implemented phase capabilities."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "Wave 9 lifecycle drift smoke across advanced lifecycle capabilities",
            "canary_or_revalidation": "uv run pytest tests/repo_quality/tools/test_lifecycle_drift_smoke.py -q",
            "rollback_or_reversal": "treat Wave 9 exit as blocked until smoke emits either closed lifecycle drift flow or typed lifecycle blocker",
        },
        "typed_contract_ref": "repo://docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md#Wave-9---Advanced-Lifecycle-Drift-Detection-And-Rule-Replay",
        "producer_ref": "repo://tests/repo_quality/tools/test_lifecycle_drift_smoke.py#test_i9_lifecycle_drift_smoke_runs_detector_to_partial_reissue_and_rule_replay",
        "artifact_ref": "repo://architecture/policy_design_case/capability_reality_report.json#w9i9_lifecycle_drift_smoke",
        "bridge_ref": "repo://tests/repo_quality/tools/test_lifecycle_drift_smoke.py#bridge_governance_events_to_claim_lifecycle",
        "consumer_ref": "repo://tools/quality/validation/check_policy_design_case_capability_ratchet.py#validate_capability_reality_report",
        "verification_ref": "repo://tests/repo_quality/tools/test_lifecycle_drift_smoke.py",
        "surface_ref": "repo://architecture/policy_design_case/capability_reality_report.json#w9i9_lifecycle_drift_smoke",
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/test_lifecycle_drift_smoke.py"
            "#test_i9_lifecycle_drift_smoke_runs_detector_to_partial_reissue_and_rule_replay"
        ),
    },
    {
        "capability_id": "w10a_bounded_liveness_deadline_invariants",
        "capability_name": "W10.A Bounded-Liveness Deadline Invariants",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "producer_pipeline_retry_lease_escalation_reissue_liveness",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2027-01-15",
        "hold_reason": "implemented with temporal invariant specs, model checks, and trace-level deadline consistency checks",
        "next_wave_target": "Wave 11 outcome-corpus liveness regression coverage",
        "chain_id": "wave10-temporal-cost-fmea-depth",
        "research_refs": ["E3", "E19", "C24", "C40", "P01", "P02", "P07", "P08", "P09", "P10"],
        "decision_refs": ["ADR-0169"],
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "runtime-quality formal invariant registry and bounded-liveness trace checker",
            "canary_or_revalidation": "uv run pytest tests/unit/runtime/quality/test_formal_invariants.py -q",
            "rollback_or_reversal": "mark W10.A producer_missing and keep finite-state invariants as the only formal closeout check",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/formal_invariants.py#REQUIRED_TEMPORAL_LIVENESS_INVARIANT_IDS",
        "producer_ref": "repo://src/polisyos/runtime/quality/formal_invariants.py#check_bounded_liveness_deadline_consistency",
        "artifact_ref": "repo://architecture/policy_design_case/formal_invariant_specs.toml#bounded_liveness_producer_pipeline",
        "bridge_ref": "repo://src/polisyos/runtime/quality/formal_invariants.py#model_check_formal_invariant_specs",
        "consumer_ref": "repo://src/polisyos/runtime/quality/formal_invariants.py#build_formal_invariant_spec_report",
        "verification_ref": "repo://tests/unit/runtime/quality/test_formal_invariants.py",
        "surface_ref": "repo://architecture/policy_design_case/formal_invariant_specs.toml#bounded_liveness_retry_lease",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_formal_invariants.py"
            "#test_bounded_liveness_flags_producer_wait_past_deadline_without_escalation"
        ),
    },
    {
        "capability_id": "w10b_review_effectiveness_measurement",
        "capability_name": "W10.B Review Effectiveness Measurement Pipeline",
        "reality_state": "implemented",
        "purpose": "diagnostic_only",
        "authority_scope": "advisory_review_effectiveness_measurement",
        "validation_profile": "production",
        "owner": "team-scientist-governance",
        "expiry": "2027-01-15",
        "hold_reason": "implemented as advisory-only VOI metadata measurement with CAS public export",
        "next_wave_target": "Wave 11 longitudinal review corpus calibration",
        "chain_id": "wave10-temporal-cost-fmea-depth",
        "research_refs": ["E19", "C24", "P05", "P09", "P10", "P13"],
        "decision_refs": ["ADR-0171"],
        "reuse_classification": "wire_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "human-review VOI metadata measurement in advisory posture only",
            "canary_or_revalidation": "uv run pytest tests/unit/scientist/governance/human_review/test_effectiveness.py -q",
            "rollback_or_reversal": "remove review_effectiveness public export while keeping runtime human-review calibration defaults",
        },
        "typed_contract_ref": "repo://src/polisyos/scientist/governance/human_review/effectiveness.py#ReviewEffectivenessReport",
        "producer_ref": "repo://src/polisyos/scientist/governance/human_review/effectiveness.py#build_review_effectiveness_report",
        "artifact_ref": "repo://src/polisyos/scientist/governance/human_review/effectiveness.py#persist_review_effectiveness_report",
        "bridge_ref": "repo://src/polisyos/runtime/quality/human_review.py#build_human_review_calibration_report",
        "consumer_ref": "repo://src/polisyos/scientist/governance/human_review/effectiveness.py#review_effectiveness_public_export",
        "verification_ref": "repo://tests/unit/scientist/governance/human_review/test_effectiveness.py",
        "surface_ref": "repo://src/polisyos/scientist/governance/human_review/effectiveness.py#review_effectiveness_public_export",
        "semantic_test_ref": (
            "repo://tests/unit/scientist/governance/human_review/test_effectiveness.py"
            "#test_effectiveness_pipeline_measures_voi_metadata_as_advisory_only"
        ),
    },
    {
        "capability_id": "w10c_missing_r14_adversarial_probes",
        "capability_name": "W10.C Missing R14 Adversarial Probes",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "authority_spoofing_prompt_injection_participation_speculation_semantic_probe",
        "validation_profile": "production",
        "owner": "team-evaluation",
        "expiry": "2027-01-15",
        "hold_reason": "implemented with three deterministic probe classes and repo-owned structural-pass fixtures",
        "next_wave_target": "Wave 11 universal outcome corpus adversarial regression pack",
        "chain_id": "wave10-temporal-cost-fmea-depth",
        "research_refs": ["E22", "C19", "C26", "P05", "P10", "P15"],
        "no_adr_required": "W10.C adds semantic probes for already accepted authority boundaries and does not introduce a new threshold.",
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "scientist eval challenge factory R14 probe registry and fixtures",
            "canary_or_revalidation": "uv run pytest tests/unit/scientist/evals/test_challenge_factory_extensions.py -q",
            "rollback_or_reversal": "remove the W10.C probe registry entries and mark R14 coverage semantic_test_missing",
        },
        "typed_contract_ref": "repo://src/polisyos/scientist/evals/challenge_factory.py#R14AdversarialProbeFixture",
        "producer_ref": "repo://src/polisyos/scientist/evals/challenge_factory.py#evaluate_r14_adversarial_probe_fixture",
        "artifact_ref": "repo://tests/fixtures/policy_design_case/w10c_adversarial_probes",
        "bridge_ref": "repo://src/polisyos/scientist/evals/challenge_factory.py#R14_ADVERSARIAL_PROBES",
        "consumer_ref": "repo://tests/unit/scientist/evals/test_challenge_factory_extensions.py#test_w10c_adversarial_probe_fixtures_fire_expected_semantic_failures",
        "verification_ref": "repo://tests/unit/scientist/evals/test_challenge_factory_extensions.py",
        "surface_ref": "repo://tests/fixtures/policy_design_case/w10c_adversarial_probes",
        "semantic_test_ref": (
            "repo://tests/unit/scientist/evals/test_challenge_factory_extensions.py"
            "#test_w10c_adversarial_probe_fixtures_fire_expected_semantic_failures"
        ),
    },
    {
        "capability_id": "w10d_authority_level_run_cost_gate",
        "capability_name": "W10.D Authority-Level Run-Cost Enforcement Gate",
        "reality_state": "implemented",
        "purpose": "closeout_input",
        "authority_scope": "production_run_cost_budget_blocking_and_research_limitation",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2027-01-15",
        "hold_reason": "implemented with W2.C telemetry ingestion, authority-level policy refs, scorecard, and closeout reader consumption",
        "next_wave_target": "Wave 12 production rollout canary cost policy calibration",
        "chain_id": "wave10-temporal-cost-fmea-depth",
        "research_refs": ["E18", "C23", "P01", "P02", "P05", "P09", "P13"],
        "no_adr_required": "W10.D enforces already governed run-cost policy refs and preserves research-authority limitation-only posture.",
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "run_cost_gate quality evidence, scorecard gate, and closeout reader",
            "canary_or_revalidation": "uv run pytest tests/unit/runtime/quality/test_cost_gate.py -q",
            "rollback_or_reversal": "remove run_cost_gate from scorecard/closeout readers and leave W2.C telemetry advisory-only",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/cost_gate.py#RUN_COST_GATE_SCHEMA_VERSION",
        "producer_ref": "repo://src/polisyos/runtime/quality/cost_gate.py#build_run_cost_gate_report",
        "artifact_ref": "repo://src/polisyos/runtime/quality/cost_gate.py#RUN_COST_GATE_FILENAME",
        "bridge_ref": "repo://src/polisyos/runtime/quality/cost_gate.py#cost_gate_scorecard_gates",
        "consumer_ref": "repo://src/polisyos/runtime/quality/closeout_reader.py#run_cost_gate",
        "verification_ref": "repo://tests/unit/runtime/quality/test_cost_gate.py",
        "surface_ref": "repo://docs/reference/runtime/run-cost-enforcement-gate.md",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_cost_gate.py"
            "#test_production_authority_over_budget_emits_typed_cost_blockers"
        ),
    },
    {
        "capability_id": "w10e_complexity_budget_governance_pruning",
        "capability_name": "W10.E Complexity Budget Governance Pruning",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "net_mav_blocking_frontier_admission_and_prune_review",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2027-01-15",
        "hold_reason": "implemented with Net-MAV computation, blocking-frontier rejection, prune review, self-application, and scorecard consumer gate",
        "next_wave_target": "Wave 11 longitudinal control-effect measurement",
        "chain_id": "wave10-temporal-cost-fmea-depth",
        "research_refs": ["E19", "C32", "P09", "P13"],
        "no_adr_required": "W10.E implements proportional-governance telemetry over W2.D self-FMEA without changing domain evidence authority.",
        "reuse_classification": "build_new",
        "rejected_reuse_evidence": [
            "performance_budget.py owns latency/cost budgets, not control marginal assurance value",
            "soft_gate_telemetry.py emits measurements, but does not decide blocking-frontier admission",
        ],
        "rollout_refs": {
            "feature_flag_or_scope": "complexity_governance report and scorecard gate for new blocking-frontier controls",
            "canary_or_revalidation": "uv run pytest tests/unit/runtime/quality/test_complexity_governance.py -q",
            "rollback_or_reversal": "remove complexity_governance_scorecard_gates and mark W10.E consumer_missing until a reader is restored",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/complexity_governance.py#COMPLEXITY_GOVERNANCE_SCHEMA_VERSION",
        "producer_ref": "repo://src/polisyos/runtime/quality/complexity_governance.py#build_complexity_governance_report",
        "artifact_ref": "repo://src/polisyos/runtime/quality/complexity_governance.py#COMPLEXITY_GOVERNANCE_FILENAME",
        "bridge_ref": "repo://src/polisyos/runtime/quality/complexity_governance.py#complexity_governance_scorecard_gates",
        "consumer_ref": "repo://src/polisyos/runtime/quality/scorecard.py#complexity_governance_scorecard_gates",
        "verification_ref": "repo://tests/unit/runtime/quality/test_complexity_governance.py",
        "surface_ref": "repo://docs/reference/policy-design-case-operator-guide.md",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_complexity_governance.py"
            "#test_complexity_governance_report_is_consumed_by_quality_scorecard"
        ),
    },
    {
        "capability_id": "w10f_repair_decision_fmea_annotation",
        "capability_name": "W10.F Repair-Decision FMEA Annotation",
        "reality_state": "implemented",
        "purpose": "closeout_input",
        "authority_scope": "prompt_tool_repair_fmea_machinery_failure_surface",
        "validation_profile": "production",
        "owner": "team-runtime-ops",
        "expiry": "2027-01-15",
        "hold_reason": "implemented with required repair FMEA refs, machinery-failure projection, scorecard, and closeout limitation surface",
        "next_wave_target": "Wave 11 repair FMEA corpus fixtures",
        "chain_id": "wave10-temporal-cost-fmea-depth",
        "research_refs": ["E19", "C24", "P05", "P10", "P13", "P15"],
        "no_adr_required": "W10.F annotates model/tool repair machinery failures without granting repaired output new authority.",
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "prompt_tool_ledger repair decisions, scorecard operator failures, and closeout repair FMEA reader",
            "canary_or_revalidation": "uv run pytest tests/unit/runtime/quality/test_prompt_tool_ledger_fmea.py -q",
            "rollback_or_reversal": "reject repair decisions without FMEA refs and remove prompt_tool_repair_fmea closeout reader",
        },
        "typed_contract_ref": "repo://src/polisyos/runtime/quality/prompt_tool_ledger.py#RepairDecisionFMEAAnnotation",
        "producer_ref": "repo://src/polisyos/runtime/quality/prompt_tool_ledger.py#build_prompt_tool_ledger_from_model_variant",
        "artifact_ref": "repo://src/polisyos/runtime/quality/prompt_tool_ledger.py#REPAIR_FMEA_SURFACE_SCHEMA_VERSION",
        "bridge_ref": "repo://src/polisyos/runtime/quality/prompt_tool_ledger.py#prompt_tool_repair_fmea_closeout_record",
        "consumer_ref": "repo://src/polisyos/runtime/quality/scorecard.py#prompt_tool_repair_machinery_failures",
        "verification_ref": "repo://tests/unit/runtime/quality/test_prompt_tool_ledger_fmea.py",
        "surface_ref": "repo://docs/reference/policy-design-case-operator-guide.md",
        "semantic_test_ref": (
            "repo://tests/unit/runtime/quality/test_prompt_tool_ledger_fmea.py"
            "#test_repair_decisions_without_fmea_refs_cannot_pass_authority_validation"
        ),
    },
    {
        "capability_id": "w10i10_cost_gate_fmea_smoke",
        "capability_name": "I10 Cost Gate + FMEA Smoke",
        "reality_state": "implemented",
        "purpose": "diagnostic_only",
        "authority_scope": "wave10_exit_acceptance_evidence",
        "validation_profile": "production",
        "owner": "team-runtime-quality",
        "expiry": "2027-01-15",
        "hold_reason": "implemented as an integration smoke over run-cost blockers, repair FMEA scorecard/closeout surfaces, and R14 semantic probe",
        "next_wave_target": "Wave 11 universal outcome corpus acceptance baseline",
        "chain_id": "wave10-temporal-cost-fmea-depth",
        "research_refs": ["E18", "E19", "E22", "C23", "C24", "C26", "P01", "P05", "P10", "P13", "P15"],
        "no_adr_required": "I10 records Wave 10 exit evidence and does not introduce new policy authority semantics beyond W10.A-F.",
        "reuse_classification": "wire_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "Wave 10 smoke over cost gate, prompt/tool repair FMEA, and R14 probe fixtures",
            "canary_or_revalidation": "uv run pytest tests/repo_quality/tools/test_cost_gate_and_fmea_smoke.py -q",
            "rollback_or_reversal": "treat Wave 10 exit as blocked until smoke emits typed blocker/semantic failure evidence",
        },
        "typed_contract_ref": "repo://docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md#wave-10---temporalliveness-invariants-run-cost-enforcement-and-self-fmea-depth",
        "producer_ref": "repo://tests/repo_quality/tools/test_cost_gate_and_fmea_smoke.py#test_i10_cost_gate_fmea_and_r14_smoke_closes_wave_10_exit_gate",
        "artifact_ref": "repo://architecture/policy_design_case/capability_reality_report.json#w10i10_cost_gate_fmea_smoke",
        "bridge_ref": "repo://tests/repo_quality/tools/test_cost_gate_and_fmea_smoke.py#cost_gate_scorecard_gates",
        "consumer_ref": "repo://tools/quality/validation/check_policy_design_case_capability_ratchet.py#validate_capability_reality_report",
        "verification_ref": "repo://tests/repo_quality/tools/test_cost_gate_and_fmea_smoke.py",
        "surface_ref": "repo://architecture/policy_design_case/capability_reality_report.json#w10i10_cost_gate_fmea_smoke",
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/test_cost_gate_and_fmea_smoke.py"
            "#test_i10_cost_gate_fmea_and_r14_smoke_closes_wave_10_exit_gate"
        ),
    },
    {
        "capability_id": "w11b_claim_evidence_decomposition_annotations",
        "capability_name": "W11.B Claim/Evidence Decomposition Annotations",
        "reality_state": "implemented",
        "purpose": "diagnostic_only",
        "authority_scope": "compilation_truthfulness_reference_annotations",
        "validation_profile": "production",
        "owner": "team-evaluation",
        "expiry": "2027-02-15",
        "hold_reason": (
            "implemented with strict annotation contracts, repo-owned annotated "
            "case artifact, fail-closed corpus checker, and negative grounding tests"
        ),
        "next_wave_target": "Wave 11.D fixture loaders and W11.E compilation truthfulness",
        "chain_id": "wave11-universal-outcome-corpus",
        "research_refs": ["E1", "E22", "C26", "P01", "P02", "P03", "P05", "P10", "P13", "P14", "P15"],
        "no_adr_required": (
            "W11.B records benchmark annotations used as truthfulness references; "
            "it does not mint claim, evidence, legal, method, participation, "
            "projection, or closeout authority."
        ),
        "reuse_classification": "extend_existing",
        "rollout_refs": {
            "feature_flag_or_scope": "repo-owned W11.B corpus annotations and validation checker only",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/corpus/test_annotations.py "
                "tests/repo_quality/tools/test_universal_corpus_annotations.py -q"
            ),
            "rollback_or_reversal": (
                "remove W11.B annotations from corpus eligibility and mark "
                "claim/evidence decomposition annotation artifact_missing"
            ),
        },
        "typed_contract_ref": "repo://src/polisyos/corpus/__init__.py#POLICY_CASE_ANNOTATION_SCHEMA_VERSION",
        "producer_ref": "repo://docs/research/universal-policy-design/outcome-corpus",
        "artifact_ref": "repo://docs/research/universal-policy-design/outcome-corpus",
        "bridge_ref": "repo://tools/quality/validation/check_universal_corpus_annotations.py",
        "consumer_ref": "repo://tools/quality/validation/check_universal_corpus_annotations.py#build_report",
        "verification_ref": "repo://tests/repo_quality/tools/test_universal_corpus_annotations.py",
        "surface_ref": "repo://docs/research/universal-policy-design/outcome-corpus/README.md",
        "semantic_test_ref": (
            "repo://tests/unit/corpus/test_annotations.py"
            "#test_claim_refs_must_be_grounded_in_case_reference_index"
        ),
    },
    {
        "capability_id": "w11c_expert_adjudication_labels",
        "capability_name": "W11.C Expert Adjudication Labels",
        "reality_state": "implemented",
        "purpose": "authority_gate",
        "authority_scope": "expert_adjudication_useful_design_metric_gate",
        "validation_profile": "production",
        "owner": "team-evaluation",
        "expiry": "2027-02-15",
        "hold_reason": (
            "implemented with strict C30 label contract, repo-owned adjudication "
            "manifests, topology validator, useful-design consumer gate, and "
            "negative semantic tests"
        ),
        "next_wave_target": "Wave 11.D fixture loaders and W11.E compilation truthfulness",
        "chain_id": "wave11-universal-outcome-corpus",
        "research_refs": ["E1", "E22", "E24", "C30", "P05", "P10", "P15"],
        "no_adr_required": (
            "W11.C records benchmark expert labels and metric eligibility only; "
            "it does not mint claim, legal, evidence, or closeout authority."
        ),
        "reuse_classification": "build_new",
        "rejected_reuse_evidence": [
            "runtime/quality/semantic_fixtures.py owns W1/W5 false-pass packs, not per-case expert reviewer topology or outcome-corpus manifests",
            "runtime/quality/human_review.py owns runtime approval calibration, not benchmark gold-card labels",
            "scientist/evals/challenge_factory.py owns adversarial probe fixtures, not universal outcome corpus adjudication artifacts",
        ],
        "rollout_refs": {
            "feature_flag_or_scope": "repo-owned W11.C outcome-corpus adjudication manifests and useful-design metric gate",
            "canary_or_revalidation": (
                "uv run pytest tests/unit/corpus/test_expert_adjudication.py "
                "tests/repo_quality/tools/test_expert_adjudication_labels.py -q"
            ),
            "rollback_or_reversal": (
                "remove W11.C manifests from useful-design eligibility and mark "
                "expert adjudication labels artifact_missing until a validated "
                "reviewer-topology artifact is restored"
            ),
        },
        "typed_contract_ref": (
            "repo://src/polisyos/corpus/__init__.py"
            "#EXPERT_ADJUDICATION_SCHEMA_VERSION"
        ),
        "producer_ref": (
            "repo://docs/research/universal-policy-design/outcome-corpus/"
            "adjudications/README.md#annotation-guide"
        ),
        "artifact_ref": (
            "repo://docs/research/universal-policy-design/outcome-corpus/adjudications"
        ),
        "bridge_ref": (
            "repo://src/polisyos/corpus/__init__.py"
            "#evaluate_expert_adjudication_manifest"
        ),
        "consumer_ref": (
            "repo://src/polisyos/corpus/__init__.py"
            "#build_expert_adjudication_useful_design_gate"
        ),
        "verification_ref": "repo://tests/unit/corpus/test_expert_adjudication.py",
        "surface_ref": (
            "repo://docs/research/universal-policy-design/outcome-corpus/"
            "adjudications/README.md"
        ),
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/test_expert_adjudication_labels.py"
            "#test_w11c_missing_adjudication_cannot_enter_useful_design_metric"
        ),
    },
)


def build_capability_reality_report_payload(
    repo_root: Path = REPO_ROOT,
    *,
    capability_claim_inputs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the Policy Design Case capability reality report from claim inputs."""

    _ = repo_root
    claims = [dict(claim) for claim in (capability_claim_inputs or DEFAULT_CAPABILITY_CLAIMS)]
    report = build_capability_reality_report(
        claims,
        validation_profile="production",
        generated_at=GENERATED_AT,
        as_of="2026-05-23",
    )
    return {
        **report,
        "tool": TOOL_NAME,
        "source": {
            "implementation_plan": (
                "docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
            ),
            "failure_patterns": "docs/reference/policy-design-case-failure-patterns.md",
            "reference_doc": REFERENCE_DOC_PATH.as_posix(),
        },
        "pattern_pass": {
            "relevant_patterns": [
                "P01",
                "P02",
                "P03",
                "P07",
                "P08",
                "P09",
                "P10",
                "P11",
                "P12",
                "P13",
                "P14",
                "P15",
            ],
            "target_correct_pattern": (
                "incomplete capabilities remain typed release/readiness evidence "
                "until the producer, artifact, bridge, consumer, surface, "
                "verification, and semantic test chain closes"
            ),
            "missing_capability_labels": [
                state for state in REALITY_STATES if state != "implemented"
            ],
            "acceptance_signal": (
                "capability claims can be counted, compared, and moved toward "
                "implemented or explicit surface_out_of_scope without laundering "
                "missing authority"
            ),
        },
        "capability_claim_inputs": claims,
    }


def rebuild_report_from_inputs(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild a report from the embedded capability_claim_inputs section."""

    inputs = payload.get("capability_claim_inputs")
    if not isinstance(inputs, Sequence) or isinstance(inputs, (str, bytes)):
        inputs = []
    return build_capability_reality_report_payload(capability_claim_inputs=inputs)


def load_capability_reality_report(
    repo_root: Path = REPO_ROOT,
    *,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    """Load the committed Policy Design Case capability reality report."""

    resolved = _resolve_repo_path(repo_root, report_path)
    return json.loads(resolved.read_text(encoding="utf-8"))


def validate_capability_reality_report(
    payload: Mapping[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Validate report integrity without requiring readiness to be green."""

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            _issue(
                "capability_ratchet_schema_version_invalid",
                "$.schema_version",
                f"schema_version must be {SCHEMA_VERSION}",
            )
        )
    if payload.get("tool") != TOOL_NAME:
        issues.append(
            _issue("capability_ratchet_tool_invalid", "$.tool", f"tool must be {TOOL_NAME}")
        )
    if not isinstance(payload.get("capability_claim_inputs"), list):
        issues.append(
            _issue(
                "capability_claim_inputs_missing",
                "$.capability_claim_inputs",
                "report must embed the claim inputs used to compute debt",
            )
        )
        rebuilt = {}
    else:
        rebuilt = rebuild_report_from_inputs(payload)
        _validate_rebuilt_equivalence(payload, rebuilt, issues)
        _validate_implemented_traceability(
            _sequence_of_mappings(payload.get("capability_claim_inputs")),
            issues,
        )
        _validate_repo_references(payload, repo_root, issues)
        _validate_wave3_corpus_coverage(repo_root, issues)
        _validate_wave4_i4_manifest(repo_root, issues)

    summary = _mapping(payload.get("summary"))
    state_counts = _mapping(summary.get("state_counts"))
    for state in REALITY_STATES:
        if state not in state_counts:
            issues.append(
                _issue(
                    "capability_state_count_missing",
                    f"$.summary.state_counts.{state}",
                    f"state_counts must include {state}",
                )
            )

    algebra = _mapping(payload.get("debt_algebra"))
    if "base_points" not in algebra or "purpose_multipliers" not in algebra:
        issues.append(
            _issue(
                "capability_debt_algebra_missing",
                "$.debt_algebra",
                "report must expose base points and purpose multipliers",
            )
        )
    templates = _mapping(payload.get("ratchet_templates"))
    for state in REALITY_STATES:
        if state not in templates:
            issues.append(
                _issue(
                    "capability_ratchet_template_missing",
                    f"$.ratchet_templates.{state}",
                    f"ratchet template missing for {state}",
                )
            )

    computed_issues = [dict(issue) for issue in _sequence_of_mappings(payload.get("issues"))]
    issues.extend(computed_issues)
    expected_integrity = "fail" if computed_issues else "pass"
    if payload.get("ratchet_integrity_status") != expected_integrity:
        issues.append(
            _issue(
                "capability_ratchet_integrity_status_drift",
                "$.ratchet_integrity_status",
                "ratchet_integrity_status must reflect computed report issues",
            )
        )

    return {
        "schema_version": "policyos.policy_design_case.capability_ratchet.validation.v1",
        "status": "fail" if issues else "pass",
        "issue_count": len(issues),
        "issues": issues,
        "readiness_band": _mapping(payload.get("readiness")).get("band"),
    }


def write_capability_reality_report(
    repo_root: Path = REPO_ROOT,
    *,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    """Write the deterministic capability report to the architecture surface."""

    payload = build_capability_reality_report_payload(repo_root)
    atomic_write_json(_resolve_repo_path(repo_root, report_path), payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    """Run the capability ratchet checker."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--write", action="store_true", help="rewrite the report")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    if args.write:
        payload = write_capability_reality_report(repo_root, report_path=args.report_path)
    else:
        payload = load_capability_reality_report(repo_root, report_path=args.report_path)
    validation = validate_capability_reality_report(payload, repo_root=repo_root)
    result = {
        **validation,
        "report_path": args.report_path.as_posix(),
    }
    if args.json_output:
        atomic_write_json(args.json_output, result)
    if validation["status"] != "pass":
        sys.stderr.write(json.dumps(result, indent=2, ensure_ascii=False))
        sys.stderr.write("\n")
        return 1
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


def _validate_rebuilt_equivalence(
    payload: Mapping[str, Any],
    rebuilt: Mapping[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    for key in (
        "summary",
        "readiness",
        "debt_algebra",
        "ratchet_templates",
        "chain_clusters",
        "blockers",
        "issues",
        "capability_claims",
    ):
        if payload.get(key) != rebuilt.get(key):
            issues.append(
                _issue(
                    "capability_ratchet_report_drift",
                    f"$.{key}",
                    f"report {key} does not match embedded claim inputs",
                )
            )


def _validate_implemented_traceability(
    claim_inputs: Sequence[Mapping[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    for index, claim in enumerate(claim_inputs):
        if claim.get("reality_state") != "implemented":
            continue
        capability_id = str(claim.get("capability_id") or f"claim_{index}")
        research_refs = _sequence_of_text(claim.get("research_refs"))
        rollout_refs = _mapping(claim.get("rollout_refs"))
        missing: list[str] = []
        if not (
            any(ref.startswith("C") for ref in research_refs)
            and any(ref.startswith("E") for ref in research_refs)
            and any(ref.startswith("P") for ref in research_refs)
        ):
            missing.append("research_refs")
        if not _sequence_of_text(claim.get("decision_refs")) and not _text(
            claim.get("no_adr_required")
        ):
            missing.append("decision_refs_or_no_adr_required")
        reuse_classification = _text(claim.get("reuse_classification"))
        if reuse_classification not in REUSE_CLASSIFICATIONS:
            missing.append("reuse_classification")
        if reuse_classification == "build_new" and not _sequence_of_text(
            claim.get("rejected_reuse_evidence")
        ):
            missing.append("rejected_reuse_evidence")
        if not set(rollout_refs) >= TRACEABILITY_ROLLOUT_FIELDS:
            missing.append("rollout_refs")
        if missing:
            issues.append(
                _issue(
                    "capability_implemented_traceability_missing",
                    f"$.capability_claim_inputs[{index}]",
                    (
                        f"Implemented capability {capability_id} must carry "
                        "research refs, decision refs or no-ADR rationale, reuse "
                        "classification, and rollout refs."
                    ),
                )
            )


def _validate_wave3_corpus_coverage(
    repo_root: Path,
    issues: list[dict[str, Any]],
) -> None:
    path = _resolve_repo_path(repo_root, WAVE3_CORPUS_COVERAGE_PATH)
    if not path.exists():
        issues.append(
            _issue(
                "wave3_producer_adapter_corpus_coverage_missing",
                f"repo://{WAVE3_CORPUS_COVERAGE_PATH.as_posix()}",
                "Wave 3 exit evidence must include producer adapter corpus coverage.",
            )
        )
        return
    try:
        coverage = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(
            _issue(
                "wave3_producer_adapter_corpus_coverage_invalid_json",
                f"repo://{WAVE3_CORPUS_COVERAGE_PATH.as_posix()}",
                f"Wave 3 producer adapter corpus coverage is not valid JSON: {exc}",
            )
        )
        return

    producer_coverage = _sequence_of_mappings(coverage.get("producer_coverage"))
    for index, producer in enumerate(producer_coverage):
        producer_name = _text(producer.get("producer")) or f"producer_{index}"
        for field in WAVE3_COVERAGE_REF_FIELDS:
            ref = _text(producer.get(field))
            if not ref:
                issues.append(
                    _issue(
                        "wave3_producer_coverage_ref_missing",
                        f"$.producer_coverage[{index}].{field}",
                        (f"Wave 3 producer {producer_name} must carry a non-empty {field}."),
                    )
                )
        if producer.get("context_only_is_non_authoritative") is not True:
            issues.append(
                _issue(
                    "wave3_context_only_authority_boundary_missing",
                    f"$.producer_coverage[{index}].context_only_is_non_authoritative",
                    (
                        f"Wave 3 producer {producer_name} must explicitly mark "
                        "context-only output as non-authoritative."
                    ),
                )
            )
    _validate_repo_references(
        coverage,
        repo_root,
        issues,
        root_path="$.wave3_producer_adapter_corpus_coverage",
    )


def _validate_wave4_i4_manifest(
    repo_root: Path,
    issues: list[dict[str, Any]],
) -> None:
    path = _resolve_repo_path(repo_root, WAVE4_I4_MANIFEST_PATH)
    if not path.exists():
        issues.append(
            _issue(
                "wave4_i4_runtime_closeout_manifest_missing",
                f"repo://{WAVE4_I4_MANIFEST_PATH.as_posix()}",
                "Wave 4 exit evidence must include the I4 runtime closeout manifest.",
            )
        )
        return
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(
            _issue(
                "wave4_i4_runtime_closeout_manifest_invalid_json",
                f"repo://{WAVE4_I4_MANIFEST_PATH.as_posix()}",
                f"Wave 4 I4 runtime closeout manifest is not valid JSON: {exc}",
            )
        )
        return

    required_phases = {"W4.A", "W4.B", "W4.C", "W4.D", "W4.E", "I4"}
    observed_phases = {
        _text(phase.get("phase_id"))
        for phase in _sequence_of_mappings(manifest.get("completed_phases"))
    }
    if manifest.get("schema_version") != (
        "policyos.policy_design_case.wave4.i4_runtime_closeout_manifest.v1"
    ):
        issues.append(
            _issue(
                "wave4_i4_runtime_closeout_manifest_schema_invalid",
                "$.wave4_i4_manifest.schema_version",
                "Wave 4 manifest schema_version is invalid.",
            )
        )
    if manifest.get("status") != "closed":
        issues.append(
            _issue(
                "wave4_i4_runtime_closeout_manifest_not_closed",
                "$.wave4_i4_manifest.status",
                "Wave 4 manifest must record closed status before the wave can close.",
            )
        )
    if not required_phases <= observed_phases:
        issues.append(
            _issue(
                "wave4_i4_runtime_closeout_manifest_phase_missing",
                "$.wave4_i4_manifest.completed_phases",
                "Wave 4 manifest must record W4.A-W4.E and I4 completion.",
            )
        )
    _validate_repo_references(manifest, repo_root, issues, root_path="$.wave4_i4_manifest")


def _validate_repo_references(
    payload: object,
    repo_root: Path,
    issues: list[dict[str, Any]],
    *,
    root_path: str = "$",
) -> None:
    for path, ref in _iter_repo_refs(payload, root_path):
        issue = validate_repo_reference(ref, repo_root=repo_root, path=path)
        if issue is not None:
            issues.append(issue)


def validate_repo_reference(
    ref: str,
    *,
    repo_root: Path = REPO_ROOT,
    path: str = "$",
) -> dict[str, str] | None:
    """Validate that a repo:// reference points at an existing file and anchor."""

    if not ref.startswith("repo://"):
        return None
    raw_ref = ref.removeprefix("repo://")
    target_path_text, separator, anchor = raw_ref.partition("#")
    target_path = Path(target_path_text)
    if target_path.is_absolute() or ".." in target_path.parts:
        return _issue(
            "capability_repo_ref_outside_repo",
            path,
            f"repo reference {ref} must stay within the repository.",
        )
    target = (repo_root / target_path).resolve()
    try:
        target.relative_to(repo_root.resolve())
    except ValueError:
        return _issue(
            "capability_repo_ref_outside_repo",
            path,
            f"repo reference {ref} must stay within the repository.",
        )
    if not target.exists():
        return _issue(
            "capability_repo_ref_file_missing",
            path,
            f"repo reference {ref} points at a missing path.",
        )
    if not separator:
        return None
    if target.is_dir():
        return _issue(
            "capability_repo_ref_anchor_on_directory",
            path,
            f"repo reference {ref} attaches an anchor to a directory.",
        )
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = target.read_text(errors="ignore")
    if _anchor_is_present(text, anchor, target.suffix):
        return None
    return _issue(
        "capability_repo_ref_anchor_missing",
        path,
        f"repo reference {ref} points at a missing anchor.",
    )


def _iter_repo_refs(value: object, path: str) -> tuple[tuple[str, str], ...]:
    refs: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            refs.extend(_iter_repo_refs(item, f"{path}.{key}"))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            refs.extend(_iter_repo_refs(item, f"{path}[{index}]"))
    elif isinstance(value, str) and value.startswith("repo://"):
        refs.append((path, value))
    return tuple(refs)


def _anchor_is_present(text: str, anchor: str, suffix: str) -> bool:
    if not anchor:
        return True
    if anchor in text:
        return True
    dotted_parts = [part for part in anchor.split(".") if part]
    if len(dotted_parts) > 1 and all(part in text for part in dotted_parts):
        return True
    if suffix.lower() in {".md", ".markdown"}:
        return anchor.lower() in _markdown_heading_slugs(text)
    return False


def _markdown_heading_slugs(text: str) -> set[str]:
    slugs: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            slugs.add(_github_markdown_heading_slug(match.group(1)))
    return slugs


def _github_markdown_heading_slug(heading: str) -> str:
    normalized = heading.strip().lower()
    normalized = re.sub(r"[^\w\s-]", "", normalized)
    return normalized.replace(" ", "-")


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _sequence_of_text(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Sequence):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


if __name__ == "__main__":
    raise SystemExit(main())
