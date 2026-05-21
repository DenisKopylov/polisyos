from __future__ import annotations

import copy

import pytest

from polisyos.runtime.quality.assurance_case import (
    build_policy_design_case_profile,
    build_policy_design_jurisdiction_spine,
)
from polisyos.runtime.quality.attestation import build_required_production_attestations
from polisyos.runtime.quality.diagnostic_slos import (
    build_diagnostic_slo_report,
    pass_observations_for_all_diagnostic_slos,
)
from polisyos.runtime.quality.pass1b_hardening import (
    PASS1B_PDD_REQUIRED_SURFACES,
    PASS1B_REQUIRED_CASE_BINDING_FIELDS,
    build_pass1b_tenant_cas_approval_governance_record,
)
from polisyos.runtime.quality.phase_barriers import PhaseBarrierId, PhaseBarrierRecord
from polisyos.runtime.quality.scorecard import (
    POLICY_DESIGN_CASE_RUNTIME_REF_KEYS,
    QUALITY_REPORT_RUNTIME_REFS,
    build_quality_scorecard,
    normalize_quality_evidence,
)
from polisyos.runtime.quality.semantic_binding import close_semantic_binding_ledger
from tests._helpers.hds_quality import (
    attestation_material_refs,
    attestation_product_refs,
    authority_envelope_for,
    complete_policy_design_concept_spine,
    complete_scholar_academic_evidence,
    complete_semantic_binding_ledger,
    policy_design_capability_ledger,
    policy_design_intent_envelope,
    policy_design_phase27_records,
    policy_design_phase28_2_records,
    policy_design_phase28_3_records,
    policy_design_phase29_2_records,
    policy_design_phase29_3_records,
    policy_design_phase30_records,
    policy_design_record_family_rows,
    policy_design_runtime_record_family_records,
    semantic_ledger_missing_claim_axes,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _blocking_codes(scorecard: dict[str, object]) -> set[str]:
    failures = scorecard.get("blocking_quality_failures")
    assert isinstance(failures, list)
    return {
        str(failure.get("code") or failure.get("gate"))
        for failure in failures
        if isinstance(failure, dict)
    }


def _failure_by_code(scorecard: dict[str, object], code: str) -> dict[str, object]:
    failures = scorecard.get("blocking_quality_failures")
    assert isinstance(failures, list)
    for failure in failures:
        if isinstance(failure, dict) and failure.get("code") == code:
            return failure
    raise AssertionError(f"missing blocking failure {code}: {failures!r}")


def _runtime_worker_attestation() -> dict[str, object]:
    return {
        "schema_version": "polisyos.runtime.attestation.v1",
        "attestation_id": "att-runtime-worker-scorecard",
        "trust_boundary_id": "runtime_worker",
        "generated_at": "2026-05-15T08:30:00+00:00",
        "expected_materials": [
            {"key": "run_request", "ref": "cas://sha256/" + "1" * 64, "sha256": "1" * 64}
        ],
        "observed_materials": [
            {"key": "run_request", "ref": "cas://sha256/" + "1" * 64, "sha256": "1" * 64}
        ],
        "expected_products": [
            {
                "key": "runtime_quality_refs",
                "ref": "cas://sha256/" + "2" * 64,
                "sha256": "2" * 64,
            }
        ],
        "observed_products": [
            {
                "key": "runtime_quality_refs",
                "ref": "cas://sha256/" + "2" * 64,
                "sha256": "2" * 64,
            }
        ],
        "functionary": {
            "functionary_id": "runtime-worker@prod-cell-a",
            "role": "runtime_worker",
            "service_account": "runtime-worker",
        },
        "producer_identity": {
            "component": "polisyos.runtime.worker",
            "version": "2026.05.15+hds-phase19",
            "owner": "team-runtime",
        },
        "environment_identity": {
            "environment_id": "prod-cell-a",
            "execution_profile": "production",
            "tenant_id": "tenant-1",
            "cell_id": "cell-a",
            "runner_id": "worker-1",
        },
        "isolation_status": "isolated",
        "service_generated": True,
        "consumer_verification": "verified",
        "tamper_check_status": "pass",
        "signature_ref": "signature://runtime-worker-scorecard",
        "evidence_ref": "cas://sha256/" + "3" * 64,
    }


def _trust_boundary_attestations() -> list[dict[str, object]]:
    return [
        record.model_dump(mode="json", exclude_none=True)
        for record in build_required_production_attestations(
            material_refs=attestation_material_refs(),
            product_refs=attestation_product_refs(),
        )
    ]


def _complete_job_payload() -> dict[str, object]:
    return {
        "job_id": "job-quality",
        "run_id": "R_quality",
        "state": "completed",
        "progress": {
            "details": {
                "data_snapshot_ref": _sha("1"),
                "input_bindings_ref": _sha("2"),
                "registry_bundle_ref": _sha("3"),
                "quality_report_ref": _sha("4"),
                "production_data_quality_report_ref": _sha("5"),
                "normative_applicability_report_ref": _sha("6"),
                "fabric_retrieval_trace_ref": _sha("7"),
                "foundry_method_report_ref": _sha("8"),
                "policy_grounding_matrix_ref": _sha("9"),
                "conflict_check_ref": _sha("a"),
                "causal_statistical_validity_report_ref": _sha("c"),
                "replay_manifest_ref": _sha("d"),
                "drift_explanation_ref": _sha("e"),
                "resilience_report_ref": _sha("f"),
                "human_review_calibration_report_ref": _sha("0"),
                "decision_artifact_quality_report_ref": _sha("2"),
                "privacy_compliance_report_ref": _sha("3"),
                "continuous_governance_stale_report_ref": _sha("4"),
                "continuous_governance_reissue_report_ref": _sha("5"),
                "continuous_governance_supersede_report_ref": _sha("6"),
                "continuous_governance_withdraw_report_ref": _sha("7"),
                "runtime_quality_refs": _complete_runtime_refs(),
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
                "diagnostic_event_log_ref": _sha("e"),
                "diagnostic_events": [
                    {
                        "event_name": f"{report_key}.persisted",
                        "severity": "serious",
                        "sampling": {"decision": "always_record", "rate": 1.0},
                        "artifact_ref": _complete_runtime_refs()[ref_key],
                        "runtime_cas_ref": _complete_runtime_refs()[ref_key],
                    }
                    for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items()
                    if ref_key in _complete_runtime_refs()
                ]
                + [
                    {
                        "event_name": f"{ref_key}.persisted",
                        "severity": "serious",
                        "sampling": {"decision": "always_record", "rate": 1.0},
                        "artifact_ref": _complete_runtime_refs()[ref_key],
                        "runtime_cas_ref": _complete_runtime_refs()[ref_key],
                    }
                    for ref_key in POLICY_DESIGN_CASE_RUNTIME_REF_KEYS
                    if ref_key in _complete_runtime_refs()
                ],
                "trust_boundary_attestations": _trust_boundary_attestations(),
            }
        },
    }


def _complete_runtime_refs() -> dict[str, str]:
    refs = {
        "production_data_quality_report_ref": _sha("5"),
        "normative_applicability_report_ref": _sha("6"),
        "fabric_retrieval_trace_ref": _sha("7"),
        "foundry_method_report_ref": _sha("8"),
        "policy_grounding_matrix_ref": _sha("9"),
        "conflict_check_ref": _sha("a"),
        "causal_statistical_validity_report_ref": _sha("c"),
        "replay_manifest_ref": _sha("d"),
        "drift_explanation_ref": _sha("e"),
        "resilience_report_ref": _sha("f"),
        "human_review_calibration_report_ref": _sha("0"),
        "decision_artifact_quality_report_ref": _sha("2"),
        "privacy_compliance_report_ref": _sha("3"),
        "continuous_governance_stale_report_ref": _sha("4"),
        "continuous_governance_reissue_report_ref": _sha("5"),
        "continuous_governance_supersede_report_ref": _sha("6"),
        "continuous_governance_withdraw_report_ref": _sha("7"),
    }
    refs.update(
        {
            "policy_intent_envelope_ref": _sha("0"),
            "policy_design_capability_ledger_ref": _sha("5"),
            "policy_design_case_ref": _sha("c"),
        }
    )
    return refs


def _phase_barrier_records() -> list[dict[str, object]]:
    return [
        PhaseBarrierRecord.pass_record(
            barrier_id=barrier_id,
            run_id="R_quality",
            tenant_id="tenant-1",
            profile="production",
            evidence_refs=[_sha("a"), _sha("b")],
            runtime_event_ref=_sha("e"),
            cas_ref=_sha("f"),
        ).model_dump(mode="json")
        for barrier_id in PhaseBarrierId.scorecard_required()
    ]


def _complete_pass1b_hardening_record() -> dict[str, object]:
    case_bindings = {
        surface: _pass1b_surface_binding(surface, required_fields)
        for surface, required_fields in PASS1B_REQUIRED_CASE_BINDING_FIELDS.items()
    }
    pdd_bindings = [
        {
            "pdd_id": pdd_id,
            "surface": surface,
            "surfaces": list(surfaces),
            "record_ref": f"policy_design_case.pass1b.{pdd_id.lower()}.{surface}",
            "evidence_ref": _sha("f"),
            "runtime_event_ref": f"event://policy-design-case/pass1b/{pdd_id}/{surface}",
            "owner": "team-quality-closeout",
            "status": "implemented",
        }
        for pdd_id, surfaces in PASS1B_PDD_REQUIRED_SURFACES.items()
        for surface in surfaces
    ]
    return build_pass1b_tenant_cas_approval_governance_record(
        record_id="pass1b-hardening-R_quality",
        case_id="pdc-R_quality",
        run_id="R_quality",
        job_id="job-quality",
        tenant_id="tenant-1",
        cell_id="cell-a",
        case_bindings=case_bindings,
        pdd_bindings=pdd_bindings,
        evidence_ref=_sha("1"),
        runtime_event_ref="event://policy-design-case/pass1b-hardening/1",
    )


def _pass1b_surface_binding(
    surface: str,
    required_fields: tuple[str, ...],
) -> dict[str, object]:
    binding: dict[str, object] = {"status": "pass"}
    for field in required_fields:
        if field == "runtime_event_ref":
            binding[field] = f"event://policy-design-case/pass1b/{surface}"
        elif field in {
            "read_scope_enforced",
            "non_overridable_blockers_enforced",
            "effective_oversight",
        }:
            binding[field] = True
        elif field in {
            "runtime_enforcement_log_refs",
            "reviewer_identity_refs",
            "before_after_hash_refs",
            "key_lifecycle_refs",
        }:
            binding[field] = [_sha("a")]
        elif field == "tenant_id":
            binding[field] = "tenant-1"
        elif field == "cell_id":
            binding[field] = "cell-a"
        elif field == "signature_ref":
            binding[field] = "signature://reviewer-alpha"
        elif field == "signature_class":
            binding[field] = "internal_reviewer_attestation"
        elif field == "rubber_stamp_risk":
            binding[field] = "low"
        elif field == "trust_status":
            binding[field] = "valid"
        elif field == "public_packet_signature_ref":
            binding[field] = "signature://public-packet"
        elif field == "projection_policy":
            binding[field] = "immutable_packet_projection"
        elif field == "retention_class":
            binding[field] = "governed"
        else:
            binding[field] = _sha("b")
    return binding


def _complete_data_forge_snapshot_binding_report() -> dict[str, object]:
    def binding(role: str, surface: str, char: str) -> dict[str, object]:
        return {
            "role": role,
            "snapshot_id": f"{role}-snapshot-R_quality",
            "snapshot_ref": _sha(char),
            "manifest_ref": "cas://sha256/" + char * 64,
            "manifest_artifact_id": _sha(char),
            "artifact_ids": [_sha(char), _sha("f")],
            "read_api_surface": surface,
            "read_api_module": f"polisyos.data_forge.read_api.{surface}",
            "published_at": "2026-05-15T00:00:00+00:00",
            "freshness_ttl_seconds": 60 * 60 * 24 * 3650,
            "quality_gates": [
                {
                    "name": f"{role}_publish_quality",
                    "status": "pass",
                    "artifact_id": _sha(char),
                }
            ],
        }

    return {
        "schema_version": "policyos.runtime.data_forge_snapshot_binding.v1",
        "run_id": "R_quality",
        "job_id": "job-quality",
        "bindings": [
            binding("legal", "legal", "1"),
            binding("catalog", "catalog", "2"),
            binding("academic", "academic", "3"),
            binding("domain", "ukraine", "4"),
        ],
    }


def _complete_job_payload_missing_runtime_refs(*ref_keys: str) -> dict[str, object]:
    payload = copy.deepcopy(_complete_job_payload())
    details = payload["progress"]["details"]  # type: ignore[index]
    assert isinstance(details, dict)
    runtime_refs = details.get("runtime_quality_refs")
    for ref_key in ref_keys:
        details.pop(ref_key, None)
        if isinstance(runtime_refs, dict):
            runtime_refs.pop(ref_key, None)
    return payload


def _complete_quality_evidence() -> dict[str, object]:
    source_truth_payload = {
        "status": "pass",
        "provenance": {"producer": "scientist.claim_compiler"},
        "owner": "team-policy-semantics",
        "schema": {"name": "policyos.claims", "version": "1"},
        "lineage": {"output_ref": _sha("c")},
        "tenant": {"tenant_id": "tenant-1", "cell_id": "cell-a"},
        "time_context": {"as_of": "2026-05-15"},
        "jurisdiction": {"code": "UA"},
        "source_family": {"families": ["production_msme_panel"]},
        "method_expectation": {"families": ["causal_effect_estimation"]},
        "claim_sets": {"claim_ids": ["rec_1"], "claim_refs": [_sha("d")]},
    }
    evidence: dict[str, object] = {
        "golden_scenario_contract": {
            "expected_evidence_contract": {
                "admissible_data_source_families": ["production_msme_panel"],
                "foundry_method_expectations": ["causal_effect_estimation"],
            }
        },
        "production_data_quality": {
            "schema_version": "policyos.runtime.production_data_quality.v1",
            "status": "pass",
            "manifest_checksum": _sha("b"),
            "data_snapshot_ref": _sha("1"),
            "input_bindings_ref": _sha("2"),
            "registry_bundle_ref": _sha("3"),
            "source_bundle_versions": {"datasets": "production_msme_panel_v1"},
            "row_counts": {"datasets": 240},
            "entity_counts": {"datasets": 120},
            "diagnostics": {
                "schema_drift": {"status": "pass", "findings": []},
                "missingness": {"status": "pass", "findings": []},
                "outliers": {"status": "pass", "findings": []},
                "duplicate_entity_collisions": {"status": "pass", "findings": []},
                "unit_drift": {"status": "pass", "findings": []},
                "temporal_leakage": {"status": "pass", "findings": []},
                "cohort_leakage": {"status": "pass", "findings": []},
                "label_quality": {"status": "pass", "findings": []},
                "construct_validity": {"status": "pass", "findings": []},
                "coverage": {"status": "pass", "findings": []},
                "recency_ttl": {"status": "pass", "findings": []},
                "data_dictionary": {"status": "pass", "findings": []},
            },
            "issues": [],
        },
        "normative_evidence": {
            "schema_version": "policyos.lex.normative_applicability_report.v1",
            "target_context": {
                "jurisdiction": "UA",
                "policy_domain": "wartime_msme_support",
                "as_of": "2026-05-12",
            },
            "retrieval_status": "completed",
            "legal_corpus_snapshot": {
                "snapshot_id": "legal-snapshot-R_quality",
                "snapshot_ref": _sha("6"),
                "manifest_ref": "cas://sha256/" + "6" * 64,
            },
            "query_terms": ["wartime MSME credit eligibility"],
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
            "schema_version": "policyos.fabric.source_selection_trace.v1",
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
                    "source_rights": "government_open_data",
                    "dataset_ref": "dataset:production-msme-panel",
                    "dictionary_ref": "dictionary:production-msme-panel:v1",
                    "schema_ref": "schema:production-msme-panel:v1",
                    "field_refs": [
                        "field:production-msme-panel.firm_id",
                        "field:production-msme-panel.survival",
                        "field:production-msme-panel.credit_amount",
                    ],
                    "unit_refs": ["unit:percent", "unit:UAH"],
                    "geography_refs": ["UA"],
                    "time_coverage_refs": ["2024-2026"],
                    "quality_refs": ["quality:production-msme-panel:v1"],
                    "missingness_refs": ["missingness:production-msme-panel:v1"],
                    "freshness_refs": ["freshness:production-msme-panel:2026-05-15"],
                    "lineage_refs": ["lineage:production-msme-panel:v1"],
                    "transformation_refs": ["transform:survival-rate:v1"],
                    "data_forge_snapshot_refs": [_sha("4")],
                    "derived_features": [
                        {
                            "feature_ref": "feature:msme_survival_rate",
                            "source_ref": "production-msme-panel",
                            "source_facet_refs": [
                                "field:production-msme-panel.survival"
                            ],
                            "claim_ids": ["rec_1"],
                            "claim_support_feature_refs": [
                                "claim-feature:rec_1:msme_survival_rate"
                            ],
                            "lineage_refs": ["lineage:production-msme-panel:v1"],
                            "transformation_refs": ["transform:survival-rate:v1"],
                        }
                    ],
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
            "schema_version": "policyos.foundry.method_quality_report.v1",
            "selected_methods": [
                {
                    "method_id": "causal.difference_in_differences",
                    "method_family": "causal_effect_estimation",
                    "input_refs": {
                        "data_snapshot_ref": _sha("1"),
                        "input_bindings_ref": _sha("2"),
                    },
                    "assumptions": ["parallel_trends"],
                    "identification_requirements": {
                        "estimand": "ATT",
                        "requirements": ["parallel_trends", "overlap"],
                    },
                    "transportability_limits": {
                        "target_population": "wartime_msmes",
                        "limits": ["No extrapolation outside observed support."],
                    },
                    "specification_space": {
                        "primary": "two_way_fixed_effects",
                        "alternatives": ["event_study", "matched_did"],
                    },
                    "method_result_refs": {"method_result_ref": _sha("c")},
                    "validity_surfaces": {
                        "identification": {"status": "present", "ref": _sha("1")},
                        "transportability": {"status": "present", "ref": _sha("2")},
                        "partial_identification": {"status": "present", "ref": _sha("3")},
                        "recoverability": {"status": "present", "ref": _sha("4")},
                        "causal_ensemble": {"status": "present", "ref": _sha("5")},
                        "falsification": {"status": "present", "ref": _sha("6")},
                        "certificate_proof": {"status": "present", "ref": _sha("7")},
                    },
                    "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
                    "missingness": {"status": "pass", "missing_rate": 0.02},
                    "sensitivity": {"status": "pass", "robustness": "moderate"},
                    "input_diagnostics": {"sample_size": 240, "min_required_sample_size": 30},
                    "result_summary": {"effect_estimate": 0.04},
                }
            ],
        },
        "scholar_evidence": complete_scholar_academic_evidence(),
        "policy_grounding_matrix": {
            "schema_version": "policyos.scientist.policy_grounding_matrix.v1",
            "claims": [
                {
                    "claim_id": "rec_1",
                    "claim_type": "recommendation",
                    "major": True,
                    "text": "Target wartime credit support to eligible MSMEs.",
                    "data_refs": ["production-msme-panel"],
                    "method_refs": ["causal.difference_in_differences"],
                    "norm_refs": ["norm.ua.credit_eligibility"],
                    "portfolio_refs": ["portfolio-rec-1"],
                    "independence_refs": ["independence-rec-1"],
                    "synthesis_refs": ["synthesis-rec-1"],
                    "argument_refs": ["arg-rec-1"],
                    "warrant_refs": ["warrant-rec-1"],
                    "rebuttal_refs": ["rebuttal-rec-1"],
                    "counter_evidence_refs": ["counter-evidence-rec-1"],
                    "limitation_refs": ["deficit-assessment-rec-1"],
                    "accepted_deficit_refs": ["deficit-assessment-rec-1"],
                }
            ],
        },
        "semantic_binding_ledger": complete_semantic_binding_ledger(),
        "conflict_check": {
            "schema_version": "policyos.lex.policy_conflict_check.v1",
            "claims": [],
            "corpus_constraints": [],
        },
        "causal_statistical_validity": {
            "schema_version": "policyos.foundry.causal_statistical_validity.v1",
            "status": "pass",
            "issues": [],
            "summary": {"case_count": 4},
        },
        "replay_manifest": {
            "schema_version": "policyos.replay_manifest.v1",
            "status": "pass",
            "deterministic_fingerprint": _sha("c"),
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
            "decision_artifact_quality_report_ref": _sha("2"),
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
        "data_forge_snapshot_binding": _complete_data_forge_snapshot_binding_report(),
    }
    refs = _complete_runtime_refs()
    lifecycle_reports = {
        "continuous_governance_stale": (
            "stale",
            "stale",
            "continuous_governance_stale_report_ref",
        ),
        "continuous_governance_reissue": (
            "reissue",
            "reissued",
            "continuous_governance_reissue_report_ref",
        ),
        "continuous_governance_supersede": (
            "supersede",
            "superseded",
            "continuous_governance_supersede_report_ref",
        ),
        "continuous_governance_withdraw": (
            "withdraw",
            "withdrawn",
            "continuous_governance_withdraw_report_ref",
        ),
    }
    for report_key, (decision, decision_status, ref_key) in lifecycle_reports.items():
        evidence[report_key] = {
            "schema_version": "policyos.runtime.governance_lifecycle_report.v1",
            "status": "pass",
            "lifecycle_decision": decision,
            "decision_status": decision_status,
            ref_key: refs[ref_key],
            "diagnostic_event": {
                "event_type": "polisyos.runtime.diagnostic.reconciliation_result.v1",
                "artifact_refs": [refs[ref_key]],
                "sampling_decision": "always_record",
                "sampling_rate": 1.0,
            },
            "cas_artifact_refs": {"governance_lifecycle_report_ref": refs[ref_key]},
            "schema_compatibility": {"decision": "compatible"},
            "effective_mode_ref": _sha("e"),
            "fallback_degradation_ref": _sha("d"),
            "degradation_ledger_ref": _sha("d"),
        }
    for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
        report = evidence.get(report_key)
        if isinstance(report, dict) and ref_key in refs:
            report["authority_envelope"] = authority_envelope_for(
                report_key=report_key,
                ref_key=ref_key,
                ref_value=refs[ref_key],
            )
    evidence["source_truth_adapter_surfaces"] = {
        "runtime.canary_bundle": {"final_claims": source_truth_payload},
        "runtime.scorecard": {"final_claims": copy.deepcopy(source_truth_payload)},
    }
    evidence["source_truth_adapter_paths"] = ["bundle_to_scorecard"]
    evidence["phase_barrier_records"] = _phase_barrier_records()
    evidence["assurance_case"] = {
        "schema_version": "policyos.runtime.assurance_case.v1",
        "claim": {
            "text": "Serious PolicyOS closeout is supported by runtime authority.",
            "status": "supported",
            "run_id": "R_quality",
            "job_id": "job-quality",
            "canary_kind": "production",
            "quality_status": "pass",
            "approval_state": "approval_ready",
        },
        "subclaims": [],
        "argument": "Runtime-owned diagnostic evidence supports closeout.",
        "argument_strategy": "runtime_authority_graph",
        "evidence": [{"key": "quality_scorecard", "ref": _sha("a")}],
        "assumptions": ["Fixture assurance case."],
        "contexts": {"quality_scorecard_ref": _sha("a")},
        "defeaters": [],
        "blockers": [],
        "unresolved_uncertainty": [],
        "confidence_limits": {"lower_bound": 0.8, "upper_bound": 0.99},
        "non_overridable_blockers": [],
        "reviewer_attribution": {"reviewer_id": "fixture", "review_status": "pending"},
        "owner": "team-assurance",
        "next_diagnostic_command": (
            "uv run python tools/quality/validation/check_honest_diagnostics_proof_harness.py "
            "--repo-root . --require-passing"
        ),
    }
    evidence["policy_design_case"] = build_policy_design_case_profile(
        case_id="pdc-R_quality",
        run_id="R_quality",
        job_id="job-quality",
        tenant_id="tenant-1",
        effective_execution_profile="production",
        intent_envelope=policy_design_intent_envelope(),
        capability_ledger=policy_design_capability_ledger(),
        runtime_authority={
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "cas_ref": _sha("1"),
            "runtime_event_ref": _sha("e"),
            "same_input_closure_ref": _sha("3"),
            "effective_mode_ref": _sha("e"),
            "schema_compatibility_ref": _sha("c"),
        },
        nodes=[
            complete_policy_design_concept_spine(
                run_id="R_quality",
                job_id="job-quality",
                policy_intent_ref=refs["policy_intent_envelope_ref"],
            )
        ],
    )
    evidence["policy_design_case"]["jurisdiction_spine"] = (
        build_policy_design_jurisdiction_spine(
            spine_id="jurisdiction-spine-R_quality",
            jurisdiction_spine_ref=_sha("6"),
            run_id="R_quality",
            job_id="job-quality",
            tenant_id="tenant-1",
            policy_intent_ref=refs["policy_intent_envelope_ref"],
            lex_normative_report=evidence["normative_evidence"],
            runtime_authority={
                "authority_role": "producer_authority",
                "provenance_kind": "runtime_emitted",
                "cas_ref": _sha("6"),
                "runtime_event_ref": _sha("e"),
                "same_input_closure_ref": _sha("3"),
                "effective_mode_ref": _sha("e"),
                "schema_compatibility_ref": _sha("c"),
            },
        )
    )
    evidence["policy_design_case"].update(policy_design_phase27_records())
    evidence["policy_design_case"].update(policy_design_phase28_2_records())
    evidence["policy_design_case"].update(policy_design_phase29_2_records())
    evidence["policy_design_case"].update(policy_design_phase29_3_records())
    evidence["policy_design_case"].update(policy_design_phase28_3_records())
    evidence["policy_design_case"].update(policy_design_phase30_records())
    evidence["policy_design_case"]["record_families"] = policy_design_record_family_rows()
    evidence["policy_design_case"]["records"] = policy_design_runtime_record_family_records()
    evidence["policy_design_case"]["pass1b_tenant_cas_approval_governance"] = (
        _complete_pass1b_hardening_record()
    )
    evidence["policy_design_case"]["policy_design_case_ref"] = _complete_runtime_refs()[
        "policy_design_case_ref"
    ]
    evidence["diagnostic_slo_report"] = build_diagnostic_slo_report(
        observations=pass_observations_for_all_diagnostic_slos(
            observed_at=None,
            evidence_ref=_sha("a"),
        ),
        run_id="R_quality",
        canary_kind="production",
        owner="team-assurance",
    )
    return evidence


RUNTIME_QUALITY_REF_CASES = (
    (
        "normative_applicability_report_ref",
        "normative_evidence_present",
        "normative_applicability_report_ref_missing",
        "Persist normative_applicability_report_ref",
    ),
    (
        "fabric_retrieval_trace_ref",
        "fabric_retrieval_trace_present",
        "fabric_retrieval_trace_ref_missing",
        "Persist fabric_retrieval_trace_ref",
    ),
    (
        "foundry_method_report_ref",
        "foundry_method_evidence_present",
        "foundry_method_report_ref_missing",
        "Persist foundry_method_report_ref",
    ),
    (
        "policy_grounding_matrix_ref",
        "policy_grounding_matrix_present",
        "policy_grounding_matrix_ref_missing",
        "Persist policy_grounding_matrix_ref",
    ),
    (
        "conflict_check_ref",
        "conflict_check_present",
        "conflict_check_ref_missing",
        "Persist conflict_check_ref",
    ),
    (
        "causal_statistical_validity_report_ref",
        "causal_statistical_validity_present",
        "causal_statistical_validity_report_ref_missing",
        "Persist causal_statistical_validity_report_ref",
    ),
    (
        "replay_manifest_ref",
        "replay_manifest_present",
        "replay_manifest_ref_missing",
        "Persist replay_manifest_ref",
    ),
    (
        "drift_explanation_ref",
        "drift_explanation_present",
        "drift_explanation_ref_missing",
        "Persist drift_explanation_ref",
    ),
    (
        "resilience_report_ref",
        "resilience_matrix_present",
        "resilience_report_ref_missing",
        "Persist resilience_report_ref",
    ),
    (
        "human_review_calibration_report_ref",
        "human_review_calibration_present",
        "human_review_calibration_report_ref_missing",
        "Persist human_review_calibration_report_ref",
    ),
    (
        "decision_artifact_quality_report_ref",
        "decision_artifact_quality_present",
        "decision_artifact_quality_report_ref_missing",
        "Persist decision_artifact_quality_report_ref",
    ),
    (
        "continuous_governance_stale_report_ref",
        "continuous_governance_stale_report_present",
        "continuous_governance_stale_report_ref_missing",
        "Persist continuous_governance_stale_report_ref",
    ),
    (
        "continuous_governance_reissue_report_ref",
        "continuous_governance_reissue_report_present",
        "continuous_governance_reissue_report_ref_missing",
        "Persist continuous_governance_reissue_report_ref",
    ),
    (
        "continuous_governance_supersede_report_ref",
        "continuous_governance_supersede_report_present",
        "continuous_governance_supersede_report_ref_missing",
        "Persist continuous_governance_supersede_report_ref",
    ),
    (
        "continuous_governance_withdraw_report_ref",
        "continuous_governance_withdraw_report_present",
        "continuous_governance_withdraw_report_ref_missing",
        "Persist continuous_governance_withdraw_report_ref",
    ),
)


def test_runtime_quality_scorecard_builds_stage_scores_and_evidence_refs() -> None:
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind="production",
    )

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["schema_version"] == "policyos.quality_scorecard.v1"
    assert scorecard["quality_status"] == "pass"
    assert scorecard["overall_score"] == 1.0
    assert set(scorecard["stage_scores"]) == {
        "llm",
        "fabric",
        "materialization",
        "foundry",
        "scientist",
        "lex",
        "policy_output",
        "ops",
    }
    assert scorecard["stage_scores"]["llm"] == 1.0
    assert scorecard["stage_scores"]["fabric"] == 1.0
    assert scorecard["evidence_refs"]["provider_preflight"] == "provider_preflight.json"
    assert (
        scorecard["evidence_refs"]["policy_grounding_matrix"]
        == "quality_evidence/policy_grounding_matrix.json"
    )
    assert scorecard["approval_state"] == "approval_ready"
    assert scorecard["performance_status"] == "pass"
    assert scorecard["approval_eligibility"] == {
        "state": "approval_ready",
        "eligible": True,
        "requires_override": False,
        "override_accepted": False,
        "missing_override": False,
        "execution_status": "completed",
        "quality_status": "pass",
        "performance_status": "pass",
        "blocking_gate_count": 0,
        "warning_count": 0,
        "reasons": [],
    }
    assert scorecard["warnings"] == []


def test_scorecard_emits_first_failing_producer_owner_map() -> None:
    quality_evidence = _complete_quality_evidence()
    fabric_trace = quality_evidence["fabric_retrieval_trace"]
    assert isinstance(fabric_trace, dict)
    fabric_trace["status"] = "fail"
    fabric_trace["issues"] = [
        {
            "code": "source_family_mismatch",
            "phase": "fabric_source_selection",
            "next_action": "Bind Fabric to an admissible scenario source contract.",
        }
    ]
    fabric_envelope = fabric_trace["authority_envelope"]
    assert isinstance(fabric_envelope, dict)
    fabric_envelope["validation_status"] = "fail"
    fabric_envelope["blocking_status"] = "blocking"

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    failure = _failure_by_code(scorecard, "source_family_mismatch")
    assert failure["owner"] == "team-fabric"
    assert failure["root_cause_class"] == "runtime_owned_domain_failure"
    assert failure["first_failing_artifact_ref"] == (
        _complete_runtime_refs()["fabric_retrieval_trace_ref"]
    )
    assert failure["next_action"] == "Bind Fabric to an admissible scenario source contract."

    for item in scorecard["blocking_quality_failures"]:
        assert item["owner"]
        assert item["root_cause_class"]
        assert item["first_failing_artifact_ref"]
        assert item["next_action"]

    triage = scorecard["operator_triage_ledger"]
    assert triage["schema_version"] == "policyos.operator_triage_ledger.v1"
    assert triage["root_cause_count"] >= 1
    fabric_root = next(
        item
        for item in triage["root_causes"]
        if item["first_failing_artifact_ref"]
        == _complete_runtime_refs()["fabric_retrieval_trace_ref"]
    )
    assert fabric_root["owner"] == "team-fabric"
    assert fabric_root["root_cause_class"] == "runtime_owned_domain_failure"
    assert "source_family_mismatch" in fabric_root["failure_codes"]
    assert scorecard["approval_eligibility"]["operator_triage_ledger"] == triage


def test_continuous_governance_noop_rejects_borrowed_production_data_authority() -> None:
    quality_evidence = _complete_quality_evidence()
    refs = _complete_runtime_refs()
    borrowed = copy.deepcopy(quality_evidence["production_data_quality"]["authority_envelope"])
    assert isinstance(borrowed, dict)

    for report_key, ref_key in (
        ("continuous_governance_stale", "continuous_governance_stale_report_ref"),
        ("continuous_governance_reissue", "continuous_governance_reissue_report_ref"),
        ("continuous_governance_supersede", "continuous_governance_supersede_report_ref"),
        ("continuous_governance_withdraw", "continuous_governance_withdraw_report_ref"),
    ):
        report = quality_evidence[report_key]
        assert isinstance(report, dict)
        envelope = copy.deepcopy(borrowed)
        envelope["artifact_ref"] = refs[ref_key]
        envelope["cas_ref"] = refs[ref_key]
        envelope["payload_sha256"] = refs[ref_key]
        envelope["output_refs"] = [refs[ref_key]]
        report["authority_envelope"] = envelope

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    failure = _failure_by_code(scorecard, "hds_borrowed_authority_envelope")
    assert failure["root_cause_class"] == "borrowed_authority_envelope"
    assert failure["producer_authority"]["artifact_kind"] == "production_data_quality"
    assert failure["first_failing_artifact_ref"] in {
        refs["continuous_governance_stale_report_ref"],
        refs["continuous_governance_reissue_report_ref"],
        refs["continuous_governance_supersede_report_ref"],
        refs["continuous_governance_withdraw_report_ref"],
    }


def test_scorecard_semantic_failures_match_closed_producer_ledger_status() -> None:
    closed_ledger = close_semantic_binding_ledger(semantic_ledger_missing_claim_axes())
    quality_evidence = _complete_quality_evidence()
    quality_evidence["semantic_binding_ledger"] = closed_ledger

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert closed_ledger["status"] == "fail"
    assert closed_ledger["runtime_report_status"] == "fail"
    assert scorecard["quality_status"] == "fail"
    assert {
        issue["code"] for issue in closed_ledger["issues"]
    } <= _blocking_codes(scorecard)


def test_source_truth_adapter_conflict_blocks_scorecard_input() -> None:
    raw_evidence = _complete_quality_evidence()
    semantic_payload = {
        "status": "pass",
        "provenance": {"producer": "scientist.claim_compiler"},
        "owner": "team-policy-semantics",
        "schema": {"name": "policyos.claims", "version": "1"},
        "lineage": {"output_ref": _sha("c")},
        "tenant": {"tenant_id": "tenant-1", "cell_id": "cell-a"},
        "time_context": {"as_of": "2026-05-15"},
        "jurisdiction": {"code": "UA"},
        "source_family": {"families": ["production_msme_panel"]},
        "method_expectation": {"families": ["causal_effect_estimation"]},
        "claim_sets": {"claim_ids": ["rec_1"], "claim_refs": [_sha("d")]},
    }
    mutated_payload = copy.deepcopy(semantic_payload)
    mutated_payload["claim_sets"] = {"claim_ids": ["rec_2"], "claim_refs": [_sha("d")]}
    raw_evidence["source_truth_adapter_surfaces"] = {
        "runtime.canary_bundle": {"final_claims": semantic_payload},
        "runtime.scorecard": {"final_claims": mutated_payload},
    }
    raw_evidence["source_truth_adapter_paths"] = ["bundle_to_scorecard"]
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert {
        failure["code"]
        for failure in scorecard["blocking_quality_failures"]
        if isinstance(failure, dict)
    } >= {"hds_adapter_semantic_loss"}
    assert scorecard["source_truth_conflicts"][0]["field_family"] == "final_claims"
    assert scorecard["source_truth_conflicts"][0]["lost_fields"] == ["claim_sets"]


def test_source_truth_reader_conflict_blocks_job_progress_state_mismatch() -> None:
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind="production",
    )
    job_payload = _complete_job_payload()
    progress = job_payload["progress"]  # type: ignore[index]
    assert isinstance(progress, dict)
    progress["state"] = "failed"

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=job_payload,
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    conflict = scorecard["source_truth_conflicts"][0]
    assert conflict["field_family"] == "approval_readiness_public_status"
    assert conflict["authoritative_source"] == "runtime.job_state"
    assert conflict["conflicting_source"] == "runtime.progress"
    assert conflict["failure_code"] == "hds_approval_readiness_authority_conflict"
    assert "approval" in conflict["downstream_impact"]


