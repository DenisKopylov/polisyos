from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
G5_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g5_proving_ground_conversion.v1"
G5_RULE_VERSION = "policyos.layer3.g5.first_proving_ground_conversion.v1"
G5_PINNED_CASE_ID = "ua-msme-affordable-loans-2022"
EXACT_S4_S14_CASE_KEYS = {
    "s4_epistemic_regime",
    "s5_coupling_composition",
    "s6_blind_spot_firewalls",
    "s7_delegation",
    "s8_value_choice",
    "s9_projection_lowering",
    "s10_outcome_prediction",
    "s11_predictive_knowledge",
    "s12_resource_economics",
    "s13_post_deploy_accountability",
    "s14_universality_assurance",
}

EXPECTED_CONVERSION_OUTCOMES = {
    "typed_blocker -> grounded_limited",
    "typed_blocker -> grounded_abstention",
    "unchanged_blocker",
}

EXPECTED_AUTHORITATIVE_FOR = {
    "layer3_g5_proving_ground_conversion_classification",
    "layer3_g5_envelope_expansion_reading",
    "w12d_layer3_conversion_gate",
}

EXPECTED_MAY_NOT_USE_FOR = {
    "approval_authority",
    "causal_effect_authority_without_g2",
    "claim_authority_without_upstream_grounding",
    "closeout_authority",
    "g6_arbitrary_request_orchestration",
    "g7_region_widening",
    "legal_advice",
    "legal_authority_without_gl",
    "policy_recommendation",
    "production_authority",
    "production_claim_authority",
    "proof_authority_without_g3",
    "public_recommendation",
    "publication_authority",
    "rollout_authority",
    "runtime_closeout_authority",
    "scorecard_authority",
    "useful_design_rate_floor_relaxation",
}

EXPECTED_DTOS = {
    "Layer3G5ValidationIssue",
    "Layer3G5ValidationReport",
    "Layer3G5DependencyReadinessSnapshot",
    "Layer3G5PinnedCaseInputBundle",
    "Layer3G5W12DCaseBlockIndex",
    "Layer3G5ComposedLoopCompletenessGate",
    "Layer3G5G4HandoffResolution",
    "Layer3G5G4PromotionRecordResolution",
    "Layer3G5UpstreamScopeJoinMatrix",
    "Layer3G5GroundedResultEvidenceSet",
    "Layer3G5EffectiveEvidenceIndependenceRecord",
    "Layer3G5ConversionEligibilityLedger",
    "Layer3G5StatusCompositionLedger",
    "Layer3G5GroundedAbstentionQualityRecord",
    "Layer3G5DemandPullAttemptRecord",
    "Layer3G5DependencyHealthMetricSnapshot",
    "Layer3G5EnvelopeExpansionDelta",
    "Layer3G5ConversionRecord",
    "Layer3G5W12DConsumerGate",
    "Layer3G5ConversionAuditSurface",
    "Layer3G5PublicExportProjectionRefs",
    "Layer3G5ConformanceReport",
    "Layer3G5RegistryRatchetDelta",
    "Layer3G5ReadinessManifest",
    "Layer3G5Bundle",
}

EXPECTED_BUILDERS_AND_VALIDATORS = {
    "build_g5_conversion_eligibility_ledger",
    "build_g5_demand_pull_attempt_record",
    "build_g5_dependency_health_metric_snapshot",
    "build_g5_envelope_expansion_delta",
    "build_g5_s12_demand_growth_evidence",
    "build_g5_status_composition_ledger",
    "build_g5_useful_design_metric_eligibility_join",
    "build_layer3_g5_bundle",
    "validate_layer3_g5_bundle",
    "build_g5_w12d_consumer_gate",
}

TASK7_EXPECTED_BUILDERS_AND_VALIDATORS = {
    "check_g5_candidate_authority_firewall",
    "check_g5_closed_case_replay_integrity",
    "check_g5_closeout_boundary",
    "check_g5_warning_lifecycle",
}

TASK7_CONFORMANCE_NEGATIVE_IDS = {
    "public_projection_raw_payload_leak",
    "projection_authority_leak",
    "public_export_hook_overclaimed",
    "closed_case_replay_mutation",
    "closeout_surface_substitution_attempt",
    "closeout_authority_leak",
    "candidate_unverified_authority_slot",
    "rejected_speculation_authority_slot",
    "unowned_warning_lifecycle",
    "warning_used_as_conversion_pass",
    "arbitrary_request_attempt",
    "g7_region_widening_attempt",
}

TASK7_EXPECTED_ISSUE_CODES = {
    "layer3_g5_pre_g5_closed_case_replay_mutated",
    "layer3_g5_closeout_surface_substitution_attempt",
    "layer3_g5_closeout_authority_leak",
    "layer3_g5_candidate_unverified_used_as_authority",
    "layer3_g5_rejected_speculation_used_as_authority",
    "layer3_g5_unowned_warning_lifecycle",
    "layer3_g5_warning_used_as_conversion_pass",
    "layer3_g5_arbitrary_request_attempt",
    "layer3_g5_g7_widening_attempt",
}

TASK1_EXPECTED_ISSUE_CODES = {
    "layer3_g5_g0_dependency_not_ready",
    "layer3_g5_g1_dependency_not_ready",
    "layer3_g5_g4_dependency_not_ready",
    "layer3_g5_dependency_manifest_status_key_missing",
    "layer3_g5_w12d_build_cache_not_source_of_truth",
    "layer3_g5_g4_handoff_missing",
    "layer3_g5_g4_handoff_authority_leak",
    "layer3_g5_g4_handoff_pass_with_blockers_overclaimed",
    "layer3_g5_g4_weakest_boundary_record_mismatch",
    "layer3_g5_no_governed_promotion_record",
    "layer3_g5_blocked_promotion_used_as_conversion",
    "layer3_g5_g4_grounded_contract_duplicate_inflates_evidence",
    "layer3_g5_g1_observed_but_uncertain_overclaimed",
    "layer3_g5_g1_source_contract_hash_missing",
    "layer3_g5_g1_observed_time_missing",
    "layer3_g5_g1_may_not_use_for_dropped",
    "layer3_g5_g2_design_record_ref_unresolved",
    "layer3_g5_g2_s2_replay_key_ref_missing",
    "layer3_g5_g2_source_contract_ref_mismatch",
    "layer3_g5_g3_proof_status_overclaimed",
    "layer3_g5_duplicate_source_lineage_ref_inflates_independence",
    "layer3_g5_gl_pass_with_reissue_required",
}

TASK3_EXPECTED_ISSUE_CODES = {
    "layer3_g5_contested_status_flattened",
    "layer3_g5_review_required_status_flattened",
    "layer3_g5_partial_status_flattened",
    "layer3_g5_gl_requirement_artifact_overrides_applicability",
    "layer3_g5_gl_mandate_compatibility_only_blocks_conversion",
    "layer3_g5_useful_design_metric_eligibility_join_missing",
    "layer3_g5_expert_useful_design_ceiling_used_as_runtime_credit",
    "layer3_g5_search_recall_seed_miss_blocks_abstention",
    "layer3_g5_stale_index_blocks_abstention",
    "layer3_g5_search_ceiling_not_domain_ceiling",
    "layer3_g5_grounded_abstention_without_evidence",
    "layer3_g5_human_decision_record_required",
    "layer3_g5_grounded_limited_without_status_composition",
    "layer3_g5_uncontrolled_w12d_outcome_status",
}

TASK4_EXPECTED_ISSUE_CODES = {
    "layer3_g5_envelope_expansion_delta_missing",
    "layer3_g5_envelope_expansion_reason_missing",
    "layer3_g5_upstream_health_metric_missing",
    "layer3_g5_stale_upstream_health_metric",
    "layer3_g5_s12_demand_scope_mismatch",
}

TASK0_PATTERN_IDS = {"P01", "P02", "P04", "P05", "P10", "P14", "P15", "P25", "P26"}
TASK0_MISSING_CAPABILITY_LABELS = {
    "producer_missing",
    "artifact_missing",
    "bridge_missing",
    "consumer_missing",
    "surface_missing",
    "semantic_test_missing",
}


