#!/usr/bin/env python3
# ruff: noqa: ANN401, E501
"""Aggregate PolicyOS best-in-class production-quality readiness evidence."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.assurance_case import (  # noqa: E402
    PolicyDesignCaseAuthorityError,
    validate_policy_design_case_concept_spine,
    validate_policy_design_case_profile,
    validate_policy_design_jurisdiction_spine,
)
from polisyos.runtime.quality.closeout_compatibility import (  # noqa: E402
    build_closeout_compatibility_record_from_bundle_dir,
    compatibility_failures_for_readiness,
)
from polisyos.runtime.quality.invariants import (  # noqa: E402
    build_production_invariant_registry_report,
)
from polisyos.runtime.quality.policy_design_case import (  # noqa: E402
    build_policy_design_case_record_registry_report,
)
from polisyos.runtime.quality.scorecard import (  # noqa: E402
    policy_design_case_claim_closeout_gates,
)
from polisyos.runtime.quality.semantic_binding import (  # noqa: E402
    deserialize_semantic_binding_ledger,
    evaluate_semantic_binding_ledger,
)
from polisyos.runtime.quality.source_truth import (  # noqa: E402
    detect_source_truth_conflict,
    load_source_truth_lattice,
)
from tools.ops_runners.runtime import canary_matrix, quality_benchmark_authority  # noqa: E402
from tools.quality.testing import local_integration_stack, runtime_resilience_matrix  # noqa: E402
from tools.quality.validation import (  # noqa: E402
    build_policy_design_case_coverage,
    check_honest_diagnostics_proof_harness,
    production_quality_evidence_inventory,
)

SCHEMA_VERSION = "policyos.production_quality_best_in_class_readiness.v1"
ASSESSMENT_ID = "policyos_production_quality_best_in_class"
TOOL_NAME = "ci.check-policyos-production-quality-best-in-class"

STATUS_VALUES = ("pass", "fail", "warn")
SERIOUS_PROFILE_BLOCKING_REF_STATUSES = frozenset({"manual_input", "fixture_input", "missing"})
FAILURE_CLASSES = (
    "operational_failure",
    "quality_failure",
    "compliance_failure",
    "resilience_failure",
    "approval_failure",
    "closeout_evidence_gap",
)
DETERMINISTIC_ENV = {"POLISYOS_LLM_SIMULATION_MODE": "1"}
DEV_SMOKE_CANARY_KINDS = frozenset({"dev", "dev_smoke", "local_smoke", "smoke", "test_smoke"})
SERIOUS_MATRIX_PROFILES = frozenset({"research", "governed", "production"})
POLICY_DESIGN_CASE_RUNTIME_REF_KEYS = (
    "policy_intent_envelope_ref",
    "policy_design_capability_ledger_ref",
    "policy_design_case_ref",
)
POLICY_DESIGN_CASE_QUALITY_FILE = "policy_design_case.json"
POLICY_DESIGN_EVIDENCE_PORTFOLIO_CONTRACT_SURFACES = (
    "strands",
    "authority_level",
    "candidate_data_source_families",
    "candidate_method_families",
    "defensible_specification_space",
    "inclusion_exclusion_rules",
    "disconfirming_lines",
    "synthesis_rules",
    "stopping_rules",
    "cost_proportionality",
)
POLICY_DESIGN_RUN_COST_PROPORTIONALITY_CONTRACT_SURFACES = (
    "runtime_performance_budget",
    "foundry_cost_model",
    "scientist_budget",
    "doe_search_budget",
    "provider_cost",
    "elapsed_time_budget",
    "human_review_burden",
    "evidence_depth_budget",
    "proportionality_evidence",
    "budget_change_records",
)
POLICY_DESIGN_BEST_IN_CLASS_BENCHMARKING_CONTRACT_SURFACES = (
    "external_audit_pass_rate",
    "human_team_benchmark",
    "reversal_rate",
    "retraction_rate",
    "calibration_error",
    "claim_substantiation_rate",
    "triangulation_coverage",
    "operator_time_to_root_cause_seconds",
    "run_cost_ledger_refs",
    "proportionality_evidence_refs",
)
POLICY_DESIGN_PARALLEL_AUTHORITY_FILES = frozenset(
    {
        "parallel_policy_design_case_authority.json",
        "parallel_case_authority.json",
        "policy_design_case_authority_profile.json",
    }
)
COMPATIBLE_SCHEMA_DECISIONS = frozenset(
    {"accepted", "backward_compatible", "compatible", "exact", "pass"}
)

_REPORT_KEY_BY_RUNTIME_REF = {
    ref_key: report_key
    for report_key, ref_key in production_quality_evidence_inventory.QUALITY_REPORT_RUNTIME_REFS.items()
}
_REPORT_FILE_BY_RUNTIME_REF = {
    ref_key: production_quality_evidence_inventory.QUALITY_REPORT_FILES[report_key]
    for ref_key, report_key in _REPORT_KEY_BY_RUNTIME_REF.items()
    if report_key in production_quality_evidence_inventory.QUALITY_REPORT_FILES
}

HDS_SUBSTRATE_COVERAGE: tuple[dict[str, Any], ...] = (
    {
        "backlog_item_id": "A7",
        "title": "continuous governance lifecycle evidence",
        "minimum_closeout_gates": ("continuous_governance_lifecycle",),
    },
    {
        "backlog_item_id": "A8",
        "title": "runtime control-plane closeout authority",
        "minimum_closeout_gates": (
            "scorecard_persisted_runtime_refs",
            "serious_phase_barriers_closed",
        ),
    },
    {
        "backlog_item_id": "A9",
        "title": "report-ref identity",
        "minimum_closeout_gates": ("serious_canary_runtime_refs",),
    },
    {
        "backlog_item_id": "A10",
        "title": "draft versus final decision packets",
        "minimum_closeout_gates": (
            "production_approval_or_signed_override",
            "final_decision_artifact_quality",
            "serious_phase_barriers_closed",
        ),
    },
    {
        "backlog_item_id": "A11",
        "title": "scorecard ref authenticity",
        "minimum_closeout_gates": ("scorecard_persisted_runtime_refs",),
    },
    {
        "backlog_item_id": "A12",
        "title": "runtime truth survives bundle assembly",
        "minimum_closeout_gates": ("serious_canary_runtime_refs",),
    },
    {
        "backlog_item_id": "A13",
        "title": "evidence provenance manifest",
        "minimum_closeout_gates": ("serious_canary_runtime_refs",),
    },
    {
        "backlog_item_id": "A14",
        "title": "validator authority precedence",
        "minimum_closeout_gates": ("serious_canary_runtime_refs",),
    },
    {
        "backlog_item_id": "A15",
        "title": "typed evidence envelopes",
        "minimum_closeout_gates": ("serious_canary_runtime_refs",),
    },
    {
        "backlog_item_id": "A16",
        "title": "phase-barrier contract",
        "minimum_closeout_gates": ("serious_phase_barriers_closed",),
    },
    {
        "backlog_item_id": "A17",
        "title": "Scientist skip authority",
        "minimum_closeout_gates": ("serious_phase_barriers_closed",),
    },
    {
        "backlog_item_id": "A18",
        "title": "prompt tool parser ledger",
        "minimum_closeout_gates": ("provider_model_quality_drift",),
    },
    {
        "backlog_item_id": "A19",
        "title": "Cluster 6 ADR set",
        "minimum_closeout_gates": ("closeout_matrix_dashboard_api_smoke",),
    },
    {
        "backlog_item_id": "A20",
        "title": "architecture boundary contract",
        "minimum_closeout_gates": ("serious_canary_runtime_refs",),
    },
    {
        "backlog_item_id": "A21",
        "title": "architecture fitness gates",
        "minimum_closeout_gates": ("closeout_matrix_dashboard_api_smoke",),
    },
    {
        "backlog_item_id": "A22",
        "title": "schema compatibility",
        "minimum_closeout_gates": ("serious_canary_runtime_refs",),
    },
    {
        "backlog_item_id": "A23",
        "title": "semantic-preserving adapters",
        "minimum_closeout_gates": ("serious_canary_runtime_refs",),
    },
    {
        "backlog_item_id": "A24",
        "title": "source-of-truth lattice",
        "minimum_closeout_gates": ("serious_canary_runtime_refs",),
    },
    {
        "backlog_item_id": "A25",
        "title": "invariant proof harness",
        "minimum_closeout_gates": ("closeout_matrix_dashboard_api_smoke",),
    },
    {
        "backlog_item_id": "A26",
        "title": "invariant ownership registry",
        "minimum_closeout_gates": ("closeout_matrix_dashboard_api_smoke",),
    },
    {
        "backlog_item_id": "A27",
        "title": "effective-mode ledger",
        "minimum_closeout_gates": ("serious_effective_mode_allowed",),
    },
    {
        "backlog_item_id": "A28",
        "title": "fallback/degradation ledger",
        "minimum_closeout_gates": ("serious_effective_mode_allowed",),
    },
)


@dataclass(frozen=True)
class FindingSpec:
    finding_id: str
    severity: str
    title: str
    owning_layer: str
    phase: str
    failure_class: str
    next_action: str
    expected_verification_command: str
    report_ids: tuple[str, ...] = ()
    required_paths: tuple[str, ...] = ()
    component: str | None = None


FINDING_SPECS: tuple[FindingSpec, ...] = (
    FindingSpec(
        finding_id="PQL-001",
        severity="PQ-Critical",
        title="Runtime-owned quality subreport refs are emitted by owning layers",
        owning_layer="lex/fabric/foundry/scientist",
        phase="1",
        failure_class="quality_failure",
        next_action="Wire missing Lex, Fabric, Foundry, grounding, and conflict refs into runtime progress before serious approval.",
        expected_verification_command="uv run pytest tests/unit/runtime/http/test_nl_pipeline_materialization.py tests/unit/tools/test_canary_evidence.py -q",
        report_ids=(
            "lex.normative_evidence",
            "fabric.retrieval_trace",
            "foundry.method_report",
            "scientist.policy_grounding_matrix",
            "lex.policy_conflict_check",
        ),
        component="quality_evidence_inventory",
    ),
    FindingSpec(
        finding_id="PQL-002",
        severity="PQ-Critical",
        title="Final policy claims have extraction and grounding matrix evidence",
        owning_layer="scientist_policy_artifacts",
        phase="1.4",
        failure_class="quality_failure",
        next_action="Emit policy grounding matrix evidence for every material final policy claim.",
        expected_verification_command="uv run pytest tests/unit/scientist/validation/test_policy_grounding_matrix.py -q",
        report_ids=("scientist.policy_grounding_matrix",),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-003",
        severity="PQ-Critical",
        title="Production metric taxonomy blocks unknown metrics before Trinity",
        owning_layer="runtime/ir_metric_registry/trinity_linker",
        phase="1.5",
        failure_class="operational_failure",
        next_action="Keep the production metric taxonomy and Trinity linker contract drift-free.",
        expected_verification_command="uv run pytest tests/contract/test_trinity_linker_contract.py tests/unit/core/phase0/test_metrics.py -q",
        report_ids=("ir.metric_taxonomy",),
        required_paths=(
            "src/polisyos/core/observability/metrics_parts.py",
            "tests/contract/test_trinity_linker_contract.py",
        ),
        component="contract_drift_checks",
    ),
    FindingSpec(
        finding_id="PQL-004",
        severity="PQ-Critical",
        title="Active-corpus conflict checks are mandatory runtime outputs",
        owning_layer="lex/scientist/governance",
        phase="2.3",
        failure_class="quality_failure",
        next_action="Persist conflict check evidence from final claims and the active normative corpus.",
        expected_verification_command="uv run pytest tests/unit/lex/test_conflict_check_report.py tests/unit/tools/test_canary_evidence.py -q",
        report_ids=("lex.policy_conflict_check",),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-005",
        severity="PQ-High",
        title="Quality scorecards expose provenance and approval readiness semantics",
        owning_layer="runtime_quality/control_api",
        phase="2.1",
        failure_class="quality_failure",
        next_action="Keep runtime scorecard gates, evidence refs, and approval eligibility stable.",
        expected_verification_command="uv run pytest tests/unit/runtime/quality/test_scorecard.py tests/unit/runtime/http/test_control_api.py -q",
        report_ids=("runtime.quality_scorecard",),
        required_paths=(
            "src/polisyos/runtime/quality/scorecard.py",
            "tests/unit/runtime/quality/test_scorecard.py",
        ),
        component="scorecard_tests",
    ),
    FindingSpec(
        finding_id="PQL-006",
        severity="PQ-High",
        title="Production approval and override packets carry reviewer trail",
        owning_layer="dashboard/governance",
        phase="2.4",
        failure_class="approval_failure",
        next_action="Require approval-ready scorecards or signed override packets before production release.",
        expected_verification_command="uv run pytest tests/unit/runtime/quality/test_approval.py tests/unit/runtime/http/test_control_api.py -q",
        required_paths=(
            "src/polisyos/runtime/quality/approval.py",
            "tests/unit/runtime/quality/test_approval.py",
        ),
        component="scorecard_tests",
    ),
    FindingSpec(
        finding_id="PQL-007",
        severity="PQ-Critical",
        title="Benchmark authority has public, hidden, rotating, adversarial, and regression packs",
        owning_layer="quality/evals",
        phase="3.1",
        failure_class="quality_failure",
        next_action="Repair benchmark-authority catalog validation or quarantine policy before using scenario evidence.",
        expected_verification_command="uv run pytest tests/repo_quality/tools/test_quality_benchmark_authority.py -q",
        report_ids=("quality.golden_scenario_contract",),
        required_paths=(
            "tools/ops_runners/runtime/quality_benchmark_authority.py",
            "tools/ops_runners/runtime/golden_quality_scenarios.json",
        ),
        component="benchmark_authority_checks",
    ),
    FindingSpec(
        finding_id="PQL-008",
        severity="PQ-Critical",
        title="Semantic support and citation faithfulness are production-checkable",
        owning_layer="scientist_evidence/lex",
        phase="3.2",
        failure_class="quality_failure",
        next_action="Keep claim-support and citation-faithfulness reports calibrated and referenced.",
        expected_verification_command="uv run pytest tests/unit/scientist/validation/test_claim_support.py tests/unit/scientist/validation/test_citation_faithfulness.py -q",
        required_paths=(
            "src/polisyos/scientist/validation/claim_support.py",
            "src/polisyos/scientist/validation/citation_faithfulness.py",
        ),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-009",
        severity="PQ-High",
        title="Source quality, freshness, and conflict signals are calibrated",
        owning_layer="scientist_evidence/fabric",
        phase="3.4",
        failure_class="quality_failure",
        next_action="Keep source-quality calibration docs, code, and tests in sync with Fabric retrieval traces.",
        expected_verification_command="uv run pytest tests/unit/scientist/evidence/test_source_quality.py tests/unit/fabric/test_source_selection_audit.py -q",
        report_ids=("fabric.retrieval_trace",),
        required_paths=(
            "src/polisyos/scientist/evidence/source_quality.py",
            "docs/reference/scientist/source-quality-calibration.md",
        ),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-010",
        severity="PQ-High",
        title="Multi-model disagreement has adjudication and selected-variant rationale",
        owning_layer="scientist/llm_orchestration",
        phase="3.5",
        failure_class="quality_failure",
        next_action="Keep LLM adjudication evidence and selected-variant rationale available for serious runs.",
        expected_verification_command="uv run pytest tests/unit/scientist/orchestration/llm/test_provider_quality.py tests/unit/tools/test_canary_evidence.py -q",
        required_paths=(
            "src/polisyos/scientist/orchestration/llm/adjudication.py",
            "src/polisyos/scientist/orchestration/llm/provider_quality.py",
        ),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-011",
        severity="PQ-Medium",
        title="Canary performance evidence is normalized across runtime surfaces",
        owning_layer="ops/runtime/dashboard",
        phase="4.1",
        failure_class="resilience_failure",
        next_action="Attach performance budget evidence for control jobs, CAS, API, and dashboard smoke routes.",
        expected_verification_command="uv run pytest tests/performance/test_runtime_hot_paths.py tests/repo_quality/tools/test_local_integration_stack.py -q",
        report_ids=("runtime.performance_summary",),
        required_paths=(
            "tools/quality/testing/local_integration_stack.py",
            "tests/performance/test_runtime_hot_paths.py",
        ),
        component="local_stack_smoke",
    ),
    FindingSpec(
        finding_id="PQL-012",
        severity="PQ-High",
        title="Governed and production CAS artifacts carry tenant-scoped ownership",
        owning_layer="core_artifacts/runtime",
        phase="4.2",
        failure_class="operational_failure",
        next_action="Persist CAS producer and governance metadata for quality artifacts.",
        expected_verification_command="uv run pytest tests/unit/core/artifacts/test_artifact_id_serialization_contract.py tests/unit/tools/test_canary_evidence.py -q",
        report_ids=("core.cas_ownership_evidence",),
        required_paths=("src/polisyos/core/artifacts/ownership.py",),
        component="quality_evidence_inventory",
    ),
    FindingSpec(
        finding_id="PQL-013",
        severity="PQ-High",
        title="Real canary matrix is stable across profile, provider, model, scenario, and data lanes",
        owning_layer="ops_runners",
        phase="4.3",
        failure_class="operational_failure",
        next_action="Keep simulated lanes CI-safe and live-provider lanes quarantined with explicit evidence attachment.",
        expected_verification_command="uv run pytest tests/repo_quality/tools/test_canary_matrix.py -q",
        required_paths=(
            "tools/ops_runners/runtime/canary_matrix.py",
            "tools/ops_runners/runtime/run_canary_matrix.py",
        ),
        component="deterministic_tests",
    ),
    FindingSpec(
        finding_id="PQL-014",
        severity="PQ-High",
        title="Continuous governance can stale, reissue, supersede, or withdraw decisions",
        owning_layer="continuous_governance",
        phase="4.4",
        failure_class="approval_failure",
        next_action="Keep drift-triggered governance lifecycle evidence wired into decision readiness.",
        expected_verification_command="uv run pytest tests/unit/scientist/governance/test_transportability_required_pass.py tests/unit/scientist/nodes/test_data_plane_gate_node.py -q",
        required_paths=(
            "src/polisyos/scientist/governance/continuous/monitors.py",
            "src/polisyos/scientist/governance/continuous/reissue.py",
        ),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-015",
        severity="PQ-Critical",
        title="Production data quality diagnostics cover serious data-backed decisions",
        owning_layer="fabric/data_forge",
        phase="5.1",
        failure_class="quality_failure",
        next_action="Emit production data quality diagnostics for schema drift, leakage, units, missingness, and construct validity.",
        expected_verification_command="uv run pytest tests/unit/runtime/quality/test_data_quality.py -q",
        report_ids=("runtime.production_data_quality", "fabric.production_data_context"),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-016",
        severity="PQ-Critical",
        title="Causal and statistical methods have benchmark proof",
        owning_layer="foundry/scientist",
        phase="5.2",
        failure_class="quality_failure",
        next_action="Run known-answer, placebo, negative-control, power, and sensitivity benchmark gates.",
        expected_verification_command="uv run pytest tests/unit/foundry/validation/test_causal_validity.py -q",
        report_ids=("foundry.causal_statistical_validity",),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-017",
        severity="PQ-Critical",
        title="LLM, tool, data, and artifact paths fail closed against abuse",
        owning_layer="security/runtime/scientist",
        phase="5.3",
        failure_class="compliance_failure",
        next_action="Keep security assurance reports blocking prompt/tool/source/provider/rendering/secret abuse.",
        expected_verification_command="uv run pytest tests/unit/security/test_policyos_runtime_abuse_gates.py -q",
        report_ids=("runtime.security_assurance_report",),
        required_paths=(
            "src/polisyos/core/security/quality_gates.py",
            "tests/unit/security/test_policyos_runtime_abuse_gates.py",
        ),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-018",
        severity="PQ-Critical",
        title="Privacy, licensing, retention, jurisdiction, and public-export checks block approval",
        owning_layer="governance/data_forge",
        phase="5.4",
        failure_class="compliance_failure",
        next_action="Resolve compliance blockers or attach signed override evidence before publication.",
        expected_verification_command="uv run pytest tests/unit/runtime/quality/test_compliance.py -q",
        report_ids=("runtime.privacy_compliance_report",),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-019",
        severity="PQ-High",
        title="Serious runs have deterministic replay and typed drift explanations",
        owning_layer="runtime/scientist",
        phase="5.5",
        failure_class="operational_failure",
        next_action="Keep replay manifests and drift explanations comparable across code, refs, data, provider, and model changes.",
        expected_verification_command="uv run pytest tests/repo_quality/tools/test_replay_canary_bundle.py tests/unit/runtime/quality/test_replay.py -q",
        report_ids=("runtime.replay_manifest", "runtime.drift_explanation"),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-020",
        severity="PQ-High",
        title="Load, soak, retry storm, brownout, CAS pressure, and dashboard degradation are covered",
        owning_layer="ops/runtime/dashboard",
        phase="5.6",
        failure_class="resilience_failure",
        next_action="Refresh the deterministic runtime resilience matrix and investigate blocking scenarios.",
        expected_verification_command="uv run pytest tests/repo_quality/tools/test_runtime_resilience_matrix.py -q",
        report_ids=("runtime.resilience_matrix",),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-021",
        severity="PQ-High",
        title="Human-review calibration measures agreement, burden, escalation, and override quality",
        owning_layer="governance/dashboard",
        phase="5.7",
        failure_class="approval_failure",
        next_action="Attach human-review calibration evidence or fail approval readiness.",
        expected_verification_command="uv run pytest tests/unit/runtime/quality/test_human_review.py tests/unit/runtime/quality/test_approval.py -q",
        report_ids=("runtime.human_review_calibration",),
        required_paths=(
            "src/polisyos/runtime/quality/human_review.py",
            "docs/reference/runtime/human-review-calibration.md",
        ),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-022",
        severity="PQ-High",
        title="Provider and model quality drift is monitored across schema, grounding, disagreement, cost, latency, and quality",
        owning_layer="llm_orchestration/ops",
        phase="5.8",
        failure_class="operational_failure",
        next_action="Attach provider/model quality ledger evidence for default production model choices.",
        expected_verification_command="uv run pytest tests/repo_quality/tools/test_provider_quality_ledger.py tests/unit/scientist/orchestration/llm/test_provider_quality.py -q",
        report_ids=("runtime.provider_model_quality_ledger",),
        required_paths=(
            "tools/ops_runners/runtime/provider_quality_ledger.py",
            "src/polisyos/scientist/orchestration/llm/provider_quality.py",
        ),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-023",
        severity="PQ-Critical",
        title="Final decision artifacts are compiler-grade for uncertainty, tradeoffs, impacts, feasibility, budget, stakeholders, and residual risk",
        owning_layer="scientist/dashboard",
        phase="5.9",
        failure_class="quality_failure",
        next_action="Compile and validate public decision artifacts before final policy approval.",
        expected_verification_command="uv run pytest tests/unit/scientist/validation/test_decision_artifact_quality.py tests/unit/scientist/artifacts/test_decision_compiler.py -q",
        report_ids=("scientist.decision_artifact_quality",),
        component="system_assurance_reports",
    ),
    FindingSpec(
        finding_id="PQL-024",
        severity="PQ-Medium",
        title="Aggregate readiness gate and closeout evidence pack are machine-readable",
        owning_layer="team_polisyos",
        phase="6.1",
        failure_class="closeout_evidence_gap",
        next_action="Run this aggregate readiness gate and attach its JSON to closeout evidence.",
        expected_verification_command="uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q",
        required_paths=(
            "tools/ci/check_policyos_production_quality_best_in_class.py",
            "tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py",
        ),
        component="readiness_aggregator",
    ),
)

_FINDING_BY_ID = {spec.finding_id: spec for spec in FINDING_SPECS}
_FINDINGS_BY_REPORT_ID: dict[str, tuple[FindingSpec, ...]] = {}
_report_index: defaultdict[str, list[FindingSpec]] = defaultdict(list)
for _spec in FINDING_SPECS:
    for _report_id in _spec.report_ids:
        _report_index[_report_id].append(_spec)
_FINDINGS_BY_REPORT_ID = {
    report_id: tuple(specs) for report_id, specs in sorted(_report_index.items())
}

_SPECIFIC_REF_OWNER = {
    "lex.normative_evidence": "PQL-001",
    "fabric.retrieval_trace": "PQL-009",
    "foundry.method_report": "PQL-001",
    "scientist.policy_grounding_matrix": "PQL-002",
    "lex.policy_conflict_check": "PQL-004",
    "quality.golden_scenario_contract": "PQL-007",
    "ir.metric_taxonomy": "PQL-003",
    "runtime.performance_summary": "PQL-011",
    "core.cas_ownership_evidence": "PQL-012",
    "runtime.production_data_quality": "PQL-015",
    "fabric.production_data_context": "PQL-015",
    "foundry.causal_statistical_validity": "PQL-016",
    "runtime.privacy_compliance_report": "PQL-018",
    "runtime.replay_manifest": "PQL-019",
    "runtime.drift_explanation": "PQL-019",
    "runtime.resilience_matrix": "PQL-020",
    "runtime.human_review_calibration": "PQL-021",
    "runtime.provider_model_quality_ledger": "PQL-022",
    "runtime.security_assurance_report": "PQL-017",
    "scientist.decision_artifact_quality": "PQL-023",
}

_REF_SPEC_BY_REPORT_ID = {
    report_id: _FINDING_BY_ID[_SPECIFIC_REF_OWNER.get(report_id, specs[0].finding_id)]
    for report_id, specs in _FINDINGS_BY_REPORT_ID.items()
}
_REF_PHASE_BY_REPORT_ID = {
    report_id: spec.phase for report_id, spec in _REF_SPEC_BY_REPORT_ID.items()
}
_REF_COMMAND_BY_REPORT_ID = {
    report_id: spec.expected_verification_command
    for report_id, spec in _REF_SPEC_BY_REPORT_ID.items()
}
_REF_ACTION_BY_REPORT_ID = {
    report_id: spec.next_action for report_id, spec in _REF_SPEC_BY_REPORT_ID.items()
}


def _build_inventory_payload(repo_root: Path) -> dict[str, Any]:
    return production_quality_evidence_inventory.build_inventory(repo_root)


def _build_invariant_registry_report(repo_root: Path) -> dict[str, Any]:
    return build_production_invariant_registry_report(repo_root=repo_root)


def _build_policy_design_case_record_registry_report(repo_root: Path) -> dict[str, Any]:
    return build_policy_design_case_record_registry_report()


def _build_proof_harness_payload(repo_root: Path) -> dict[str, Any]:
    return check_honest_diagnostics_proof_harness.build_proof_payload(repo_root=repo_root)


def _repo_path(repo_root: Path, rel_path: str) -> Path:
    return repo_root / rel_path


def _path_status(repo_root: Path, paths: Sequence[str]) -> tuple[str, list[str]]:
    missing = [path for path in paths if not _repo_path(repo_root, path).exists()]
    return ("fail" if missing else "pass"), missing


def _policy_design_evidence_portfolio_design_contract_component(
    repo_root: Path,
) -> dict[str, Any]:
    status, missing = _path_status(
        repo_root,
        (
            "src/polisyos/runtime/quality/evidence_portfolio.py",
            "src/polisyos/runtime/quality/scorecard.py",
            "schemas/runtime_quality/policy_design_evidence_portfolio_design_v1.schema.json",
            "tests/unit/runtime/quality/test_evidence_portfolio_design.py",
            "tests/unit/runtime/quality/test_policy_design_case_false_passes.py",
            "tests/repo_quality/tools/test_policy_design_case_coverage.py",
        ),
    )
    coverage_error: str | None = None
    try:
        coverage_payload = build_policy_design_case_coverage.build_coverage_payload(
            repo_root=repo_root
        )
        metric = dict(
            coverage_payload.get("metrics", {}).get("portfolio_predeclaration_pct", {})
        )
    except build_policy_design_case_coverage.CoverageInputError as exc:
        status = "fail"
        missing.append("coverage.portfolio_predeclaration_pct")
        coverage_error = str(exc)
        metric = {}
    if coverage_error is None and (
        metric.get("value") != 100.0
        or not str(metric.get("measurement_status") or "").startswith("wave15")
    ):
        status = "fail"
        missing.append("coverage.portfolio_predeclaration_pct")

    result = {
        "status": status,
        "missing": missing,
        "coverage_metric": {
            "value": metric.get("value"),
            "measurement_status": metric.get("measurement_status"),
            "numerator": metric.get("numerator"),
            "denominator": metric.get("denominator"),
        },
        "contract_surfaces": list(POLICY_DESIGN_EVIDENCE_PORTFOLIO_CONTRACT_SURFACES),
        "producer_guard": "validate_portfolio_predeclaration_before_evidence_acceptance",
        "scorecard_gate": "policy_design_wave15_evidence_portfolio_design",
        "expected_verification_command": (
            "uv run pytest tests/unit/runtime/quality/test_evidence_portfolio_design.py "
            "tests/unit/runtime/quality/test_policy_design_case_false_passes.py "
            "tests/repo_quality/tools/test_policy_design_case_coverage.py -q"
        ),
    }
    if coverage_error is not None:
        result["coverage_error"] = coverage_error
    return result


def _policy_design_run_cost_proportionality_contract_component(
    repo_root: Path,
) -> dict[str, Any]:
    status, missing = _path_status(
        repo_root,
        (
            "src/polisyos/runtime/quality/run_cost_proportionality.py",
            "src/polisyos/runtime/quality/scorecard.py",
            "schemas/runtime_quality/policy_design_run_cost_proportionality_ledger_v1.schema.json",
            "docs/reference/runtime/run-cost-proportionality-ledger.md",
            "tests/unit/runtime/quality/test_run_cost_proportionality.py",
            "tests/unit/runtime/quality/test_policy_design_case_false_passes.py",
            "tests/unit/tools/test_canary_evidence.py",
            "tests/repo_quality/tools/test_policy_design_case_coverage.py",
        ),
    )
    coverage_error: str | None = None
    try:
        coverage_payload = build_policy_design_case_coverage.build_coverage_payload(
            repo_root=repo_root
        )
        metric = dict(
            coverage_payload.get("metrics", {}).get("benchmarking_proportionality_pct", {})
        )
    except build_policy_design_case_coverage.CoverageInputError as exc:
        status = "fail"
        missing.append("coverage.benchmarking_proportionality_pct")
        coverage_error = str(exc)
        metric = {}
    if coverage_error is None and (
        float(metric.get("value") or 0.0) < 50.0
        or not str(metric.get("measurement_status") or "").startswith(("wave30", "wave31"))
    ):
        status = "fail"
        missing.append("coverage.benchmarking_proportionality_pct")

    result = {
        "status": status,
        "missing": missing,
        "coverage_metric": {
            "value": metric.get("value"),
            "measurement_status": metric.get("measurement_status"),
            "numerator": metric.get("numerator"),
            "denominator": metric.get("denominator"),
        },
        "contract_surfaces": list(POLICY_DESIGN_RUN_COST_PROPORTIONALITY_CONTRACT_SURFACES),
        "producer_guard": "build_run_cost_proportionality_ledger_from_quality_context",
        "scorecard_gate": "policy_design_wave30_run_cost_proportionality",
        "expected_verification_command": (
            "uv run pytest tests/unit/runtime/quality/test_run_cost_proportionality.py "
            "tests/unit/runtime/quality/test_policy_design_case_false_passes.py "
            "tests/unit/tools/test_canary_evidence.py::"
            "test_assemble_canary_evidence_projects_wave30_run_cost_ledger "
            "tests/repo_quality/tools/test_policy_design_case_coverage.py -q"
        ),
    }
    if coverage_error is not None:
        result["coverage_error"] = coverage_error
    return result


def _policy_design_best_in_class_benchmarking_contract_component(
    repo_root: Path,
) -> dict[str, Any]:
    status, missing = _path_status(
        repo_root,
        (
            "src/polisyos/runtime/quality/policy_benchmarking.py",
            "src/polisyos/runtime/quality/scorecard.py",
            "schemas/runtime_quality/policy_design_best_in_class_benchmarking_v1.schema.json",
            "docs/reference/runtime/best-in-class-benchmarking.md",
            "tests/unit/runtime/quality/test_policy_benchmarking.py",
            "tests/repo_quality/tools/test_policy_design_case_coverage.py",
            "tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py",
        ),
    )
    coverage_error: str | None = None
    try:
        coverage_payload = build_policy_design_case_coverage.build_coverage_payload(
            repo_root=repo_root
        )
        metric = dict(
            coverage_payload.get("metrics", {}).get("benchmarking_proportionality_pct", {})
        )
    except build_policy_design_case_coverage.CoverageInputError as exc:
        status = "fail"
        missing.append("coverage.benchmarking_proportionality_pct")
        coverage_error = str(exc)
        metric = {}
    if coverage_error is None and (
        float(metric.get("value") or 0.0) < 100.0
        or not str(metric.get("measurement_status") or "").startswith("wave31")
    ):
        status = "fail"
        missing.append("coverage.benchmarking_proportionality_pct")

    result = {
        "status": status,
        "missing": missing,
        "coverage_metric": {
            "value": metric.get("value"),
            "measurement_status": metric.get("measurement_status"),
            "numerator": metric.get("numerator"),
            "denominator": metric.get("denominator"),
        },
        "contract_surfaces": list(
            POLICY_DESIGN_BEST_IN_CLASS_BENCHMARKING_CONTRACT_SURFACES
        ),
        "validator": "validate_policy_benchmarking_record",
        "scorecard_gate": "policy_design_wave31_best_in_class_benchmarking",
        "expected_verification_command": (
            "uv run pytest tests/unit/runtime/quality/test_policy_benchmarking.py "
            "tests/repo_quality/tools/test_policy_design_case_coverage.py "
            "tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py::"
            "test_readiness_payload_exposes_wave31_best_in_class_benchmarking_component -q"
        ),
    }
    if coverage_error is not None:
        result["coverage_error"] = coverage_error
    return result


def _component_results(repo_root: Path, inventory_payload: Mapping[str, Any]) -> dict[str, Any]:
    results: dict[str, Any] = {}

    required_ref_rows = _rows(inventory_payload.get("serious_profile_required_refs"))
    inventory_failures = [
        _inventory_ref_failure(row)
        for row in required_ref_rows
        if _inventory_required_ref_is_hard_missing(row)
    ]
    inventory_warnings = [
        _inventory_ref_warning(row)
        for row in required_ref_rows
        if _inventory_required_ref_is_warning(row)
    ]
    results["quality_evidence_inventory"] = {
        "status": "fail" if inventory_failures else ("warn" if inventory_warnings else "pass"),
        "schema_version": inventory_payload.get("schema_version"),
        "required_ref_count": len(required_ref_rows),
        "failures": inventory_failures,
        "warnings": inventory_warnings,
        "expected_verification_command": (
            "uv run pytest tests/repo_quality/tools/test_production_quality_evidence_inventory.py -q"
        ),
    }

    benchmark_failures = _benchmark_authority_failures()
    results["benchmark_authority_checks"] = {
        "status": "fail" if benchmark_failures else "pass",
        "failures": benchmark_failures,
        "required_pack_kinds": list(quality_benchmark_authority.REQUIRED_PACK_KINDS),
        "expected_verification_command": (
            "uv run pytest tests/repo_quality/tools/test_quality_benchmark_authority.py -q"
        ),
    }

    local_stack_status, local_stack_missing = _path_status(
        repo_root,
        (
            "tools/quality/testing/local_integration_stack.py",
            "tests/repo_quality/tools/test_local_integration_stack.py",
            "apps/runtime-dashboard/playwright.config.ts",
        ),
    )
    stack_env = local_integration_stack._runtime_env_overrides()
    if stack_env.get("POLISYOS_LLM_SIMULATION_MODE") != "1":
        local_stack_status = "fail"
        local_stack_missing.append("POLISYOS_LLM_SIMULATION_MODE=1")
    results["local_stack_smoke"] = {
        "status": local_stack_status,
        "missing": local_stack_missing,
        "runtime_env_overrides": stack_env,
        "expected_verification_command": (
            "uv run pytest tests/repo_quality/tools/test_local_integration_stack.py "
            "tests/repo_quality/tools/test_runtime_dashboard_playwright_config.py -q"
        ),
    }

    scorecard_status, scorecard_missing = _path_status(
        repo_root,
        (
            "src/polisyos/runtime/quality/scorecard.py",
            "tests/unit/runtime/quality/test_scorecard.py",
            "tests/unit/runtime/quality/test_approval.py",
            "tests/unit/tools/test_canary_evidence.py",
        ),
    )
    results["scorecard_tests"] = {
        "status": scorecard_status,
        "missing": scorecard_missing,
        "approval_states": [
            "execution_failed",
            "quality_failed",
            "quality_warn",
            "approval_ready",
            "override_required",
        ],
        "expected_verification_command": (
            "uv run pytest tests/unit/runtime/quality/test_scorecard.py "
            "tests/unit/runtime/quality/test_approval.py tests/unit/tools/test_canary_evidence.py -q"
        ),
    }

    contract_status, contract_missing = _path_status(
        repo_root,
        (
            "tools/ops_runners/runtime/check_runtime_api_contract.py",
            "schemas/runtime_api_v1.openapi.json",
            "packages/runtime-api-client/runtimeApiClient.ts",
            "apps/runtime-dashboard/src/api/types.ts",
        ),
    )
    results["contract_drift_checks"] = {
        "status": contract_status,
        "missing": contract_missing,
        "expected_verification_command": (
            "uv run python tools/ops_runners/runtime/check_runtime_api_contract.py"
        ),
    }

    deterministic_status, deterministic_missing = _path_status(
        repo_root,
        (
            "tools/ops_runners/runtime/canary_matrix.py",
            "tools/ops_runners/runtime/run_canary_matrix.py",
            "tests/repo_quality/tools/test_canary_matrix.py",
        ),
    )
    matrix_payload = canary_matrix.build_matrix_payload()
    ready_lanes = int(matrix_payload.get("summary", {}).get("ready", 0))
    if ready_lanes <= 0:
        deterministic_status = "fail"
        deterministic_missing.append("canary_matrix.ready_lanes")
    results["deterministic_tests"] = {
        "status": deterministic_status,
        "missing": deterministic_missing,
        "ready_lane_count": ready_lanes,
        "expected_verification_command": (
            "uv run pytest tests/repo_quality/tools/test_canary_matrix.py -q"
        ),
    }

    assurance_status, assurance_missing = _path_status(
        repo_root,
        (
            "src/polisyos/runtime/quality/data_quality.py",
            "src/polisyos/foundry/validation/causal_validity.py",
            "src/polisyos/core/security/quality_gates.py",
            "src/polisyos/runtime/quality/compliance.py",
            "src/polisyos/runtime/quality/replay.py",
            "tools/quality/testing/runtime_resilience_matrix.py",
            "src/polisyos/runtime/quality/human_review.py",
            "tools/ops_runners/runtime/provider_quality_ledger.py",
            "src/polisyos/scientist/validation/decision_artifact_quality.py",
        ),
    )
    resilience_payload = runtime_resilience_matrix.build_matrix_payload(deterministic=True)
    if resilience_payload.get("mode") != "deterministic":
        assurance_status = "fail"
        assurance_missing.append("runtime_resilience_matrix.deterministic_mode")
    results["system_assurance_reports"] = {
        "status": assurance_status,
        "missing": assurance_missing,
        "resilience_summary": resilience_payload.get("summary", {}),
        "expected_verification_command": (
            "uv run pytest tests/repo_quality/tools/test_runtime_resilience_matrix.py "
            "tests/repo_quality/tools/test_provider_quality_ledger.py "
            "tests/unit/security/test_policyos_runtime_abuse_gates.py -q"
        ),
    }

    aggregator_status, aggregator_missing = _path_status(
        repo_root,
        (
            "tools/ci/check_policyos_production_quality_best_in_class.py",
            "tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py",
        ),
    )
    results["readiness_aggregator"] = {
        "status": aggregator_status,
        "missing": aggregator_missing,
        "expected_verification_command": (
            "uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q"
        ),
    }

    registry_report = _component_payload_or_error(
        lambda: _build_invariant_registry_report(repo_root)
    )
    registry_status = str(registry_report.get("status") or "fail")
    results["invariant_registry"] = {
        "status": "pass" if registry_status == "pass" else "fail",
        "schema_version": registry_report.get("schema_version"),
        "summary": registry_report.get("summary", {}),
        "issues": _rows(registry_report.get("issues")),
        "expected_verification_command": (
            "uv run pytest tests/repo_quality/tools/test_production_invariant_registry.py -q"
        ),
    }

    pdc_registry_report = _component_payload_or_error(
        lambda: _build_policy_design_case_record_registry_report(repo_root)
    )
    pdc_registry_status = str(pdc_registry_report.get("status") or "fail")
    results["policy_design_case_record_registry"] = {
        "status": "pass" if pdc_registry_status == "pass" else "fail",
        "schema_version": pdc_registry_report.get("schema_version"),
        "summary": pdc_registry_report.get("summary", {}),
        "issues": _rows(pdc_registry_report.get("issues")),
        "record_family_count": (
            pdc_registry_report.get("summary", {}).get("record_family_count")
            if isinstance(pdc_registry_report.get("summary"), Mapping)
            else None
        ),
        "expected_verification_command": (
            "uv run pytest tests/unit/runtime/quality/test_policy_design_case_record_registry.py "
            "tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q"
        ),
    }
    results["policy_design_evidence_portfolio_design_contract"] = (
        _policy_design_evidence_portfolio_design_contract_component(repo_root)
    )
    results["policy_design_run_cost_proportionality_contract"] = (
        _policy_design_run_cost_proportionality_contract_component(repo_root)
    )
    results["policy_design_best_in_class_benchmarking_contract"] = (
        _policy_design_best_in_class_benchmarking_contract_component(repo_root)
    )

    proof_payload = _component_payload_or_error(lambda: _build_proof_harness_payload(repo_root))
    proof_status = str(proof_payload.get("status") or "fail")
    results["hds_proof_harness"] = {
        "status": "pass" if proof_status == "pass" else "fail",
        "schema_version": proof_payload.get("schema_version"),
        "summary": proof_payload.get("summary", {}),
        "violations": _rows(proof_payload.get("violations")),
        "expected_verification_command": (
            "uv run pytest tests/repo_quality/tools/test_honest_diagnostics_proof_harness.py -q"
        ),
    }

    return results


def _component_payload_or_error(builder: Any) -> dict[str, Any]:
    try:
        payload = builder()
    except Exception as exc:  # pragma: no cover - surfaced in readiness payload.
        return {
            "status": "fail",
            "summary": {"error": f"{exc.__class__.__name__}: {exc}"},
            "issues": [
                {
                    "code": "component_payload_failed",
                    "message": f"{exc.__class__.__name__}: {exc}",
                }
            ],
            "violations": [
                {
                    "code": "component_payload_failed",
                    "message": f"{exc.__class__.__name__}: {exc}",
                }
            ],
        }
    return dict(payload) if isinstance(payload, Mapping) else {"status": "fail"}


def _benchmark_authority_failures() -> list[dict[str, Any]]:
    try:
        catalog = quality_benchmark_authority.load_quality_benchmark_catalog()
        return list(quality_benchmark_authority.validate_quality_benchmark_catalog(catalog))
    except Exception as exc:  # pragma: no cover - surfaced in payload.
        return [
            {
                "code": "benchmark_authority_load_failed",
                "message": f"{exc.__class__.__name__}: {exc}",
                "next_action": "Repair benchmark authority catalog before production-quality closeout.",
            }
        ]


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _inventory_required_ref_is_hard_missing(row: Mapping[str, Any]) -> bool:
    status = str(row.get("status") or "").strip()
    return status in SERIOUS_PROFILE_BLOCKING_REF_STATUSES


def _inventory_required_ref_is_warning(row: Mapping[str, Any]) -> bool:
    status = str(row.get("status") or "").strip()
    return status == "warn"


def _inventory_ref_warning(row: Mapping[str, Any]) -> dict[str, Any]:
    return _ref_guidance(row, status="warn")


def _inventory_ref_failure(row: Mapping[str, Any]) -> dict[str, Any]:
    return _ref_guidance(row, status="fail")


def _ref_guidance(row: Mapping[str, Any], *, status: str) -> dict[str, Any]:
    report_id = str(row.get("report_id") or "unknown")
    return {
        "status": status,
        "report_id": report_id,
        "expected_ref": str(row.get("expected_ref") or ""),
        "owning_layer": str(row.get("owner_runtime_layer") or "unknown"),
        "phase": _REF_PHASE_BY_REPORT_ID.get(report_id, "6.1"),
        "next_action": (
            str(row.get("first_missing_producer") or "").strip()
            or _REF_ACTION_BY_REPORT_ID.get(report_id)
            or "Attach the missing serious-profile evidence ref before approval."
        ),
        "expected_verification_command": _REF_COMMAND_BY_REPORT_ID.get(
            report_id,
            "uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q",
        ),
    }


def _serious_bundle_ref_failures(
    *,
    repo_root: Path,
    inventory_payload: Mapping[str, Any],
    serious_evidence_root: Path | None,
) -> list[dict[str, Any]]:
    if serious_evidence_root is None:
        return []
    root = (
        serious_evidence_root
        if serious_evidence_root.is_absolute()
        else repo_root / serious_evidence_root
    )
    failures: list[dict[str, Any]] = []
    for row in _rows(inventory_payload.get("serious_profile_required_refs")):
        expected_ref = str(row.get("expected_ref") or "").strip()
        if not expected_ref:
            continue
        if _expected_ref_present(root, expected_ref):
            continue
        failure = _ref_guidance(row, status="fail")
        failure["evidence_root"] = str(root)
        path_part, _, fragment = expected_ref.partition("#")
        observed_ref = (
            _observed_runtime_ref_fragment(root, fragment)
            if path_part == "runtime_quality_ref" and fragment
            else None
        )
        if observed_ref is not None:
            ref_key = fragment.lstrip("/").split(".")[-1]
            failure["source_truth_conflict"] = detect_source_truth_conflict(
                field_family="runtime_refs",
                authoritative_source="runtime.cas",
                authoritative_surface="runtime.cas",
                authoritative_values={ref_key: f"runtime_quality_ref#{ref_key}"},
                conflicting_source="runtime.canary_bundle",
                conflicting_surface="runtime.canary_bundle",
                conflicting_values={ref_key: observed_ref},
                fields=(ref_key,),
                downstream_impact=(
                    "Readiness would accept bundle-local refs as runtime CAS authority."
                ),
                lattice=load_source_truth_lattice(),
            )
        failures.append(failure)
    return failures


def _runtime_closeout_bundle_missing_failure() -> dict[str, Any]:
    return {
        "source": "runtime_closeout_evidence",
        "status": "fail",
        "code": "hds_runtime_closeout_bundle_missing",
        "minimum_closeout_gate": "runtime_closeout_authority",
        "message": (
            "--require-passing requires a fresh selected serious evidence bundle. "
            "Static inventory is only a producer map and cannot satisfy runtime closeout."
        ),
        "next_action": (
            "Run the deterministic canary matrix and pass --matrix-run-json, or pass "
            "--serious-evidence-root for the selected serious bundle."
        ),
        "expected_verification_command": (
            "uv run python tools/ops_runners/runtime/run_canary_matrix.py "
            "--deterministic --json-output "
            "_build/.tmp/production-quality/final_deterministic_matrix.json "
            "--timeout-s 1200"
        ),
    }


def _expected_ref_present(root: Path, expected_ref: str) -> bool:
    path_part, _, fragment = expected_ref.partition("#")
    if not fragment:
        return (root / path_part).exists()

    candidate_json = root / path_part
    if path_part.endswith(".json") and candidate_json.exists():
        payload = _load_json_or_none(candidate_json)
        return _payload_contains_ref_fragment(payload, fragment)

    if path_part == "runtime_quality_ref":
        return any(
            _payload_contains_runtime_ref_fragment(_load_json_or_none(path), fragment)
            for path in (
                root / "bundle.json",
                root / "job.json",
                root / "run.json",
                root / "quality_evidence" / "quality_scorecard.json",
            )
        )

    if path_part == "cas_manifest":
        return any(
            _payload_contains_ref_fragment(_load_json_or_none(path), fragment)
            for path in root.rglob("*.manifest.json")
        )

    return False


def _load_json_or_none(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _profile_from_lane_id(lane_id: str) -> str:
    for part in lane_id.split("__"):
        key, _, value = part.partition("-")
        if key == "profile":
            return value
    return ""


def _serious_evidence_bundles_from_matrix_run(
    *,
    repo_root: Path,
    matrix_run_json: Path | None,
) -> list[dict[str, Any]]:
    if matrix_run_json is None:
        return []
    matrix_path = matrix_run_json if matrix_run_json.is_absolute() else repo_root / matrix_run_json
    payload = _load_json_or_none(matrix_path)
    if not isinstance(payload, Mapping):
        return []
    bundles: list[dict[str, Any]] = []
    lanes = payload.get("lanes")
    if not isinstance(lanes, list):
        return bundles
    for lane in lanes:
        if not isinstance(lane, Mapping):
            continue
        lane_id = str(lane.get("lane_id") or "")
        profile = str(lane.get("profile") or _profile_from_lane_id(lane_id))
        if profile not in SERIOUS_MATRIX_PROFILES:
            continue
        if str(lane.get("status") or "") != "passed":
            continue
        if str(lane.get("scorecard_status") or "pass") != "pass":
            continue
        bundle_path_raw = lane.get("bundle_path")
        if not isinstance(bundle_path_raw, str) or not bundle_path_raw.strip():
            continue
        bundle_path = Path(bundle_path_raw)
        if not bundle_path.is_absolute():
            bundle_path = repo_root / bundle_path
        bundles.append(
            {
                "source": "matrix_run",
                "lane_id": lane_id,
                "profile": profile,
                "matrix_run_json": str(matrix_path),
                "root": bundle_path,
            }
        )
    return bundles


def _matrix_run_failure_rows(
    *,
    repo_root: Path,
    matrix_run_json: Path | None,
) -> list[dict[str, Any]]:
    if matrix_run_json is None:
        return []
    matrix_path = matrix_run_json if matrix_run_json.is_absolute() else repo_root / matrix_run_json
    payload = _load_json_or_none(matrix_path)
    if not isinstance(payload, Mapping):
        return []
    lanes = payload.get("lanes")
    if not isinstance(lanes, list):
        return []
    failures: list[dict[str, Any]] = []
    for lane in lanes:
        if not isinstance(lane, Mapping):
            continue
        lane_id = str(lane.get("lane_id") or "")
        profile = str(lane.get("profile") or _profile_from_lane_id(lane_id))
        if profile not in SERIOUS_MATRIX_PROFILES:
            continue
        status = str(lane.get("status") or "")
        scorecard_status = str(lane.get("scorecard_status") or "")
        if status == "passed" and scorecard_status == "pass":
            continue
        envelope = lane.get("failure_envelope")
        envelope_map = dict(envelope) if isinstance(envelope, Mapping) else {}
        envelope_code = str(envelope_map.get("code") or "unknown").strip() or "unknown"
        owner = str(envelope_map.get("owner") or "runtime-quality").strip() or "runtime-quality"
        root_cause_class = (
            str(
                envelope_map.get("root_cause_class")
                or envelope_map.get("type")
                or "runtime_lane_failure"
            ).strip()
            or "runtime_lane_failure"
        )
        next_action = (
            str(
                envelope_map.get("next_action")
                or "Inspect and disposition the matrix lane failure before closeout."
            ).strip()
            or "Inspect and disposition the matrix lane failure before closeout."
        )
        failures.append(
            {
                "source": "matrix_run",
                "status": "fail",
                "code": "hds_matrix_lane_not_passed",
                "minimum_closeout_gate": "runtime_closeout_authority",
                "lane_id": lane_id,
                "profile": profile,
                "matrix_run_json": str(matrix_path),
                "lane_status": status or "unknown",
                "scorecard_status": scorecard_status or "unknown",
                "failure_envelope_code": envelope_code,
                "failure_envelope": envelope_map,
                "owner": owner,
                "root_cause_class": root_cause_class,
                "next_action": next_action,
                "expected_verification_command": (
                    "uv run python tools/quality/validation/inspect_evidence_bundles.py "
                    f"--repo-root . --matrix-run-json {matrix_path} --json-output "
                    "_build/.tmp/production-quality/final_evidence_bundle_inspection.json"
                ),
            }
        )
    return failures


def _payload_contains_ref_fragment(payload: Any, fragment: str) -> bool:
    if payload is None:
        return False
    fragment = fragment.lstrip("/")
    if not fragment:
        return True
    keys = [part for part in fragment.replace("/", ".").split(".") if part]
    return _payload_has_path(payload, keys) or _payload_has_key(payload, keys[-1])


def _payload_contains_runtime_ref_fragment(payload: Any, fragment: str) -> bool:
    if payload is None:
        return False
    fragment = fragment.lstrip("/")
    if not fragment:
        return True
    keys = [part for part in fragment.replace("/", ".").split(".") if part]
    value = _payload_value_at_path(payload, keys)
    if not _runtime_ref_is_authority_bearing(value) and keys:
        value = _payload_authority_value_for_key(payload, keys[-1])
    return _runtime_ref_is_authority_bearing(value)


def _observed_runtime_ref_fragment(root: Path, fragment: str) -> str | None:
    fragment = fragment.lstrip("/")
    if not fragment:
        return None
    keys = [part for part in fragment.replace("/", ".").split(".") if part]
    for path in (
        root / "bundle.json",
        root / "job.json",
        root / "run.json",
        root / "quality_evidence" / "quality_scorecard.json",
    ):
        payload = _load_json_or_none(path)
        if payload is None:
            continue
        value = _payload_value_at_path(payload, keys)
        if value is None and keys:
            value = _payload_value_for_key(payload, keys[-1])
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _runtime_ref_is_authority_bearing(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    normalized = text.replace("\\", "/")
    if (
        normalized.startswith("quality_evidence/")
        or normalized.startswith("./")
        or normalized.startswith("../")
        or normalized.endswith(".json")
    ):
        return False
    return normalized.startswith(("sha256:", "cas://", "s3://", "gs://"))


def _payload_has_path(payload: Any, keys: Sequence[str]) -> bool:
    current = payload
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return False
        current = current[key]
    return current not in (None, "", [])


def _payload_value_at_path(payload: Any, keys: Sequence[str]) -> Any:
    current = payload
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _payload_has_key(payload: Any, key: str) -> bool:
    if isinstance(payload, Mapping):
        if key in payload and payload[key] not in (None, "", []):
            return True
        return any(_payload_has_key(value, key) for value in payload.values())
    if isinstance(payload, list):
        return any(_payload_has_key(value, key) for value in payload)
    return False


def _payload_value_for_key(payload: Any, key: str) -> Any:
    if isinstance(payload, Mapping):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _payload_value_for_key(value, key)
            if found is not None:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _payload_value_for_key(value, key)
            if found is not None:
                return found
    return None


def _component_failures(component_results: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for component_name, component in sorted(component_results.items()):
        if not isinstance(component, Mapping):
            continue
        if str(component.get("status") or "pass") != "fail":
            continue
        failures.append(
            {
                "status": "fail",
                "component": component_name,
                "expected_verification_command": component.get(
                    "expected_verification_command",
                    "uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q",
                ),
            }
        )
    return failures


def _component_warnings(component_results: Mapping[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for component_name, component in sorted(component_results.items()):
        if not isinstance(component, Mapping):
            continue
        if str(component.get("status") or "pass") != "warn":
            continue
        warnings.append({"status": "warn", "component": component_name})
    return warnings


def _minimum_closeout_gate_results(
    *,
    repo_root: Path,
    inventory_payload: Mapping[str, Any],
    invariant_registry_report: Mapping[str, Any],
    serious_evidence_root: Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if serious_evidence_root is None:
        return [], []

    root = (
        serious_evidence_root
        if serious_evidence_root.is_absolute()
        else repo_root / serious_evidence_root
    )
    bundle_payloads = _load_bundle_payloads(root)
    bundle = bundle_payloads.get("bundle", {})
    scorecard = bundle_payloads.get("scorecard", {})
    canary_kind = _text_value(bundle.get("canary_kind"))
    dev_smoke = canary_kind in DEV_SMOKE_CANARY_KINDS
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for source_name, payload in (("bundle", bundle), ("scorecard", scorecard)):
        status = _text_value(payload.get("quality_status") or payload.get("status"))
        if status in {"", "pass"}:
            continue
        finding = {
            "source": source_name,
            "status": "warn" if dev_smoke and status == "warn" else "fail",
            "code": "hds_serious_status_not_pass",
            "message": (
                "Serious closeout requires status=pass; warn is allowed only for "
                "explicit dev smoke bundles."
            ),
            "actual_status": status,
            "canary_kind": canary_kind or "unknown",
            "next_action": "Rebuild closeout from passing runtime authority evidence.",
            "expected_verification_command": (
                "uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q"
            ),
        }
        if finding["status"] == "warn":
            warnings.append(finding)
        else:
            failures.append(finding)

    scorecard_gate_failures, scorecard_gate_warnings = _scorecard_blocking_gate_results(
        scorecard=scorecard,
        canary_kind=canary_kind,
        dev_smoke=dev_smoke,
    )
    failures.extend(scorecard_gate_failures)
    warnings.extend(scorecard_gate_warnings)

    inventory_runtime_rows = [
        row
        for row in _rows(inventory_payload.get("serious_profile_required_refs"))
        if str(row.get("status") or "") == "runtime_emitted"
        and str(row.get("expected_ref") or "").startswith("runtime_quality_ref#")
    ]
    for row in inventory_runtime_rows:
        ref_key = str(row.get("expected_ref") or "").split("#", 1)[-1]
        if _authority_ref_value(bundle_payloads, ref_key) is not None:
            continue
        invariant = _invariant_for_ref_key(invariant_registry_report, ref_key)
        failures.append(
            {
                "source": "static_inventory",
                "status": "fail",
                "code": "hds_runtime_ref_missing",
                "report_id": str(row.get("report_id") or "unknown"),
                "invariant_id": str(invariant.get("invariant_id") or "unknown"),
                "pql_id": str(invariant.get("pql_id") or "unknown"),
                "minimum_closeout_gate": str(invariant.get("minimum_closeout_gate") or "unknown"),
                "expected_ref": str(row.get("expected_ref") or ""),
                "message": (
                    "Static inventory declares runtime-emitted support, but the "
                    "serious bundle does not contain an authority-bearing runtime ref."
                ),
                "next_action": str(row.get("first_missing_producer") or row.get("producer") or ""),
                "expected_verification_command": _REF_COMMAND_BY_REPORT_ID.get(
                    str(row.get("report_id") or ""),
                    "uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q",
                ),
            }
        )

    for invariant in _rows(invariant_registry_report.get("invariants")):
        invariant_failures, invariant_warnings = _minimum_closeout_invariant_results(
            invariant=invariant,
            bundle_payloads=bundle_payloads,
            canary_kind=canary_kind,
            dev_smoke=dev_smoke,
        )
        failures.extend(invariant_failures)
        warnings.extend(invariant_warnings)

    pdc_failures, pdc_warnings = _policy_design_case_closeout_results(
        bundle_payloads=bundle_payloads,
        canary_kind=canary_kind,
        dev_smoke=dev_smoke,
    )
    failures.extend(pdc_failures)
    warnings.extend(pdc_warnings)

    return failures, warnings


def _scorecard_blocking_gate_results(
    *,
    scorecard: Any,
    canary_kind: str,
    dev_smoke: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(scorecard, Mapping):
        return [], []

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    emitted: set[tuple[str, str]] = set()

    for gate in _scorecard_blocking_gate_rows(scorecard):
        code = _text_value(
            gate.get("code") or gate.get("gate") or gate.get("name")
        ) or "quality_scorecard_blocking_gate_failed"
        gate_name = _text_value(gate.get("name") or gate.get("gate"))
        emitted_key = (code, gate_name)
        if emitted_key in emitted:
            continue
        emitted.add(emitted_key)
        finding = _scorecard_blocking_gate_failure(scorecard=scorecard, gate=gate)
        if dev_smoke and _text_value(gate.get("status")) == "warn":
            finding["status"] = "warn"
            finding["canary_kind"] = canary_kind or "unknown"
            warnings.append(finding)
        else:
            failures.append(finding)

    return failures, warnings


def _scorecard_blocking_gate_rows(scorecard: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    gates = scorecard.get("quality_gates")
    if isinstance(gates, list):
        rows.extend(
            gate
            for gate in gates
            if isinstance(gate, Mapping)
            and _text_value(gate.get("status")) == "fail"
            and _truthy(gate.get("blocking"))
        )

    blocking_failures = scorecard.get("blocking_quality_failures")
    if isinstance(blocking_failures, list):
        rows.extend(
            failure
            for failure in blocking_failures
            if isinstance(failure, Mapping)
        )
    return rows


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _scorecard_blocking_gate_failure(
    *,
    scorecard: Mapping[str, Any],
    gate: Mapping[str, Any],
) -> dict[str, Any]:
    code = _text_value(
        gate.get("code") or gate.get("gate") or gate.get("name")
    ) or "quality_scorecard_blocking_gate_failed"
    gate_name = _text_value(gate.get("name") or gate.get("gate")) or code
    next_command = _text_value(gate.get("next_command"))
    return {
        "status": "fail",
        "code": code,
        "source": "quality_scorecard",
        "invariant_id": "quality_scorecard.blocking_gates",
        "pql_id": "PDC-WAVE14"
        if code.startswith(("policy_design_producer", "policy_design_final_claim_producer"))
        else "PQL-007",
        "minimum_closeout_gate": _scorecard_gate_minimum_closeout_gate(code, gate_name),
        "owning_layer": _text_value(gate.get("layer")) or "runtime.quality.scorecard",
        "message": _text_value(gate.get("message"))
        or f"Scorecard blocking gate failed: {gate_name}.",
        "evidence": {
            "gate_name": gate_name,
            "gate_status": _text_value(gate.get("status")) or "fail",
            "scorecard_status": _text_value(
                scorecard.get("quality_status") or scorecard.get("status")
            )
            or "unknown",
            "evidence_ref": _text_value(gate.get("evidence_ref")) or None,
        },
        "next_action": _text_value(gate.get("next_action"))
        or "Rebuild closeout from passing runtime authority evidence.",
        "expected_verification_command": next_command
        or (
            "uv run pytest tests/unit/runtime/quality/test_policy_design_case_false_passes.py "
            "tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q"
        ),
    }


def _scorecard_gate_minimum_closeout_gate(code: str, gate_name: str) -> str:
    if code.startswith(("policy_design_producer", "policy_design_final_claim_producer")):
        return "policy_design_case.producer_contract_runtime_evidence"
    if gate_name:
        return f"quality_scorecard.{gate_name}"
    return "quality_scorecard.blocking_gates"


def _invariant_for_ref_key(
    invariant_registry_report: Mapping[str, Any],
    ref_key: str,
) -> Mapping[str, Any]:
    for invariant in _rows(invariant_registry_report.get("invariants")):
        if ref_key in _string_values(invariant.get("required_ref_keys")):
            return invariant
    return {}


def _minimum_closeout_invariant_results(
    *,
    invariant: Mapping[str, Any],
    bundle_payloads: Mapping[str, Any],
    canary_kind: str,
    dev_smoke: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    scorecard = bundle_payloads.get("scorecard", {})
    required_ref_keys = _string_values(invariant.get("required_ref_keys"))
    required_artifact_kinds = _string_values(invariant.get("required_artifact_kinds"))
    required_scorecard_gates = _string_values(invariant.get("scorecard_gate_names"))

    for ref_key in required_ref_keys:
        runtime_ref = _authority_ref_value(bundle_payloads, ref_key)
        report = _quality_report_for_ref_key(bundle_payloads, ref_key)
        if runtime_ref is None:
            failures.append(
                _minimum_closeout_failure(
                    invariant,
                    code="hds_runtime_ref_missing",
                    source="invariant_registry",
                    message=f"Runtime authority ref is missing or not CAS-backed: {ref_key}.",
                    evidence={"ref_key": ref_key},
                )
            )
        elif not _runtime_event_for_ref(bundle_payloads, runtime_ref):
            failures.append(
                _minimum_closeout_failure(
                    invariant,
                    code="hds_runtime_event_ref_missing",
                    source="serious_evidence_bundle",
                    message=f"Runtime event ref is missing for {ref_key}.",
                    evidence={"ref_key": ref_key, "runtime_ref": runtime_ref},
                )
            )

        if (
            runtime_ref is not None
            and required_artifact_kinds
            and not _cas_artifact_ref_present(
                bundle_payloads,
                runtime_ref=runtime_ref,
                artifact_kinds=required_artifact_kinds,
            )
        ):
            failures.append(
                _minimum_closeout_failure(
                    invariant,
                    code="hds_cas_artifact_ref_missing",
                    source="serious_evidence_bundle",
                    message=f"CAS artifact ref is missing for {ref_key}.",
                    evidence={
                        "ref_key": ref_key,
                        "runtime_ref": runtime_ref,
                        "required_artifact_kinds": required_artifact_kinds,
                    },
                )
            )

        if report is None or not isinstance(report.get("authority_envelope"), Mapping):
            failures.append(
                _minimum_closeout_failure(
                    invariant,
                    code="hds_authority_envelope_missing",
                    source="serious_evidence_bundle",
                    message=f"Authority envelope is missing for {ref_key}.",
                    evidence={"ref_key": ref_key},
                )
            )

        schema_record = report.get("schema_compatibility") if isinstance(report, Mapping) else None
        schema_decision = (
            _text_value(schema_record.get("decision") or schema_record.get("status"))
            if isinstance(schema_record, Mapping)
            else ""
        )
        if schema_decision not in COMPATIBLE_SCHEMA_DECISIONS:
            failures.append(
                _minimum_closeout_failure(
                    invariant,
                    code="hds_schema_compatibility_missing",
                    source="serious_evidence_bundle",
                    message=f"Schema compatibility is missing or non-pass for {ref_key}.",
                    evidence={"ref_key": ref_key, "decision": schema_decision},
                )
            )

        for field_name, code in (
            ("same_input_closure_ref", "hds_same_input_closure_missing"),
            ("effective_mode_ref", "hds_mode_ledger_missing"),
            ("degradation_ledger_ref", "hds_degradation_ledger_missing"),
            ("projection_boundaries_ref", "hds_projection_boundary_missing"),
        ):
            alias = (
                "effective_mode_ledger_ref"
                if field_name == "effective_mode_ref"
                else "fallback_degradation_ref"
                if field_name == "degradation_ledger_ref"
                else "projection_boundary_ref"
                if field_name == "projection_boundaries_ref"
                else None
            )
            value = (
                _payload_value_for_key(report, field_name) if isinstance(report, Mapping) else None
            )
            if value is None and alias and isinstance(report, Mapping):
                value = _payload_value_for_key(report, alias)
            if _runtime_ref_is_authority_bearing(value):
                continue
            failures.append(
                _minimum_closeout_failure(
                    invariant,
                    code=code,
                    source="serious_evidence_bundle",
                    message=f"{field_name} is missing or not authority-bearing for {ref_key}.",
                    evidence={"ref_key": ref_key, "field": field_name},
                )
            )

        report_status = _text_value(report.get("status") if isinstance(report, Mapping) else "")
        if report_status and report_status != "pass":
            failures.append(
                _minimum_closeout_failure(
                    invariant,
                    code="hds_report_status_not_pass",
                    source="serious_evidence_bundle",
                    message=f"Serious quality report is non-pass for {ref_key}.",
                    evidence={"ref_key": ref_key, "status": report_status},
                )
            )

    for gate_name in required_scorecard_gates:
        gate_status = _scorecard_gate_status(scorecard, gate_name)
        if gate_status == "pass":
            continue
        finding = _minimum_closeout_failure(
            invariant,
            code="hds_scorecard_gate_not_pass",
            source="quality_scorecard",
            message=f"Scorecard gate is missing or non-pass: {gate_name}.",
            evidence={"gate_name": gate_name, "status": gate_status or "missing"},
        )
        if dev_smoke and gate_status == "warn":
            finding["status"] = "warn"
            finding["canary_kind"] = canary_kind or "unknown"
            warnings.append(finding)
        else:
            failures.append(finding)

    return failures, warnings


def _policy_design_case_closeout_results(
    *,
    bundle_payloads: Mapping[str, Any],
    canary_kind: str,
    dev_smoke: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if dev_smoke:
        return [], []
    if canary_kind and canary_kind not in SERIOUS_MATRIX_PROFILES:
        return [], []

    failures: list[dict[str, Any]] = []
    quality_reports = bundle_payloads.get("quality_reports")
    reports = quality_reports if isinstance(quality_reports, Mapping) else {}
    for ref_key in POLICY_DESIGN_CASE_RUNTIME_REF_KEYS:
        runtime_ref = _authority_ref_value(bundle_payloads, ref_key)
        if runtime_ref is None:
            failures.append(
                _policy_design_case_failure(
                    code=f"{ref_key}_missing",
                    source="serious_evidence_bundle",
                    message=f"Policy Design Case runtime identity ref is missing: {ref_key}.",
                    evidence={"ref_key": ref_key},
                )
            )
            continue
        if not _runtime_event_for_ref(bundle_payloads, runtime_ref):
            failures.append(
                _policy_design_case_failure(
                    code="policy_design_case_runtime_event_missing",
                    source="serious_evidence_bundle",
                    message=f"Policy Design Case runtime ref has no diagnostic event: {ref_key}.",
                    evidence={"ref_key": ref_key, "runtime_ref": runtime_ref},
                )
            )

    case_payload = reports.get(POLICY_DESIGN_CASE_QUALITY_FILE)
    if not isinstance(case_payload, Mapping):
        failures.append(
            _policy_design_case_failure(
                code="policy_design_case_missing",
                source="serious_evidence_bundle",
                message="Serious closeout bundle is missing policy_design_case.json.",
                evidence={"quality_file": POLICY_DESIGN_CASE_QUALITY_FILE},
            )
        )
    else:
        if not isinstance(case_payload.get("case_registry_entry"), Mapping):
            failures.append(
                _policy_design_case_failure(
                    code="policy_design_case_registry_entry_missing",
                    source="serious_evidence_bundle",
                    message="Policy Design Case is missing its registry entry.",
                    evidence={"quality_file": POLICY_DESIGN_CASE_QUALITY_FILE},
                )
            )
        try:
            validate_policy_design_case_profile(case_payload)
        except PolicyDesignCaseAuthorityError as exc:
            failures.append(
                _policy_design_case_failure(
                    code=exc.code,
                    source="serious_evidence_bundle",
                    message=str(exc),
                    evidence={"quality_file": POLICY_DESIGN_CASE_QUALITY_FILE},
                )
            )
        failures.extend(_policy_design_spine_failures(case_payload))
        failures.extend(
            _policy_design_claim_closeout_failures(
                case_payload,
                canary_kind=canary_kind or "production",
            )
        )

    semantic_payload = reports.get("semantic_binding_ledger.json")
    if isinstance(semantic_payload, Mapping):
        failures.extend(_semantic_binding_spine_failures(semantic_payload))

    for filename in sorted(POLICY_DESIGN_PARALLEL_AUTHORITY_FILES & set(reports)):
        failures.append(
            _policy_design_case_failure(
                code="policy_design_parallel_case_authority",
                source="serious_evidence_bundle",
                message="Serious closeout bundle contains a parallel Policy Design Case authority.",
                evidence={"quality_file": filename},
            )
        )

    return failures, []


def _policy_design_spine_failures(
    case_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    concept_spine = _concept_spine_from_case(case_payload)
    if isinstance(concept_spine, Mapping):
        try:
            validated = validate_policy_design_case_concept_spine(concept_spine)
        except PolicyDesignCaseAuthorityError as exc:
            failures.append(
                _policy_design_spine_failure(
                    code=exc.code,
                    message=str(exc),
                    evidence={"quality_file": POLICY_DESIGN_CASE_QUALITY_FILE},
                )
            )
        else:
            failures.extend(
                _policy_design_blocker_failures(
                    validated,
                    source="policy_design_case.concept_spine",
                )
            )
    jurisdiction_spine = case_payload.get("jurisdiction_spine")
    if isinstance(jurisdiction_spine, Mapping):
        try:
            validated = validate_policy_design_jurisdiction_spine(jurisdiction_spine)
        except PolicyDesignCaseAuthorityError as exc:
            failures.append(
                _policy_design_spine_failure(
                    code=exc.code,
                    message=str(exc),
                    evidence={"quality_file": POLICY_DESIGN_CASE_QUALITY_FILE},
                )
            )
        else:
            failures.extend(
                _policy_design_blocker_failures(
                    validated,
                    source="policy_design_case.jurisdiction_spine",
                )
            )
    return failures


def _policy_design_claim_closeout_failures(
    case_payload: Mapping[str, Any],
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for gate in policy_design_case_claim_closeout_gates(
        case_payload,
        canary_kind=canary_kind,
    ):
        code = _text_value(gate.get("code") or gate.get("gate") or gate.get("name"))
        if not code:
            continue
        failures.append(
            _policy_design_claim_closeout_failure(
                code=code,
                message=(
                    _text_value(gate.get("message"))
                    or f"Policy Design Case claim closeout gate failed: {code}."
                ),
                evidence={
                    "quality_file": POLICY_DESIGN_CASE_QUALITY_FILE,
                    "gate_name": _text_value(gate.get("name")) or code,
                    "evidence_ref": _text_value(gate.get("evidence_ref")) or None,
                },
                missing_input=_text_value(gate.get("missing_input")) or None,
                affected_claim=_text_value(gate.get("affected_claim")) or None,
                next_command=_text_value(gate.get("next_command")) or None,
            )
        )
    return failures


def _concept_spine_from_case(case_payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    spine = case_payload.get("concept_spine")
    if isinstance(spine, Mapping):
        return spine
    nodes = case_payload.get("nodes")
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if isinstance(node, Mapping) and str(node.get("node_type") or "") == "concept_spine":
            return node
    return None


def _policy_design_blocker_failures(
    validated: Mapping[str, Any],
    *,
    source: str,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for blocker in _rows(validated.get("blockers")):
        failures.append(
            _policy_design_spine_failure(
                code=str(blocker.get("code") or "policy_design_spine_blocked"),
                message=str(blocker.get("message") or "Policy Design spine is blocked."),
                evidence={
                    "source": source,
                    "blocker": blocker,
                },
                missing_input=_text_value(blocker.get("missing_input")) or None,
                conflicting_producer=(
                    _text_value(blocker.get("conflicting_producer"))
                    or _text_value(blocker.get("source_component"))
                    or None
                ),
                affected_claim=_text_value(blocker.get("affected_claim")) or None,
                next_command=(
                    _text_value(blocker.get("next_diagnostic_command"))
                    or _text_value(blocker.get("next_command"))
                    or None
                ),
            )
        )
    if not failures and str(validated.get("status") or "") == "blocked":
        failures.append(
            _policy_design_spine_failure(
                code="policy_design_spine_blocked",
                message="Policy Design spine is blocked without a scorecard-readable blocker.",
                evidence={"source": source},
            )
        )
    return failures


def _semantic_binding_spine_failures(
    semantic_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    try:
        ledger = deserialize_semantic_binding_ledger(semantic_payload)
    except (TypeError, ValueError) as exc:
        return [
            _policy_design_spine_failure(
                code="semantic_binding_ledger_invalid",
                message=f"Semantic binding ledger is invalid: {exc}",
                evidence={"quality_file": "semantic_binding_ledger.json"},
            )
        ]
    evaluation = evaluate_semantic_binding_ledger(ledger)
    failures: list[dict[str, Any]] = []
    for issue in evaluation.issues:
        if not _is_spine_issue_code(issue.code):
            continue
        failures.append(
            _policy_design_spine_failure(
                code=issue.code,
                message=issue.message,
                evidence={
                    "quality_file": "semantic_binding_ledger.json",
                    "refs": list(issue.refs),
                },
                missing_input=issue.missing_input,
                conflicting_producer=issue.conflicting_producer,
                affected_claim=issue.affected_claim or issue.claim_id,
                next_command=issue.next_command,
            )
        )
    return failures


def _is_spine_issue_code(code: str) -> bool:
    normalized = code.casefold()
    return "spine" in normalized or normalized in {
        "semantic_producer_concept_mismatch",
        "semantic_producer_jurisdiction_mismatch",
        "semantic_producer_unit_mismatch",
        "semantic_producer_period_mismatch",
        "semantic_producer_geography_mismatch",
        "semantic_local_concept_leakage",
    }


def _policy_design_spine_failure(
    *,
    code: str,
    message: str,
    evidence: Mapping[str, Any],
    missing_input: str | None = None,
    conflicting_producer: str | None = None,
    affected_claim: str | None = None,
    next_command: str | None = None,
) -> dict[str, Any]:
    return _policy_design_case_failure(
        code=code,
        source="semantic_binding_ledger"
        if code.startswith("semantic_")
        else "serious_evidence_bundle",
        message=message,
        evidence=evidence,
        minimum_closeout_gate="policy_design_case.spine_closure",
        next_action=(
            "Regenerate concept, jurisdiction, unit, period, geography, and claim "
            "bindings against the stable per-run spine refs."
        ),
        expected_verification_command=(
            next_command
            or "uv run pytest tests/unit/runtime/quality/test_semantic_binding.py "
            "tests/unit/runtime/quality/test_scorecard.py -q"
        ),
        diagnostics={
            "missing_input": missing_input,
            "conflicting_producer": conflicting_producer,
            "affected_claim": affected_claim,
            "next_command": next_command,
        },
    )


def _policy_design_claim_closeout_failure(
    *,
    code: str,
    message: str,
    evidence: Mapping[str, Any],
    missing_input: str | None = None,
    affected_claim: str | None = None,
    next_command: str | None = None,
) -> dict[str, Any]:
    return _policy_design_case_failure(
        code=code,
        source="serious_evidence_bundle",
        message=message,
        evidence=evidence,
        minimum_closeout_gate="policy_design_case.claim_argument_closeout_gate",
        next_action=(
            "Regenerate final major claims as assurance-case nodes with runtime "
            "producer and portfolio refs, argument, warrant, rebuttal, visible "
            "counter-evidence, assurance-deficit, blocker, and BERL evidence."
        ),
        expected_verification_command=(
            next_command
            or "uv run pytest tests/unit/runtime/quality/test_policy_design_case_false_passes.py "
            "tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q"
        ),
        diagnostics={
            "missing_input": missing_input,
            "affected_claim": affected_claim,
            "next_command": next_command,
        },
    )


def _policy_design_case_failure(
    *,
    code: str,
    source: str,
    message: str,
    evidence: Mapping[str, Any],
    minimum_closeout_gate: str = "policy_design_case_runtime_identity",
    next_action: str | None = None,
    expected_verification_command: str | None = None,
    diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "status": "fail",
        "code": code,
        "source": source,
        "invariant_id": "policy_design_case.wave5",
        "pql_id": "PDC-WAVE5",
        "minimum_closeout_gate": minimum_closeout_gate,
        "owning_layer": "runtime.quality.policy_design_case",
        "message": message,
        "evidence": dict(evidence),
        "next_action": next_action
        or (
            "Materialize policy intent, capability ledger, case registry entry, "
            "and runtime Policy Design Case profile before serious closeout."
        ),
        "expected_verification_command": expected_verification_command
        or (
            "uv run pytest tests/unit/runtime/quality/test_scorecard.py "
            "tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q"
        ),
    }
    for key, value in (diagnostics or {}).items():
        if value is not None:
            payload[key] = value
    return payload


def _minimum_closeout_failure(
    invariant: Mapping[str, Any],
    *,
    code: str,
    source: str,
    message: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "status": "fail",
        "code": code,
        "source": source,
        "invariant_id": str(invariant.get("invariant_id") or "unknown"),
        "pql_id": str(invariant.get("pql_id") or "unknown"),
        "minimum_closeout_gate": str(invariant.get("minimum_closeout_gate") or "unknown"),
        "owning_layer": str(invariant.get("final_owner") or "unknown"),
        "message": message,
        "evidence": dict(evidence),
        "next_action": str(
            invariant.get("next_diagnostic_command")
            or "Rebuild closeout with complete runtime authority evidence."
        ),
        "expected_verification_command": str(
            invariant.get("next_diagnostic_command")
            or "uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q"
        ),
    }


def _load_bundle_payloads(root: Path) -> dict[str, Any]:
    payloads: dict[str, Any] = {
        "bundle": _load_json_or_none(root / "bundle.json") or {},
        "job": _load_json_or_none(root / "job.json") or {},
        "run": _load_json_or_none(root / "run.json") or {},
        "artifacts": _load_json_or_none(root / "artifacts.json") or {},
        "dashboard": _load_json_or_none(root / "dashboard.json") or {},
        "scorecard": _load_json_or_none(root / "quality_evidence" / "quality_scorecard.json") or {},
    }
    quality_reports: dict[str, Any] = {}
    quality_dir = root / "quality_evidence"
    if quality_dir.exists():
        for path in sorted(quality_dir.glob("*.json")):
            if path.name == "quality_scorecard.json":
                continue
            quality_reports[path.name] = _load_json_or_none(path) or {}
    payloads["quality_reports"] = quality_reports
    manifests: list[Any] = []
    for path in sorted(root.rglob("*.manifest.json")):
        manifests.append(_load_json_or_none(path) or {})
    payloads["cas_manifests"] = manifests
    return payloads


def _authority_ref_value(bundle_payloads: Mapping[str, Any], ref_key: str) -> str | None:
    for payload_name in ("job", "run", "scorecard", "bundle", "artifacts"):
        value = _payload_authority_value_for_key(bundle_payloads.get(payload_name), ref_key)
        if value is not None:
            return value
    return None


def _payload_authority_value_for_key(payload: Any, key: str) -> str | None:
    if isinstance(payload, Mapping):
        if key in payload and _runtime_ref_is_authority_bearing(payload[key]):
            return str(payload[key]).strip()
        for value in payload.values():
            found = _payload_authority_value_for_key(value, key)
            if found is not None:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _payload_authority_value_for_key(value, key)
            if found is not None:
                return found
    return None


def _quality_report_for_ref_key(
    bundle_payloads: Mapping[str, Any],
    ref_key: str,
) -> Mapping[str, Any] | None:
    quality_reports = bundle_payloads.get("quality_reports")
    if not isinstance(quality_reports, Mapping):
        return None
    index = quality_reports.get("minimum_closeout_authority_index.json")
    if isinstance(index, Mapping):
        records = index.get("records")
        if isinstance(records, Mapping):
            record = records.get(ref_key)
            if isinstance(record, Mapping):
                return record
    filename = _REPORT_FILE_BY_RUNTIME_REF.get(ref_key)
    if filename:
        report = quality_reports.get(filename)
        if isinstance(report, Mapping):
            return report
    for report in quality_reports.values():
        if not isinstance(report, Mapping):
            continue
        envelope = report.get("authority_envelope")
        if isinstance(envelope, Mapping) and _runtime_ref_is_authority_bearing(
            envelope.get("cas_ref") or envelope.get("artifact_ref")
        ):
            return report
    return None


def _runtime_event_for_ref(
    bundle_payloads: Mapping[str, Any],
    runtime_ref: str,
) -> bool:
    for event in _diagnostic_events(bundle_payloads):
        if runtime_ref in _diagnostic_event_ref_values(event):
            return True
    return False


def _diagnostic_events(payload: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if key == "diagnostic_events":
                if isinstance(value, list):
                    events.extend(dict(item) for item in value if isinstance(item, Mapping))
                elif isinstance(value, Mapping):
                    events.append(dict(value))
            else:
                events.extend(_diagnostic_events(value))
    elif isinstance(payload, list):
        for item in payload:
            events.extend(_diagnostic_events(item))
    return events


def _diagnostic_event_ref_values(event: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for key in (
        "artifact_ref",
        "cas_ref",
        "payload_ref",
        "runtime_cas_ref",
        "runtime_event_ref",
    ):
        value = event.get(key)
        if isinstance(value, str) and value:
            refs.add(value)
    for value in event.values():
        if isinstance(value, str) and _runtime_ref_is_authority_bearing(value):
            refs.add(value)
    return refs


def _cas_artifact_ref_present(
    bundle_payloads: Mapping[str, Any],
    *,
    runtime_ref: str,
    artifact_kinds: Sequence[str],
) -> bool:
    if not _runtime_ref_is_authority_bearing(runtime_ref):
        return False
    quality_reports = bundle_payloads.get("quality_reports")
    if isinstance(quality_reports, Mapping):
        for report in quality_reports.values():
            if not isinstance(report, Mapping):
                continue
            cas_refs = report.get("cas_artifact_refs")
            if isinstance(cas_refs, Mapping) and runtime_ref in {
                str(value) for value in cas_refs.values()
            }:
                return True
    for manifest in bundle_payloads.get("cas_manifests", []):
        if not isinstance(manifest, Mapping):
            continue
        if runtime_ref in json.dumps(manifest, sort_keys=True):
            return True
        manifest_roles = {
            str(item.get("role") or "")
            for item in manifest.get("inputs", [])
            if isinstance(item, Mapping)
        }
        if set(artifact_kinds) & manifest_roles:
            return True
    return False


def _scorecard_gate_status(scorecard: Any, gate_name: str) -> str:
    if not isinstance(scorecard, Mapping):
        return ""
    gates = scorecard.get("quality_gates")
    if not isinstance(gates, list):
        return ""
    for gate in gates:
        if not isinstance(gate, Mapping):
            continue
        name = str(gate.get("name") or gate.get("gate") or "").strip()
        if name == gate_name:
            return str(gate.get("status") or "").strip()
    return ""


def _hds_substrate_coverage(
    *,
    invariant_registry_report: Mapping[str, Any],
    proof_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    registry_gates = {
        str(row.get("minimum_closeout_gate") or "")
        for row in _rows(invariant_registry_report.get("invariants"))
    }
    proof_gates = {
        str(row.get("minimum_closeout_gate") or "")
        for row in _rows(proof_payload.get("invariant_proofs"))
    }
    failing_proof_gates = {
        str(row.get("minimum_closeout_gate") or "")
        for row in _rows(proof_payload.get("violations"))
    }
    rows: list[dict[str, Any]] = []
    for item in HDS_SUBSTRATE_COVERAGE:
        gates = list(item["minimum_closeout_gates"])
        rows.append(
            {
                "backlog_item_id": item["backlog_item_id"],
                "title": item["title"],
                "minimum_closeout_gates": gates,
                "readiness_enforced": True,
                "registry_rows_present": sorted(set(gates) & registry_gates),
                "proof_rows_present": sorted(set(gates) & proof_gates),
                "status": "fail" if set(gates) & failing_proof_gates else "pass",
            }
        )
    return rows


def _string_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _text_value(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _external_evidence(paths: Sequence[Path], *, repo_root: Path) -> dict[str, Any]:
    attachments: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    for raw_path in paths:
        path = raw_path if raw_path.is_absolute() else repo_root / raw_path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            warnings.append(
                {
                    "path": str(path),
                    "code": "external_evidence_missing",
                    "message": "Optional external evidence file was not found.",
                }
            )
            continue
        except json.JSONDecodeError as exc:
            warnings.append(
                {
                    "path": str(path),
                    "code": "external_evidence_invalid_json",
                    "message": str(exc),
                }
            )
            continue
        if not isinstance(payload, Mapping):
            warnings.append(
                {
                    "path": str(path),
                    "code": "external_evidence_not_object",
                    "message": "Optional external evidence must be a JSON object.",
                }
            )
            continue
        attachments.append(
            {
                "path": str(path),
                "schema_version": str(payload.get("schema_version") or "unknown"),
                "status": str(payload.get("status") or "attached"),
                "provider": payload.get("provider"),
                "evidence_ref": payload.get("evidence_ref"),
            }
        )
    return {
        "required_for_deterministic_gate": False,
        "attached_count": len(attachments),
        "attachments": attachments,
        "warnings": warnings,
    }


def _finding_status(
    spec: FindingSpec,
    *,
    component_results: Mapping[str, Any],
    inventory_payload: Mapping[str, Any],
    ref_failures: Sequence[Mapping[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    notes: list[dict[str, Any]] = []
    failure_report_ids = {str(failure.get("report_id") or "") for failure in ref_failures}
    if set(spec.report_ids) & failure_report_ids:
        notes.extend(
            dict(failure)
            for failure in ref_failures
            if str(failure.get("report_id") or "") in set(spec.report_ids)
        )
        return "fail", notes

    if spec.component:
        component = component_results.get(spec.component)
        if isinstance(component, Mapping):
            component_status = str(component.get("status") or "pass")
            if component_status == "fail":
                notes.append(
                    {
                        "status": "fail",
                        "component": spec.component,
                        "next_action": spec.next_action,
                        "expected_verification_command": spec.expected_verification_command,
                    }
                )
                return "fail", notes
            if component_status == "warn":
                notes.append(
                    {
                        "status": "warn",
                        "component": spec.component,
                        "next_action": spec.next_action,
                        "expected_verification_command": spec.expected_verification_command,
                    }
                )
                return "warn", notes

    warning_report_ids = _inventory_warning_report_ids(inventory_payload)
    if set(spec.report_ids) & warning_report_ids:
        notes.append(
            {
                "status": "warn",
                "component": "quality_evidence_inventory",
                "report_ids": sorted(set(spec.report_ids) & warning_report_ids),
                "next_action": spec.next_action,
                "expected_verification_command": spec.expected_verification_command,
            }
        )
        return "warn", notes

    return "pass", notes


def _inventory_warning_report_ids(inventory_payload: Mapping[str, Any]) -> set[str]:
    return {
        str(row.get("report_id") or "")
        for row in _rows(inventory_payload.get("serious_profile_required_refs"))
        if _inventory_required_ref_is_warning(row)
    }


def _build_findings(
    *,
    repo_root: Path,
    component_results: Mapping[str, Any],
    inventory_payload: Mapping[str, Any],
    ref_failures: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for spec in FINDING_SPECS:
        path_status, missing_paths = _path_status(repo_root, spec.required_paths)
        status, notes = _finding_status(
            spec,
            component_results=component_results,
            inventory_payload=inventory_payload,
            ref_failures=ref_failures,
        )
        if path_status == "fail":
            status = "fail"
            notes.append(
                {
                    "status": "fail",
                    "missing_paths": missing_paths,
                    "next_action": spec.next_action,
                    "expected_verification_command": spec.expected_verification_command,
                }
            )
        findings.append(
            {
                "finding_id": spec.finding_id,
                "status": status,
                "severity": spec.severity,
                "title": spec.title,
                "failure_class": spec.failure_class,
                "owning_layer": spec.owning_layer,
                "phase": spec.phase,
                "next_action": spec.next_action,
                "expected_verification_command": spec.expected_verification_command,
                "component": spec.component,
                "report_ids": list(spec.report_ids),
                "required_paths": list(spec.required_paths),
                "missing_paths": missing_paths,
                "notes": notes,
            }
        )
    return findings


def _summary(findings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(finding.get("status") or "unknown") for finding in findings)
    class_counts: dict[str, dict[str, int]] = {}
    for failure_class in FAILURE_CLASSES:
        rows = [finding for finding in findings if finding.get("failure_class") == failure_class]
        row_counts = Counter(str(row.get("status") or "unknown") for row in rows)
        class_counts[failure_class] = {
            "pass": row_counts.get("pass", 0),
            "fail": row_counts.get("fail", 0),
            "warn": row_counts.get("warn", 0),
            "total": len(rows),
        }
    return {
        "finding_count": len(findings),
        "status_counts": {status: status_counts.get(status, 0) for status in STATUS_VALUES},
        "failure_class_counts": class_counts,
    }


def build_readiness_payload(
    *,
    repo_root: Path = REPO_ROOT,
    external_evidence_paths: Sequence[Path] = (),
    serious_evidence_root: Path | None = None,
    matrix_run_json: Path | None = None,
    require_runtime_closeout_evidence: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    serious_evidence_bundles: list[dict[str, Any]] = []
    if serious_evidence_root is not None:
        explicit_root = (
            serious_evidence_root
            if serious_evidence_root.is_absolute()
            else repo_root / serious_evidence_root
        )
        serious_evidence_bundles.append(
            {
                "source": "serious_evidence_root",
                "root": explicit_root,
                "profile": "explicit",
            }
        )
    serious_evidence_bundles.extend(
        _serious_evidence_bundles_from_matrix_run(
            repo_root=repo_root,
            matrix_run_json=matrix_run_json,
        )
    )
    matrix_run_failures = _matrix_run_failure_rows(
        repo_root=repo_root,
        matrix_run_json=matrix_run_json,
    )
    inventory_payload = _build_inventory_payload(repo_root)
    component_results = _component_results(repo_root, inventory_payload)
    inventory_failures = [
        failure
        for failure in component_results["quality_evidence_inventory"]["failures"]
        if isinstance(failure, Mapping)
    ]
    bundle_failures: list[dict[str, Any]] = []
    for bundle in serious_evidence_bundles:
        bundle_failures.extend(
            _serious_bundle_ref_failures(
                repo_root=repo_root,
                inventory_payload=inventory_payload,
                serious_evidence_root=bundle["root"],
            )
        )
    ref_failures = [*inventory_failures, *bundle_failures]
    invariant_registry_report = _component_payload_or_error(
        lambda: _build_invariant_registry_report(repo_root)
    )
    proof_payload = _component_payload_or_error(lambda: _build_proof_harness_payload(repo_root))
    minimum_closeout_failures: list[dict[str, Any]] = []
    minimum_closeout_warnings: list[dict[str, Any]] = []
    closeout_compatibility: list[dict[str, Any]] = []
    for bundle in serious_evidence_bundles:
        bundle_minimum_failures, bundle_minimum_warnings = _minimum_closeout_gate_results(
            repo_root=repo_root,
            inventory_payload=inventory_payload,
            invariant_registry_report=invariant_registry_report,
            serious_evidence_root=bundle["root"],
        )
        minimum_closeout_failures.extend(bundle_minimum_failures)
        minimum_closeout_warnings.extend(bundle_minimum_warnings)
        compatibility_record = build_closeout_compatibility_record_from_bundle_dir(
            bundle["root"]
        )
        compatibility_record["bundle_root"] = str(bundle["root"])
        compatibility_record["source"] = bundle.get("source")
        closeout_compatibility.append(compatibility_record)
        minimum_closeout_failures.extend(
            compatibility_failures_for_readiness(
                compatibility_record,
                bundle_root=bundle["root"],
            )
        )
    minimum_closeout_failures.extend(matrix_run_failures)
    if require_runtime_closeout_evidence and not serious_evidence_bundles:
        missing_bundle = _runtime_closeout_bundle_missing_failure()
        ref_failures.append(dict(missing_bundle))
        minimum_closeout_failures.append(missing_bundle)
    findings = _build_findings(
        repo_root=repo_root,
        component_results=component_results,
        inventory_payload=inventory_payload,
        ref_failures=ref_failures,
    )
    summary = _summary(findings)
    component_failures = _component_failures(component_results)
    component_warnings = _component_warnings(component_results)
    fail_count = (
        summary["status_counts"]["fail"] + len(component_failures) + len(minimum_closeout_failures)
    )
    warn_count = (
        summary["status_counts"]["warn"] + len(component_warnings) + len(minimum_closeout_warnings)
    )
    status = "fail" if fail_count else ("warn" if warn_count else "pass")
    passes_required = fail_count == 0
    return {
        "schema_version": SCHEMA_VERSION,
        "assessment_id": ASSESSMENT_ID,
        "tool": TOOL_NAME,
        "repo_root": str(repo_root),
        "status": status,
        "passes_required": passes_required,
        "passes_all": passes_required and warn_count == 0,
        "deterministic_gate": {
            "requires_live_llm": False,
            "llm_simulation_mode": DETERMINISTIC_ENV["POLISYOS_LLM_SIMULATION_MODE"],
            "live_provider_lanes": "optional_external_evidence",
            "network_required": False,
        },
        "live_provider_evidence": _external_evidence(
            external_evidence_paths,
            repo_root=repo_root,
        ),
        "summary": summary,
        "findings": findings,
        "required_serious_profile_ref_failures": ref_failures,
        "minimum_closeout_gate_failures": minimum_closeout_failures,
        "minimum_closeout_gate_warnings": minimum_closeout_warnings,
        "closeout_compatibility": closeout_compatibility,
        "matrix_run_failures": matrix_run_failures,
        "serious_evidence_bundles": [
            {key: str(value) if isinstance(value, Path) else value for key, value in bundle.items()}
            for bundle in serious_evidence_bundles
        ],
        "component_failures": component_failures,
        "component_warnings": component_warnings,
        "hds_substrate_coverage": _hds_substrate_coverage(
            invariant_registry_report=invariant_registry_report,
            proof_payload=proof_payload,
        ),
        "component_results": component_results,
        "verification": {
            "acceptance_commands": [
                "uv run python tools/ci/check_policyos_production_quality_best_in_class.py --repo-root . --output-format json --require-passing",
                "uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q",
            ],
            "deterministic_commands": sorted(
                {
                    spec.expected_verification_command
                    for spec in FINDING_SPECS
                    if "live" not in spec.expected_verification_command
                }
            ),
        },
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _format_text(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"{TOOL_NAME}: {payload['status']}",
        f"findings: {summary['finding_count']} "
        f"pass={summary['status_counts']['pass']} "
        f"warn={summary['status_counts']['warn']} "
        f"fail={summary['status_counts']['fail']}",
        "deterministic: live LLM calls are not required",
    ]
    for finding in payload["findings"]:
        if finding["status"] == "pass":
            continue
        lines.append(
            f"[{finding['status']}] {finding['finding_id']} "
            f"{finding['failure_class']} {finding['owning_layer']} "
            f"phase={finding['phase']}: {finding['next_action']}"
        )
        lines.append(f"  verify: {finding['expected_verification_command']}")
    return "\n".join(lines) + "\n"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    parser.add_argument("--require-passing", action="store_true")
    parser.add_argument(
        "--external-evidence",
        "--live-provider-evidence",
        action="append",
        type=Path,
        default=[],
        help="Optional live-provider or other external JSON evidence to attach without gating deterministic CI.",
    )
    parser.add_argument(
        "--serious-evidence-root",
        type=Path,
        help="Optional serious-profile evidence bundle root whose required refs must be present.",
    )
    parser.add_argument(
        "--matrix-run-json",
        type=Path,
        help=(
            "Optional deterministic canary matrix run JSON. With --require-passing, "
            "selected passed serious bundles in this matrix are validated as runtime evidence."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    matrix_run_json = args.matrix_run_json
    if args.require_passing and args.serious_evidence_root is None and matrix_run_json is None:
        default_matrix = (
            args.repo_root / "_build/.tmp/production-quality/final_deterministic_matrix.json"
        )
        if default_matrix.exists():
            matrix_run_json = default_matrix
    payload = build_readiness_payload(
        repo_root=args.repo_root,
        external_evidence_paths=args.external_evidence,
        serious_evidence_root=args.serious_evidence_root,
        matrix_run_json=matrix_run_json,
        require_runtime_closeout_evidence=args.require_passing,
    )
    rendered = dump_json(payload) if args.output_format == "json" else _format_text(payload)
    if args.output is not None:
        output = args.output if args.output.is_absolute() else args.repo_root / args.output
        atomic_write_text(output, rendered)
    else:
        sys.stdout.write(rendered)
    if args.require_passing and not payload["passes_all"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
