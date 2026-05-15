from __future__ import annotations

from copy import deepcopy
from typing import Any

from polisyos.runtime.quality.scorecard import (
    QUALITY_REPORT_FILES,
    QUALITY_REPORT_RUNTIME_REFS,
    build_quality_scorecard,
    normalize_quality_evidence,
)

HDS_XFAIL_REASON = "HDS red control pending implementation"


def sha(char: str) -> str:
    return "sha256:" + char * 64


def runtime_cas_refs() -> dict[str, str]:
    chars = "123456789abcdef0123456789abcdef"
    return {
        ref_key: sha(chars[index])
        for index, ref_key in enumerate(QUALITY_REPORT_RUNTIME_REFS.values())
    }


def bundle_local_runtime_refs() -> dict[str, str]:
    return {
        ref_key: f"quality_evidence/{QUALITY_REPORT_FILES[report_key]}"
        for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items()
    }


def complete_job_payload(
    *,
    runtime_refs: dict[str, str] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    progress_details: dict[str, Any] = {
        "data_snapshot_ref": sha("a"),
        "input_bindings_ref": sha("b"),
        "registry_bundle_ref": sha("c"),
        "quality_report_ref": sha("d"),
        "production_data_quality_report_ref": sha("1"),
        "llm_model_variants": [
            {
                "model_variant_id": "qwen_1",
                "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                "provider": "gateway",
                "status": "completed",
                "schema_healing_count": 0,
                "prompt_tokens": 120,
                "completion_tokens": 32,
                "total_tokens": 152,
                "cost_usd": 0.0001,
            }
        ],
        "run_performance_summary": {"status": "pass"},
    }
    progress_details.update(runtime_cas_refs() if runtime_refs is None else runtime_refs)
    progress_details.update(details or {})
    return {
        "job_id": "job-hds-red-control",
        "run_id": "R_hds_red_control",
        "state": "completed",
        "progress": {"details": progress_details},
    }


def complete_quality_evidence() -> dict[str, Any]:
    return {
        "golden_scenario_contract": {
            "scenario_id": "ukraine_msme_wartime_credit_support",
            "expected_evidence_contract": {
                "admissible_data_source_families": ["production_msme_panel"],
                "foundry_method_expectations": ["causal_effect_estimation"],
            },
        },
        "production_data_quality": {
            "schema_version": "policyos.runtime.production_data_quality.v1",
            "status": "pass",
            "manifest_checksum": sha("e"),
            "data_snapshot_ref": sha("a"),
            "input_bindings_ref": sha("b"),
            "registry_bundle_ref": sha("c"),
            "source_bundle_versions": {"datasets": "production_msme_panel_v1"},
            "row_counts": {"datasets": 240},
            "entity_counts": {"datasets": 120},
            "diagnostics": {
                key: {"status": "pass", "findings": []}
                for key in (
                    "schema_drift",
                    "missingness",
                    "outliers",
                    "duplicate_entity_collisions",
                    "unit_drift",
                    "temporal_leakage",
                    "cohort_leakage",
                    "label_quality",
                    "construct_validity",
                    "coverage",
                    "recency_ttl",
                    "data_dictionary",
                )
            },
            "issues": [],
        },
        "normative_evidence": {
            "status": "pass",
            "target_context": {
                "jurisdiction": "UA",
                "policy_domain": "wartime_msme_support",
                "as_of": "2026-05-12",
            },
            "applied_norms": [
                {
                    "norm_id": "norm.ua.credit_eligibility",
                    "jurisdiction": "UA",
                    "policy_domain": "wartime_msme_support",
                    "effective_from": "2024-01-01",
                    "source_authority": "Verkhovna Rada",
                    "authority_level": "statute",
                }
            ],
            "recommendation_claims": [
                {
                    "claim_id": "rec_1",
                    "major": True,
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ],
        },
        "fabric_retrieval_trace": {
            "status": "pass",
            "query_intent": {
                "policy_domain": "wartime_msme_support",
                "query_outcome": "msme_survival_rate",
                "query_treatment": "wartime_credit_support",
            },
            "candidate_sources": [
                {
                    "source_id": "production-msme-panel",
                    "source_family": "production_msme_panel",
                    "source_kind": "production_data",
                    "freshness": {"status": "pass"},
                    "coverage": {"status": "pass"},
                    "schema_compatibility": {"status": "pass"},
                    "relevance_rationale": "Matches requested outcome and treatment.",
                }
            ],
            "selected_source_ids": ["production-msme-panel"],
            "rejected_sources": [{"source_id": "fixture-source", "reason_code": "fixture"}],
        },
        "foundry_method_report": {
            "status": "pass",
            "selected_methods": [
                {
                    "method_id": "causal.difference_in_differences",
                    "method_family": "causal_effect_estimation",
                    "input_refs": {
                        "data_snapshot_ref": sha("a"),
                        "input_bindings_ref": sha("b"),
                    },
                    "assumptions": ["parallel_trends"],
                    "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
                    "missingness": {"status": "pass", "missing_rate": 0.02},
                    "sensitivity": {"status": "pass", "robustness": "moderate"},
                    "input_diagnostics": {"sample_size": 240, "min_required_sample_size": 30},
                    "result_summary": {"effect_estimate": 0.04},
                }
            ],
        },
        "policy_grounding_matrix": {
            "status": "pass",
            "claims": [
                {
                    "claim_id": "rec_1",
                    "claim_type": "recommendation",
                    "major": True,
                    "text": "Target wartime credit support to eligible MSMEs.",
                    "data_refs": ["production-msme-panel"],
                    "method_refs": ["causal.difference_in_differences"],
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ],
        },
        "conflict_check": {"status": "pass", "claims": [], "corpus_constraints": []},
        "causal_statistical_validity": {
            "schema_version": "policyos.foundry.causal_statistical_validity.v1",
            "status": "pass",
            "issues": [],
            "summary": {"case_count": 4},
        },
        "replay_manifest": {
            "schema_version": "policyos.replay_manifest.v1",
            "status": "pass",
            "deterministic_fingerprint": sha("f"),
        },
        "drift_explanation": {
            "schema_version": "policyos.drift_explanation.v1",
            "status": "match",
            "production_readiness": "pass",
            "differences": [],
        },
        "resilience_matrix": {
            "schema_version": "policyos.runtime.resilience_matrix.v1",
            "status": "pass",
            "summary": {"status": "pass"},
            "operator_findings": [],
        },
        "human_review_calibration": {
            "schema_version": "policyos.human_review_calibration_report.v1",
            "status": "pass",
            "quality_signals": [],
            "summary": {"review_count": 0},
        },
        "decision_artifact_quality": {
            "schema_version": "policyos.scientist.decision_artifact_quality.v1",
            "status": "pass",
            "issues": [],
            "decision_artifact_quality_report_ref": sha("2"),
        },
        "privacy_compliance_report": {
            "schema_version": "policyos.privacy_compliance_report.v1",
            "status": "pass",
            "issues": [],
            "summary": {
                "production_data_source_count": 1,
                "public_artifact_family_count": 1,
            },
        },
    }


def scorecard_for(
    *,
    canary_kind: str = "production",
    job_payload: dict[str, Any] | None = None,
    quality_evidence: dict[str, Any] | None = None,
    normalize: bool = True,
) -> dict[str, Any]:
    evidence = deepcopy(quality_evidence or complete_quality_evidence())
    if normalize:
        evidence = normalize_quality_evidence(evidence, canary_kind=canary_kind)
    return build_quality_scorecard(
        canary_kind=canary_kind,
        job_id="job-hds-red-control",
        run_id="R_hds_red_control",
        execution_status="completed",
        job_payload=job_payload or complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=evidence,
    )


def blocking_codes(scorecard: dict[str, Any]) -> set[str]:
    return {
        str(failure.get("code") or failure.get("gate"))
        for failure in scorecard.get("blocking_quality_failures", [])
        if isinstance(failure, dict)
    }