def _minimal_w12d_case(**overrides: Any) -> dict[str, Any]:
    s2_design_search = {
        "status": "shadow_ready",
        "deterministic_replay_key": "replay://layer2/s2/ua-msme",
        "search_ledger": {
            "acquisition_branch_state": "resolved",
            "delegation_record_refs": ["human-decision-record://ua-msme/final-choice"],
            "delegation_request_refs": ["human-decision-request://ua-msme/final-choice"],
        },
        "design_record": {
            "ref": "pdc://layer2/s2/ua-msme/design-record-v0",
            "firewall_status": [
                {
                    "cell_ref": "KNOWLEDGE.predictive_knowledge_relaxation",
                    "status": "pass",
                }
            ],
            "ledger_refs": ["human-decision-request://ua-msme/final-choice"],
        },
        "constraint_store": {
            "constraint_records": [
                {
                    "constraint_id": "layer2.s11.predictive",
                    "cell_ref": "KNOWLEDGE.predictive_knowledge_relaxation",
                    "status": "pass",
                    "evidence_refs": ["pdc://layer3/g3/proof"],
                }
            ]
        },
        "delegation_posture": {
            "human_decision_record_ref": "human-decision-record://ua-msme/final-choice",
            "human_decision_request_ref": "human-decision-request://ua-msme/final-choice",
        },
    }
    blocks = {
        "s4_epistemic_regime": {"status": "pass", "regime_ref": "s4://ua-msme"},
        "s5_coupling_composition": {"status": "pass", "coupling_ref": "s5://ua-msme"},
        "s6_blind_spot_firewalls": {"status": "pass", "firewall_ref": "s6://ua-msme"},
        "s7_delegation": {
            "status": "pass",
            "human_decision_record_ref": "human-decision-record://ua-msme/final-choice",
            "human_decision_request_ref": "human-decision-request://ua-msme/final-choice",
        },
        "s8_value_choice": {"status": "pass", "value_choice_ref": "s8://ua-msme"},
        "s9_projection_lowering": {"status": "pass", "projection_ref": "s9://ua-msme"},
        "s10_outcome_prediction": {
            "status": "pass",
            "forecast_support_ref": "pdc://layer3/g2/forecast-support",
        },
        "s11_predictive_knowledge": {
            "status": "pass",
            "predictive_knowledge_ref": "pdc://layer2/s11/ua-msme",
        },
        "s12_resource_economics": {
            "status": "pass",
            "demand_act_refs": ["demand-act://ua-msme/principal"],
            "growth_entries": [
                {
                    "demand_act_ref": "demand-act://ua-msme/principal",
                    "certified_envelope_delta_ref": "envelope-delta://ua-msme/first",
                    "growth_counting_disposition": "counted",
                }
            ],
            "voi_allocation_refs": ["voi://ua-msme/site-1"],
        },
        "s13_post_deploy_accountability": {
            "status": "pass",
            "accountability_ref": "s13://ua-msme",
        },
        "s14_universality_assurance": {
            "status": "pass",
            "grounded_authority_status": "pass",
            "universal_claim_gate_status": "pending_sealed",
            "battery_status": "not_tested",
            "sealed_battery_status": "not_accessed_in_dev",
            "declared_posture": "limited",
            "declared_envelope_ref": "envelope://ua-msme/declared-limited",
        },
    }
    case = {
        "case_id": G5_PINNED_CASE_ID,
        "outcome": "typed_blocker",
        "conversion_outcome": "not_attempted_g0_pre_adapter",
        "counts_toward_useful_design": False,
        "source_path": "repo://tests/fixtures/universal-corpus/cases/ua-msme.json",
        "s2_design_search": s2_design_search,
        "layer3_g0_grounding_gate": {"status": "pass"},
        "layer3_g1_grounding_gate": {"status": "pass"},
        "layer3_g2_forecast_gate": {"status": "pass"},
        "layer3_g3_analytics_search_gate": {"status": "pass"},
        "authority_outcomes": {"production": {"outcome": "typed_blocker"}},
        "typed_blockers": [{"code": "w12d_typed_blocker"}],
        **blocks,
    }
    case.update(overrides)
    return case


def _minimal_w12d_report(case: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "policyos.policy_design_case.w12d_universal_outcome_corpus.v1",
        "phase_id": "W12.D",
        "corpus_ref": "repo://tests/fixtures/universal-corpus",
        "mode": "test",
        "cases": [case or _minimal_w12d_case()],
        "summary": {"grounded_conversion_count": 0},
        "typed_blockers": [{"code": "w12d_typed_blocker"}],
    }


def _copy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload))


def _resolved_pinned_bundle(g5: Any, *, universal_status: str = "pass") -> Any:
    case = _minimal_w12d_case()
    case["s14_universality_assurance"]["universal_claim_gate_status"] = universal_status
    return g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(case),
    )


def _pass_dependency_snapshot(g5: Any) -> Any:
    return g5.build_g5_dependency_readiness_snapshot(
        REPO_ROOT,
        manifest_overrides={
            "g0": {"status": "pass"},
            "g1": {"status": "pass", "counts": {"g0_v2_dependency_status": "pass"}},
            "g2": {
                "status": "pass",
                "g1_dependency_status": "pass",
                "g2_w12d_consumer_gate_status": "pass",
            },
            "g3": {
                "status": "pass",
                "g2_dependency_status": "pass",
                "g3_w12d_consumer_gate_status": "pass",
            },
            "gl": {
                "status": "pass",
                "g0_dependency_status": "pass",
                "gl_conformance_status": "pass",
                "gl_reference_resolution_status": "pass",
                "gl_amendment_lineage_status": "pass",
            },
            "g4": {"status": "pass", "g4_g5_promotion_handoff_status": "pass"},
        },
    )


def _g4_resolution(
    g5: Any,
    *,
    claim_families: tuple[str, ...] = ("causal_forecast", "proof"),
    state: str = "governed_promoted",
    blocker_refs: tuple[str, ...] = (),
) -> Any:
    return g5.resolve_g5_g4_handoff(
        REPO_ROOT,
        handoff_payload={
            "status": "pass",
            "authoritative_for": ["g5_first_proving_ground_promotion_state_input_refs"],
            "may_not_use_for": ["conversion_authority_without_g5"],
        },
        promotion_records_payload={
            "promotion_records": [
                {
                    "promotion_record_id": "promotion://ua-msme/design",
                    "case_id": G5_PINNED_CASE_ID,
                    "promotion_state": state,
                    "promotion_scope": {"claim_families": list(claim_families)},
                    "source_design_record_ref": "pdc://layer2/s2/ua-msme/design-record-v0",
                    "source_design_record_digest": "sha256:design",
                    "blocker_refs": list(blocker_refs),
                    "limitation_refs": [],
                    "upstream_contract_refs": ["source-contract://ua-msme"],
                    "may_not_use_for": ["production_authority"],
                }
            ]
        },
        requested_scope={"claim_families": claim_families},
    )


def _scope_join_matrix(
    g5: Any,
    *,
    g1_grounding_status: str = "pass",
    g2_case_id: str = G5_PINNED_CASE_ID,
    g3_proof_status: str = "validated",
) -> Any:
    source_contract_ref = "source-contract://ua-msme"
    matrix = g5.build_g5_upstream_scope_join_matrix(
        REPO_ROOT,
        g1_bindings=[
            {
                "case_id": G5_PINNED_CASE_ID,
                "grounding_status": g1_grounding_status,
                "source_contract_ref": source_contract_ref,
                "source_contract_content_hash": "sha256:source",
                "observed_through": "2026-06-01",
                "may_not_use_for": ["claim_authority_without_g5"],
            }
        ],
        g2_handoffs=[
            {
                "case_id": g2_case_id,
                "status": "pass",
                "design_record_ledger_refs": ["pdc://layer2/s2/ua-msme/design-record-v0"],
                "s2_deterministic_replay_key_refs": ["replay://layer2/s2/ua-msme"],
                "source_contract_ref": source_contract_ref,
                "forecast_support_refs": ["forecast://ua-msme"],
                "calibration_record_refs": ["calibration://ua-msme"],
                "uncertainty_interval_refs": ["uncertainty://ua-msme"],
            }
        ],
        g3_records=[
            {
                "case_id": g2_case_id,
                "proof_status": g3_proof_status,
                "proof_record_refs": ["proof://ua-msme"],
                "s11_record": {
                    "proof_status": g3_proof_status,
                    "source_lineage_refs": ["lineage://ua-msme/a", "lineage://ua-msme/b"],
                },
            }
        ],
    )
    if g2_case_id == G5_PINNED_CASE_ID and g3_proof_status != "identified":
        return matrix.model_copy(update={"status": "pass", "issue_codes": ()})
    return matrix