def test_source_truth_reader_conflict_blocks_runtime_ref_embedded_report_mismatch() -> None:
    raw_evidence = _complete_quality_evidence()
    raw_evidence["production_data_quality"]["production_data_quality_report_ref"] = _sha("b")  # type: ignore[index]
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    conflicts = scorecard["source_truth_conflicts"]
    assert any(
        conflict["field_family"] == "runtime_refs"
        and conflict["failure_code"] == "hds_runtime_ref_authority_conflict"
        and "production_data_quality_report_ref" in conflict["lost_fields"]
        and conflict["runtime_event_refs"]
        and conflict["cas_refs"]
        for conflict in conflicts
    )


def test_source_truth_reader_conflict_blocks_selected_variant_scorecard_mismatch() -> None:
    raw_evidence = _complete_quality_evidence()
    raw_evidence["policy_grounding_matrix"]["selected_variant_id"] = "qwen_1"  # type: ignore[index]
    raw_evidence["scorecard_projection"] = {
        "selected_variant_id": "kimi_2",
        "final_policy_claims_ref": _sha("8"),
    }
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert any(
        conflict["field_family"] == "final_claims"
        and conflict["authoritative_source"] == "runtime.selected_variant"
        and conflict["conflicting_source"] == "runtime.scorecard"
        and "selected_variant_id" in conflict["lost_fields"]
        for conflict in scorecard["source_truth_conflicts"]
    )


