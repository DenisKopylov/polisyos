#!/usr/bin/env python3
# ruff: noqa: E501, T201
"""Inventory production-quality evidence refs, fields, producers, and validators.

The inventory is a producer map for the runtime evidence contract. Closeout
authority lives in canary bundles and the readiness aggregator, but this file
keeps the static owner, validator, and expected-ref map stable.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.capability_white_space import (  # noqa: E402
    build_capability_white_space_report_from_duckdb,
    dump_capability_white_space_report,
)
from polisyos.runtime.quality.cost_degradation import (  # noqa: E402
    COST_DEGRADATION_TELEMETRY_FILENAME,
    COST_DEGRADATION_TELEMETRY_REPORT_KEY,
)
from polisyos.runtime.quality.cost_gate import (  # noqa: E402
    RUN_COST_GATE_FILENAME,
    RUN_COST_GATE_REPORT_KEY,
)
from polisyos.runtime.quality.data_forge_binding import (  # noqa: E402
    DATA_FORGE_SNAPSHOT_BINDING_FILE,
    DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY,
)
from polisyos.runtime.quality.hypothesis_ledger import (  # noqa: E402
    HYPOTHESIS_LEDGER_FILENAME,
    HYPOTHESIS_LEDGER_REF_KEY,
    HYPOTHESIS_LEDGER_REPORT_KEY,
)
from polisyos.runtime.quality.prompt_tool_ledger import PROMPT_TOOL_LEDGER_FILENAME  # noqa: E402

SCHEMA_VERSION = "policyos.production_quality_evidence_inventory.v1"
PHASE = "0.1"
SNAPSHOT_DATE = "2026-05-13"
OWNER = "team-quality"
STATUS_VALUES = ("manual_input", "fixture_input", "runtime_emitted", "missing")
DEFAULT_BASELINE = (
    REPO_ROOT / "architecture" / "baselines" / "production_quality" / "evidence_inventory.json"
)

_QUALITY_REF_FIELDS = (
    "QualityRef.status",
    "QualityRef.score",
    "QualityRef.report_ref",
    "QualityRef.reason_code",
    "QualityRef.quality_surface",
    "QualityRef.remediation_link",
)
_KNOWN_LITERAL_NAMES: dict[str, object] = {
    "DATA_FORGE_SNAPSHOT_BINDING_FILE": DATA_FORGE_SNAPSHOT_BINDING_FILE,
    "DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY": DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY,
    "COST_DEGRADATION_TELEMETRY_FILENAME": COST_DEGRADATION_TELEMETRY_FILENAME,
    "COST_DEGRADATION_TELEMETRY_REPORT_KEY": COST_DEGRADATION_TELEMETRY_REPORT_KEY,
    "HYPOTHESIS_LEDGER_FILENAME": HYPOTHESIS_LEDGER_FILENAME,
    "HYPOTHESIS_LEDGER_REF_KEY": HYPOTHESIS_LEDGER_REF_KEY,
    "HYPOTHESIS_LEDGER_REPORT_KEY": HYPOTHESIS_LEDGER_REPORT_KEY,
    "PROMPT_TOOL_LEDGER_FILENAME": PROMPT_TOOL_LEDGER_FILENAME,
    "RUN_COST_GATE_FILENAME": RUN_COST_GATE_FILENAME,
    "RUN_COST_GATE_REPORT_KEY": RUN_COST_GATE_REPORT_KEY,
}


def _literal_assignment(path: Path, name: str) -> object:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        is_named_assign = isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        )
        is_named_ann_assign = (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        )
        if is_named_assign or is_named_ann_assign:
            value = node.value
            if value is not None:
                return _literal_eval_with_names(value)
    raise ValueError(f"{name} assignment not found in {path}")


def _literal_eval_with_names(node: ast.AST) -> object:
    if isinstance(node, ast.Name) and node.id in _KNOWN_LITERAL_NAMES:
        return _KNOWN_LITERAL_NAMES[node.id]
    if isinstance(node, ast.Dict):
        return {
            _literal_eval_with_names(key): _literal_eval_with_names(value)
            for key, value in zip(node.keys, node.values, strict=True)
            if key is not None
        }
    if isinstance(node, ast.Tuple):
        return tuple(_literal_eval_with_names(item) for item in node.elts)
    if isinstance(node, ast.List):
        return [_literal_eval_with_names(item) for item in node.elts]
    return ast.literal_eval(node)


_SCORECARD_PATH = REPO_ROOT / "src" / "polisyos" / "runtime" / "quality" / "scorecard.py"
QUALITY_REPORT_FILES: dict[str, str] = dict(
    _literal_assignment(_SCORECARD_PATH, "QUALITY_REPORT_FILES")
)
QUALITY_REPORT_RUNTIME_REFS: dict[str, str] = dict(
    _literal_assignment(_SCORECARD_PATH, "QUALITY_REPORT_RUNTIME_REFS")
)
REQUIRED_MATERIALIZATION_REFS: tuple[str, ...] = tuple(
    _literal_assignment(_SCORECARD_PATH, "REQUIRED_MATERIALIZATION_REFS")
)

QUALITY_REPORT_IDS_BY_KEY = {
    "production_data_quality": "runtime.production_data_quality",
    "normative_evidence": "lex.normative_evidence",
    "fabric_retrieval_trace": "fabric.retrieval_trace",
    "foundry_method_report": "foundry.method_report",
    "policy_grounding_matrix": "scientist.policy_grounding_matrix",
    "semantic_binding_ledger": "runtime.semantic_binding_ledger",
    "conflict_check": "lex.policy_conflict_check",
    "causal_statistical_validity": "foundry.causal_statistical_validity",
    "replay_manifest": "runtime.replay_manifest",
    "drift_explanation": "runtime.drift_explanation",
    "resilience_matrix": "runtime.resilience_matrix",
    "human_review_calibration": "runtime.human_review_calibration",
    "decision_artifact_quality": "scientist.decision_artifact_quality",
    "provider_model_quality_ledger": "runtime.provider_model_quality_ledger",
    "security_assurance_report": "runtime.security_assurance_report",
    "privacy_compliance_report": "runtime.privacy_compliance_report",
    "continuous_governance_stale": "scientist.continuous_governance_stale",
    "continuous_governance_reissue": "scientist.continuous_governance_reissue",
    "continuous_governance_supersede": "scientist.continuous_governance_supersede",
    "continuous_governance_withdraw": "scientist.continuous_governance_withdraw",
    "can_i_closeout": "runtime.can_i_closeout",
    "hypothesis_ledger": "runtime.hypothesis_ledger",
}


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for capability white-space reports.",
    )
    parser.add_argument(
        "--capability-index",
        type=Path,
        default=None,
        help="Primary capability_index_v1.duckdb to query for Phase 6 white-space.",
    )
    parser.add_argument("--check", action="store_true", help="Fail if the baseline JSON drifts")
    return parser.parse_args(argv)


def _resolve(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _source_exists(repo_root: Path, rel_path: str) -> bool:
    return (repo_root / rel_path).exists()


def _producer(
    *,
    name: str,
    kind: str,
    source_path: str,
    current_emission: str,
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": kind,
        "source_path": source_path,
        "source_exists": _source_exists(repo_root, source_path),
        "current_emission": current_emission,
    }


def _quality_ref_field_rows() -> list[dict[str, Any]]:
    return [
        {
            "field_path": field_path,
            "owner_runtime_layer": "fabric_trust_envelope",
            "expected_ref": "FabricDecisionData.quality",
            "producer": "polisyos.fabric.evidence.decision_data.QualityRef",
            "status": "runtime_emitted",
        }
        for field_path in _QUALITY_REF_FIELDS
    ]


def _quality_report_specs(repo_root: Path) -> list[dict[str, Any]]:
    quality_ref = {
        key: f"quality_evidence/{filename}"
        for key, filename in sorted(QUALITY_REPORT_FILES.items())
    }

    rows = [
        {
            "id": "quality.golden_scenario_contract",
            "title": "Golden scenario expected evidence contract",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["golden_scenario_contract"],
            "owner_runtime_layer": "quality_scenarios",
            "artifact_fields": [
                "scenario_id",
                "context.country",
                "context.policy_domain",
                "expected_evidence_contract.normative_fact_classes",
                "expected_evidence_contract.admissible_data_source_families",
                "expected_evidence_contract.foundry_method_expectations",
                "expected_evidence_contract.conflict_checks",
            ],
            "producer": _producer(
                name="tools.ops_runners.runtime.quality_scenarios.load_quality_scenario_contract",
                kind="runtime_bundle_emitter",
                source_path="tools/ops_runners/runtime/quality_scenarios.py",
                current_emission=(
                    "Canary evidence freezes the checked-in benchmark scenario contract "
                    "into every serious runtime evidence bundle."
                ),
                repo_root=repo_root,
            ),
            "validators": [
                "tools.ops_runners.runtime.quality_scenarios.validate_quality_scenario_contract",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "lex.normative_evidence",
            "title": "Lex normative applicability report",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["normative_evidence"],
            "owner_runtime_layer": "lex",
            "artifact_fields": [
                "schema_version",
                "status",
                "target_context",
                "applied_norms",
                "rejected_norms",
                "recommendation_coverage",
                "issues[].code",
                "issues[].next_action",
            ],
            "producer": _producer(
                name="polisyos.lex.normpack.applicability_report.build_normative_applicability_report",
                kind="runtime_report_builder",
                source_path="src/polisyos/lex/normpack/applicability_report.py",
                current_emission=(
                    "NL pipeline persists normative_applicability_report_ref; canary "
                    "bundles resolve it into quality_evidence/normative_evidence.json."
                ),
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.lex.normpack.applicability_report.normalize_normative_applicability_report",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "fabric.retrieval_trace",
            "title": "Fabric source-selection quality trace",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["fabric_retrieval_trace"],
            "owner_runtime_layer": "fabric_retrieval",
            "artifact_fields": [
                "schema_version",
                "status",
                "query_intent",
                "candidate_sources",
                "selected_sources",
                "rejected_sources",
                "issues[].code",
                "summary.selected_source_count",
            ],
            "producer": _producer(
                name="polisyos.fabric.catalog.source_selection_audit.build_fabric_source_selection_trace",
                kind="runtime_report_builder",
                source_path="src/polisyos/fabric/catalog/source_selection_audit.py",
                current_emission=(
                    "NL pipeline persists fabric_retrieval_trace_ref; canary bundles "
                    "resolve it into quality_evidence/fabric_retrieval_trace.json."
                ),
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.fabric.catalog.source_selection_audit.normalize_fabric_retrieval_trace",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "foundry.method_report",
            "title": "Foundry method-quality report",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["foundry_method_report"],
            "owner_runtime_layer": "foundry_methods",
            "artifact_fields": [
                "schema_version",
                "status",
                "selected_methods",
                "selected_methods[].input_refs",
                "selected_methods[].assumptions",
                "selected_methods[].uncertainty",
                "selected_methods[].missingness",
                "selected_methods[].sensitivity",
                "issues[].code",
            ],
            "producer": _producer(
                name="polisyos.foundry.validation.method_quality.build_foundry_method_report",
                kind="runtime_report_builder",
                source_path="src/polisyos/foundry/validation/method_quality.py",
                current_emission=(
                    "NL pipeline persists foundry_method_report_ref; canary bundles "
                    "resolve it into quality_evidence/foundry_method_report.json."
                ),
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.foundry.validation.method_quality.normalize_foundry_method_report",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "scientist.policy_grounding_matrix",
            "title": "Scientist policy grounding matrix",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["policy_grounding_matrix"],
            "owner_runtime_layer": "scientist_policy_artifacts",
            "artifact_fields": [
                "schema_version",
                "status",
                "claims",
                "claims[].data_refs",
                "claims[].method_refs",
                "claims[].norm_refs",
                "model_variants",
                "issues[].missing_evidence_type",
            ],
            "producer": _producer(
                name="polisyos.scientist.validation.policy_grounding.build_policy_grounding_matrix_report",
                kind="runtime_report_builder",
                source_path="src/polisyos/scientist/validation/policy_grounding.py",
                current_emission=(
                    "NL pipeline persists policy_grounding_matrix_ref from final policy "
                    "claims; canary bundles resolve it into the scorecard evidence pack."
                ),
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.scientist.validation.policy_grounding.normalize_policy_grounding_matrix",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.semantic_binding_ledger",
            "title": "Runtime semantic binding ledger",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["semantic_binding_ledger"],
            "owner_runtime_layer": "semantic_binding",
            "artifact_fields": [
                "schema_version",
                "status",
                "semantic_binding_ref",
                "policy_intent_ref",
                "intent",
                "lex",
                "fabric",
                "foundry",
                "scientist",
                "final_compiler",
            ],
            "producer": _producer(
                name="polisyos.runtime.quality.semantic_binding.build_semantic_binding_ledger",
                kind="runtime_report_builder",
                source_path="src/polisyos/runtime/quality/semantic_binding.py",
                current_emission=(
                    "NL pipeline persists semantic_binding_ledger_ref after building "
                    "Lex, Fabric, Foundry, Scientist, and final compiler binding "
                    "records; canary bundles resolve it into scorecard evidence."
                ),
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.runtime.quality.semantic_binding.deserialize_semantic_binding_ledger",
                "polisyos.runtime.quality.semantic_binding.evaluate_semantic_binding_ledger",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "lex.policy_conflict_check",
            "title": "Lex policy conflict check",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["conflict_check"],
            "owner_runtime_layer": "normative_conflict",
            "artifact_fields": [
                "schema_version",
                "status",
                "policy_claims",
                "corpus_constraints",
                "conflicts",
                "conflicts[].blocking",
                "issues[].next_action",
            ],
            "producer": _producer(
                name="polisyos.lex.normpack.conflict_check.build_policy_conflict_check_report",
                kind="runtime_report_builder",
                source_path="src/polisyos/lex/normpack/conflict_check.py",
                current_emission=(
                    "NL pipeline persists conflict_check_ref against the active corpus; "
                    "canary bundles resolve it into quality_evidence/conflict_check.json."
                ),
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.lex.normpack.conflict_check.normalize_policy_conflict_check_report",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.production_data_quality",
            "title": "Production data quality diagnostics",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["production_data_quality"],
            "owner_runtime_layer": "fabric_materialization",
            "artifact_fields": [
                "schema_version",
                "status",
                "production_data_quality_report_ref",
                "manifest_checksum",
                "source_bundle_versions",
                "row_counts",
                "entity_counts",
                "diagnostics",
                "claim_diagnostics",
                "issues[].next_action",
            ],
            "producer": _producer(
                name="polisyos.runtime.quality.data_quality.build_production_data_quality_report",
                kind="runtime_report_builder",
                source_path="src/polisyos/runtime/quality/data_quality.py",
                current_emission="NL production materialization and canary evidence emit production data quality reports.",
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.runtime.quality.data_quality.normalize_production_data_quality_report",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "foundry.causal_statistical_validity",
            "title": "Causal and statistical validity benchmark report",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["causal_statistical_validity"],
            "owner_runtime_layer": "foundry_causal_validity",
            "artifact_fields": [
                "schema_version",
                "status",
                "ref_key",
                "benchmark_suite_id",
                "method_families",
                "cases",
                "issues",
            ],
            "producer": _producer(
                name="polisyos.foundry.validation.causal_validity.build_causal_statistical_validity_report",
                kind="deterministic_benchmark_builder",
                source_path="src/polisyos/foundry/validation/causal_validity.py",
                current_emission="Canary evidence assembles deterministic offline benchmark evidence.",
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.foundry.validation.causal_validity.normalize_causal_statistical_validity_report",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.replay_manifest",
            "title": "Deterministic replay manifest",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["replay_manifest"],
            "owner_runtime_layer": "runtime_replay",
            "artifact_fields": [
                "schema_version",
                "request_fingerprint",
                "git_sha",
                "dependency_fingerprints",
                "provider_model_metadata",
                "data_refs",
                "cas_refs",
                "quality_scorecard_ref",
            ],
            "producer": _producer(
                name="polisyos.runtime.quality.replay.build_replay_manifest",
                kind="runtime_report_builder",
                source_path="src/polisyos/runtime/quality/replay.py",
                current_emission="Canary evidence and replay bundle tooling emit sanitized replay manifests.",
                repo_root=repo_root,
            ),
            "validators": ["polisyos.runtime.quality.replay.explain_replay_drift"],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.drift_explanation",
            "title": "Replay drift explanation",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["drift_explanation"],
            "owner_runtime_layer": "runtime_replay",
            "artifact_fields": [
                "schema_version",
                "status",
                "production_readiness",
                "execution_summary_match",
                "quality_summary_match",
                "differences",
            ],
            "producer": _producer(
                name="polisyos.runtime.quality.replay.explain_replay_drift",
                kind="runtime_report_builder",
                source_path="src/polisyos/runtime/quality/replay.py",
                current_emission="Canary evidence compares deterministic manifests and records typed drift evidence.",
                repo_root=repo_root,
            ),
            "validators": ["polisyos.runtime.quality.replay.explain_replay_drift"],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.resilience_matrix",
            "title": "Runtime resilience matrix",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["resilience_matrix"],
            "owner_runtime_layer": "runtime_resilience",
            "artifact_fields": [
                "schema_version",
                "resilience_report_ref",
                "slo_budgets",
                "summary",
                "operator_findings",
                "scenarios",
            ],
            "producer": _producer(
                name="tools.quality.testing.runtime_resilience_matrix.build_matrix_payload",
                kind="deterministic_matrix_builder",
                source_path="tools/quality/testing/runtime_resilience_matrix.py",
                current_emission="Canary evidence embeds the deterministic resilience matrix.",
                repo_root=repo_root,
            ),
            "validators": ["tools.quality.testing.runtime_resilience_matrix.build_matrix_payload"],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.human_review_calibration",
            "title": "Human-review calibration report",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["human_review_calibration"],
            "owner_runtime_layer": "human_review_calibration",
            "artifact_fields": [
                "schema_version",
                "status",
                "summary",
                "quality_signals",
                "reviewer_burden",
                "unresolved_disagreements",
            ],
            "producer": _producer(
                name="polisyos.runtime.quality.human_review.build_human_review_calibration_report",
                kind="runtime_report_builder",
                source_path="src/polisyos/runtime/quality/human_review.py",
                current_emission="Canary evidence emits calibration evidence from review events or deterministic empty fixtures.",
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.runtime.quality.human_review.evaluate_review_packet",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.privacy_compliance_report",
            "title": "Privacy, licensing, and compliance report",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["privacy_compliance_report"],
            "owner_runtime_layer": "privacy_compliance",
            "artifact_fields": [
                "schema_version",
                "status",
                "summary",
                "production_data_sources",
                "public_artifact_families",
                "issues",
                "override",
            ],
            "producer": _producer(
                name="polisyos.data_forge.read_api.build_privacy_compliance_report",
                kind="runtime_report_builder",
                source_path="src/polisyos/data_forge/read_api/compliance.py",
                current_emission="NL pipeline and canary evidence emit compliance evidence without raw sensitive records.",
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.runtime.quality.compliance.normalize_runtime_privacy_compliance_report",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.security_assurance_report",
            "title": "Security assurance report",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["security_assurance_report"],
            "owner_runtime_layer": "security_quality_gates",
            "artifact_fields": [
                "schema_version",
                "status",
                "security_assurance_report_ref",
                "surfaces",
                "findings",
                "issues",
            ],
            "producer": _producer(
                name="polisyos.core.security.quality_gates.build_security_assurance_report",
                kind="runtime_report_builder",
                source_path="src/polisyos/core/security/quality_gates.py",
                current_emission="Canary evidence emits sanitized LLM/tool/data/artifact/runtime/dashboard security assurance reports.",
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.core.security.quality_gates.security_gates_from_report",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.provider_model_quality_ledger",
            "title": "Provider and model quality drift ledger",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["provider_model_quality_ledger"],
            "owner_runtime_layer": "llm_orchestration",
            "artifact_fields": [
                "schema_version",
                "provider_model_quality_ledger_ref",
                "default_production_model",
                "observations",
                "model_actions",
                "quality_drift",
            ],
            "producer": _producer(
                name="tools.ops_runners.runtime.provider_quality_ledger.build_provider_quality_ledger",
                kind="runtime_quality_ledger_builder",
                source_path="tools/ops_runners/runtime/provider_quality_ledger.py",
                current_emission=(
                    "Canary evidence builds provider_model_quality_ledger from completed "
                    "default production model observations and persists it in the bundle."
                ),
                repo_root=repo_root,
            ),
            "validators": [
                "tools.ops_runners.runtime.provider_quality_ledger.build_provider_quality_ledger",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.hypothesis_ledger",
            "title": "HypothesisLedger candidate firewall evidence",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["hypothesis_ledger"],
            "owner_runtime_layer": "candidate_firewall",
            "artifact_fields": [
                "schema_version",
                "status",
                "hypothesis_ledger_ref",
                "entries",
                "entries[].candidate_type",
                "entries[].authority_status",
                "candidate_firewall",
            ],
            "producer": _producer(
                name="polisyos.runtime.quality.hypothesis_ledger.persist_hypothesis_ledger",
                kind="runtime_report_builder",
                source_path="src/polisyos/runtime/quality/hypothesis_ledger.py",
                current_emission=(
                    "Runtime capability and semantic-binding paths persist "
                    "HypothesisLedger evidence so LLM candidates remain advisory "
                    "until producer-backed admission."
                ),
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.runtime.quality.hypothesis_ledger.deserialize_hypothesis_ledger",
                "polisyos.runtime.quality.scorecard._hypothesis_candidate_firewall_gates",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.can_i_closeout",
            "title": "Can-I-closeout verdict",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["can_i_closeout"],
            "owner_runtime_layer": "closeout_authority",
            "artifact_fields": [
                "schema_version",
                "status",
                "verdict",
                "can_close",
                "issues",
                "quality_report_refs",
                "capability_index_ref",
            ],
            "producer": _producer(
                name="polisyos.runtime.quality.closeout_reader.build_can_i_closeout_verdict",
                kind="runtime_report_builder",
                source_path="src/polisyos/runtime/quality/closeout_reader.py",
                current_emission=(
                    "Canary evidence and closeout tooling compile typed closeout "
                    "verdicts from scorecard, quality reports, and capability refs."
                ),
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.runtime.quality.closeout_reader.build_can_i_closeout_verdict",
                "polisyos.runtime.quality.scorecard._can_i_closeout_scorecard_gates",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "scientist.decision_artifact_quality",
            "title": "Decision artifact quality report",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": quality_ref["decision_artifact_quality"],
            "owner_runtime_layer": "scientist_decision_artifact",
            "artifact_fields": [
                "schema_version",
                "status",
                "decision_artifact_quality_report_ref",
                "input_refs",
                "summary",
                "issues",
            ],
            "producer": _producer(
                name="polisyos.scientist.validation.decision_artifact_quality.build_decision_artifact_quality_report",
                kind="runtime_report_builder",
                source_path="src/polisyos/scientist/validation/decision_artifact_quality.py",
                current_emission="Canary evidence compiles public decision artifacts and emits decision quality evidence.",
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.scientist.validation.decision_artifact_quality.normalize_decision_artifact_quality_report",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.performance_summary",
            "title": "Runtime performance and LLM accounting summary",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": "performance.json",
            "owner_runtime_layer": "nl_pipeline",
            "artifact_fields": [
                "run_performance_summary.schema_version",
                "run_performance_summary.llm",
                "run_performance_summary.phase_budgets",
                "run_performance_summary.steps_by_action",
                "run_performance_summary.variant_rows",
                "llm_model_variants[].total_tokens",
                "llm_model_variants[].cost_usd",
            ],
            "producer": _producer(
                name="polisyos.runtime.http.services.control.nl_pipeline._build_run_performance_summary",
                kind="runtime_emitter",
                source_path="src/polisyos/runtime/http/services/control/nl_pipeline.py",
                current_emission="Builds run_performance_summary and canary_evidence writes performance.json when present.",
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.runtime.quality.scorecard._llm_gates",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "ir.metric_taxonomy",
            "title": "Metric taxonomy summary",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": "bundle.json#metric_taxonomy",
            "owner_runtime_layer": "metric_taxonomy",
            "artifact_fields": [
                "metric_taxonomy.available",
                "metric_taxonomy.schema_version",
                "metric_taxonomy.metric_count",
                "metric_taxonomy.fingerprint",
                "metric_taxonomy.canonicalizer",
            ],
            "producer": _producer(
                name="tools.ops_runners.runtime.canary_evidence._metric_taxonomy_summary",
                kind="runtime_bundle_emitter",
                source_path="tools/ops_runners/runtime/canary_evidence.py",
                current_emission="Summarizes DEFAULT_METRIC_REGISTRY into bundle.json.",
                repo_root=repo_root,
            ),
            "validators": [
                "tools.ops_runners.runtime.canary_evidence._metric_taxonomy_summary",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "llm.provider_preflight",
            "title": "LLM provider preflight report",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": "provider_preflight.json",
            "owner_runtime_layer": "llm_gateway",
            "artifact_fields": [
                "provider_preflight.status",
                "provider_preflight.models",
                "provider_preflight.failure",
                "provider_preflight.retryable",
                "provider_preflight_ref",
            ],
            "producer": _producer(
                name="polisyos.runtime.http.services.control.run_lifecycle.queue_natural_language_run",
                kind="runtime_preflight_emitter",
                source_path="src/polisyos/runtime/http/services/control/run_lifecycle.py",
                current_emission="Runs provider preflight for research/governed/production profiles and persists failed preflight refs.",
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.runtime.quality.scorecard._llm_gates",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "fabric.production_data_context",
            "title": "Production-data evidence context",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": "production_data_evidence.json",
            "owner_runtime_layer": "fabric_materialization",
            "artifact_fields": [
                "production_data_evidence.context.root",
                "production_data_evidence.context.manifest_path",
                "production_data_evidence.context.manifest_sha256",
                "production_data_evidence.context.bundles",
                "production_data_evidence.materialization_refs",
            ],
            "producer": _producer(
                name="polisyos.runtime.http.services.control.production_data.production_data_evidence_context",
                kind="runtime_context_emitter",
                source_path="src/polisyos/runtime/http/services/control/production_data.py",
                current_emission="Builds production_data_evidence_context; canary_evidence writes production_data_evidence.json when refs/context exist.",
                repo_root=repo_root,
            ),
            "validators": [
                "tools.ops_runners.runtime.canary_evidence._extract_production_data_evidence",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "fabric.materialization_refs",
            "title": "Production materialization refs",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": "artifacts.json#materialization_refs",
            "owner_runtime_layer": "fabric_materialization",
            "artifact_fields": list(REQUIRED_MATERIALIZATION_REFS),
            "producer": _producer(
                name="polisyos.runtime.http.services.control.nl_pipeline._materialize_production_data_artifacts",
                kind="runtime_materialization_emitter",
                source_path="src/polisyos/runtime/http/services/control/nl_pipeline.py",
                current_emission="Emits data_snapshot_ref, input_bindings_ref, registry_bundle_ref, and quality_report_ref for production-data runs.",
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.runtime.quality.scorecard._materialization_gate",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "runtime.quality_scorecard",
            "title": "Production quality scorecard",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": "quality_evidence/quality_scorecard.json",
            "owner_runtime_layer": "runtime_quality_scorecard",
            "artifact_fields": [
                "schema_version",
                "quality_status",
                "overall_score",
                "stage_scores",
                "quality_gates",
                "quality_gates[].evidence_ref",
                "blocking_quality_failures",
                "evidence_refs",
            ],
            "producer": _producer(
                name="polisyos.runtime.quality.scorecard.build_quality_scorecard",
                kind="runtime_scorecard_builder",
                source_path="src/polisyos/runtime/quality/scorecard.py",
                current_emission="canary_evidence builds and writes quality_evidence/quality_scorecard.json.",
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.runtime.quality.scorecard.build_quality_scorecard",
            ],
            "first_missing_producer": None,
        },
        {
            "id": "core.cas_ownership_evidence",
            "title": "CAS ownership evidence on persisted quality artifacts",
            "status": "runtime_emitted",
            "required_for_serious_profile": True,
            "expected_ref": "cas_manifest#producer",
            "owner_runtime_layer": "core_artifacts",
            "artifact_fields": [
                "cas_manifest.producer",
                "cas_manifest.producer.component",
                "cas_manifest.producer.version",
                "cas_manifest.producer.git",
                "cas_manifest.governance",
                "cas_manifest.inputs",
            ],
            "producer": _producer(
                name="polisyos.core.artifacts.store.FileSystemCAS.put_json",
                kind="cas_manifest_writer",
                source_path="src/polisyos/core/artifacts/store.py",
                current_emission=(
                    "Runtime quality artifacts and canary bundles include CAS manifest "
                    "producer, governance, and input ownership metadata."
                ),
                repo_root=repo_root,
            ),
            "validators": [
                "polisyos.core.artifacts.manifest.ArtifactManifest",
            ],
            "first_missing_producer": None,
        },
    ]
    governance_lifecycle_fields = [
        "schema_version",
        "status",
        "report_id",
        "lifecycle_decision",
        "decision_status",
        "decision_packet_ref",
        "monitor_event_refs",
        "cas_artifact_refs",
        "schema_compatibility",
        "effective_mode_ref",
        "degradation_ledger_ref",
        "runtime_quality_ref_key",
        "authority_requirements",
    ]
    for report_key, decision in (
        ("continuous_governance_stale", "stale"),
        ("continuous_governance_reissue", "reissue"),
        ("continuous_governance_supersede", "supersede"),
        ("continuous_governance_withdraw", "withdraw"),
    ):
        rows.append(
            {
                "id": QUALITY_REPORT_IDS_BY_KEY[report_key],
                "title": f"Continuous governance {decision} lifecycle report",
                "status": "runtime_emitted",
                "required_for_serious_profile": True,
                "expected_ref": quality_ref[report_key],
                "owner_runtime_layer": "scientist_governance_lifecycle",
                "artifact_fields": list(governance_lifecycle_fields),
                "producer": _producer(
                    name=(
                        "polisyos.scientist.governance.continuous."
                        "emit_governance_lifecycle_evidence"
                    ),
                    kind="runtime_report_builder",
                    source_path="src/polisyos/scientist/governance/continuous/monitors.py",
                    current_emission=(
                        "Continuous governance monitors persist runtime-owned "
                        f"{decision} lifecycle authority evidence with CAS refs, "
                        "diagnostic events, and authority envelopes."
                    ),
                    repo_root=repo_root,
                ),
                "validators": [
                    (
                        "polisyos.scientist.governance.continuous.monitors."
                        "emit_governance_lifecycle_evidence"
                    ),
                    (
                        "polisyos.scientist.governance.continuous.monitors."
                        "_validate_lifecycle_decision"
                    ),
                ],
                "first_missing_producer": None,
            }
        )
    return rows


def _validators(repo_root: Path) -> list[dict[str, Any]]:
    rows = [
        (
            "tools.ops_runners.runtime.quality_scenarios.validate_quality_scenario_contract",
            "quality_scenarios",
            "quality_evidence/golden_scenario_contract.json",
            "tools/ops_runners/runtime/quality_scenarios.py",
            ["expected_evidence_contract", "context"],
        ),
        (
            "polisyos.lex.normpack.applicability_report.normalize_normative_applicability_report",
            "lex",
            "quality_evidence/normative_evidence.json",
            "src/polisyos/lex/normpack/applicability_report.py",
            ["target_context", "applied_norms", "recommendation_coverage"],
        ),
        (
            "polisyos.fabric.catalog.source_selection_audit.normalize_fabric_retrieval_trace",
            "fabric_retrieval",
            "quality_evidence/fabric_retrieval_trace.json",
            "src/polisyos/fabric/catalog/source_selection_audit.py",
            ["query_intent", "candidate_sources", "selected_sources", "rejected_sources"],
        ),
        (
            "polisyos.foundry.validation.method_quality.normalize_foundry_method_report",
            "foundry_methods",
            "quality_evidence/foundry_method_report.json",
            "src/polisyos/foundry/validation/method_quality.py",
            ["selected_methods", "input_refs", "assumptions", "uncertainty"],
        ),
        (
            "polisyos.scientist.validation.policy_grounding.normalize_policy_grounding_matrix",
            "scientist_policy_artifacts",
            "quality_evidence/policy_grounding_matrix.json",
            "src/polisyos/scientist/validation/policy_grounding.py",
            ["claims", "data_refs", "method_refs", "norm_refs", "model_variants"],
        ),
        (
            "polisyos.runtime.quality.semantic_binding.evaluate_semantic_binding_ledger",
            "semantic_binding",
            "quality_evidence/semantic_binding_ledger.json",
            "src/polisyos/runtime/quality/semantic_binding.py",
            [
                "semantic_binding_ref",
                "policy_intent_ref",
                "lex",
                "fabric",
                "foundry",
                "scientist",
                "final_compiler",
            ],
        ),
        (
            "polisyos.lex.normpack.conflict_check.normalize_policy_conflict_check_report",
            "normative_conflict",
            "quality_evidence/conflict_check.json",
            "src/polisyos/lex/normpack/conflict_check.py",
            ["policy_claims", "corpus_constraints", "conflicts"],
        ),
        (
            "polisyos.runtime.quality.scorecard._llm_gates",
            "llm_gateway",
            "provider_preflight.json",
            "src/polisyos/runtime/quality/scorecard.py",
            ["provider_preflight", "llm_model_variants", "token_usage", "cost_usd"],
        ),
        (
            "polisyos.runtime.quality.scorecard._materialization_gate",
            "fabric_materialization",
            "artifacts.json#materialization_refs",
            "src/polisyos/runtime/quality/scorecard.py",
            list(REQUIRED_MATERIALIZATION_REFS),
        ),
        (
            "polisyos.runtime.quality.scorecard._report_gates",
            "runtime_quality_scorecard",
            "quality_evidence/*",
            "src/polisyos/runtime/quality/scorecard.py",
            list(QUALITY_REPORT_FILES),
        ),
        (
            "polisyos.runtime.quality.scorecard._evidence_refs",
            "runtime_quality_scorecard",
            "quality_scorecard.evidence_refs",
            "src/polisyos/runtime/quality/scorecard.py",
            ["evidence_refs"],
        ),
        (
            "polisyos.runtime.quality.scorecard.build_quality_scorecard",
            "runtime_quality_scorecard",
            "quality_evidence/quality_scorecard.json",
            "src/polisyos/runtime/quality/scorecard.py",
            ["quality_status", "stage_scores", "quality_gates", "blocking_quality_failures"],
        ),
        (
            "tools.ops_runners.runtime.canary_evidence._metric_taxonomy_summary",
            "metric_taxonomy",
            "bundle.json#metric_taxonomy",
            "tools/ops_runners/runtime/canary_evidence.py",
            ["metric_taxonomy.schema_version", "metric_taxonomy.fingerprint"],
        ),
        (
            "tools.ops_runners.runtime.canary_evidence._extract_production_data_evidence",
            "fabric_materialization",
            "production_data_evidence.json",
            "tools/ops_runners/runtime/canary_evidence.py",
            ["production_data_evidence_context", *REQUIRED_MATERIALIZATION_REFS],
        ),
        (
            "polisyos.core.artifacts.manifest.ArtifactManifest",
            "core_artifacts",
            "cas_manifest#producer",
            "src/polisyos/core/artifacts/manifest.py",
            ["producer", "governance", "inputs", "schema"],
        ),
    ]
    return [
        {
            "id": validator_id,
            "owner_runtime_layer": owner_layer,
            "expected_ref": expected_ref,
            "source_path": source_path,
            "source_exists": _source_exists(repo_root, source_path),
            "validated_fields": list(validated_fields),
        }
        for validator_id, owner_layer, expected_ref, source_path, validated_fields in rows
    ]


def _quality_artifact_fields(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = _quality_ref_field_rows()
    for report in reports:
        report_id = str(report["id"])
        expected_ref = str(report["expected_ref"])
        owner_layer = str(report["owner_runtime_layer"])
        producer_name = str(report["producer"]["name"])
        for field_path in report["artifact_fields"]:
            rows.append(
                {
                    "field_path": f"{report_id}.{field_path}",
                    "owner_runtime_layer": owner_layer,
                    "expected_ref": expected_ref,
                    "producer": producer_name,
                    "status": report["status"],
                }
            )

    reports_by_id = {str(report["id"]): report for report in reports}
    for report_key, runtime_ref in sorted(QUALITY_REPORT_RUNTIME_REFS.items()):
        report_id = QUALITY_REPORT_IDS_BY_KEY.get(report_key, f"runtime.{report_key}")
        report = reports_by_id.get(report_id)
        if report is None:
            rows.append(
                {
                    "field_path": f"runtime_quality_refs.{runtime_ref}",
                    "owner_runtime_layer": "unknown",
                    "expected_ref": f"runtime_quality_ref#{runtime_ref}",
                    "producer": f"unregistered quality report mapping for {report_key}",
                    "status": "missing",
                }
            )
            continue
        runtime_status = (
            "runtime_emitted" if report["status"] == "runtime_emitted" else "missing"
        )
        rows.append(
            {
                "field_path": f"runtime_quality_refs.{runtime_ref}",
                "owner_runtime_layer": report["owner_runtime_layer"],
                "expected_ref": f"runtime_quality_ref#{runtime_ref}",
                "producer": (
                    report["producer"]["name"]
                    if runtime_status == "runtime_emitted"
                    else report["first_missing_producer"]
                ),
                "status": runtime_status,
            }
        )

    rows.extend(
        [
            {
                "field_path": "quality_scorecard.evidence_refs",
                "owner_runtime_layer": "runtime_quality_scorecard",
                "expected_ref": "quality_evidence/quality_scorecard.json",
                "producer": "polisyos.runtime.quality.scorecard.build_quality_scorecard",
                "status": "runtime_emitted",
            },
            {
                "field_path": "production_data_evidence.materialization_refs.quality_report_ref",
                "owner_runtime_layer": "fabric_materialization",
                "expected_ref": "production_data_evidence.json",
                "producer": "tools.ops_runners.runtime.canary_evidence._extract_production_data_evidence",
                "status": "runtime_emitted",
            },
            {
                "field_path": "cas_manifest.producer",
                "owner_runtime_layer": "core_artifacts",
                "expected_ref": "cas_manifest#producer",
                "producer": "polisyos.core.artifacts.store.FileSystemCAS.put_json",
                "status": "runtime_emitted",
            },
        ]
    )
    return sorted(rows, key=lambda row: str(row["field_path"]))


def _serious_profile_required_refs(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for report in reports:
        if not report["required_for_serious_profile"]:
            continue
        rows.append(
            {
                "report_id": report["id"],
                "expected_ref": report["expected_ref"],
                "status": report["status"],
                "owner_runtime_layer": report["owner_runtime_layer"],
                "producer": report["producer"]["name"],
                "first_missing_producer": report["first_missing_producer"],
                "validators": list(report["validators"]),
            }
        )

    reports_by_id = {str(report["id"]): report for report in reports}
    for report_key, runtime_ref in sorted(QUALITY_REPORT_RUNTIME_REFS.items()):
        report_id = QUALITY_REPORT_IDS_BY_KEY.get(report_key, f"runtime.{report_key}")
        report = reports_by_id.get(report_id)
        if report is None:
            rows.append(
                {
                    "report_id": report_id,
                    "field_path": runtime_ref,
                    "expected_ref": f"runtime_quality_ref#{runtime_ref}",
                    "status": "missing",
                    "owner_runtime_layer": "unknown",
                    "producer": f"unregistered quality report mapping for {report_key}",
                    "first_missing_producer": (
                        f"Register {report_key} in production quality evidence inventory."
                    ),
                    "validators": [],
                }
            )
            continue
        runtime_status = (
            "runtime_emitted" if report["status"] == "runtime_emitted" else "missing"
        )
        producer = (
            report["producer"]["name"]
            if runtime_status == "runtime_emitted"
            else report["first_missing_producer"]
        )
        rows.append(
            {
                "report_id": report_id,
                "field_path": runtime_ref,
                "expected_ref": f"runtime_quality_ref#{runtime_ref}",
                "status": runtime_status,
                "owner_runtime_layer": report["owner_runtime_layer"],
                "producer": producer,
                "first_missing_producer": report["first_missing_producer"],
                "validators": list(report["validators"]),
            }
        )

    materialization_report = next(
        report for report in reports if report["id"] == "fabric.materialization_refs"
    )
    for ref in REQUIRED_MATERIALIZATION_REFS:
        rows.append(
            {
                "report_id": materialization_report["id"],
                "field_path": ref,
                "expected_ref": f"artifacts.json#{ref}",
                "status": materialization_report["status"],
                "owner_runtime_layer": materialization_report["owner_runtime_layer"],
                "producer": materialization_report["producer"]["name"],
                "first_missing_producer": materialization_report["first_missing_producer"],
                "validators": list(materialization_report["validators"]),
            }
        )
    return sorted(
        rows,
        key=lambda row: (str(row["expected_ref"]), str(row.get("field_path") or "")),
    )


def _status_counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("status")) for row in rows)
    return {status: counts.get(status, 0) for status in STATUS_VALUES}


def build_inventory(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build the stable Phase 0.1 evidence inventory payload."""
    repo_root = repo_root.resolve()
    reports = _quality_report_specs(repo_root)
    fields = _quality_artifact_fields(reports)
    validators = _validators(repo_root)
    required_refs = _serious_profile_required_refs(reports)
    missing_required = [
        row
        for row in required_refs
        if row["status"] in {"manual_input", "fixture_input", "missing"}
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "snapshot_date": SNAPSHOT_DATE,
        "owner": OWNER,
        "mode": "read_only_inventory",
        "status_model": {
            "allowed_statuses": list(STATUS_VALUES),
            "definitions": {
                "manual_input": "Evidence is authored or selected by a human/operator.",
                "fixture_input": "Evidence can be supplied by fixtures or CLI input but is not emitted by the runtime path yet.",
                "runtime_emitted": "Evidence is emitted by the runtime/canary path today.",
                "missing": "The field/ref contract exists, but no current producer emits it.",
            },
        },
        "quality_reports": reports,
        "quality_artifact_fields": fields,
        "validators": validators,
        "serious_profile_required_refs": required_refs,
        "summary": {
            "quality_report_count": len(reports),
            "quality_artifact_field_count": len(fields),
            "validator_count": len(validators),
            "required_serious_profile_ref_count": len(required_refs),
            "quality_report_status_counts": _status_counts(reports),
            "required_ref_status_counts": _status_counts(required_refs),
            "missing_or_input_required_producers": [
                {
                    "expected_ref": row["expected_ref"],
                    "status": row["status"],
                    "first_missing_producer": row["first_missing_producer"],
                }
                for row in missing_required
            ],
        },
        "readiness_aggregator_contract": {
            "stable_json": True,
            "sort_keys": True,
            "primary_keys": {
                "quality_reports": "id",
                "quality_artifact_fields": "field_path",
                "validators": "id",
                "serious_profile_required_refs": "expected_ref",
            },
            "blocking_statuses_for_serious_profile": ["manual_input", "fixture_input", "missing"],
        },
        "source_paths": {
            "scorecard": "src/polisyos/runtime/quality/scorecard.py",
            "canary_evidence": "tools/ops_runners/runtime/canary_evidence.py",
            "nl_pipeline": "src/polisyos/runtime/http/services/control/nl_pipeline.py",
            "run_lifecycle": "src/polisyos/runtime/http/services/control/run_lifecycle.py",
            "production_data": "src/polisyos/runtime/http/services/control/production_data.py",
        },
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    """Return canonical JSON suitable for checked-in baselines and aggregators."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def check_artifacts(
    *,
    repo_root: Path = REPO_ROOT,
    baseline_path: Path = DEFAULT_BASELINE,
) -> list[str]:
    baseline = _resolve(baseline_path, repo_root)
    expected = dump_json(build_inventory(repo_root))
    if not baseline.exists():
        return [f"baseline missing: {_rel(baseline, repo_root)}"]
    actual = baseline.read_text(encoding="utf-8")
    if actual != expected:
        return [f"baseline out of date: {_rel(baseline, repo_root)}"]
    return []


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    if args.capability_index is not None:
        capability_index = _resolve(args.capability_index, repo_root)
        output = _resolve(args.output or args.json_output, repo_root)
        payload = build_capability_white_space_report_from_duckdb(capability_index)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(dump_capability_white_space_report(payload), encoding="utf-8")
        return 0

    output = _resolve(args.json_output, repo_root)

    if args.check:
        failures = check_artifacts(repo_root=repo_root, baseline_path=output)
        if failures:
            for failure in failures:
                print(failure)
            return 1
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dump_json(build_inventory(repo_root)), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