def _evidence_set(g5: Any, *, family: str = "g2_g3_design_support") -> Any:
    return g5.build_g5_grounded_result_evidence_set(
        [
            {
                "ref": "evidence://ua-msme/forecast",
                "family": family,
                "lineage_refs": ["lineage://ua-msme/a"],
                "source_hash": "sha256:forecast",
            },
            {
                "ref": "evidence://ua-msme/proof",
                "family": family,
                "lineage_refs": ["lineage://ua-msme/b"],
                "source_hash": "sha256:proof",
            },
        ]
    )


def _valid_eligibility_kwargs(g5: Any) -> dict[str, Any]:
    return {
        "pinned_case_input_bundle": _resolved_pinned_bundle(g5),
        "dependency_snapshot": _pass_dependency_snapshot(g5),
        "g4_handoff_resolution": _g4_resolution(g5),
        "upstream_scope_join_matrix": _scope_join_matrix(g5),
        "grounded_result_evidence_set": _evidence_set(g5),
        "requested_scope": {
            "claim_families": ("causal_forecast", "proof"),
            "envelope_ref": "envelope://ua-msme/declared-limited",
        },
        "search_health": {"search_recall_status": "pass", "index_freshness_status": "pass"},
    }


def _g5() -> Any:
    try:
        return import_module("polisyos.runtime.quality.layer3_proving_ground_conversion")
    except ModuleNotFoundError as exc:
        if exc.name == "polisyos.runtime.quality.layer3_proving_ground_conversion":
            pytest.fail(
                "G5 runtime module is missing; add "
                "polisyos.runtime.quality.layer3_proving_ground_conversion.",
                pytrace=False,
            )
        raise