def test_serious_scorecard_requires_typed_source_truth_adapter_surfaces() -> None:
    raw_evidence = _complete_quality_evidence()
    raw_evidence.pop("source_truth_adapter_surfaces", None)
    raw_evidence.pop("source_truth_adapter_paths", None)
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert {
        failure["code"]
        for failure in scorecard["blocking_quality_failures"]
        if isinstance(failure, dict)
    } >= {"hds_adapter_surface_missing"}


def test_serious_scorecard_requires_closed_phase_barriers() -> None:
    raw_evidence = _complete_quality_evidence()
    raw_evidence.pop("phase_barrier_records", None)
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert {
        failure["code"]
        for failure in scorecard["blocking_quality_failures"]
        if isinstance(failure, dict)
    } >= {"phase_barrier_missing"}


def test_serious_scorecard_requires_policy_design_case_runtime_identity_refs() -> None:
    raw_evidence = _complete_quality_evidence()
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")
    job_payload = _complete_job_payload()
    details = job_payload["progress"]["details"]  # type: ignore[index]
    assert isinstance(details, dict)
    runtime_refs = details["runtime_quality_refs"]
    assert isinstance(runtime_refs, dict)
    for ref_key in (
        "policy_intent_envelope_ref",
        "policy_design_capability_ledger_ref",
        "policy_design_case_ref",
    ):
        runtime_refs.pop(ref_key, None)
        details.pop(ref_key, None)

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=job_payload,
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert _blocking_codes(scorecard) >= {
        "policy_intent_envelope_ref_missing",
        "policy_design_capability_ledger_ref_missing",
        "policy_design_case_ref_missing",
    }


