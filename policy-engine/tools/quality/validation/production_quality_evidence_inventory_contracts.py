#!/usr/bin/env python3
# ruff: noqa: E501
"""Describe quality evidence fields, validators, and serious-profile obligations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.quality.validation.production_quality_evidence_inventory_bindings import (
    _source_exists,
)

_QUALITY_REF_FIELDS = (
    "QualityRef.status",
    "QualityRef.score",
    "QualityRef.report_ref",
    "QualityRef.reason_code",
    "QualityRef.quality_surface",
    "QualityRef.remediation_link",
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


def _validators(
    repo_root: Path,
    *,
    quality_report_files: Mapping[str, str],
    required_materialization_refs: Sequence[str],
) -> list[dict[str, Any]]:
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
            [
                "query_intent",
                "candidate_sources",
                "selected_sources",
                "rejected_sources",
            ],
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
            list(required_materialization_refs),
        ),
        (
            "polisyos.runtime.quality.scorecard._report_gates",
            "runtime_quality_scorecard",
            "quality_evidence/*",
            "src/polisyos/runtime/quality/scorecard.py",
            list(quality_report_files),
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
            [
                "quality_status",
                "stage_scores",
                "quality_gates",
                "blocking_quality_failures",
            ],
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
            ["production_data_evidence_context", *required_materialization_refs],
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


def _quality_artifact_fields(
    reports: list[dict[str, Any]], quality_report_runtime_refs: Mapping[str, str]
) -> list[dict[str, Any]]:
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
    for report_key, runtime_ref in sorted(quality_report_runtime_refs.items()):
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
        runtime_status = "runtime_emitted" if report["status"] == "runtime_emitted" else "missing"
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


def _serious_profile_required_refs(
    reports: list[dict[str, Any]],
    quality_report_runtime_refs: Mapping[str, str],
    required_materialization_refs: Sequence[str],
) -> list[dict[str, Any]]:
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
    for report_key, runtime_ref in sorted(quality_report_runtime_refs.items()):
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
        runtime_status = "runtime_emitted" if report["status"] == "runtime_emitted" else "missing"
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
    for ref in required_materialization_refs:
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