def _dump(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return dict(payload)


def _issue_codes(report: Any) -> set[str]:
    return {str(issue["code"]) for issue in _dump(report).get("issues", [])}


def test_layer3_g5_task0_pattern_pass_records_missing_capability_labels() -> None:
    """P01/P02/P10 red baseline: G5 is not real until producer->consumer is wired."""

    assert {"P01", "P02", "P04", "P05", "P10"} <= TASK0_PATTERN_IDS
    assert {
        "producer_missing",
        "artifact_missing",
        "bridge_missing",
        "consumer_missing",
        "surface_missing",
        "semantic_test_missing",
    } <= TASK0_MISSING_CAPABILITY_LABELS


def test_layer3_g5_contracts_are_strict_and_frozen_red_baseline() -> None:
    """P04/P05 red baseline: conversion status and authority boundary are load-bearing."""

    g5 = _g5()

    assert g5.G5_SCHEMA_VERSION == G5_SCHEMA_VERSION
    assert g5.G5_RULE_VERSION == G5_RULE_VERSION
    assert g5.G5_PINNED_CASE_ID == G5_PINNED_CASE_ID
    assert set(g5.G5_CONVERSION_OUTCOMES) == EXPECTED_CONVERSION_OUTCOMES
    assert set(g5.G5_AUTHORITATIVE_FOR) == EXPECTED_AUTHORITATIVE_FOR
    assert set(g5.G5_MAY_NOT_USE_FOR) >= EXPECTED_MAY_NOT_USE_FOR


def test_layer3_g5_runtime_surface_declares_dtos_builders_and_issue_codes() -> None:
    """P01/P10 red baseline: structural contracts must be paired with semantic negatives."""

    g5 = _g5()

    assert set(dir(g5)) >= EXPECTED_DTOS
    assert set(dir(g5)) >= EXPECTED_BUILDERS_AND_VALIDATORS
    assert {
        "layer3_g5_g4_handoff_missing",
        "layer3_g5_w12d_consumer_gate_missing",
        "layer3_g5_grounded_limited_without_g2_g3_design_support",
        "layer3_g5_source_only_promotion_overclaims_grounded_limited",
        "layer3_g5_effective_independence_missing",
        "layer3_g5_public_raw_payload_leak",
    } <= set(g5.ALL_ISSUE_CODES)
    assert set(g5.ALL_ISSUE_CODES) >= TASK3_EXPECTED_ISSUE_CODES
    assert set(g5.ALL_ISSUE_CODES) >= TASK4_EXPECTED_ISSUE_CODES


def test_layer3_g5_task7_declares_closeout_candidate_warning_replay_checks() -> None:
    """P05/P07/P09/P15: Task 7 needs executable negative checks, not only labels."""

    g5 = _g5()

    assert set(dir(g5)) >= TASK7_EXPECTED_BUILDERS_AND_VALIDATORS
    assert set(g5.ALL_ISSUE_CODES) >= TASK7_EXPECTED_ISSUE_CODES
    assert set(g5.G5_CONFORMANCE_NEGATIVE_IDS) >= TASK7_CONFORMANCE_NEGATIVE_IDS


def test_layer3_g5_persisted_bundle_uses_compute_path_not_green_unchanged_blocker() -> None:
    g5 = _g5()
    bundle = g5.build_layer3_g5_bundle(REPO_ROOT)
    payload = _dump(bundle)

    eligibility = payload["conversion_eligibility_ledger"]

    if eligibility["conversion_outcome"] == "unchanged_blocker":
        assert eligibility["status"] == "fail"
        assert payload["readiness_manifest"]["status"] == "fail"
    else:
        assert eligibility["conversion_outcome"] == "typed_blocker -> grounded_abstention"
        assert eligibility["status"] == "pass"
        assert payload["readiness_manifest"]["status"] == "pass"
        assert payload["readiness_manifest"]["g5_grounded_abstention_count"] == 1
        assert payload["envelope_expansion_delta"]["conversion_reason"] == (
            "grounded_abstention_no_useful_design_credit"
        )
        assert payload["useful_design_metric_eligibility_join"][
            "counts_toward_runtime_useful_design"
        ] is False


def test_layer3_g5_validator_rejects_green_unchanged_blocker() -> None:
    g5 = _g5()
    bundle = _dump(g5.build_layer3_g5_bundle(REPO_ROOT))
    bundle["conversion_eligibility_ledger"] = {
        **bundle["conversion_eligibility_ledger"],
        "status": "pass",
        "conversion_outcome": "unchanged_blocker",
    }
    bundle["readiness_manifest"] = {
        **bundle["readiness_manifest"],
        "status": "pass",
        "g5_conversion_outcome": "unchanged_blocker",
        "issue_codes": [],
    }

    report = g5.validate_layer3_g5_bundle(REPO_ROOT, bundle)

    assert _dump(report)["status"] == "fail"
    assert "layer3_g5_unchanged_blocker_green_status" in _issue_codes(report)


def test_layer3_g5_dependency_snapshot_requires_g0_g1_g4() -> None:
    g5 = _g5()

    snapshot = g5.build_g5_dependency_readiness_snapshot(
        REPO_ROOT,
        manifest_overrides={
            "g0": {"status": "fail"},
            "g1": {"counts": {"g1_search_recall_status": "pass"}},
            "g4": {"status": "missing"},
        },
    )

    assert snapshot.status == "fail"
    assert snapshot.g0_dependency_status == "fail"
    assert snapshot.g1_dependency_status == "pass"
    assert snapshot.g4_dependency_status == "missing"
    assert {
        "layer3_g5_g0_dependency_not_ready",
        "layer3_g5_g4_dependency_not_ready",
    } <= set(snapshot.issue_codes)


def test_layer3_g5_dependency_resolver_reads_slice_specific_readiness_keys() -> None:
    g5 = _g5()

    snapshot = g5.build_g5_dependency_readiness_snapshot(REPO_ROOT)

    assert snapshot.status == "fail"
    assert snapshot.g1_grounding_status == "grounded_or_uncertain"
    assert snapshot.g1_search_recall_status == "pass"
    assert snapshot.g2_w12d_consumer_gate_status == "fail"
    assert snapshot.g2_conformance_status == "fail"
    assert snapshot.g3_w12d_consumer_gate_status == "pass"
    assert snapshot.g3_conformance_status == "pass"
    assert "layer3_g5_g4_dependency_not_ready" in snapshot.issue_codes
    assert snapshot.gl_conformance_status == "pass"
    assert snapshot.gl_reissue_status == "reissue_required"
    assert snapshot.g4_g5_promotion_handoff_status == "pass"
    assert "layer3_g5_dependency_manifest_status_key_missing" not in snapshot.issue_codes


def test_layer3_g5_dependency_resolver_ignores_stale_build_cache_reports() -> None:
    g5 = _g5()

    snapshot = g5.build_g5_dependency_readiness_snapshot(
        REPO_ROOT,
        explicit_w12d_payload_ref="_build/.tmp/production-quality/w12d-report.json",
    )

    assert snapshot.w12d_payload_freshness_status == "stale_build_cache_rejected"
    assert "layer3_g5_w12d_build_cache_not_source_of_truth" in snapshot.issue_codes


def test_layer3_g5_g4_handoff_resolution_admits_governed_only() -> None:
    g5 = _g5()

    resolution = g5.resolve_g5_g4_handoff(REPO_ROOT)
    states = {record.promotion_state for record in resolution.promotion_record_resolutions}

    assert resolution.status == "fail"
    assert resolution.governed_promotion_input_count == 0
    assert resolution.blocked_promotion_input_count == 2
    assert states == {"promotion_blocked"}
    assert "layer3_g5_no_governed_promotion_record" in resolution.issue_codes
    assert "layer3_g5_blocked_promotion_used_as_conversion" in resolution.issue_codes


def test_layer3_g5_blocked_promotion_cannot_be_conversion_input() -> None:
    g5 = _g5()

    resolution = g5.resolve_g5_g4_handoff(
        REPO_ROOT,
        requested_scope={"claim_families": ("causal_forecast",)},
    )
    blocked = next(
        record
        for record in resolution.promotion_record_resolutions
        if record.promotion_state == "promotion_blocked"
    )

    assert blocked.admitted_for_g5_conversion is False
    assert "layer3_g5_blocked_promotion_used_as_conversion" in blocked.issue_codes


def test_layer3_g5_g4_weakest_boundary_artifact_is_not_enough_without_matching_record() -> None:
    g5 = _g5()
    resolution = g5.resolve_g5_g4_handoff(
        REPO_ROOT,
        promotion_records_payload={"promotion_records": []},
        weakest_boundary_payload={"status": "pass", "weakest_boundary_reason": "source_data"},
    )

    assert resolution.status == "fail"
    assert "layer3_g5_no_governed_promotion_record" in resolution.issue_codes
    assert "layer3_g5_g4_weakest_boundary_record_mismatch" in resolution.issue_codes


def test_layer3_g5_g4_handoff_pass_with_blockers_blocks_requested_scope() -> None:
    g5 = _g5()
    resolution = g5.resolve_g5_g4_handoff(
        REPO_ROOT,
        requested_scope={"claim_families": ("causal_forecast",)},
    )

    assert resolution.handoff_status == "pass"
    assert "layer3_g5_g4_handoff_pass_with_blockers_overclaimed" in resolution.issue_codes


def test_layer3_g5_g4_grounded_contract_duplicates_do_not_inflate_evidence() -> None:
    g5 = _g5()
    evidence = g5.build_g5_grounded_result_evidence_set(
        [
            {"ref": "repo://contract/1", "lineage_refs": ["lineage://a"], "source_hash": "sha256:a"},
            {"ref": "repo://contract/1", "lineage_refs": ["lineage://a"], "source_hash": "sha256:a"},
        ]
    )

    assert evidence.lineage_deduplication_record.raw_ref_count == 2
    assert evidence.lineage_deduplication_record.deduped_ref_count == 1
    assert "layer3_g5_g4_grounded_contract_duplicate_inflates_evidence" in evidence.issue_codes


def test_layer3_g5_g1_observed_but_uncertain_binding_limits_conversion_scope() -> None:
    g5 = _g5()

    matrix = g5.build_g5_upstream_scope_join_matrix(REPO_ROOT)

    assert matrix.g1_grounding_status == "missing"
    assert matrix.g1_conversion_scope_disposition == "blocked_missing_source_contract"
    assert "layer3_g5_g1_source_contract_hash_missing" in matrix.issue_codes


def test_layer3_g5_g1_source_contract_hash_and_observed_time_required_for_scope_join() -> None:
    g5 = _g5()
    matrix = g5.build_g5_upstream_scope_join_matrix(
        REPO_ROOT,
        g1_bindings=[
            {
                "case_id": G5_PINNED_CASE_ID,
                "grounding_status": "observed_but_uncertain",
                "may_not_use_for": ["claim_authority"],
            }
        ],
    )

    assert "layer3_g5_g1_source_contract_hash_missing" in matrix.issue_codes
    assert "layer3_g5_g1_observed_time_missing" in matrix.issue_codes


def test_layer3_g5_g1_may_not_use_for_denials_are_preserved() -> None:
    g5 = _g5()
    matrix = g5.build_g5_upstream_scope_join_matrix(
        REPO_ROOT,
        g1_bindings=[
            {
                "case_id": G5_PINNED_CASE_ID,
                "grounding_status": "pass",
                "source_contract_content_hash": "sha256:test",
                "observed_through": "2026-04-10",
            }
        ],
    )

    assert "layer3_g5_g1_may_not_use_for_dropped" in matrix.issue_codes


def test_layer3_g5_g2_design_record_alias_requires_explicit_normalization() -> None:
    g5 = _g5()
    matrix = g5.build_g5_upstream_scope_join_matrix(
        REPO_ROOT,
        g2_handoffs=[
            {
                "status": "pass",
                "design_record_ledger_refs": ["pdc://layer2/s2/alias"],
                "s2_deterministic_replay_key_refs": ["replay://ua-msme"],
                "source_contract_ref": "source-contract://layer3.ua_msme.firm_survival.panel",
                "calibration_record_refs": ["calibration://ok"],
                "uncertainty_interval_refs": ["interval://ok"],
            }
        ],
    )

    assert "layer3_g5_g2_design_record_ref_unresolved" in matrix.issue_codes


def test_layer3_g5_g2_empty_s2_replay_key_refs_block_grounded_limited() -> None:
    g5 = _g5()
    matrix = g5.build_g5_upstream_scope_join_matrix(REPO_ROOT)

    assert "layer3_g5_g2_s2_replay_key_ref_missing" in matrix.issue_codes


def test_layer3_g5_g2_source_contract_ref_mismatch_blocks_scope_join() -> None:
    g5 = _g5()
    matrix = g5.build_g5_upstream_scope_join_matrix(REPO_ROOT)

    assert "layer3_g5_missing_g2_calibration_ref" in matrix.issue_codes


def test_layer3_g5_g3_duplicate_source_lineage_refs_do_not_inflate_independence() -> None:
    g5 = _g5()
    matrix = g5.build_g5_upstream_scope_join_matrix(REPO_ROOT)

    assert "layer3_g5_duplicate_source_lineage_ref_inflates_independence" in matrix.issue_codes


def test_layer3_g5_independence_adapter_uses_existing_collapse_dimensions() -> None:
    g5 = _g5()
    evidence = g5.build_g5_grounded_result_evidence_set(
        [
            {
                "ref": "proof://a",
                "lineage_refs": ["lineage://a", "lineage://a"],
                "source_hash": "sha256:a",
            }
        ]
    )

    adapter = evidence.effective_independence_record.independence_map_payload

    assert adapter["schema_version"] == "policyos.runtime.policy_design_case.independence_map.v1"
    assert "source_lineage_cluster_id" in adapter["collapse_dimensions_used"]
    assert adapter["raw_evidence_line_count"] >= adapter[
        "effective_independent_evidence_count"
    ]


def test_layer3_g5_gl_pass_with_reissue_required_narrows_or_blocks_legal_scope() -> None:
    g5 = _g5()
    snapshot = g5.build_g5_dependency_readiness_snapshot(REPO_ROOT)

    assert snapshot.gl_dependency_status == "pass_with_reissue_limits"
    assert "layer3_g5_gl_pass_with_reissue_required" in snapshot.issue_codes


def test_layer3_g5_pinned_case_bundle_requires_full_w12d_payload() -> None:
    g5 = _g5()

    bundle = g5.build_g5_pinned_case_input_bundle(REPO_ROOT)

    assert bundle.status == "fail"
    assert "layer3_g5_w12d_full_payload_missing" in bundle.issue_codes


def test_layer3_g5_w12d_bundle_extracts_exact_s4_s14_case_keys() -> None:
    g5 = _g5()

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(),
    )

    assert bundle.case_id == G5_PINNED_CASE_ID
    assert set(bundle.w12d_case_block_index.block_keys) >= EXACT_S4_S14_CASE_KEYS
    assert bundle.composed_loop_completeness_gate.status == "pass"
    assert bundle.s2_status == "shadow_ready"
    assert bundle.case_digest.startswith("sha256:")
    assert bundle.replay_refs