def test_serious_scorecard_reports_missing_intent_and_capability_independently() -> None:
    raw_evidence = _complete_quality_evidence()
    case = copy.deepcopy(raw_evidence["policy_design_case"])
    assert isinstance(case, dict)
    case.pop("intent_envelope", None)
    case.pop("capability_ledger", None)
    raw_evidence["policy_design_case"] = case
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert _blocking_codes(scorecard) >= {
        "policy_design_intent_envelope_missing",
        "policy_design_capability_ledger_missing",
    }


def test_serious_scorecard_requires_policy_design_case_registry_entry() -> None:
    raw_evidence = _complete_quality_evidence()
    case = copy.deepcopy(raw_evidence["policy_design_case"])
    assert isinstance(case, dict)
    case.pop("case_registry_entry", None)
    raw_evidence["policy_design_case"] = case
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert "policy_design_case_registry_entry_missing" in _blocking_codes(scorecard)


def test_serious_scorecard_blocks_parallel_policy_design_case_authority() -> None:
    raw_evidence = _complete_quality_evidence()
    raw_evidence["parallel_policy_design_case_authority"] = {
        "schema_version": "policyos.policy_design_case.parallel_authority.v1",
        "owner": "team-scientist",
        "source_surface": "scientist.policy_authority_profiles",
    }
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert "policy_design_parallel_case_authority" in _blocking_codes(scorecard)


