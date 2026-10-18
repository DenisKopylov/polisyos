#!/usr/bin/env python3
# ruff: noqa: E501
"""Describe the production-quality report producers and their emitted artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.quality.validation.production_quality_evidence_inventory_bindings import (
    _source_exists,
)


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


def _quality_report_specs(
    repo_root: Path,
    quality_report_files: Mapping[str, str],
    required_materialization_refs: Sequence[str],
    quality_report_ids_by_key: Mapping[str, str],
) -> list[dict[str, Any]]:
    quality_ref = {
        key: f"quality_evidence/{filename}"
        for key, filename in sorted(quality_report_files.items())
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
                "generated_at",
                "status",
                "security_assurance_report_ref",
                "assured_paths",
                "issues",
                "blockers",
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
            "artifact_fields": list(required_materialization_refs),
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
                "id": quality_report_ids_by_key[report_key],
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