def test_layer3_g5_composed_loop_completeness_requires_s4_s14_and_s14() -> None:
    g5 = _g5()
    case = _minimal_w12d_case()
    del case["s10_outcome_prediction"]

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(case),
    )

    assert bundle.composed_loop_completeness_gate.status == "fail"
    assert "s10_outcome_prediction" in bundle.w12d_case_block_index.missing_block_keys
    assert "layer3_g5_w12d_s4_s14_case_key_missing" in bundle.issue_codes


def test_layer3_g5_s14_missing_or_failed_blocks_conversion() -> None:
    g5 = _g5()
    case = _minimal_w12d_case()
    case["s14_universality_assurance"]["grounded_authority_status"] = "fail"

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(case),
    )

    assert bundle.composed_loop_completeness_gate.status == "fail"
    assert "layer3_g5_s14_gate_missing_or_failed" in bundle.issue_codes


def test_layer3_g5_manifest_only_w12d_input_fails_closed() -> None:
    g5 = _g5()

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload={"schema_version": "manifest", "phase_id": "W12.D"},
    )

    assert bundle.status == "fail"
    assert "layer3_g5_w12d_manifest_only_not_payload" in bundle.issue_codes


def test_layer3_g5_stale_build_cache_w12d_input_fails_closed() -> None:
    g5 = _g5()

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(),
        w12d_payload_ref="_build/.tmp/production-quality/w12d-report.json",
    )

    assert bundle.status == "fail"
    assert "layer3_g5_w12d_build_cache_not_source_of_truth" in bundle.issue_codes


def test_layer3_g5_w12d_hook_uses_per_case_s4_s14_before_corpus_summaries() -> None:
    g5 = _g5()
    report = _minimal_w12d_report()
    report.pop("s14_universality_assurance_summary", None)

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=report,
        source_context="w12d_hook",
    )

    assert bundle.composed_loop_completeness_gate.status == "pass"
    assert "layer3_g5_w12d_g3_summary_location_unhandled" not in bundle.issue_codes


def test_layer3_g5_s2_acquisition_required_routes_to_abstention_or_blocker() -> None:
    g5 = _g5()
    case = _minimal_w12d_case()
    case["s2_design_search"]["status"] = "acquisition_required"
    case["s2_design_search"]["search_ledger"]["acquisition_branch_state"] = "bridge_missing"

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(case),
    )

    assert bundle.s2_status == "acquisition_required"
    assert bundle.s2_acquisition_branch_state == "bridge_missing"
    assert "layer3_g5_s2_acquisition_required_unresolved" in bundle.issue_codes
    assert "layer3_g5_s2_bridge_missing_unresolved" in bundle.issue_codes


def test_layer3_g5_design_record_firewall_warn_limit_block_statuses_compose_before_conversion() -> None:
    g5 = _g5()
    case = _minimal_w12d_case()
    case["s2_design_search"]["design_record"]["firewall_status"].append(
        {"cell_ref": "MEASUREMENT.proxy", "status": "warn"}
    )

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(case),
    )

    assert "warn" in bundle.design_record_firewall_statuses
    assert "layer3_g5_design_record_firewall_status_flattened" in bundle.issue_codes


def test_layer3_g5_constraint_store_block_status_blocks_or_limits_conversion() -> None:
    g5 = _g5()
    case = _minimal_w12d_case()
    case["s2_design_search"]["constraint_store"]["constraint_records"][0]["status"] = "block"

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(case),
    )

    assert "block" in bundle.constraint_store_statuses
    assert "layer3_g5_constraint_store_block_ignored" in bundle.issue_codes


def test_layer3_g5_p26_resolver_reads_s7_delegation_record_ref_not_only_generic_human_refs() -> None:
    g5 = _g5()

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(),
    )

    assert bundle.s7_human_decision_record_ref == "human-decision-record://ua-msme/final-choice"
    assert "layer3_g5_s7_delegation_record_ref_unresolved" not in bundle.issue_codes


def test_layer3_g5_s12_growth_entry_demand_act_and_envelope_delta_are_reused() -> None:
    g5 = _g5()

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(),
    )

    assert bundle.s12_demand_act_refs == ("demand-act://ua-msme/principal",)
    assert bundle.s12_certified_envelope_delta_refs == ("envelope-delta://ua-msme/first",)


def test_layer3_g5_s14_pending_sealed_limits_universality_claim_but_not_declared_envelope_ref() -> None:
    g5 = _g5()

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(),
    )

    assert bundle.s14_universal_claim_gate_status == "pending_sealed"
    assert bundle.s14_declared_envelope_ref == "envelope://ua-msme/declared-limited"
    assert "layer3_g5_s14_pending_sealed_overclaimed" in bundle.issue_codes


def test_layer3_g5_w12d_fresh_payload_builder_uses_supported_signature(
    monkeypatch: Any,
) -> None:
    g5 = _g5()
    calls: list[dict[str, Any]] = []

    def fake_builder(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return _minimal_w12d_report()

    monkeypatch.setattr(g5, "_build_w12d_full_payload", fake_builder)

    bundle = g5.build_g5_pinned_case_input_bundle(REPO_ROOT, build_fresh_payload=True)

    assert bundle.status == "pass"
    assert calls and "case_results" in calls[0]


def test_layer3_g5_non_pinned_case_widening_attempt_fails_closed() -> None:
    g5 = _g5()
    case = _minimal_w12d_case(case_id="non-pinned")

    bundle = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(case),
    )

    assert bundle.status == "fail"
    assert "layer3_g5_non_pinned_case_widening_attempt" in bundle.issue_codes


def test_layer3_g5_pinned_case_digest_is_replayable() -> None:
    g5 = _g5()
    first = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(),
    )
    second = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(),
    )

    assert first.case_digest == second.case_digest
    assert first.replay_refs == second.replay_refs


def test_layer3_g5_source_only_promotion_cannot_claim_causal_design() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["g4_handoff_resolution"] = _g4_resolution(
        g5,
        claim_families=("source_data",),
    )

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_source_only_promotion_overclaims_causal_design" in ledger.issue_codes


def test_layer3_g5_source_only_promotion_cannot_claim_grounded_limited() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["g4_handoff_resolution"] = _g4_resolution(
        g5,
        claim_families=("source_data",),
    )

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.grounding_disposition == "ungrounded_blocked"
    assert "layer3_g5_source_only_promotion_overclaims_grounded_limited" in (
        ledger.issue_codes
    )


def test_layer3_g5_grounded_limited_requires_g2_g3_design_support() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["upstream_scope_join_matrix"] = inputs["upstream_scope_join_matrix"].model_copy(
        update={
            "status": "fail",
            "issue_codes": ("layer3_g5_g2_g3_scope_mismatch",),
        }
    )

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_grounded_limited_without_g2_g3_design_support" in (
        ledger.issue_codes
    )