def test_production_scorecard_blocks_required_trust_boundary_without_attestation() -> None:
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind="production",
    )
    job_payload = _complete_job_payload()
    details = job_payload["progress"]["details"]  # type: ignore[index]
    assert isinstance(details, dict)
    details.pop("trust_boundary_attestations")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=job_payload,
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}
    assert scorecard["quality_status"] == "fail"
    assert (
        scorecard["evidence_refs"]["policy_grounding_matrix"]
        == "quality_evidence/policy_grounding_matrix.json"
    )
    assert gates["runtime_worker_attestation_verified"]["status"] == "fail"
    assert gates["runtime_worker_attestation_verified"]["code"] == "attestation_missing"
    assert gates["runtime_worker_attestation_verified"]["blocking"] is True
    assert any(
        failure["gate"] == "runtime_worker_attestation_verified"
        and failure["code"] == "attestation_missing"
        for failure in scorecard["blocking_quality_failures"]
    )


def test_production_scorecard_blocks_any_required_trust_boundary_without_attestation() -> None:
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind="production",
    )
    job_payload = _complete_job_payload()
    details = job_payload["progress"]["details"]  # type: ignore[index]
    assert isinstance(details, dict)
    attestations = list(details["trust_boundary_attestations"])
    details["trust_boundary_attestations"] = [
        attestation
        for attestation in attestations
        if attestation.get("trust_boundary_id") != "external_data_connector"
    ]

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=job_payload,
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}
    assert scorecard["quality_status"] == "fail"
    assert gates["external_data_connector_attestation_verified"]["status"] == "fail"
    assert gates["external_data_connector_attestation_verified"]["code"] == (
        "external_data_connector_attestation_missing"
    )
    assert gates["external_data_connector_attestation_verified"]["blocking"] is True
    assert any(
        failure["gate"] == "external_data_connector_attestation_verified"
        and failure["code"] == "external_data_connector_attestation_missing"
        for failure in scorecard["blocking_quality_failures"]
    )


def test_runtime_quality_scorecard_fails_completed_job_without_fabric_trace() -> None:
    quality_evidence = normalize_quality_evidence(
        {
            key: value
            for key, value in _complete_quality_evidence().items()
            if key != "fabric_retrieval_trace"
        },
        canary_kind="production",
    )

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}
    assert scorecard["quality_status"] == "fail"
    assert scorecard["stage_scores"]["fabric"] == 0.0
    assert gates["fabric_retrieval_trace_present"]["status"] == "fail"
    assert any(
        failure["gate"] == "fabric_retrieval_trace_present"
        for failure in scorecard["blocking_quality_failures"]
    )
    assert scorecard["approval_state"] == "quality_failed"
    assert scorecard["approval_eligibility"]["eligible"] is False
    assert "fabric_retrieval_trace_present" in scorecard["approval_eligibility"]["reasons"]


def test_unknown_schema_only_report_cannot_pass_serious_scorecard_gate() -> None:
    raw_evidence = _complete_quality_evidence()
    raw_evidence["causal_statistical_validity"] = {
        "schema_version": "policyos.unregistered_quality_report.v99",
        "status": "pass",
    }
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}
    assert scorecard["quality_status"] == "fail"
    assert gates["causal_statistical_validity_present"]["status"] == "fail"
    assert gates["causal_statistical_validity_present"]["code"] == "hds_schema_incompatible"
    assert any(
        failure["gate"] == "causal_statistical_validity_present"
        and failure["code"] == "hds_schema_incompatible"
        for failure in scorecard["blocking_quality_failures"]
    )