def test_layer3_g5_does_not_treat_g4_pass_as_design_level_promotion() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["g4_handoff_resolution"] = _g4_resolution(
        g5,
        claim_families=("source_data",),
    )

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.g4_design_scope_status == "missing"
    assert "layer3_g5_g4_pass_without_design_scope" in ledger.issue_codes


def test_layer3_g5_g2_g3_green_artifacts_do_not_override_blocked_g4_design_scope() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["g4_handoff_resolution"] = _g4_resolution(
        g5,
        state="promotion_blocked",
        blocker_refs=("blocker://g4/causal-probe",),
    )

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_blocked_promotion_used_as_conversion" in ledger.issue_codes


def test_layer3_g5_grounded_limited_requires_upstream_scope_join() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["upstream_scope_join_matrix"] = inputs["upstream_scope_join_matrix"].model_copy(
        update={"status": "fail", "issue_codes": ("layer3_g5_upstream_scope_join_missing",)}
    )

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.status == "fail"
    assert "layer3_g5_upstream_scope_join_missing" in ledger.issue_codes


def test_layer3_g5_unrelated_green_g2_g3_artifacts_do_not_satisfy_conversion() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["upstream_scope_join_matrix"] = _scope_join_matrix(
        g5,
        g2_case_id="other-case",
    )

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_g2_g3_scope_mismatch" in ledger.issue_codes


def test_layer3_g5_effective_independence_missing_blocks_grounded_limited() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    evidence = inputs["grounded_result_evidence_set"]
    inputs["grounded_result_evidence_set"] = evidence.model_copy(
        update={
            "status": "fail",
            "effective_independence_record": evidence.effective_independence_record.model_copy(
                update={
                    "status": "fail",
                    "issue_codes": ("layer3_g5_effective_independence_missing",),
                }
            ),
            "issue_codes": ("layer3_g5_effective_independence_missing",),
        }
    )

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_effective_independence_missing" in ledger.issue_codes


def test_layer3_g5_raw_ref_dedup_without_independence_map_blocks_grounded_limited() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    evidence = inputs["grounded_result_evidence_set"]
    inputs["grounded_result_evidence_set"] = evidence.model_copy(
        update={
            "status": "fail",
            "effective_independence_record": evidence.effective_independence_record.model_copy(
                update={
                    "status": "fail",
                    "issue_codes": ("layer3_g5_raw_ref_dedup_used_as_independence",),
                }
            ),
            "issue_codes": ("layer3_g5_raw_ref_dedup_used_as_independence",),
        }
    )

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_raw_ref_dedup_used_as_independence" in ledger.issue_codes


def test_layer3_g5_grounded_limited_requires_useful_design_metric_eligibility_join_for_credit() -> None:
    g5 = _g5()

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **_valid_eligibility_kwargs(g5),
        requested_conversion_outcome="typed_blocker -> grounded_limited",
        useful_design_credit_requested=True,
    )
    composition = g5.build_g5_status_composition_ledger(
        conversion_eligibility_ledger=ledger,
        useful_design_metric_eligibility_join=None,
        w12d_outcome="typed_blocker",
    )

    assert composition.counts_toward_runtime_useful_design is False
    assert "layer3_g5_useful_design_metric_eligibility_join_missing" in (
        composition.issue_codes
    )


def test_layer3_g5_expert_useful_design_ceiling_is_not_runtime_credit() -> None:
    g5 = _g5()

    join = g5.build_g5_useful_design_metric_eligibility_join(
        conversion_outcome="typed_blocker -> grounded_limited",
        useful_design_credit_requested=True,
        expert_useful_design_ceiling={"status": "eligible"},
        w11c_useful_design_gate=None,
    )

    assert join.counts_toward_runtime_useful_design is False
    assert "layer3_g5_expert_useful_design_ceiling_used_as_runtime_credit" in (
        join.issue_codes
    )


def test_layer3_g5_grounded_limited_requires_scope_covering_evidence() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["grounded_result_evidence_set"] = _evidence_set(g5, family="g1_source_contract")

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_grounded_contract_ref_missing" in ledger.issue_codes


def test_layer3_g5_grounded_abstention_requires_search_recall_and_freshness() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["search_health"] = {"search_recall_status": "fail", "index_freshness_status": "stale"}

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_abstention",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_search_recall_seed_miss_blocks_abstention" in ledger.issue_codes
    assert "layer3_g5_stale_index_blocks_abstention" in ledger.issue_codes


def test_layer3_g5_search_ceiling_is_not_domain_ceiling() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["search_health"] = {
        "search_recall_status": "fail",
        "index_freshness_status": "pass",
        "non_conversion_reason": "domain_ceiling",
    }

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_abstention",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_search_ceiling_not_domain_ceiling" in ledger.issue_codes


def test_layer3_g5_status_composition_does_not_add_uncontrolled_w12d_outcome() -> None:
    g5 = _g5()
    ledger = g5.Layer3G5ConversionEligibilityLedger(
        status="pass",
        conversion_outcome="typed_blocker -> grounded_limited",
        grounding_disposition="grounded_limited",
    )

    composition = g5.build_g5_status_composition_ledger(
        conversion_eligibility_ledger=ledger,
        w12d_outcome="grounded_limited",
    )

    assert composition.status == "fail"
    assert "grounded_limited" not in composition.allowed_w12d_outcomes
    assert "layer3_g5_uncontrolled_w12d_outcome_status" in composition.issue_codes


def test_layer3_g5_conversion_cannot_outrank_weakest_boundary() -> None:
    g5 = _g5()

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **_valid_eligibility_kwargs(g5),
        requested_conversion_outcome="typed_blocker -> grounded_limited",
        weakest_boundary={
            "status": "limited",
            "weakest_boundary_reason": "source_data_only",
        },
    )

    assert ledger.weakest_boundary_reason == "source_data_only"
    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_conversion_exceeds_weakest_boundary" in ledger.issue_codes


def test_layer3_g5_mixed_upstream_statuses_narrow_or_block_conversion() -> None:
    g5 = _g5()

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **_valid_eligibility_kwargs(g5),
        requested_conversion_outcome="typed_blocker -> grounded_limited",
        upstream_statuses=("warn", "partial", "review_required"),
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert ledger.mixed_upstream_statuses == ("warn", "partial", "review_required")
    assert "layer3_g5_mixed_status_composition_missing" in ledger.issue_codes


def test_layer3_g5_high_stakes_scope_requires_human_decision_record_or_narrows() -> None:
    g5 = _g5()
    case = _minimal_w12d_case()
    case["s7_delegation"].pop("human_decision_record_ref")
    case["s2_design_search"]["delegation_posture"].pop("human_decision_record_ref")
    case["s2_design_search"]["search_ledger"]["delegation_record_refs"] = []
    inputs = _valid_eligibility_kwargs(g5)
    inputs["pinned_case_input_bundle"] = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(case),
    )
    inputs["requested_scope"] = {
        "claim_families": ("causal_forecast", "proof"),
        "stakes": "high",
    }

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_human_decision_record_required" in ledger.issue_codes


def test_layer3_g5_g1_observed_but_uncertain_cannot_be_claim_authority() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["upstream_scope_join_matrix"] = _scope_join_matrix(
        g5,
        g1_grounding_status="observed_but_uncertain",
    )
    inputs["requested_scope"] = {
        "claim_families": ("causal_forecast", "proof"),
        "requires_claim_authority": True,
    }

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_g1_observed_but_uncertain_overclaimed" in ledger.issue_codes


def test_layer3_g5_s2_bridge_missing_blocks_or_limits_conversion() -> None:
    g5 = _g5()
    case = _minimal_w12d_case()
    case["s2_design_search"]["status"] = "acquisition_required"
    case["s2_design_search"]["search_ledger"]["acquisition_branch_state"] = "bridge_missing"
    inputs = _valid_eligibility_kwargs(g5)
    inputs["pinned_case_input_bundle"] = g5.build_g5_pinned_case_input_bundle(
        REPO_ROOT,
        w12d_report_payload=_minimal_w12d_report(case),
    )

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_s2_bridge_missing_unresolved" in ledger.issue_codes


def test_layer3_g5_gl_requirement_artifact_does_not_override_applicability_fail() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["requested_scope"] = {"claim_families": ("legal_mandate",)}

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
        gl_legal_authority_payload={
            "status": "pass",
            "applicability_status": "fail",
            "legal_requirement_artifact_ref": "legal-requirement://ua-msme",
        },
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_gl_applicability_fail_blocks_conversion" in ledger.issue_codes
    assert "layer3_g5_gl_requirement_artifact_overrides_applicability" in (
        ledger.issue_codes
    )


def test_layer3_g5_gl_mandate_compatibility_only_blocks_mandate_conversion() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["requested_scope"] = {"claim_families": ("mandate",)}

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
        gl_mandate_records=[{"status": "compatibility_only", "s6_evaluation_ref": None}],
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_gl_mandate_compatibility_only_blocks_conversion" in (
        ledger.issue_codes
    )


def test_layer3_g5_s14_grounded_authority_pass_does_not_override_pending_sealed_gate() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["pinned_case_input_bundle"] = _resolved_pinned_bundle(
        g5,
        universal_status="pending_sealed",
    )
    inputs["requested_scope"] = {"claim_families": ("universal_claim",)}

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_s14_pending_sealed_overclaimed" in ledger.issue_codes


def test_layer3_g5_g3_identified_proof_is_not_claim_authority() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["upstream_scope_join_matrix"] = _scope_join_matrix(
        g5,
        g3_proof_status="identified",
    )

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_limited",
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_g3_proof_status_overclaimed" in ledger.issue_codes


def test_layer3_g5_envelope_expansion_delta_records_first_reading() -> None:
    g5 = _g5()
    bundle = _resolved_pinned_bundle(g5)
    s12_evidence = g5.build_g5_s12_demand_growth_evidence(
        s12_case_signals={
            "demand_act_refs": list(bundle.s12_demand_act_refs),
            "growth_entries": [
                {
                    "demand_act_ref": "demand-act://ua-msme/principal",
                    "certified_envelope_delta_ref": "envelope-delta://ua-msme/first",
                    "reuse_acquisition_ref": "reuse://layer2/s3/source-adapter",
                }
            ],
            "voi_allocation_refs": ["voi://ua-msme/site-1"],
        },
        requested_scope={"envelope_ref": bundle.s14_declared_envelope_ref},
    )
    demand_pull = g5.build_g5_demand_pull_attempt_record(
        pinned_case_input_bundle=bundle,
        s12_demand_growth_evidence=s12_evidence,
        s3_demand_pull_refs=("s3://reuse/source-adapter",),
        attempted_grounding_path_refs=("g5://attempt/source-to-design",),
    )
    ledger = g5.Layer3G5ConversionEligibilityLedger(
        status="pass",
        conversion_outcome="typed_blocker -> grounded_limited",
        grounding_disposition="grounded_limited",
    )

    delta = g5.build_g5_envelope_expansion_delta(
        conversion_eligibility_ledger=ledger,
        demand_pull_attempt_record=demand_pull,
        s12_demand_growth_evidence=s12_evidence,
        envelope_ref=bundle.s14_declared_envelope_ref,
        region_ref="region://ua",
        numerator=1,
        denominator=1,
        conversion_reason="grounded_limited_first_envelope",
    )

    assert delta.status == "expanding"
    assert delta.envelope_expansion_rate == 1.0
    assert delta.envelope_ref == "envelope://ua-msme/declared-limited"
    assert delta.numerator == 1
    assert delta.denominator == 1
    assert delta.envelope_delta_refs == ("envelope-delta://ua-msme/first",)
    assert "demand-act://ua-msme/principal" in delta.demand_pull_refs


def test_layer3_g5_grounded_abstention_requires_demand_pull_attempt_refs() -> None:
    g5 = _g5()
    inputs = _valid_eligibility_kwargs(g5)
    inputs["search_health"] = {
        "search_recall_status": "pass",
        "index_freshness_status": "pass",
    }

    ledger = g5.build_g5_conversion_eligibility_ledger(
        **inputs,
        requested_conversion_outcome="typed_blocker -> grounded_abstention",
        demand_pull_attempt_record=None,
    )

    assert ledger.conversion_outcome == "unchanged_blocker"
    assert "layer3_g5_grounded_abstention_without_demand_pull_attempt" in (
        ledger.issue_codes
    )


def test_layer3_g5_demand_pull_resolves_from_s12_case_signals() -> None:
    g5 = _g5()
    bundle = _resolved_pinned_bundle(g5)
    s12_evidence = g5.build_g5_s12_demand_growth_evidence(
        s12_case_signals={
            "principal_ref": "principal://ua-msme/ministry",
            "demand_act_refs": ["demand-act://ua-msme/principal"],
            "growth_entries": [
                {
                    "demand_act_ref": "demand-act://ua-msme/principal",
                    "certified_envelope_delta_ref": "envelope-delta://ua-msme/first",
                    "reuse_acquisition_ref": "reuse://layer2/s3/source-adapter",
                }
            ],
            "voi_allocation_refs": ["voi://ua-msme/site-1"],
        },
        requested_scope={"envelope_ref": bundle.s14_declared_envelope_ref},
    )

    demand_pull = g5.build_g5_demand_pull_attempt_record(
        pinned_case_input_bundle=bundle,
        s12_demand_growth_evidence=s12_evidence,
        s3_demand_pull_refs=("s3://reuse/source-adapter",),
    )

    assert demand_pull.status == "pass"
    assert demand_pull.s12_demand_act_refs == ("demand-act://ua-msme/principal",)
    assert demand_pull.s12_voi_refs == ("voi://ua-msme/site-1",)
    assert demand_pull.accountable_principal_refs == ("principal://ua-msme/ministry",)
    assert "layer3_g5_grounded_abstention_without_demand_pull_attempt" not in (
        demand_pull.issue_codes
    )


def test_layer3_g5_flat_expansion_records_reason_not_metric_failure() -> None:
    g5 = _g5()
    bundle = _resolved_pinned_bundle(g5)
    s12_evidence = g5.build_g5_s12_demand_growth_evidence(
        s12_case_signals={
            "demand_act_refs": ["demand-act://ua-msme/principal"],
            "growth_entries": [
                {
                    "demand_act_ref": "demand-act://ua-msme/principal",
                    "certified_envelope_delta_ref": "envelope-delta://ua-msme/first",
                }
            ],
        }
    )
    demand_pull = g5.build_g5_demand_pull_attempt_record(
        pinned_case_input_bundle=bundle,
        s12_demand_growth_evidence=s12_evidence,
    )

    delta = g5.build_g5_envelope_expansion_delta(
        conversion_eligibility_ledger=g5.Layer3G5ConversionEligibilityLedger(
            status="fail",
            conversion_outcome="unchanged_blocker",
        ),
        demand_pull_attempt_record=demand_pull,
        s12_demand_growth_evidence=s12_evidence,
        envelope_ref=bundle.s14_declared_envelope_ref,
        numerator=0,
        denominator=3,
        conversion_reason="domain_ceiling",
    )

    assert delta.status == "flat"
    assert delta.envelope_expansion_rate == 0.0
    assert delta.conversion_reason == "domain_ceiling"
    assert "layer3_g5_envelope_expansion_reason_missing" not in delta.issue_codes


def test_layer3_g5_health_snapshot_carries_all_five_constitution_metrics() -> None:
    g5 = _g5()
    delta = g5.Layer3G5EnvelopeExpansionDelta(
        status="expanding",
        envelope_expansion_rate=1.0,
        numerator=1,
        denominator=1,
        conversion_reason="grounded_limited_first_envelope",
    )

    snapshot = g5.build_g5_dependency_health_metric_snapshot(
        envelope_expansion_delta=delta,
        upstream_health_readings={
            "adapter-semantic-loss": {"status": "pass"},
            "governance-throughput": {"status": "pass"},
            "demand-pull-vs-abstention": {"status": "pass"},
            "search-recall@known-seeds + index-staleness": {"status": "pass"},
        },
    )

    assert set(snapshot.metric_statuses) == {
        "envelope-expansion-rate",
        "adapter-semantic-loss",
        "governance-throughput",
        "demand-pull-vs-abstention",
        "search-recall@known-seeds + index-staleness",
    }
    assert snapshot.health_toml["envelope-expansion-rate"]["value"] == 1.0
    assert snapshot.status == "pass"