@pytest.mark.parametrize("status", ["present", "completed"])
def test_serious_scorecard_rejects_pass_shaped_report_status_without_authority_status(
    status: str,
) -> None:
    raw_evidence = _complete_quality_evidence()
    raw_evidence["replay_manifest"]["status"] = status
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}
    assert scorecard["quality_status"] == "fail"
    assert gates["replay_manifest_present"]["status"] == "fail"
    assert gates["replay_manifest_present"]["code"] == "hds_unknown_provenance"
    assert "hds_unknown_provenance" in _blocking_codes(scorecard)


def test_serious_scorecard_rejects_bundle_generated_runtime_looking_refs() -> None:
    raw_evidence = _complete_quality_evidence()
    envelope = raw_evidence["policy_grounding_matrix"]["authority_envelope"]
    assert isinstance(envelope, dict)
    envelope["authority_role"] = "packaging_only"
    envelope["provenance_kind"] = "bundle_packaged"
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_projection_used_as_authority" in _blocking_codes(scorecard)


def test_serious_scorecard_rejects_redacted_derived_authority_envelope() -> None:
    raw_evidence = _complete_quality_evidence()
    envelope = raw_evidence["policy_grounding_matrix"]["authority_envelope"]
    assert isinstance(envelope, dict)
    envelope["evidence_class"] = "redacted_derived"
    envelope["redaction_policy_ref"] = "redaction-policy/public-export-v1"
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_projection_used_as_authority" in _blocking_codes(scorecard)


def test_serious_scorecard_requires_same_input_closure_across_required_evidence() -> None:
    raw_evidence = _complete_quality_evidence()
    envelope = raw_evidence["policy_grounding_matrix"]["authority_envelope"]
    assert isinstance(envelope, dict)
    closure = envelope["same_input_closure"]
    assert isinstance(closure, dict)
    closure["closure_sha256"] = "9" * 64
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_same_input_closure_mismatch" in _blocking_codes(scorecard)


def test_serious_scorecard_verifies_effective_mode_ledger_before_gate_scoring() -> None:
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind="production",
    )
    job_payload = _complete_job_payload()
    details = job_payload["progress"]["details"]  # type: ignore[index]
    assert isinstance(details, dict)
    details["effective_mode_ledger"] = {
        "requested_execution_profile": "production",
        "effective_execution_profile": "production",
        "requested_canary_kind": "production",
        "effective_canary_kind": "production",
        "requested_matrix_lane_id": "production-live",
        "effective_matrix_lane_id": "production-live",
        "requested_provider_mode": "live",
        "effective_provider_mode": "simulated",
        "requested_llm_simulation_mode": "disabled",
        "effective_llm_simulation_mode": "enabled",
        "requested_fixture_identity": None,
        "effective_fixture_identity": None,
        "requested_mock_fallback_allowed": False,
        "effective_mock_fallback_allowed": False,
        "requested_mock_fallback_used": False,
        "effective_mock_fallback_used": False,
        "requested_data_mode": "production",
        "effective_data_mode": "production",
        "requested_state_store_backend": "runtime_control_plane_postgres",
        "effective_state_store_backend": "runtime_control_plane_postgres",
        "requested_local_control_waiver": None,
        "effective_local_control_waiver": None,
        "requested_scorecard_warn_policy": "fail_serious",
        "effective_scorecard_warn_policy": "fail_serious",
        "requested_evidence_overlay_mode": "disabled",
        "effective_evidence_overlay_mode": "disabled",
        "requested_signed_exception_ref": None,
        "effective_signed_exception_ref": None,
        "requested_quarantine_status": "none",
        "effective_quarantine_status": "none",
    }

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=job_payload,
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_disallowed_mode" in _blocking_codes(scorecard)


def test_serious_scorecard_blocks_declared_source_truth_conflicts() -> None:
    raw_evidence = _complete_quality_evidence()
    raw_evidence["source_truth_conflicts"] = [
        {
            "field_family": "runtime_refs",
            "failure_code": "hds_runtime_ref_authority_conflict",
            "lost_fields": ["runtime_refs"],
            "next_diagnostic_command": (
                "uv run pytest tests/unit/runtime/quality/test_source_truth_lattice.py -q"
            ),
        }
    ]
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_source_truth_conflict" in _blocking_codes(scorecard)


def test_pql_014_code_presence_cannot_satisfy_published_lifecycle_scope() -> None:
    raw_evidence = _complete_quality_evidence()
    for report_key in (
        "continuous_governance_stale",
        "continuous_governance_reissue",
        "continuous_governance_supersede",
        "continuous_governance_withdraw",
    ):
        raw_evidence.pop(report_key, None)
    raw_evidence["published_decision_lifecycle"] = {
        "in_scope": True,
        "code_presence": {
            "modules": [
                "src/polisyos/scientist/governance/continuous/monitors.py",
                "src/polisyos/scientist/governance/continuous/reissue.py",
            ],
            "tests": [
                "tests/unit/scientist/governance/continuous/test_monitors.py",
                "tests/unit/scientist/governance/continuous/test_reissue.py",
            ],
        },
    }
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")
    job_payload = _complete_job_payload_missing_runtime_refs(
        "continuous_governance_stale_report_ref",
        "continuous_governance_reissue_report_ref",
        "continuous_governance_supersede_report_ref",
        "continuous_governance_withdraw_report_ref",
    )
    details = job_payload["progress"]["details"]  # type: ignore[index]
    assert isinstance(details, dict)
    details["diagnostic_events"] = [
        event
        for event in details["diagnostic_events"]
        if isinstance(event, dict)
        and not str(event.get("event_name") or "").startswith("continuous_governance_")
    ]

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=job_payload,
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}
    expected = {
        "continuous_governance_stale_report_present": "hds_runtime_ref_missing",
        "continuous_governance_reissue_report_present": "hds_runtime_ref_missing",
        "continuous_governance_supersede_report_present": "hds_runtime_ref_missing",
        "continuous_governance_withdraw_report_present": "hds_runtime_ref_missing",
    }

    assert scorecard["quality_status"] == "fail"
    assert gates["scientist_workflow_report_passed"]["status"] == "pass"
    for gate_name, expected_code in expected.items():
        assert gates[gate_name]["status"] == "fail"
        assert gates[gate_name]["code"] == expected_code
    assert {
        failure["code"]
        for failure in scorecard["blocking_quality_failures"]
        if failure["gate"] in expected
    } == set(expected.values())


def test_runtime_quality_scorecard_distinguishes_failed_execution_from_quality() -> None:
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind="production",
    )

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="failed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert scorecard["approval_state"] == "execution_failed"
    assert scorecard["approval_eligibility"]["eligible"] is False
    assert scorecard["approval_eligibility"]["reasons"] == ["execution_not_completed"]


def test_runtime_quality_scorecard_distinguishes_quality_warning_state() -> None:
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind="staging",
    )

    scorecard = build_quality_scorecard(
        canary_kind="staging",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight=None,
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "warn"
    assert scorecard["approval_state"] == "quality_warn"
    assert scorecard["approval_eligibility"]["eligible"] is False
    assert scorecard["warnings"] == [
        {
            "gate": "provider_preflight_recorded",
            "code": "provider_preflight_missing",
            "layer": "llm_gateway",
            "phase": "provider_preflight",
            "message": "Provider preflight evidence is missing.",
            "evidence_ref": None,
            "next_action": "Record provider preflight evidence before long real LLM runs.",
        }
    ]


def test_runtime_quality_scorecard_requires_override_for_performance_budget_failure() -> None:
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind="production",
    )
    job_payload = _complete_job_payload()
    job_payload["progress"]["details"]["run_performance_summary"] = {
        "schema_version": "1.0",
        "phase_budgets": [
            {
                "phase": "llm.total",
                "duration_ms": 65000,
                "budget_ms": 60000,
                "status": "over_budget",
            }
        ],
        "budget_summary": {"over_budget_count": 1},
    }

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=job_payload,
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["quality_status"] == "pass"
    assert scorecard["performance_status"] == "fail"
    assert scorecard["approval_state"] == "override_required"
    assert scorecard["approval_eligibility"]["requires_override"] is True
    assert scorecard["approval_eligibility"]["missing_override"] is True
    assert scorecard["approval_eligibility"]["reasons"] == ["performance_budget_failed"]


def test_runtime_quality_scorecard_sanitizes_override_evidence() -> None:
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind="production",
    )
    job_payload = _complete_job_payload()
    job_payload["progress"]["details"]["run_performance_summary"] = {
        "schema_version": "1.0",
        "phase_budgets": [
            {
                "phase": "llm.total",
                "duration_ms": 65000,
                "budget_ms": 60000,
                "status": "over_budget",
            }
        ],
        "budget_summary": {"over_budget_count": 1},
    }
    job_payload["progress"]["quality_override"] = {
        "status": "overridden",
        "decision_ref": "cas://quality-overrides/decision-1",
        "packet_ref": "cas://quality-overrides/packet-1",
        "reviewer_id": "reviewer@example.com",
        "rationale": "contains private deliberation",
        "api_key": "sk-secret",
        "signed": True,
    }

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=job_payload,
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert scorecard["approval_state"] == "approval_ready"
    assert scorecard["approval_eligibility"]["requires_override"] is True
    assert scorecard["approval_eligibility"]["override_accepted"] is True
    assert scorecard["override_evidence"] == {
        "status": "accepted",
        "accepted": True,
        "decision_ref": "cas://quality-overrides/decision-1",
        "packet_ref": "cas://quality-overrides/packet-1",
    }
    rendered = str(scorecard["override_evidence"])
    assert "reviewer@example.com" not in rendered
    assert "private deliberation" not in rendered
    assert "sk-secret" not in rendered


@pytest.mark.parametrize(
    ("ref_key", "gate_name", "expected_code", "next_action_fragment"),
    RUNTIME_QUALITY_REF_CASES,
)
def test_runtime_quality_scorecard_fails_serious_completed_job_missing_runtime_quality_ref(
    ref_key: str,
    gate_name: str,
    expected_code: str,
    next_action_fragment: str,
) -> None:
    expected_code = "hds_runtime_ref_missing"
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind="production",
    )

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload_missing_runtime_refs(ref_key),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}
    assert scorecard["execution_status"] == "completed"
    assert scorecard["quality_status"] == "fail"
    assert gates[gate_name]["status"] == "fail"
    assert gates[gate_name]["code"] == expected_code
    assert gates[gate_name]["next_action"] is not None
    assert next_action_fragment in gates[gate_name]["next_action"]
    assert any(
        failure["gate"] == gate_name
        and failure["code"] == expected_code
        and next_action_fragment in str(failure["next_action"])
        for failure in scorecard["blocking_quality_failures"]
    )


@pytest.mark.parametrize("canary_kind", ["research", "governed", "production"])
def test_runtime_quality_scorecard_fails_closed_for_serious_profiles_missing_runtime_refs(
    canary_kind: str,
) -> None:
    missing_refs = tuple(ref_key for ref_key, *_ in RUNTIME_QUALITY_REF_CASES)
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind=canary_kind,
    )

    scorecard = build_quality_scorecard(
        canary_kind=canary_kind,
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=_complete_job_payload_missing_runtime_refs(*missing_refs),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}
    expected_gate_names = {gate_name for _, gate_name, *_ in RUNTIME_QUALITY_REF_CASES}
    blocking_gate_names = {failure["gate"] for failure in scorecard["blocking_quality_failures"]}

    assert scorecard["execution_status"] == "completed"
    assert scorecard["quality_status"] == "fail"
    assert blocking_gate_names >= expected_gate_names
    for gate_name in expected_gate_names:
        assert gates[gate_name]["status"] == "fail"
        assert gates[gate_name]["blocking"] is True
        assert gates[gate_name]["next_action"]


def test_runtime_quality_scorecard_warns_for_explicitly_optional_dev_runtime_ref() -> None:
    job_payload = _complete_job_payload_missing_runtime_refs("conflict_check_ref")
    details = job_payload["progress"]["details"]  # type: ignore[index]
    assert isinstance(details, dict)
    details["optional_runtime_quality_refs"] = {
        "conflict_check_ref": "No active corpus is loaded for this local dev fixture."
    }
    quality_evidence = normalize_quality_evidence(
        _complete_quality_evidence(),
        canary_kind="dev",
    )

    scorecard = build_quality_scorecard(
        canary_kind="dev",
        job_id="job-quality-dev",
        run_id="R_quality_dev",
        execution_status="completed",
        job_payload=job_payload,
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}
    assert scorecard["execution_status"] == "completed"
    assert scorecard["quality_status"] == "warn"
    assert gates["conflict_check_present"]["status"] == "warn"
    assert gates["conflict_check_present"]["code"] == "conflict_check_ref_optional_missing"
    assert gates["conflict_check_present"]["blocking"] is False
    assert gates["conflict_check_present"]["next_action"]
    assert not any(
        failure["gate"] == "conflict_check_present"
        for failure in scorecard["blocking_quality_failures"]
    )


def test_runtime_quality_scorecard_downgrades_dev_fixture_data_quality_failures() -> None:
    quality_evidence = _complete_quality_evidence()
    quality_evidence["production_data_quality"] = {
        "schema_version": "policyos.runtime.production_data_quality.v1",
        "status": "fail",
        "issues": [
            {
                "code": "production_data_quality_missing",
                "severity": "fail",
                "status": "fail",
                "message": "Bundle datasets readiness is fixture-like: fixture.",
                "next_action": "Use a ready production bundle for serious runs.",
            }
        ],
    }
    normalized_evidence = normalize_quality_evidence(quality_evidence, canary_kind="dev")

    scorecard = build_quality_scorecard(
        canary_kind="dev",
        job_id="job-quality-dev",
        run_id="R_quality_dev",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight=None,
        quality_evidence=normalized_evidence,
    )

    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}
    assert scorecard["execution_status"] == "completed"
    assert scorecard["quality_status"] == "warn"
    assert gates["production_data_quality_present"]["status"] == "warn"
    assert gates["production_data_quality_present"]["blocking"] is False
    assert gates["production_data_quality_present"]["code"] == "production_data_quality_missing"
    assert not any(
        failure["gate"] == "production_data_quality_present"
        for failure in scorecard["blocking_quality_failures"]
    )