def test_layer3_g5_stale_upstream_health_reading_blocks_or_limits_conversion() -> None:
    g5 = _g5()
    delta = g5.Layer3G5EnvelopeExpansionDelta(
        status="flat",
        envelope_expansion_rate=0.0,
        numerator=0,
        denominator=2,
        conversion_reason="search_ceiling",
    )

    snapshot = g5.build_g5_dependency_health_metric_snapshot(
        envelope_expansion_delta=delta,
        upstream_health_readings={
            "adapter-semantic-loss": {"status": "pass"},
            "governance-throughput": {"status": "pass"},
            "demand-pull-vs-abstention": {"status": "pass"},
            "search-recall@known-seeds + index-staleness": {"status": "stale"},
        },
    )

    assert snapshot.status == "fail"
    assert "layer3_g5_stale_upstream_health_metric" in snapshot.issue_codes


def test_layer3_g5_missing_envelope_delta_blocks_readiness() -> None:
    g5 = _g5()
    demand_pull = g5.Layer3G5DemandPullAttemptRecord(
        status="pass",
        demand_pull_refs=("demand-act://ua-msme/principal",),
    )
    s12_evidence = g5.Layer3G5S12DemandGrowthEvidence(
        status="pass",
        demand_act_refs=("demand-act://ua-msme/principal",),
    )

    delta = g5.build_g5_envelope_expansion_delta(
        conversion_eligibility_ledger=g5.Layer3G5ConversionEligibilityLedger(
            status="fail",
            conversion_outcome="unchanged_blocker",
        ),
        demand_pull_attempt_record=demand_pull,
        s12_demand_growth_evidence=s12_evidence,
        envelope_ref=None,
        numerator=0,
        denominator=1,
        conversion_reason="unchanged_blocker",
    )

    assert delta.status == "blocked"
    assert "layer3_g5_envelope_expansion_delta_missing" in delta.issue_codes


def test_layer3_g5_s12_growth_without_envelope_delta_cannot_count_expansion() -> None:
    g5 = _g5()
    s12_evidence = g5.build_g5_s12_demand_growth_evidence(
        s12_case_signals={
            "demand_act_refs": ["demand-act://ua-msme/principal"],
            "growth_entries": [
                {
                    "demand_act_ref": "demand-act://ua-msme/principal",
                    "growth_counting_disposition": "counted",
                }
            ],
        }
    )

    assert s12_evidence.status == "fail"
    assert "layer3_g5_s12_growth_without_envelope_delta" in s12_evidence.issue_codes


def test_layer3_g5_s12_demand_act_ref_missing_blocks_demand_pull_credit() -> None:
    g5 = _g5()
    s12_evidence = g5.build_g5_s12_demand_growth_evidence(
        s12_case_signals={
            "growth_entries": [
                {
                    "certified_envelope_delta_ref": "envelope-delta://ua-msme/first",
                    "growth_counting_disposition": "counted",
                }
            ],
        }
    )
    demand_pull = g5.build_g5_demand_pull_attempt_record(
        pinned_case_input_bundle=_resolved_pinned_bundle(g5),
        s12_demand_growth_evidence=s12_evidence,
    )

    assert demand_pull.status == "fail"
    assert "layer3_g5_s12_demand_act_ref_missing" in demand_pull.issue_codes


def test_layer3_g5_closed_case_replay_integrity_allows_g5_overlay_only() -> None:
    g5 = _g5()

    safe = g5.check_g5_closed_case_replay_integrity(
        pre_g5_payload={
            "case_id": G5_PINNED_CASE_ID,
            "outcome": "typed_blocker",
            "layer3_g4_gate_status": "pass_with_blockers",
        },
        post_g5_payload={
            "case_id": G5_PINNED_CASE_ID,
            "outcome": "typed_blocker",
            "layer3_g4_gate_status": "pass_with_blockers",
            "g5_readiness_summary": {"status": "pass"},
        },
    )
    mutated = g5.check_g5_closed_case_replay_integrity(
        pre_g5_payload={
            "case_id": G5_PINNED_CASE_ID,
            "outcome": "typed_blocker",
            "layer3_g4_gate_status": "pass_with_blockers",
        },
        post_g5_payload={
            "case_id": G5_PINNED_CASE_ID,
            "outcome": "pass",
            "layer3_g4_gate_status": "pass",
            "g5_readiness_summary": {"status": "pass"},
        },
    )

    assert safe.status == "pass"
    assert mutated.status == "fail"
    assert "layer3_g5_pre_g5_closed_case_replay_mutated" in mutated.issue_codes


def test_layer3_g5_closeout_boundary_rejects_surface_substitution() -> None:
    g5 = _g5()

    check = g5.check_g5_closeout_boundary(
        {
            "observed_surface_refs": [
                "architecture/policy_design_case/layer3_g5_readiness_manifest.json",
                "architecture/policy_design_case/layer3_g5_public_export_projection_refs.json",
            ],
            "substitutes_module_owned_closeout_evidence": True,
            "authoritative_for": ["runtime_closeout_authority"],
        }
    )

    assert check.status == "fail"
    assert "layer3_g5_closeout_surface_substitution_attempt" in check.issue_codes
    assert "layer3_g5_closeout_authority_leak" in check.issue_codes


def test_layer3_g5_candidate_firewall_rejects_candidate_authority_slots() -> None:
    g5 = _g5()

    check = g5.check_g5_candidate_authority_firewall(
        {
            "conversion_refs": ["candidate_unverified://g5/speculative-conversion"],
            "claim_authority_refs": ["rejected_speculation://g5/claim"],
            "projection_authority_refs": ["candidate_unverified://g5/projection"],
        }
    )

    assert check.status == "fail"
    assert "layer3_g5_candidate_unverified_used_as_authority" in check.issue_codes
    assert "layer3_g5_rejected_speculation_used_as_authority" in check.issue_codes


def test_layer3_g5_warning_lifecycle_rejects_unowned_warning_bypass() -> None:
    g5 = _g5()

    check = g5.check_g5_warning_lifecycle(
        [
            {
                "status": "warn",
                "message": "soft caveat without owner",
                "conversion_pass_effect": True,
                "useful_design_credit_effect": True,
            }
        ]
    )

    assert check.status == "fail"
    assert "layer3_g5_unowned_warning_lifecycle" in check.issue_codes
    assert "layer3_g5_warning_used_as_conversion_pass" in check.issue_codes


def test_layer3_g5_task7_conformance_report_covers_negative_and_performance_contracts() -> None:
    g5 = _g5()
    bundle = g5.build_layer3_g5_bundle(REPO_ROOT)
    report = bundle.conformance_report
    negative_results = {result.negative_id: result for result in report.negative_results}
    observed_issue_codes = {
        code
        for result in report.negative_results
        for code in result.observed_issue_codes
    }
    performance = report.performance_contract

    assert report.status == "pass"
    assert set(negative_results) >= TASK7_CONFORMANCE_NEGATIVE_IDS
    assert all(result.status == "pass" for result in negative_results.values())
    assert observed_issue_codes >= TASK7_EXPECTED_ISSUE_CODES
    assert report.closed_case_replay_integrity["status"] == "pass"
    assert report.closeout_boundary_check.status == "pass"
    assert report.candidate_firewall_check["status"] == "pass"
    assert report.warning_lifecycle_check["status"] == "pass"
    assert performance["status"] == "pass"
    assert performance["bounded_artifact_read_policy"] == "explicit_expected_paths_only"
    assert performance["request_path_repo_glob_allowed"] is False
    assert performance["upstream_builder_rerun_in_request_path"] is False
    assert performance["w12d_import_mode"] == "lazy"
